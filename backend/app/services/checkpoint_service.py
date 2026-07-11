import base64
import json
from datetime import datetime, timezone
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[2]
CHECKPOINT_DIR = BACKEND_DIR / "data" / "checkpoints"
EXCLUDED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".next",
    "dist",
    "build",
}
EXCLUDED_FILES = {".env"}


def create_run_checkpoint(run_id: str, repo_path: Path) -> dict:
    root = repo_path.resolve()
    files = []

    for file_path in _iter_checkpoint_files(root):
        relative_path = file_path.relative_to(root).as_posix()
        files.append(
            {
                "path": relative_path,
                "content": base64.b64encode(file_path.read_bytes()).decode("ascii"),
            }
        )

    payload = {
        "run_id": run_id,
        "repo_path": str(root),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "files": files,
    }
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    _checkpoint_path(run_id).write_text(json.dumps(payload, indent=2), encoding="utf-8")

    return {
        "run_id": run_id,
        "repo_path": str(root),
        "file_count": len(files),
    }


def restore_run_checkpoint(run_id: str) -> dict:
    checkpoint_path = _checkpoint_path(run_id)
    if not checkpoint_path.exists():
        return {
            "status": "missing",
            "message": "No local checkpoint exists for this run.",
            "restored_files": 0,
            "removed_files": 0,
        }

    payload = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    root = Path(payload["repo_path"]).resolve()
    if not root.exists() or not root.is_dir():
        return {
            "status": "error",
            "message": f"Checkpoint repo path no longer exists: {root}",
            "restored_files": 0,
            "removed_files": 0,
        }

    saved_files = {
        item["path"]: base64.b64decode(item["content"])
        for item in payload.get("files", [])
    }
    removed_files = 0

    for file_path in _iter_checkpoint_files(root):
        relative_path = file_path.relative_to(root).as_posix()
        if relative_path not in saved_files:
            file_path.unlink()
            removed_files += 1

    for relative_path, contents in saved_files.items():
        target = (root / relative_path).resolve()
        if not _is_within(root, target):
            continue

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(contents)

    return {
        "status": "restored",
        "message": "Repo restored to the local checkpoint captured before this run.",
        "restored_files": len(saved_files),
        "removed_files": removed_files,
    }


def _checkpoint_path(run_id: str) -> Path:
    return CHECKPOINT_DIR / f"{run_id}.json"


def _iter_checkpoint_files(root: Path):
    for path in root.rglob("*"):
        if not path.is_file():
            continue

        relative_parts = path.relative_to(root).parts
        if any(part in EXCLUDED_DIRS for part in relative_parts):
            continue

        if path.name in EXCLUDED_FILES:
            continue

        yield path


def _is_within(root: Path, target: Path) -> bool:
    try:
        target.relative_to(root)
    except ValueError:
        return False

    return True
