import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from app.services.git_service import GitSnapshot
from app.services.openai_agent_service import (
    AgentRunResult,
    OPENAI_AGENT_GUARDRAILS,
    is_read_only_task,
)
from app.services.test_runner import TestRunResult


def build_success_or_failure_run(
    *,
    run_id: str,
    repo_path: Path,
    task: str,
    started_at: str,
    git_before: GitSnapshot,
    agent_result: AgentRunResult,
    fallback_agent_result: AgentRunResult | None,
    repair_agent_result: AgentRunResult | None,
    first_changed_count: int,
    test_result: TestRunResult,
    git_after_agent: GitSnapshot,
    git_after: GitSnapshot,
    memory_before: list[str] | None = None,
    memory_learned: list[str] | None = None,
) -> dict:
    completed_at = _now()
    final_agent_result = (
        repair_agent_result or fallback_agent_result or agent_result
    )
    tests_passed = test_result.return_code == 0
    agent_passed = final_agent_result.return_code == 0
    git_ok = git_after.status.return_code == 0
    changed_files = git_after_agent.changed_files
    changed_count = len(changed_files)
    memory_before = memory_before or []
    memory_learned = memory_learned or []
    memory_used = agent_result.memory_used
    no_code_changes = (
        agent_passed and changed_count == 0 and not is_read_only_task(task)
    )
    safety_actions = _safety_actions(task, changed_files)
    has_safety_warnings = any(
        action["command"] != "Protected paths guarded" for action in safety_actions
    )

    if no_code_changes and agent_passed and git_ok:
        status = "needs_attention"
    elif agent_passed and tests_passed and git_ok:
        status = "completed"
    else:
        status = "failed"

    return {
        "run_id": run_id,
        "status": status,
        "repo_path": str(repo_path),
        "task": task,
        "started_at": started_at,
        "completed_at": completed_at,
        "agents": [
            _analyzer_agent(git_before),
            _planner_agent(task, agent_result.preloaded_files, memory_used),
            _coder_agent(
                agent_result,
                fallback_agent_result,
                repair_agent_result,
                first_changed_count,
                changed_count,
                no_code_changes,
            ),
            _tester_agent(test_result),
            _reviewer_agent(git_after_agent, changed_count, no_code_changes),
        ],
        "changed_files": changed_files,
        "tests": {
            "command": "python -m pytest",
            "status": "passed" if tests_passed else "failed",
            "summary": _test_summary(test_result),
        },
        "safety": {
            "risk_score": _risk_score(
                agent_passed,
                tests_passed,
                git_ok,
                no_code_changes,
                has_safety_warnings,
            ),
            "risk_reason": _risk_reason(
                agent_passed,
                tests_passed,
                git_ok,
                no_code_changes,
                has_safety_warnings,
            ),
            "blocked_actions": safety_actions,
        },
        "memory": {
            "before": (
                memory_before
                if memory_before
                else ["No prior repo memory loaded for this run."]
            ),
            "learned": memory_learned
            or [
                f"Use python -m pytest to verify changes in {repo_path.name}.",
                _learned_change_summary(changed_count, no_code_changes),
                "Keep BroPilot changes small and reviewable before PR creation.",
            ],
            "used": _memory_used_items(memory_used),
        },
        "pr_summary": {
            "title": _pr_title(task),
            "body": _pr_body(
                repo_path=repo_path,
                changed_count=changed_count,
                no_code_changes=no_code_changes,
                test_result=test_result,
            ),
            "markdown": _pr_markdown(
                task=task,
                changed_files=changed_files,
                test_result=test_result,
                safety_actions=safety_actions,
            ),
        },
    }


