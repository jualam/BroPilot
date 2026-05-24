import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.services.test_runner import TestRunResult


BACKEND_DIR = Path(__file__).resolve().parents[2]
MEMORY_DIR = BACKEND_DIR / "data" / "memory"
MAX_LESSONS = 12
MAX_RUNS = 10


@dataclass
class RepoMemory:
    file_path: Path
    repo_name: str
    lessons: list[str]


def load_repo_memory(repo_path: Path) -> RepoMemory:
    file_path = _memory_file_path(repo_path)
    repo_name = repo_path.name

    if not file_path.exists():
        return RepoMemory(file_path=file_path, repo_name=repo_name, lessons=[])

    try:
        payload = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return RepoMemory(file_path=file_path, repo_name=repo_name, lessons=[])

    lessons = [
        str(item).strip()
        for item in payload.get("lessons", [])
        if str(item).strip()
    ]

    return RepoMemory(
        file_path=file_path,
        repo_name=str(payload.get("repo_name") or repo_name),
        lessons=_dedupe(lessons)[:MAX_LESSONS],
    )


def memory_prompt_block(lessons: list[str]) -> str:
    if not lessons:
        return "No prior BroPilot repo memory was found for this run."

    return "\n".join(f"- {lesson}" for lesson in lessons)


def learn_from_run(
    *,
    repo_path: Path,
    run_id: str,
    task: str,
    previous_lessons: list[str],
    changed_files: list[dict],
    test_result: TestRunResult,
) -> list[str]:
    learned = _build_lessons(
        repo_path=repo_path,
        task=task,
        changed_files=changed_files,
        test_result=test_result,
    )
    merged_lessons = _dedupe([*learned, *previous_lessons])[:MAX_LESSONS]
    file_path = _memory_file_path(repo_path)
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)

    existing_runs = _load_runs(file_path)
    run_entry = {
        "run_id": run_id,
        "task": _compact(task, 160),
        "status": "passed" if test_result.return_code == 0 else "failed",
        "changed_files": [file.get("path", "") for file in changed_files],
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }

    payload = {
        "repo_name": repo_path.name,
        "repo_path": str(repo_path),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "lessons": merged_lessons,
        "runs": [run_entry, *existing_runs][:MAX_RUNS],
    }
    file_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    return learned


def _build_lessons(
    *,
    repo_path: Path,
    task: str,
    changed_files: list[dict],
    test_result: TestRunResult,
) -> list[str]:
    changed_paths = [str(file.get("path", "")) for file in changed_files]
    lessons = [
        f"Use python -m pytest to verify changes in {repo_path.name}.",
    ]

    if (repo_path / "tests" / "test_main.py").is_file():
        lessons.append("Tests live in tests/test_main.py.")

    if (repo_path / "main.py").is_file():
        lessons.append("The FastAPI app entrypoint is main.py.")

    if (repo_path / "auth.py").is_file():
        lessons.append("Auth and profile lookup logic is in auth.py.")

    if changed_paths:
        lessons.append(f"Recent BroPilot changes touched: {', '.join(changed_paths[:5])}.")

    if test_result.return_code == 0:
        lessons.append(f"Last verification passed for task: {_compact(task, 90)}.")
    else:
        lessons.append(
            "Last verification failed; keep the patch reviewable and rerun python -m pytest."
        )

    return _dedupe(lessons)


def _memory_file_path(repo_path: Path) -> Path:
    resolved = str(repo_path.resolve()).lower()
    digest = hashlib.sha1(resolved.encode("utf-8")).hexdigest()[:10]
    safe_name = "".join(
        character if character.isalnum() or character in ("-", "_") else "-"
        for character in repo_path.name.lower()
    ).strip("-") or "repo"

    return MEMORY_DIR / f"{safe_name}-{digest}.json"


def _load_runs(file_path: Path) -> list[dict]:
    if not file_path.exists():
        return []

    try:
        payload = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []

    runs = payload.get("runs", [])
    return runs if isinstance(runs, list) else []


def _dedupe(items: list[str]) -> list[str]:
    seen = set()
    result = []

    for item in items:
        cleaned = " ".join(item.strip().split())
        key = cleaned.lower()
        if not cleaned or key in seen:
            continue

        seen.add(key)
        result.append(cleaned)

    return result


def _compact(value: str, limit: int) -> str:
    cleaned = " ".join(value.strip().split())
    if len(cleaned) <= limit:
        return cleaned

    return f"{cleaned[: limit - 3]}..."
