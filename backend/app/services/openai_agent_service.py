import asyncio
import importlib
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.services.context_preloader import preload_repo_context
from app.services.repo_memory import memory_prompt_block


DEFAULT_OPENAI_AGENT_MODEL = "gpt-5.6-terra"
OPENAI_AGENT_MODEL_ENV = "BROPILOT_OPENAI_AGENT_MODEL"
OPENAI_AGENT_TIMEOUT_SECONDS = 20 * 60
OPENAI_AGENT_GUARDRAILS = (
    "You are Code Pilot, the code-change workflow inside BroPilot Workbench. "
    "Make small, review-ready code changes. Use only the provided tools to read "
    "and write files. Do not modify .env, .venv, .git, .gitagent, workspace, "
    "skills/, node_modules, or generated artifacts. Prefer existing files and "
    "project conventions. If tests are needed and a tests/ directory exists, "
    "put tests there. Do not commit, push, merge, or run shell commands. The "
    "backend will run python -m pytest and capture git diff after you finish."
)


@dataclass
class AgentRunResult:
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


def get_openai_agent_model() -> str:
    return os.environ.get(OPENAI_AGENT_MODEL_ENV, DEFAULT_OPENAI_AGENT_MODEL).strip() or (
        DEFAULT_OPENAI_AGENT_MODEL
    )


def is_read_only_task(task: str) -> bool:
    normalized = " ".join(task.lower().split())
    code_change_markers = (
        "add ",
        "fix ",
        "modify ",
        "update ",
        "implement ",
        "create ",
        "write ",
        "make python -m pytest pass",
        "add tests",
        "return 404",
    )
    if any(marker in normalized for marker in code_change_markers):
        return False

    read_only_markers = (
        "read-only",
        "read only",
        "no code changes",
        "do not make code changes",
        "don't make code changes",
        "do not change any files",
        "don't change any files",
        "without changing",
        "without modifying",
        "analyze only",
        "inspect only",
        "review only",
        "explain only",
    )

    return any(marker in normalized for marker in read_only_markers)


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
            "The previous Code Pilot attempt changed files, but backend verification failed.",
            f"ORIGINAL TASK:\n{task.strip()}",
            f"CHANGED FILES:\n{changed_summary}",
            "REPAIR INSTRUCTIONS:",
            (
                "Use the read_file and write_file tools directly. Fix the current "
                "working tree so python -m pytest passes. Keep the intended feature "
                "behavior. Modify only the relevant files."
            ),
            f"PYTEST FAILURE OUTPUT:\n{_compact_text(test_output, limit=5000)}",
        ]
    )


def build_fallback_prompt(task: str) -> str:
    return "\n\n".join(
        [
            f"TASK:\n{task.strip()}",
            "The previous Code Pilot attempt produced no code changes.",
            (
                "Use read_file and write_file tools directly. Modify only the relevant "
                "files. Keep the change small and reviewable."
            ),
        ]
    )


def run_openai_agent(
    repo_path: Path,
    task: str,
    *,
    prompt_override: str | None = None,
    attempt: str = "primary",
    memory_items: list[str] | None = None,
) -> AgentRunResult:
    repo_context = preload_repo_context(repo_path)
    model = get_openai_agent_model()
    command = ["openai-agents", "--model", model, "--attempt", attempt]
    prompt = (
        _build_prompt(prompt_override, repo_context.to_prompt_block(), memory_items or [])
        if prompt_override
        else _build_prompt(task, repo_context.to_prompt_block(), memory_items or [])
    )

    try:
        stdout = asyncio.run(
            _run_agent_async(repo_path=repo_path, prompt=prompt, model=model)
        )
    except TimeoutError as error:
        return AgentRunResult(
            command=command,
            return_code=124,
            stdout="",
            stderr=str(error),
            timed_out=True,
            preloaded_files=repo_context.file_paths,
            attempt=attempt,
            memory_used=memory_items or [],
        )
    except ImportError as error:
        return AgentRunResult(
            command=command,
            return_code=127,
            stdout="",
            stderr=(
                f"{error}. Install backend dependencies with: "
                "pip install -r backend/requirements.txt"
            ),
            preloaded_files=repo_context.file_paths,
            attempt=attempt,
            memory_used=memory_items or [],
        )
    except Exception as error:
        return AgentRunResult(
            command=command,
            return_code=1,
            stdout="",
            stderr=f"OpenAI Agents runner failed: {error}",
            preloaded_files=repo_context.file_paths,
            attempt=attempt,
            memory_used=memory_items or [],
        )

    return AgentRunResult(
        command=command,
        return_code=0,
        stdout=stdout,
        stderr="",
        preloaded_files=repo_context.file_paths,
        attempt=attempt,
        memory_used=memory_items or [],
    )


