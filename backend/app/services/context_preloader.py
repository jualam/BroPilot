from dataclasses import dataclass
from pathlib import Path


CONTEXT_FILES = (
    "README.md",
    "main.py",
    "auth.py",
    "models.py",
    "tests/test_main.py",
)
MAX_FILE_CHARS = 12000
MAX_TOTAL_CHARS = 50000


@dataclass
class PreloadedFile:
    path: str
    contents: str
    truncated: bool = False


@dataclass
class RepoContext:
    files: list[PreloadedFile]

    @property
    def file_paths(self) -> list[str]:
        return [file.path for file in self.files]

    def to_prompt_block(self) -> str:
        if not self.files:
            return "No known repo files were found to preload."

        blocks = []
        for file in self.files:
            contents = file.contents
            if file.truncated:
                contents = f"{contents}\n[BroPilot truncated this file for prompt size]"

            blocks.append(
                "\n".join(
                    [
                        f"BEGIN FILE: {file.path}",
                        contents,
                        f"END FILE: {file.path}",
                    ]
                )
            )

        return "\n\n".join(blocks)


def preload_repo_context(repo_path: Path) -> RepoContext:
    files: list[PreloadedFile] = []
    total_chars = 0

    for relative_path in CONTEXT_FILES:
        path = repo_path / Path(relative_path)
        if not path.is_file():
            continue

        remaining_chars = MAX_TOTAL_CHARS - total_chars
        if remaining_chars <= 0:
            break

        raw_contents = path.read_text(encoding="utf-8", errors="replace")
        limit = min(MAX_FILE_CHARS, remaining_chars)
        contents = raw_contents[:limit]
        truncated = len(raw_contents) > limit
        total_chars += len(contents)

        files.append(
            PreloadedFile(
                path=relative_path,
                contents=contents,
                truncated=truncated,
            )
        )

    return RepoContext(files=files)
