import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.schemas.run import StartRunRequest
from app.services.flight_recorder import (
    build_error_run,
    build_success_or_failure_run,
)
from app.services.git_service import (
    CleanupResult,
    cleanup_gitclaw_scaffold,
    get_git_snapshot,
)
from app.services.gitclaw_service import (
    build_fallback_prompt,
    build_test_repair_prompt,
    is_read_only_task,
    run_gitclaw,
)
from app.services.repo_memory import learn_from_run, load_repo_memory
from app.services.test_runner import run_pytest

router = APIRouter(prefix="/api/runs", tags=["runs"])

BACKEND_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BACKEND_DIR / "data" / "runs"


@router.post("/start")
def start_run(payload: StartRunRequest):
    run_id = str(uuid.uuid4())[:8]
    started_at = datetime.now(timezone.utc).isoformat()
    repo_path = Path(payload.repo_path).expanduser()

    if not repo_path.exists() or not repo_path.is_dir():
        return _save_run(
            build_error_run(
                run_id=run_id,
                repo_path=payload.repo_path,
                task=payload.task,
                started_at=started_at,
                message=f"Repo path does not exist or is not a directory: {payload.repo_path}",
            )
        )

    if not os.environ.get("OPENAI_API_KEY"):
        return _save_run(
            build_error_run(
                run_id=run_id,
                repo_path=str(repo_path),
                task=payload.task,
                started_at=started_at,
                message="OPENAI_API_KEY is not set. Set it in the backend process environment and restart uvicorn.",
            )
        )

    try:
        repo_memory = load_repo_memory(repo_path)
        git_before = get_git_snapshot(repo_path)
        if git_before.status.return_code != 0:
            return _save_run(
                build_error_run(
                    run_id=run_id,
                    repo_path=str(repo_path),
                    task=payload.task,
                    started_at=started_at,
                    message=(
                        "Repo path exists, but git status failed: "
                        f"{git_before.status.stderr.strip()}"
                    ),
                )
        )

        gitclaw_result = run_gitclaw(
            repo_path, payload.task, memory_items=repo_memory.lessons
        )
        cleanup_result = cleanup_gitclaw_scaffold(
            repo_path,
            status_before=git_before.status.stdout,
            created_scaffold_paths=gitclaw_result.created_scaffold_paths,
        )
        gitclaw_result.stdout = _append_cleanup_summary(
            gitclaw_result.stdout, cleanup_result
        )
        git_after_gitclaw = get_git_snapshot(repo_path)
        first_changed_count = len(git_after_gitclaw.changed_files)
        fallback_gitclaw_result = None

        if first_changed_count == 0 and not is_read_only_task(payload.task):
            fallback_gitclaw_result = run_gitclaw(
                repo_path,
                payload.task,
                prompt_override=build_fallback_prompt(payload.task),
                attempt="fallback",
                memory_items=repo_memory.lessons,
            )
            fallback_cleanup_result = cleanup_gitclaw_scaffold(
                repo_path,
                status_before=git_before.status.stdout,
                created_scaffold_paths=fallback_gitclaw_result.created_scaffold_paths,
            )
            fallback_gitclaw_result.stdout = _append_cleanup_summary(
                fallback_gitclaw_result.stdout, fallback_cleanup_result
            )
            git_after_gitclaw = get_git_snapshot(repo_path)

        test_result = run_pytest(repo_path)
        repair_gitclaw_result = None

        if test_result.return_code != 0 and not is_read_only_task(payload.task):
            repair_gitclaw_result = run_gitclaw(
                repo_path,
                payload.task,
                prompt_override=build_test_repair_prompt(
                    payload.task,
                    _join_output(test_result.stdout, test_result.stderr),
                    git_after_gitclaw.changed_files,
                ),
                attempt="test-repair",
                memory_items=repo_memory.lessons,
            )
            repair_cleanup_result = cleanup_gitclaw_scaffold(
                repo_path,
                status_before=git_before.status.stdout,
                created_scaffold_paths=repair_gitclaw_result.created_scaffold_paths,
            )
            repair_gitclaw_result.stdout = _append_cleanup_summary(
                repair_gitclaw_result.stdout, repair_cleanup_result
            )
            git_after_gitclaw = get_git_snapshot(repo_path)
            test_result = run_pytest(repo_path)

        git_after = get_git_snapshot(repo_path)
        learned_memory = learn_from_run(
            repo_path=repo_path,
            run_id=run_id,
            task=payload.task,
            previous_lessons=repo_memory.lessons,
            changed_files=git_after_gitclaw.changed_files,
            test_result=test_result,
        )

        run_data = build_success_or_failure_run(
            run_id=run_id,
            repo_path=repo_path,
            task=payload.task,
            started_at=started_at,
            git_before=git_before,
            gitclaw_result=gitclaw_result,
            fallback_gitclaw_result=fallback_gitclaw_result,
            repair_gitclaw_result=repair_gitclaw_result,
            first_changed_count=first_changed_count,
            test_result=test_result,
            git_after_gitclaw=git_after_gitclaw,
            git_after=git_after,
            memory_before=repo_memory.lessons,
            memory_learned=learned_memory,
        )
    except Exception as error:
        run_data = build_error_run(
            run_id=run_id,
            repo_path=str(repo_path),
            task=payload.task,
            started_at=started_at,
            message=f"Unexpected backend error while running BroPilot: {error}",
        )

    return _save_run(run_data)


@router.get("/{run_id}")
def get_run(run_id: str):
    file_path = DATA_DIR / f"{run_id}.json"

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Run not found")

    return json.loads(file_path.read_text(encoding="utf-8"))


def _save_run(run_data: dict):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    file_path = DATA_DIR / f"{run_data['run_id']}.json"
    file_path.write_text(json.dumps(run_data, indent=2), encoding="utf-8")

    return run_data


def _append_cleanup_summary(output: str, cleanup: CleanupResult) -> str:
    parts = [output.strip()] if output.strip() else []
    parts.append(f"BroPilot scaffold cleanup: {cleanup.summary}")

    for label, result in [
        ("unstage", cleanup.unstaged),
        ("restore", cleanup.restored),
        ("clean", cleanup.cleaned),
    ]:
        if result and result.return_code != 0:
            parts.append(
                f"Cleanup {label} exited with {result.return_code}: {result.stderr.strip()}"
            )

    return "\n\n".join(parts)


def _join_output(stdout: str, stderr: str) -> str:
    parts = []

    if stdout.strip():
        parts.append(f"stdout:\n{stdout.strip()}")

    if stderr.strip():
        parts.append(f"stderr:\n{stderr.strip()}")

    return "\n\n".join(parts) or "No pytest output captured."
