import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from app.services.context_preloader import preload_repo_context
from app.services.repo_memory import memory_prompt_block


DEFAULT_GITCLAW_MODEL = "openai:gpt-4o"
GITCLAW_MODEL_ENV = "BROPILOT_GITCLAW_MODEL"
GITCLAW_TIMEOUT_SECONDS = 20 * 60
BACKEND_DIR = Path(__file__).resolve().parents[2]
RUNNER_PATH = BACKEND_DIR / "scripts" / "gitclaw_runner.mjs"
GITCLAW_GUARDRAILS = (
    "The relevant files are already included below. Do not use shell search "
    "commands. Do not use grep, ls, find, Get-Content, Select-String, or "
    "command-line file discovery. Use the provided file contents to decide "
    "changes. Use write tool to update only the necessary files. For the demo "
    "repo, profile lookup logic is in main.py and auth.py. Tests are in "
    "tests/test_main.py. If changing tests, write to tests/test_main.py, not "
    "root-level test_main.py. Keep the change small. Do not touch .env, .venv, "
    ".git, .gitagent, workspace, or git metadata. Do not create root-level "
    "test files. Put tests under tests/. BroPilot backend will run python -m "
    "pytest after Gitclaw finishes. If the requested task requires code "
    "changes, modify the relevant files instead of only explaining the issue."
)


@dataclass
class CommandResult:
    command: list[str]
    return_code: int
    stdout: str
    stderr: str
    timed_out: bool = False
    preloaded_files: list[str] = field(default_factory=list)
    created_scaffold_paths: list[str] = field(default_factory=list)
    scaffold_summary: str = ""
    attempt: str = "primary"
    memory_used: list[str] = field(default_factory=list)


PROFILE_FALLBACK_PROMPT = """Modify the existing FastAPI demo app.
Use write tool directly. Do not use cli or shell commands. Do not search the filesystem.
Make these exact changes:
1. In auth.py, change get_profile(username) so unknown users raise KeyError(username) instead of returning an Unknown User profile.
2. In main.py, update the /profile/{username} route so it catches KeyError and raises HTTPException(status_code=404, detail='User not found').
3. In tests/test_main.py, update the unknown user profile test so GET /profile/mallory returns status code 404 and response JSON {'detail': 'User not found'}.
Do not create root-level test files.
Only modify auth.py, main.py, and tests/test_main.py.
BroPilot backend will run python -m pytest after you finish."""

GENERIC_FALLBACK_PROMPT = """Use write tool directly.
Do not use cli or shell commands.
Do not search the filesystem.
Modify only the relevant files.
Do not create root-level test files.
Keep the change small."""


def build_test_repair_prompt(
    task: str, test_output: str, changed_files: list[dict]
) -> str:
    changed_paths = [
        str(file.get("path", "")).strip()
        for file in changed_files
        if str(file.get("path", "")).strip()
    ]
    changed_summary = ", ".join(changed_paths) if changed_paths else "No changed files captured."

    return "\n\n".join(
        [
            "The previous Gitclaw attempt changed files, but BroPilot backend verification failed.",
            f"ORIGINAL TASK:\n{task.strip()}",
            f"CHANGED FILES:\n{changed_summary}",
            "REPAIR INSTRUCTIONS:",
            (
                "Use write tool directly. Do not use cli or shell commands. "
                "Do not search the filesystem. Fix the current working tree so "
                "python -m pytest passes. Keep the intended feature behavior. "
                "Modify only the relevant files. Do not create root-level test files."
            ),
            f"PYTEST FAILURE OUTPUT:\n{_compact_text(test_output, limit=5000)}",
        ]
    )


def build_gitclaw_prompt(
    task: str, context_block: str = "", memory_items: list[str] | None = None
) -> str:
    return "\n\n".join(
        [
            f"TASK:\n{task.strip()}",
            f"REPO MEMORY FROM PREVIOUS BROPILOT RUNS:\n{memory_prompt_block(memory_items or [])}",
            f"INSTRUCTIONS:\n{GITCLAW_GUARDRAILS}",
            f"PRELOADED REPO CONTEXT:\n{context_block.strip()}",
        ]
    )


def build_fallback_prompt(task: str) -> str:
    if _is_profile_lookup_task(task):
        return PROFILE_FALLBACK_PROMPT

    return f"TASK:\n{task.strip()}\n\nINSTRUCTIONS:\n{GENERIC_FALLBACK_PROMPT}"


def get_gitclaw_model() -> str:
    return os.environ.get(GITCLAW_MODEL_ENV, DEFAULT_GITCLAW_MODEL).strip() or (
        DEFAULT_GITCLAW_MODEL
    )


def is_read_only_task(task: str) -> bool:
    normalized = " ".join(task.lower().split())
    read_only_markers = (
        "read-only",
        "read only",
        "do not modify",
        "don't modify",
        "no code changes",
        "without changing",
        "without modifying",
        "analyze only",
        "inspect only",
        "review only",
        "explain only",
    )

    return any(marker in normalized for marker in read_only_markers)


