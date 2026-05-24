import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


GITCLAW_RUNTIME_ROOTS = (".gitagent", "workspace")
MAX_DIFF_VIEW_CHARS = 20000


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
    diff_numstat: GitCommandResult
    diff_summary: GitCommandResult
    changed_files: list[dict[str, str]]


def get_git_snapshot(repo_path: Path) -> GitSnapshot:
    status = run_git(repo_path, ["status", "--porcelain"])
    diff_stat = run_git(repo_path, ["diff", "--stat"])
    diff_numstat = run_git(repo_path, ["diff", "--numstat", "HEAD", "--"])
    diff_summary = run_git(repo_path, ["diff", "--summary"])

    diff_stats = (
        parse_numstat(diff_numstat.stdout) if diff_numstat.return_code == 0 else {}
    )
    changed_files = (
        parse_changed_files(status.stdout, diff_stats)
        if status.return_code == 0
        else []
    )
    changed_files = enrich_changed_files(repo_path, changed_files)

    return GitSnapshot(
        status=status,
        diff_stat=diff_stat,
        diff_numstat=diff_numstat,
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


def parse_changed_files(
    status_output: str, diff_stats: dict[str, dict[str, int]] | None = None
) -> list[dict[str, str]]:
    files: list[dict[str, str]] = []
    diff_stats = diff_stats or {}

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
                "additions": diff_stats.get(path, {}).get("additions", 0),
                "deletions": diff_stats.get(path, {}).get("deletions", 0),
                "diff_stat": _format_file_stat(path, diff_stats.get(path)),
            }
        )

    return files


def enrich_changed_files(
    repo_path: Path, changed_files: list[dict[str, str]]
) -> list[dict[str, str]]:
    enriched = []

    for file in changed_files:
        before_contents = _read_before_contents(repo_path, file["path"])
        after_contents = _read_after_contents(repo_path, file["path"])
        before, before_truncated = _truncate_file_contents(before_contents)
        after, after_truncated = _truncate_file_contents(after_contents)

        enriched.append(
            {
                **file,
                "before_contents": before,
                "after_contents": after,
                "content_truncated": before_truncated or after_truncated,
            }
        )

    return enriched


def parse_numstat(numstat_output: str) -> dict[str, dict[str, int]]:
    stats: dict[str, dict[str, int]] = {}

    for line in numstat_output.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue

        additions = _parse_count(parts[0])
        deletions = _parse_count(parts[1])
        path = parts[2].split(" => ")[-1].strip("{}")

        stats[path] = {
            "additions": additions,
            "deletions": deletions,
        }

    return stats


def _parse_count(value: str) -> int:
    return int(value) if value.isdigit() else 0


def _format_file_stat(path: str, stats: dict[str, int] | None) -> str:
    if not stats:
        return f"{path} +0 -0"

    return f"{path} +{stats['additions']} -{stats['deletions']}"


def _read_before_contents(repo_path: Path, path: str) -> str:
    result = run_git(repo_path, ["show", f"HEAD:{path.replace('\\', '/')}"])
    if result.return_code != 0:
        return ""

    return result.stdout


def _read_after_contents(repo_path: Path, path: str) -> str:
    file_path = repo_path / Path(path)
    if not file_path.is_file():
        return ""

    return file_path.read_text(encoding="utf-8", errors="replace")


def _truncate_file_contents(value: str) -> tuple[str, bool]:
    if len(value) <= MAX_DIFF_VIEW_CHARS:
        return value, False

    return (
        f"{value[:MAX_DIFF_VIEW_CHARS]}\n[BroPilot truncated this file for display]",
        True,
    )


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