def build_error_run(
    *,
    run_id: str,
    repo_path: str,
    task: str,
    started_at: str,
    message: str,
) -> dict:
    completed_at = _now()

    return {
        "run_id": run_id,
        "status": "failed",
        "repo_path": repo_path,
        "task": task,
        "started_at": started_at,
        "completed_at": completed_at,
        "agents": [
            {
                "name": "Analyzer Agent",
                "status": "failed",
                "summary": "BroPilot could not start the local workflow.",
                "details": message,
            },
            {
                "name": "Planner Agent",
                "status": "skipped",
                "summary": "Planning was skipped.",
                "details": "Fix the startup error and run BroPilot again.",
            },
            {
                "name": "Coder Agent",
                "status": "skipped",
                "summary": "OpenAI Agents SDK was not invoked.",
                "details": "No files were read or written by OpenAI Agents SDK for this run.",
            },
            {
                "name": "Tester Agent",
                "status": "skipped",
                "summary": "Tests were not run.",
                "details": "Verification only runs after the workflow passes startup checks.",
            },
            {
                "name": "Reviewer Agent",
                "status": "skipped",
                "summary": "Review data was not generated.",
                "details": "No git diff was captured for this failed startup.",
            },
        ],
        "changed_files": [],
        "tests": {
            "command": "python -m pytest",
            "status": "skipped",
            "summary": message,
        },
        "safety": {
            "risk_score": "blocked",
            "blocked_actions": [
                {
                    "command": "workflow startup",
                    "reason": message,
                }
            ],
        },
        "memory": {
            "before": ["No prior repo memory loaded for this run."],
            "learned": [message],
            "used": [],
        },
        "pr_summary": {
            "title": "BroPilot workflow did not start",
            "body": [
                message,
                "No commit was created and nothing was pushed.",
            ],
        },
    }


def _analyzer_agent(git_before: GitSnapshot) -> dict:
    if git_before.status.return_code != 0:
        return {
            "name": "Analyzer Agent",
            "status": "failed",
            "summary": "Could not read git status before the run.",
            "details": _command_details(git_before.status.stderr),
        }

    status_text = git_before.status.stdout.strip() or "Working tree was clean."
    return {
        "name": "Analyzer Agent",
        "status": "completed",
        "summary": "Recorded git status before invoking OpenAI Agents SDK.",
        "details": _command_details(status_text),
    }


def _planner_agent(
    task: str, preloaded_files: list[str], memory_used: list[str]
) -> dict:
    return {
        "name": "Planner Agent",
        "status": "completed",
        "summary": "Built a constrained OpenAI Agents SDK task prompt.",
        "details": _command_details(
            "\n\n".join(
                [
                    f"Task: {task}",
                    f"Repo memory loaded: {_memory_loaded_summary(memory_used)}",
                    f"Preloaded files: {_preloaded_files_summary(preloaded_files)}",
                    f"Guardrails: {OPENAI_AGENT_GUARDRAILS}",
                ]
            )
        ),
    }


def _coder_agent(
    result: AgentRunResult,
    fallback_result: AgentRunResult | None,
    repair_result: AgentRunResult | None,
    first_changed_count: int,
    final_changed_count: int,
    no_code_changes: bool,
) -> dict:
    final_result = repair_result or fallback_result or result

    if no_code_changes:
        status = "needs_attention"
        summary = (
            "Fallback OpenAI Agents SDK attempt also produced 0 code changes."
            if fallback_result
            else "OpenAI Agents SDK completed but produced 0 code changes."
        )
    elif repair_result and final_result.return_code == 0:
        status = "completed"
        summary = "OpenAI Agents SDK ran a test repair attempt after pytest failed."
    elif final_result.return_code == 0:
        status = "completed"
        summary = (
            f"Fallback OpenAI Agents SDK attempt changed {final_changed_count} file(s)."
            if fallback_result
            else "OpenAI Agents SDK finished successfully."
        )
    elif final_result.timed_out:
        status = "failed"
        summary = "OpenAI Agents SDK timed out before finishing."
    else:
        status = "failed"
        summary = f"OpenAI Agents SDK exited with code {final_result.return_code}."

    return {
        "name": "Coder Agent",
        "status": status,
        "summary": summary,
        "details": _command_details(
            _coder_details(
                result,
                fallback_result,
                repair_result,
                first_changed_count,
                final_changed_count,
            )
        ),
    }


