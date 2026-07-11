import asyncio
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from app.services.context_preloader import preload_repo_context
from app.services.repo_memory import memory_prompt_block


MODEL_SOL = "gpt-5.6-sol"
MODEL_TERRA = "gpt-5.6-terra"
MODEL_LUNA = "gpt-5.6-luna"
DEFAULT_OPENAI_AGENT_MODEL = MODEL_TERRA
OPENAI_AGENT_MODEL_ENV = "BROPILOT_OPENAI_AGENT_MODEL"
OPENAI_AGENT_TIMEOUT_SECONDS = 20 * 60
OPENAI_AGENT_GUARDRAILS = (
    "You are part of Code Pilot, the code-change workflow inside BroPilot "
    "Workbench. Make small, review-ready changes. Use only provided tools. "
    "Do not modify .env, .venv, .git, .gitagent, workspace, skills/, "
    "node_modules, or generated artifacts. Prefer existing project patterns. "
    "Do not commit, push, merge, or run shell commands. The backend will run "
    "python -m pytest and capture git diff after you finish."
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
    planner_summary: str = ""
    selected_model: str = DEFAULT_OPENAI_AGENT_MODEL
    reviewer_summary: str = ""


@dataclass
class PlanResult:
    model: str
    summary: str
    raw_output: str


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
    prompt_task = prompt_override or task
    command = ["openai-agents", "--workflow", attempt]

    try:
        plan, stdout = asyncio.run(
            _run_agent_workflow_async(
                repo_path=repo_path,
                task=prompt_task,
                context_block=repo_context.to_prompt_block(),
                memory_items=memory_items or [],
                attempt=attempt,
            )
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
            stderr=f"OpenAI Agents workflow failed: {error}",
            preloaded_files=repo_context.file_paths,
            attempt=attempt,
            memory_used=memory_items or [],
            selected_model=get_openai_agent_model(),
        )

    return AgentRunResult(
        command=[*command, "--model", plan.model],
        return_code=0,
        stdout=stdout,
        stderr="",
        preloaded_files=repo_context.file_paths,
        attempt=attempt,
        memory_used=memory_items or [],
        planner_summary=plan.summary,
        selected_model=plan.model,
    )


def run_reviewer_agent(
    *,
    repo_path: Path,
    task: str,
    changed_files: list[dict],
    test_status: str,
    memory_items: list[str] | None = None,
) -> AgentRunResult:
    changed_paths = [
        str(file.get("path", "")).strip()
        for file in changed_files
        if str(file.get("path", "")).strip()
    ]
    prompt = "\n\n".join(
        [
            f"TASK:\n{task.strip()}",
            f"CHANGED FILES:\n{', '.join(changed_paths) or 'No changed files.'}",
            f"TEST STATUS:\n{test_status}",
            f"REPO MEMORY:\n{memory_prompt_block(memory_items or [])}",
            (
                "Summarize the review signal in 3 concise bullets: what changed, "
                "what was verified, and what a human reviewer should inspect. "
                "Do not invent files or claim merge readiness."
            ),
        ]
    )

    try:
        summary = asyncio.run(_run_reviewer_async(prompt=prompt))
    except Exception as error:
        return AgentRunResult(
            command=["openai-agents", "--workflow", "reviewer", "--model", MODEL_LUNA],
            return_code=1,
            stdout="",
            stderr=f"Reviewer Agent failed: {error}",
            attempt="reviewer",
            memory_used=memory_items or [],
            selected_model=MODEL_LUNA,
        )

    return AgentRunResult(
        command=["openai-agents", "--workflow", "reviewer", "--model", MODEL_LUNA],
        return_code=0,
        stdout=summary,
        stderr="",
        attempt="reviewer",
        memory_used=memory_items or [],
        selected_model=MODEL_LUNA,
        reviewer_summary=summary,
    )


async def _run_agent_workflow_async(
    *,
    repo_path: Path,
    task: str,
    context_block: str,
    memory_items: list[str],
    attempt: str,
) -> tuple[PlanResult, str]:
    try:
        from agents import Agent, Runner, function_tool
    except ImportError as error:
        raise ImportError("openai-agents is not installed") from error

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

    planner = Agent(
        name="Planner Agent",
        instructions=(
            "Create a small implementation plan for Code Pilot. Choose exactly "
            f"one model from {MODEL_SOL}, {MODEL_TERRA}, {MODEL_LUNA}. Use "
            f"{MODEL_LUNA} for trivial endpoint/test changes, {MODEL_TERRA} for "
            f"normal feature work, and {MODEL_SOL} for complex refactors, security, "
            "or ambiguous multi-file work. Return compact JSON with keys: "
            "model, summary, files, verification."
        ),
        model=get_openai_agent_model(),
    )
    plan_prompt = _build_planner_prompt(task, context_block, memory_items)
    plan_output = await _run_with_timeout(Runner.run(planner, input=plan_prompt))
    plan = _parse_plan(_final_output(plan_output), task)

    if attempt == "test-repair":
        agent_name = "Repair Agent"
        instructions = (
            f"{OPENAI_AGENT_GUARDRAILS} You are the Repair Agent. Use pytest "
            "failure output in the prompt to make the smallest fix needed."
        )
    else:
        agent_name = "Coder Agent"
        instructions = (
            f"{OPENAI_AGENT_GUARDRAILS} You are the Coder Agent. Follow the "
            "Planner Agent plan, edit only necessary files, and summarize changes."
        )

    coder = Agent(
        name=agent_name,
        instructions=instructions,
        model=plan.model,
        tools=[read_file, write_file],
    )
    coder_prompt = _build_coder_prompt(task, context_block, memory_items, plan)
    coder_output = await _run_with_timeout(Runner.run(coder, input=coder_prompt))
    coder_text = _final_output(coder_output)

    stdout = "\n".join(
        [
            "OpenAI Agents SDK workflow completed.",
            f"planner_agent: {plan.summary}",
            f"planner_selected_model: {plan.model}",
            f"{agent_name.lower().replace(' ', '_')}: {_compact_text(coder_text, limit=3000)}",
        ]
    )
    return plan, stdout


async def _run_reviewer_async(*, prompt: str) -> str:
    try:
        from agents import Agent, Runner
    except ImportError as error:
        raise ImportError("openai-agents is not installed") from error

    reviewer = Agent(
        name="Reviewer Agent",
        instructions=(
            "You are the Reviewer Agent for BroPilot Workbench. Produce concise, "
            "evidence-grounded review notes from the task, changed files, tests, "
            "and memory. Do not approve automatically."
        ),
        model=MODEL_LUNA,
    )
    result = await _run_with_timeout(Runner.run(reviewer, input=prompt))
    return _compact_text(_final_output(result), limit=1400)


async def _run_with_timeout(awaitable: object) -> object:
    return await asyncio.wait_for(awaitable, timeout=OPENAI_AGENT_TIMEOUT_SECONDS)


def _build_planner_prompt(task: str, context_block: str, memory_items: list[str]) -> str:
    return "\n\n".join(
        [
            f"TASK:\n{task.strip()}",
            f"REPO MEMORY:\n{memory_prompt_block(memory_items)}",
            f"PRELOADED REPO CONTEXT:\n{context_block.strip()}",
            "Return JSON only.",
        ]
    )


def _build_coder_prompt(
    task: str, context_block: str, memory_items: list[str], plan: PlanResult
) -> str:
    return "\n\n".join(
        [
            f"TASK:\n{task.strip()}",
            f"PLANNER PLAN:\n{plan.summary}",
            f"SELECTED MODEL:\n{plan.model}",
            f"REPO MEMORY:\n{memory_prompt_block(memory_items)}",
            f"INSTRUCTIONS:\n{OPENAI_AGENT_GUARDRAILS}",
            f"PRELOADED REPO CONTEXT:\n{context_block.strip()}",
            (
                "Use read_file and write_file tools directly. When done, summarize "
                "files changed and the review intent. The backend will run tests."
            ),
        ]
    )


def _parse_plan(output: str, task: str) -> PlanResult:
    fallback_model = _heuristic_model(task)
    try:
        payload = json.loads(_extract_json(output))
    except json.JSONDecodeError:
        return PlanResult(
            model=fallback_model,
            summary=f"Fallback plan: keep the change small, edit relevant files, verify with pytest. Model: {fallback_model}.",
            raw_output=output,
        )

    model = str(payload.get("model") or fallback_model).strip()
    if model not in {MODEL_SOL, MODEL_TERRA, MODEL_LUNA}:
        model = fallback_model
    summary = str(payload.get("summary") or "").strip()
    files = payload.get("files") or []
    verification = str(payload.get("verification") or "python -m pytest").strip()
    if not summary:
        summary = "Keep the change small, edit relevant files, verify with pytest."
    if isinstance(files, list) and files:
        summary = f"{summary} Files: {', '.join(str(file) for file in files[:5])}."
    summary = f"{summary} Verification: {verification}."
    return PlanResult(model=model, summary=_compact_text(summary, limit=900), raw_output=output)


def _heuristic_model(task: str) -> str:
    normalized = task.lower()
    complex_markers = (
        "security",
        "auth",
        "permission",
        "refactor",
        "architecture",
        "database",
        "migration",
        "concurrency",
        "race",
    )
    small_markers = (
        "/status",
        "/health",
        "/ping",
        "simple",
        "one endpoint",
        "add tests",
    )
    if any(marker in normalized for marker in complex_markers):
        return MODEL_SOL
    if any(marker in normalized for marker in small_markers):
        return MODEL_LUNA
    return get_openai_agent_model()


def _extract_json(value: str) -> str:
    stripped = value.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end != -1 and end > start:
        return stripped[start : end + 1]
    return stripped


def _final_output(result: object) -> str:
    output = getattr(result, "final_output", None)
    if output is None:
        output = str(result)
    return str(output)


def _compact_text(value: object, limit: int = 1200) -> str:
    if isinstance(value, str):
        text = value
    else:
        text = json.dumps(value, ensure_ascii=True)

    text = " ".join(text.split())
    if len(text) <= limit:
        return text

    return f"{text[:limit]}... [truncated]"
