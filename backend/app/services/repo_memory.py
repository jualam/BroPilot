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
    legacy_file_path = _legacy_memory_file_path(repo_path)
    repo_name = repo_path.name

    if not file_path.exists() and legacy_file_path.exists():
        file_path = legacy_file_path

    if not file_path.exists():
        return RepoMemory(file_path=file_path, repo_name=repo_name, lessons=[])

    try:
        payload = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return RepoMemory(file_path=file_path, repo_name=repo_name, lessons=[])

    raw_lessons = [
        str(item).strip()
        for item in payload.get("lessons", [])
        if str(item).strip()
    ]

    return RepoMemory(
        file_path=file_path,
        repo_name=str(payload.get("repo_name") or repo_name),
        lessons=_merge_lessons(raw_lessons),
    )


def memory_prompt_block(lessons: list[str]) -> str:
    if not lessons:
        return "No prior BroPilot repo memory was found for this run."

    return "\n".join(f"- {lesson}" for lesson in _merge_lessons(lessons))


def learn_from_run(
    *,
    repo_path: Path,
    run_id: str,
    task: str,
    previous_lessons: list[str],
    changed_files: list[dict],
    test_result: TestRunResult,
) -> list[str]:
    learned = _merge_lessons(
        _build_lessons(
            repo_path=repo_path,
            task=task,
            changed_files=changed_files,
            test_result=test_result,
        )
    )
    merged_lessons = _merge_lessons(learned, previous_lessons)
    file_path = _memory_file_path(repo_path)
    legacy_file_path = _legacy_memory_file_path(repo_path)
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)

    existing_runs = _load_runs(file_path)
    if not existing_runs and legacy_file_path.exists():
        existing_runs = _load_runs(legacy_file_path)

    run_entry = {
        "run_id": run_id,
        "task": _compact(task, 160),
        "status": "passed" if test_result.return_code == 0 else "failed",
        "changed_files": _changed_paths(changed_files),
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
    changed_paths = _changed_paths(changed_files)
    lessons = ["Verify with python -m pytest."]

    if (repo_path / "tests" / "test_main.py").is_file():
        lessons.append("Tests: tests/test_main.py.")

    if (repo_path / "main.py").is_file():
        lessons.append("FastAPI entrypoint: main.py.")

    if (repo_path / "auth.py").is_file():
        lessons.append("Auth/profile logic: auth.py.")

    if changed_paths:
        lessons.append(f"Recent touched files: {', '.join(changed_paths[:5])}.")
        feature_lesson = _feature_lesson(task, changed_paths)
        if feature_lesson:
            lessons.append(feature_lesson)

    if test_result.return_code == 0:
        lessons.append("Latest verification: pytest passed.")
    else:
        lessons.append("Latest verification: pytest failed; repair using pytest output.")

    return lessons


def _memory_file_path(repo_path: Path) -> Path:
    return MEMORY_DIR / f"{_safe_repo_name(repo_path)}-data.json"


def _legacy_memory_file_path(repo_path: Path) -> Path:
    resolved = str(repo_path.resolve()).lower()
    digest = hashlib.sha1(resolved.encode("utf-8")).hexdigest()[:10]
    return MEMORY_DIR / f"{_safe_repo_name(repo_path)}-{digest}.json"


def _safe_repo_name(repo_path: Path) -> str:
    safe_name = "".join(
        character if character.isalnum() or character in ("-", "_") else "-"
        for character in repo_path.name.lower()
    ).strip("-") or "repo"

    return safe_name


def _load_runs(file_path: Path) -> list[dict]:
    if not file_path.exists():
        return []

    try:
        payload = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []

    runs = payload.get("runs", [])
    return runs if isinstance(runs, list) else []


def _merge_lessons(*lesson_groups: list[str]) -> list[str]:
    merged: list[str] = []
    seen_keys: set[str] = set()

    for lesson in _dedupe([lesson for group in lesson_groups for lesson in group]):
        canonical = _canonical_lesson(lesson)
        key = _lesson_key(canonical)

        if not canonical or key in seen_keys:
            continue

        seen_keys.add(key)
        merged.append(canonical)

        if len(merged) >= MAX_LESSONS:
            break

    return merged


def _canonical_lesson(lesson: str) -> str:
    cleaned = " ".join(lesson.strip().split())
    normalized = cleaned.lower()

    if normalized.startswith("use python -m pytest") or normalized.startswith(
        "verify with python -m pytest"
    ):
        return "Verify with python -m pytest."

    if normalized.startswith("tests live in tests/test_main.py") or normalized.startswith(
        "tests: tests/test_main.py"
    ):
        return "Tests: tests/test_main.py."

    if normalized.startswith("the fastapi app entrypoint is main.py") or normalized.startswith(
        "fastapi entrypoint: main.py"
    ):
        return "FastAPI entrypoint: main.py."

    if normalized.startswith("auth and profile lookup logic is in auth.py") or normalized.startswith(
        "auth/profile logic: auth.py"
    ):
        return "Auth/profile logic: auth.py."

    if normalized.startswith("recent bropilot changes touched:"):
        return f"Recent touched files: {_extract_after_colon(cleaned)}"

    if normalized.startswith("recent touched files:"):
        return cleaned

    if normalized.startswith("feature:"):
        return _compact(cleaned, 140)

    if normalized.startswith("last verification passed") or normalized.startswith(
        "latest verification: pytest passed"
    ):
        return "Latest verification: pytest passed."

    if normalized.startswith("last verification failed") or normalized.startswith(
        "latest verification: pytest failed"
    ):
        return "Latest verification: pytest failed; repair using pytest output."

    return _compact(cleaned, 120)


def _lesson_key(lesson: str) -> str:
    normalized = lesson.lower()
    if normalized.startswith("verify with"):
        return "verify"
    if normalized.startswith("tests:"):
        return "tests"
    if normalized.startswith("fastapi entrypoint:"):
        return "entrypoint"
    if normalized.startswith("auth/profile logic:"):
        return "domain-auth"
    if normalized.startswith("recent touched files:"):
        return "recent-files"
    if normalized.startswith("feature:"):
        return normalized
    if normalized.startswith("latest verification:"):
        return "latest-verification"

    return normalized


def _changed_paths(changed_files: list[dict]) -> list[str]:
    paths = []

    for file in changed_files:
        path = str(file.get("path", "")).strip().replace("\\", "/")
        if path and path not in paths:
            paths.append(path)

    return paths


def _feature_lesson(task: str, changed_paths: list[str]) -> str:
    normalized = task.lower()
    endpoint = _extract_endpoint(normalized)
    if endpoint:
        main_file = _first_matching_path(changed_paths, "main.py")
        test_file = _first_matching_path(changed_paths, "test")
        parts = [f"Feature: {endpoint} endpoint"]
        if main_file:
            parts.append(f"implementation {main_file}")
        if test_file:
            parts.append(f"test {test_file}")
        return "; ".join(parts) + "."

    if "profile" in normalized and "404" in normalized:
        touched = ", ".join(changed_paths[:3])
        return f"Feature: unknown profile returns 404; touched {touched}."

    if "rate limit" in normalized or "rate limiting" in normalized:
        touched = ", ".join(changed_paths[:3])
        return f"Feature: login rate limiting; touched {touched}."

    return ""


def _extract_endpoint(task: str) -> str:
    match = _search_endpoint(task)
    return match or ""


def _search_endpoint(task: str) -> str:
    import re

    match = re.search(r"/[a-z0-9_-]+", task)
    return match.group(0) if match else ""


def _first_matching_path(paths: list[str], needle: str) -> str:
    for path in paths:
        if needle in path:
            return path

    return ""


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


def _extract_after_colon(value: str) -> str:
    _, _, tail = value.partition(":")
    return tail.strip() or value


def _compact(value: str, limit: int) -> str:
    cleaned = " ".join(value.strip().split())
    if len(cleaned) <= limit:
        return cleaned

    return f"{cleaned[: limit - 3]}..."