def _tester_agent(result: TestRunResult) -> dict:
    passed = result.return_code == 0
    return {
        "name": "Tester Agent",
        "status": "completed" if passed else "failed",
        "summary": "Ran python -m pytest." if passed else _test_summary(result),
        "details": _command_details(_result_details(result)),
    }


def _reviewer_agent(
    git_after: GitSnapshot, changed_count: int, no_code_changes: bool
) -> dict:
    if git_after.status.return_code != 0:
        return {
            "name": "Reviewer Agent",
            "status": "failed",
            "summary": "Could not capture final git status.",
            "details": _command_details(git_after.status.stderr),
        }

    details = "\n\n".join(
        item
        for item in [
            f"Changed files: {changed_count}",
            git_after.status.stdout.strip(),
            git_after.diff_stat.stdout.strip(),
            git_after.diff_summary.stdout.strip(),
        ]
        if item
    )

    return {
        "name": "Reviewer Agent",
        "status": "needs_attention" if no_code_changes else "completed",
        "summary": (
            "OpenAI Agents SDK completed but produced 0 code changes."
            if no_code_changes
            else "Captured final git status and diff summary."
        ),
        "details": _command_details(
            "OpenAI Agents SDK completed but produced 0 code changes."
            if no_code_changes
            else details or "No working tree changes detected."
        ),
    }


def _test_summary(result: TestRunResult) -> str:
    if result.return_code == 0:
        return _last_interesting_line(result.stdout) or "pytest passed."

    if result.timed_out:
        return "pytest timed out."

    return _last_interesting_line(_join_output(result.stdout, result.stderr)) or (
        f"pytest exited with code {result.return_code}."
    )


def _risk_score(
    agent_passed: bool,
    tests_passed: bool,
    git_ok: bool,
    no_code_changes: bool,
    has_safety_warnings: bool = False,
) -> str:
    if no_code_changes or has_safety_warnings:
        return "medium"

    if agent_passed and tests_passed and git_ok:
        return "low"

    if git_ok:
        return "medium"

    return "high"


def _risk_reason(
    agent_passed: bool,
    tests_passed: bool,
    git_ok: bool,
    no_code_changes: bool,
    has_safety_warnings: bool = False,
) -> str:
    if no_code_changes:
        return "No code changes were produced, so human review is needed before treating the task as done."

    if has_safety_warnings:
        return "Review needed: OpenAI Agents SDK changed at least one file outside the task or safety boundary."

    if agent_passed and tests_passed and git_ok:
        return "Clean review signal: OpenAI Agents SDK changed files, git status was captured, and pytest passed."

    if git_ok:
        return "Review needed: BroPilot captured the patch, but verification did not fully pass."

    return "High attention: BroPilot could not reliably capture git status for the final review."


def _pr_title(task: str) -> str:
    cleaned = " ".join(task.strip().split())
    if not cleaned:
        return "BroPilot code changes"

    if len(cleaned) <= 100:
        return cleaned

    candidate = cleaned[:100].rsplit(" ", 1)[0].strip()
    return f"{candidate or cleaned[:100].strip()}..."


def _status_word(return_code: int) -> str:
    return "passed" if return_code == 0 else f"failed with exit code {return_code}"


def _preloaded_files_summary(preloaded_files: list[str]) -> str:
    if not preloaded_files:
        return "No known repo files were found."

    return ", ".join(preloaded_files)


def _learned_change_summary(changed_count: int, no_code_changes: bool) -> str:
    if no_code_changes:
        return "Latest OpenAI Agents SDK run produced 0 code changes and needs attention."

    return f"Latest run changed {changed_count} file(s)."