async def _run_agent_async(*, repo_path: Path, prompt: str, model: str) -> str:
    Agent, Runner, function_tool = _load_agents_sdk()

    def safe_path(relative_path: str) -> Path:
        normalized = relative_path.replace("\\", "/").strip().strip("/")
        if not normalized:
            raise ValueError("Path is required.")
        blocked_roots = (
            ".env",
            ".venv",
            ".git",
            ".gitagent",
            "workspace",
            "skills",
            "node_modules",
        )
        parts = normalized.split("/")
        if parts[0] in blocked_roots:
            raise ValueError(f"Protected path is not writable: {relative_path}")
        resolved = (repo_path / normalized).resolve()
        root = repo_path.resolve()
        if root not in resolved.parents and resolved != root:
            raise ValueError(f"Path escapes repo: {relative_path}")
        return resolved

    @function_tool
    def read_file(path: str) -> str:
        target = safe_path(path)
        if not target.is_file():
            return f"[missing file: {path}]"
        return target.read_text(encoding="utf-8", errors="replace")[:20000]

    @function_tool
    def write_file(path: str, contents: str) -> str:
        target = safe_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(contents, encoding="utf-8")
        return f"wrote {path}"

    agent = Agent(
        name="Code Pilot",
        instructions=OPENAI_AGENT_GUARDRAILS,
        model=model,
        tools=[read_file, write_file],
    )

    result = await asyncio.wait_for(
        Runner.run(agent, input=prompt),
        timeout=OPENAI_AGENT_TIMEOUT_SECONDS,
    )
    output = getattr(result, "final_output", None)
    if output is None:
        output = str(result)

    return "\n".join(
        [
            "OpenAI Agents SDK runner completed.",
            f"model: {model}",
            f"assistant: {_compact_text(output, limit=3000)}",
        ]
    )


def _load_agents_sdk() -> tuple[type[Any], Any, Any]:
    try:
        sdk = importlib.import_module("agents")
        return sdk.Agent, sdk.Runner, sdk.function_tool
    except (AttributeError, ImportError) as error:
        repo_root = Path(__file__).resolve().parents[3]
        original_path = list(sys.path)
        removed_modules = {
            name: module
            for name, module in list(sys.modules.items())
            if name == "agents" or name.startswith("agents.")
        }

        sys.path = [
            entry
            for entry in sys.path
            if Path(entry or ".").resolve() != repo_root
        ]
        for name in removed_modules:
            sys.modules.pop(name, None)

        try:
            sdk = importlib.import_module("agents")
            return sdk.Agent, sdk.Runner, sdk.function_tool
        except (AttributeError, ImportError) as retry_error:
            raise ImportError("openai-agents is not installed") from retry_error
        finally:
            sys.path = original_path


def _build_prompt(task_or_override: str | None, context_block: str, memory_items: list[str]) -> str:
    return "\n\n".join(
        [
            f"TASK:\n{(task_or_override or '').strip()}",
            f"REPO MEMORY FROM PREVIOUS CODE PILOT RUNS:\n{memory_prompt_block(memory_items)}",
            f"INSTRUCTIONS:\n{OPENAI_AGENT_GUARDRAILS}",
            f"PRELOADED REPO CONTEXT:\n{context_block.strip()}",
            (
                "When you are done, summarize the files changed and the review "
                "intent. The backend will independently run tests and capture git diff."
            ),
        ]
    )


def _compact_text(value: object, limit: int = 1200) -> str:
    if isinstance(value, str):
        text = value
    else:
        text = json.dumps(value, ensure_ascii=True)

    text = " ".join(text.split())
    if len(text) <= limit:
        return text

    return f"{text[:limit]}... [truncated]"
