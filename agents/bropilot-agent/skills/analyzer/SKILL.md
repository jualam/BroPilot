---
name: analyzer
description: Inspect the repository and identify the safest path for a requested code change.
---

# Analyzer Skill

The Analyzer reads the task, checks the current repository context, and identifies the files most likely to matter.

Responsibilities:

- Confirm the repository appears to match the requested task.
- Note existing test locations and project conventions.
- Identify protected paths such as `.env`, `.venv`, `.git`, `.gitagent`, and generated workspaces.
- Report if the task appears read-only, unsafe, or underspecified.
- Avoid shell search commands when direct file context is available.