def _safety_actions(task: str, changed_files: list[dict]) -> list[dict]:
    actions = [
        {
            "command": "Protected paths guarded",
            "reason": (
                "BroPilot instructed OpenAI Agents SDK to avoid .env, .venv, .git, "
                ".gitagent, workspace, skills/, and git metadata."
            ),
        }
    ]
    changed_paths = [
        _normalize_repo_path(str(file.get("path", "")))
        for file in changed_files
        if file.get("path")
    ]
    allowed_paths = _explicit_allowed_paths(task)

    if allowed_paths:
        unexpected_paths = [
            path for path in changed_paths if not _path_allowed(path, allowed_paths)
        ]
        if unexpected_paths:
            actions.append(
                {
                    "command": "Unexpected file changed",
                    "reason": (
                        f"{', '.join(unexpected_paths)} changed even though the task "
                        f"requested only {', '.join(allowed_paths)}."
                    ),
                }
            )

    protected_changes = [
        path
        for path in changed_paths
        if path.startswith(("skills/", ".env", ".venv/", ".git/", ".gitagent/", "workspace/"))
    ]
    if protected_changes:
        actions.append(
            {
                "command": "Protected path changed",
                "reason": (
                    f"{', '.join(protected_changes)} changed even though BroPilot "
                    "guardrails marked protected paths as review-sensitive."
                ),
            }
        )

    return actions


def _explicit_allowed_paths(task: str) -> list[str]:
    cleaned_task = " ".join(task.replace("\\", "/").split())
    patterns = [
        r"(?:update|modify|change|edit)\s+only\s+(.+?)(?:\.|$)",
        r"only\s+(?:update|modify|change|edit)\s+(.+?)(?:\.|$)",
    ]

    for pattern in patterns:
        match = re.search(pattern, cleaned_task, flags=re.IGNORECASE)
        if not match:
            continue

        paths = _extract_repo_paths(match.group(1))
        if paths:
            return paths

    return []


def _extract_repo_paths(value: str) -> list[str]:
    candidates = re.findall(r"[\w./-]+(?:\.[A-Za-z0-9_]+|/)", value)
    paths = []

    for candidate in candidates:
        path = _normalize_repo_path(candidate)
        if path and path not in {"py", "json"} and path not in paths:
            paths.append(path)

    return paths


def _path_allowed(path: str, allowed_paths: list[str]) -> bool:
    return any(
        path == allowed_path
        or (allowed_path.endswith("/") and path.startswith(allowed_path))
        for allowed_path in allowed_paths
    )


def _normalize_repo_path(path: str) -> str:
    return path.replace("\\", "/").strip().strip(".,;:'\"`")


def _memory_used_items(memory_used: list[str]) -> list[str]:
    items = [
        "Applied protected-path guardrails before invoking OpenAI Agents SDK.",
        "Backend subprocess runner handled verification instead of OpenAI Agents SDK shell tools.",
    ]

    if memory_used:
        items.insert(0, f"Loaded {len(memory_used)} repo memory item(s) into the OpenAI Agents SDK prompt.")
        items.extend(memory_used[:5])
    else:
        items.insert(0, "No previous repo memory was available, so BroPilot started fresh.")

    return items


def _memory_loaded_summary(memory_used: list[str]) -> str:
    if not memory_used:
        return "No prior repo memory found."

    return f"Loaded {len(memory_used)} repo memory item(s): {', '.join(memory_used[:4])}"


def _pr_body(
    *,
    repo_path: Path,
    changed_count: int,
    no_code_changes: bool,
    test_result: TestRunResult,
) -> list[str]:
    if no_code_changes:
        return [
            f"Ran OpenAI Agents SDK against {repo_path.name}, but it produced 0 code changes.",
            "BroPilot did not mark the requested task as completed.",
            f"Verification still ran: python -m pytest {_status_word(test_result.return_code)}.",
        ]

    return [
        f"Ran OpenAI Agents SDK against {repo_path.name} with the configured safety prompt.",
        f"Captured {changed_count} changed file(s) from git status.",
        f"Verification result: python -m pytest {_status_word(test_result.return_code)}.",
    ]


