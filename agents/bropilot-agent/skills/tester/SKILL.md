---
name: tester
description: Coordinate verification while letting the BroPilot backend run commands.
---

# Tester Skill

The Tester records the verification approach and interprets results produced by the BroPilot backend.

Responsibilities:

- Use `python -m pytest` for the demo repository.
- Do not depend on Gitclaw shell commands for Windows verification.
- Report the exact command, pass/fail status, and relevant output summary.
- If tests fail, connect failures back to likely changed files.
- Do not mark a task complete when tests pass only because no code changed.
