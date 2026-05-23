import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


GITCLAW_RUNTIME_ROOTS = (".gitagent", "workspace")


@dataclass
class GitCommandResult:
    command: list[str]
    return_code: int
    stdout: str
    stderr: str


@dataclass
class CleanupResult:
    unstaged: GitCommandResult | None
    restored: GitCommandResult | None
    cleaned: GitCommandResult | None
    summary: str


@dataclass
class GitSnapshot:
    status: GitCommandResult
    diff_stat: GitCommandResult
    diff_summary: GitCommandResult
    changed_files: list[dict[str, str]]


def get_git_snapshot(repo_path: Path) -> GitSnapshot:
    status = run_git(repo_path, ["status", "--porcelain"])
    diff_stat = run_git(repo_path, ["diff", "--stat"])
    diff_summary = run_git(repo_path, ["diff", "--summary"])

    changed_files = (
        parse_changed_files(status.stdout) if status.return_code == 0 else []
    )

    return GitSnapshot(
        status=status,
        diff_stat=diff_stat,
        diff_summary=diff_summary,
        changed_files=changed_files,
    )


def cleanup_gitclaw_scaffold(
    repo_path: Path,
    status_before: str = "",
    created_scaffold_paths: list[str] | None = None,
) -> CleanupResult:
    status = run_git(repo_path, ["status", "--porcelain", "--untracked-files=all"])
    if status.return_code != 0:
        return CleanupResult(
            unstaged=None,
            restored=None,
            cleaned=None,
            summary=f"Skipped scaffold cleanup because git status failed: {status.stderr.strip()}",
        )

    entries = _parse_status_entries(status.stdout)
    before_paths = {
        entry["path"] for entry in _parse_status_entries(status_before)
    }
    gitignore_was_clean = ".gitignore" not in before_paths
    should_restore_gitignore = gitignore_was_clean and any(
        entry["path"] == ".gitignore" for entry in entries
    )
    created_roots = tuple(created_scaffold_paths or ())
    cleanup_roots = (*created_roots, *GITCLAW_RUNTIME_ROOTS)
    cleanup_paths = [
        entry["path"]
        for entry in entries
        if _is_cleanup_path(entry["path"], cleanup_roots)
        or (entry["path"] == ".gitignore" and should_restore_gitignore)
    ]
    staged_paths = [
        entry["path"]
        for entry in entries
        if entry["index_status"] != " "
        and entry["status_code"] != "??"
        and (
            _is_cleanup_path(entry["path"], cleanup_roots)
            or (entry["path"] == ".gitignore" and should_restore_gitignore)
        )
    ]

    unstaged = (
        run_git(repo_path, ["restore", "--staged", "--", *staged_paths])
        if staged_paths
        else None
    )

    restore_roots = (".gitignore",) if should_restore_gitignore else ()
    tracked_roots = _tracked_roots(repo_path, restore_roots)
    restored = (
        run_git(repo_path, ["restore", "--", *tracked_roots])
        if tracked_roots
        else None
    )

    cleaned = (
        run_git(repo_path, ["clean", "-fdx", "--", *cleanup_roots])
        if cleanup_roots
        else None
    )

    touched = sorted(set(cleanup_paths))
    summary_parts = []
    if touched:
        summary_parts.append(f"cleanup candidates: {', '.join(touched)}")
    if staged_paths:
        summary_parts.append(f"unstaged: {', '.join(sorted(set(staged_paths)))}")
    if tracked_roots:
        summary_parts.append(f"restored tracked roots: {', '.join(tracked_roots)}")
    if cleaned and cleaned.stdout.strip():
        summary_parts.append(cleaned.stdout.strip())
    if created_roots:
        summary_parts.append(
            f"Temporary scaffold cleaned up: {', '.join(created_roots)}"
        )

    return CleanupResult(
        unstaged=unstaged,
        restored=restored,
        cleaned=cleaned,
        summary="; ".join(summary_parts) or "No Gitclaw scaffold cleanup needed.",
    )


def run_git(repo_path: Path, args: list[str]) -> GitCommandResult:
    executable = shutil.which("git")
    command = [executable or "git", *args]

    if executable is None:
        return GitCommandResult(
            command=command,
            return_code=127,
            stdout="",
            stderr="git was not found on PATH.",
        )

    try:
        completed = subprocess.run(
            command,
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired as error:
        return GitCommandResult(
            command=command,
            return_code=124,
            stdout=_coerce_output(error.stdout),
            stderr=_coerce_output(error.stderr) or "git command timed out.",
        )

    return GitCommandResult(
        command=command,
        return_code=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def parse_changed_files(status_output: str) -> list[dict[str, str]]:
    files: list[dict[str, str]] = []

    for line in status_output.splitlines():
        if len(line) < 4:
            continue

        status_code = line[:2]
        raw_path = line[3:]
        path = raw_path.split(" -> ")[-1]
        change_type = _change_type_from_status(status_code)

        files.append(
            {
                "path": path,
                "change_type": change_type,
                "summary": f"{change_type.capitalize()} in the working tree.",
            }
        )

    return files


def _parse_status_entries(status_output: str) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []

    for line in status_output.splitlines():
        if len(line) < 4:
            continue

        path = line[3:].split(" -> ")[-1].replace("\\", "/")
        entries.append(
            {
                "status_code": line[:2],
                "index_status": line[0],
                "worktree_status": line[1],
                "path": path,
            }
        )

    return entries


def _is_cleanup_path(path: str, roots: tuple[str, ...]) -> bool:
    normalized = path.replace("\\", "/").strip("/")

    return any(
        normalized == root or normalized.startswith(f"{root}/")
        for root in roots
    )


def _tracked_roots(repo_path: Path, roots: tuple[str, ...]) -> list[str]:
    tracked = []

    for root in roots:
        result = run_git(repo_path, ["ls-files", "--", root])
        if result.return_code == 0 and result.stdout.strip():
            tracked.append(root)

    return tracked


def _change_type_from_status(status_code: str) -> str:
    if status_code == "??":
        return "created"

    if "R" in status_code:
        return "renamed"

    if "D" in status_code:
        return "deleted"

    if "A" in status_code:
        return "created"

    if "M" in status_code:
        return "modified"

    return "changed"


def _coerce_output(value: bytes | str | None) -> str:
    if value is None:
        return ""

    if isinstance(value, bytes):
        return value.decode(errors="replace")

    return value