def _pr_markdown(
    *,
    task: str,
    changed_files: list[dict],
    test_result: TestRunResult,
    safety_actions: list[dict],
) -> str:
    changed_paths = [
        str(file.get("path", "")).strip()
        for file in changed_files
        if str(file.get("path", "")).strip()
    ]
    review_flags = [
        action["reason"]
        for action in safety_actions
        if action["command"] != "Protected paths guarded"
    ]

    sections = [
        "## Summary",
        f"- Task: {task.strip()}",
    ]

    if changed_paths:
        sections.extend(
            [
                "- Changed files:",
                *[f"  - {path}" for path in changed_paths],
            ]
        )
    else:
        sections.append("- No code changes were captured.")

    sections.extend(
        [
            "",
            "## Verification",
            f"- python -m pytest {_status_word(test_result.return_code)}",
            "",
            "## Review",
            "- Human review required before merge",
            "- No automatic commit, push, or merge was performed",
        ]
    )

    if review_flags:
        sections.extend(
            [
                "",
                "## Safety Notes",
                *[f"- {flag}" for flag in review_flags],
            ]
        )

    return "\n".join(sections)


def _join_output(stdout: str, stderr: str) -> str:
    parts = []

    if stdout.strip():
        parts.append(f"stdout:\n{stdout.strip()}")

    if stderr.strip():
        parts.append(f"stderr:\n{stderr.strip()}")

    return "\n\n".join(parts)


def _result_details(result: AgentRunResult | TestRunResult) -> str:
    output = _join_output(result.stdout, result.stderr)

    return "\n\n".join(
        item
        for item in [
            f"attempt: {result.attempt}" if isinstance(result, AgentRunResult) else "",
            (
                result.scaffold_summary
                if isinstance(result, AgentRunResult) and result.scaffold_summary
                else ""
            ),
            f"command: {_display_command(result.command)}",
            f"return_code: {result.return_code}",
            output or "No stdout or stderr captured.",
        ]
        if item
    )


def _display_command(command: list[str]) -> str:
    return subprocess.list2cmdline(command)


def _coder_details(
    result: AgentRunResult,
    fallback_result: AgentRunResult | None,
    repair_result: AgentRunResult | None,
    first_changed_count: int,
    final_changed_count: int,
) -> str:
    sections = [
        f"First OpenAI Agents SDK attempt changed {first_changed_count} file(s).",
        _result_details(result),
    ]

    if fallback_result:
        sections.extend(
            [
                "First OpenAI Agents SDK attempt produced 0 changes.",
                "Fallback OpenAI Agents SDK attempt started.",
                (
                    f"Fallback changed {final_changed_count} file(s)."
                    if final_changed_count
                    else "Fallback also produced 0 changes."
                ),
                _result_details(fallback_result),
            ]
        )

    if repair_result:
        sections.extend(
            [
                "BroPilot backend verification failed after the first code attempt.",
                "Test repair OpenAI Agents SDK attempt started with pytest output in the prompt.",
                f"After repair, git status shows {final_changed_count} changed file(s).",
                _result_details(repair_result),
            ]
        )

    return "\n\n".join(sections)


def _last_interesting_line(output: str) -> str:
    for line in reversed(output.splitlines()):
        stripped = line.strip()
        if stripped and not stripped.startswith("="):
            return stripped

    return ""


def _command_details(value: str) -> str:
    return _truncate(value.strip() or "No details captured.")


def _truncate(value: str, limit: int = 4000) -> str:
    if len(value) <= limit:
        return value

    return f"{value[:limit]}...\n[output truncated]"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

