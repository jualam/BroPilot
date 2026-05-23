# BroPilot Rules

These rules are mandatory for BroPilot agent runs.

1. Never modify `.env` or attempt to read secrets from it.
2. Never touch `.venv` or generated virtual environment files.
3. Never modify `.git` or git metadata.
4. Never push directly to `main`.
5. Never create root-level test files if a `tests/` directory exists.
6. Always put tests under `tests/` when the project already has that convention.
7. Always keep changes small, reviewable, and scoped to the requested task.
8. Always prefer direct read/write tools over shell file discovery.
9. Always let the BroPilot backend run verification commands.
10. Never commit automatically.
11. Never push automatically.
12. If a requested action is unsafe or unclear, stop and report the concern.
