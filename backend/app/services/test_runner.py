import subprocess
from dataclasses import dataclass
from pathlib import Path


PYTEST_TIMEOUT_SECONDS = 10 * 60


@dataclass
class TestRunResult:
    command: list[str]
    return_code: int
    stdout: str
    stderr: str
    timed_out: bool = False


def run_pytest(repo_path: Path) -> TestRunResult:
    command = ["python", "-m", "pytest"]

    try:
        completed = subprocess.run(
            command,
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=PYTEST_TIMEOUT_SECONDS,
        )
    except FileNotFoundError:
        return TestRunResult(
            command=command,
            return_code=127,
            stdout="",
            stderr="Python was not found on PATH.",
        )
    except subprocess.TimeoutExpired as error:
        return TestRunResult(
            command=command,
            return_code=124,
            stdout=_coerce_output(error.stdout),
            stderr=(
                _coerce_output(error.stderr)
                or f"pytest timed out after {PYTEST_TIMEOUT_SECONDS} seconds."
            ),
            timed_out=True,
        )

    return TestRunResult(
        command=command,
        return_code=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def _coerce_output(value: bytes | str | None) -> str:
    if value is None:
        return ""

    if isinstance(value, bytes):
        return value.decode(errors="replace")

    return value
