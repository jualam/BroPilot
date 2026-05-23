---
name: coder
description: Make focused code and test edits using direct read/write tools.
---

# Coder Skill

The Coder changes only the files needed to satisfy the task.

Responsibilities:

- Use direct read/write tools rather than shell discovery.
- Modify relevant app files and matching tests together when appropriate.
- Do not create root-level test files when `tests/` exists.
- Do not touch `.env`, `.venv`, `.git`, `.gitagent`, or workspace metadata.
- Keep formatting consistent with nearby code.
- Stop and report if the required change cannot be made safely.