def run_gitclaw(
    repo_path: Path,
    task: str,
    *,
    prompt_override: str | None = None,
    attempt: str = "primary",
    memory_items: list[str] | None = None,
) -> CommandResult:
    executable = shutil.which("node")
    repo_context = preload_repo_context(repo_path)
    model = get_gitclaw_model()
    created_scaffold_paths = _ensure_temporary_scaffold(repo_path, model)
    scaffold_summary = _scaffold_summary(created_scaffold_paths)
    prompt = (
        _fallback_prompt_with_memory(prompt_override, memory_items or [])
        if prompt_override
        else build_gitclaw_prompt(task, repo_context.to_prompt_block(), memory_items or [])
    )
    command = [
        executable or "node",
        str(RUNNER_PATH),
        "--repoPath",
        str(repo_path),
        "--prompt",
        prompt,
        "--model",
        model,
    ]

    if executable is None:
        return CommandResult(
            command=command,
            return_code=127,
            stdout="",
            stderr="Node.js was not found on PATH.",
            preloaded_files=repo_context.file_paths,
            created_scaffold_paths=created_scaffold_paths,
            scaffold_summary=scaffold_summary,
            attempt=attempt,
            memory_used=memory_items or [],
        )

    try:
        completed = subprocess.run(
            command,
            cwd=BACKEND_DIR,
            capture_output=True,
            env=os.environ.copy(),
            text=True,
            timeout=GITCLAW_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as error:
        return CommandResult(
            command=command,
            return_code=124,
            stdout=_format_runner_output(_coerce_output(error.stdout)),
            stderr=(
                _coerce_output(error.stderr)
                or f"Gitclaw timed out after {GITCLAW_TIMEOUT_SECONDS} seconds."
            ),
            timed_out=True,
            preloaded_files=repo_context.file_paths,
            created_scaffold_paths=created_scaffold_paths,
            scaffold_summary=scaffold_summary,
            attempt=attempt,
            memory_used=memory_items or [],
        )

    return CommandResult(
        command=command,
        return_code=completed.returncode,
        stdout=_format_runner_output(completed.stdout),
        stderr=completed.stderr,
        preloaded_files=repo_context.file_paths,
        created_scaffold_paths=created_scaffold_paths,
        scaffold_summary=scaffold_summary,
        attempt=attempt,
        memory_used=memory_items or [],
    )


def _ensure_temporary_scaffold(repo_path: Path, model: str) -> list[str]:
    created_paths: list[str] = []

    agent_yaml = repo_path / "agent.yaml"
    if not agent_yaml.exists():
        agent_yaml.write_text(
            "\n".join(
                [
                    'spec_version: "0.1.0"',
                    "name: bropilot-temp-agent",
                    "version: 0.1.0",
                    "description: Temporary BroPilot Gitclaw agent for local repo editing",
                    "model:",
                    f'  preferred: "{model}"',
                    "tools: [read, write, memory]",
                    "runtime:",
                    "  max_turns: 30",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        created_paths.append("agent.yaml")

    soul = repo_path / "SOUL.md"
    if not soul.exists():
        soul.write_text(
            "You are BroPilot, a careful engineering agent. Make small, "
            "reviewable code changes and use read/write tools instead of "
            "shell commands.\n",
            encoding="utf-8",
        )
        created_paths.append("SOUL.md")

    memory_dir = repo_path / "memory"
    if not memory_dir.exists():
        memory_dir.mkdir(parents=True, exist_ok=True)
        (memory_dir / "MEMORY.md").write_text(
            "# BroPilot Temporary Memory\n\nNo persisted memory for this run.\n",
            encoding="utf-8",
        )
        created_paths.append("memory")

    return created_paths


def _scaffold_summary(created_paths: list[str]) -> str:
    if not created_paths:
        return "Temporary Gitclaw agent scaffold not needed; existing scaffold found."

    return f"Temporary Gitclaw agent scaffold created: {', '.join(created_paths)}."


def _is_profile_lookup_task(task: str) -> bool:
    normalized = " ".join(task.lower().split())
    profile_markers = ("profile", "profile lookup", "/profile")
    behavior_markers = ("404", "unknown user", "unknown users", "not found")

    return any(marker in normalized for marker in profile_markers) and any(
        marker in normalized for marker in behavior_markers
    )


def _fallback_prompt_with_memory(prompt: str, memory_items: list[str]) -> str:
    return "\n\n".join(
        [
            prompt.strip(),
            "REPO MEMORY FROM PREVIOUS BROPILOT RUNS:",
            memory_prompt_block(memory_items),
        ]
    )


def _format_runner_output(raw_stdout: str) -> str:
    prefix = "Gitclaw SDK runner used with cli tool disabled."
    if not raw_stdout.strip():
        return prefix

    try:
        payload = json.loads(raw_stdout)
    except json.JSONDecodeError:
        return f"{prefix}\n\nRaw runner stdout:\n{raw_stdout.strip()}"

    lines = [
        prefix,
        f"runner_status: {payload.get('status', 'unknown')}",
    ]

    if payload.get("error"):
        lines.append(f"runner_error: {payload['error']}")

    for event in payload.get("events", []):
        event_type = event.get("type", "unknown")

        if event_type == "assistant":
            content = _compact_text(event.get("content", ""))
            lines.append(f"assistant: {content}")
        elif event_type == "tool_use":
            lines.append(
                f"tool_use: {event.get('toolName', 'unknown')} "
                f"{json.dumps(event.get('args'), ensure_ascii=True)}"
            )
        elif event_type == "tool_result":
            content = _compact_text(event.get("content", ""))
            marker = "error" if event.get("isError") else "ok"
            lines.append(f"tool_result ({marker}): {content}")
        elif event_type == "system":
            content = _compact_text(event.get("content", ""))
            lines.append(f"system/{event.get('subtype', 'event')}: {content}")

    return "\n".join(lines)


def _compact_text(value: object, limit: int = 1200) -> str:
    if isinstance(value, str):
        text = value
    else:
        text = json.dumps(value, ensure_ascii=True)

    text = " ".join(text.split())
    if len(text) <= limit:
        return text

    return f"{text[:limit]}... [truncated]"


def _coerce_output(value: bytes | str | None) -> str:
    if value is None:
        return ""

    if isinstance(value, bytes):
        return value.decode(errors="replace")

    return value
