# BroPilot Agent Configuration

This folder contains the curated Gitclaw-native agent specification for BroPilot.

BroPilot's backend uses the Gitclaw SDK runner to create temporary agent scaffolding inside target repositories during local runs. That temporary scaffold exists only so Gitclaw can operate safely against a repo. The `agents/bropilot-agent/` folder is the permanent, reviewable source of truth for BroPilot's intended agent behavior, identity, rules, memory, skills, and safety posture.

## Key Files

- `agent.yaml` defines BroPilot's model, tools, runtime settings, skills, and compliance posture.
- `SOUL.md` describes BroPilot's engineering identity and working style.
- `RULES.md` records hard safety and reviewability constraints.
- `DUTIES.md` documents the agent workflow.
- `memory/MEMORY.md` stores starter memory and local workflow lessons.
- `skills/` contains role-specific instructions for each BroPilot phase.
- `hooks/hooks.yaml` documents intended safety hooks for blocking unsafe actions.

## Workflow

BroPilot follows a five-stage workflow:

Analyzer -> Planner -> Coder -> Tester -> Reviewer

The Analyzer understands the repository and task. The Planner proposes a small implementation path. The Coder makes focused read/write edits. The Tester records backend-run verification results. The Reviewer prepares the final human-facing summary.

## Safety Philosophy

BroPilot prepares code for review; it does not bypass review.

- No direct push to `main`.
- No automatic merge.
- No `.env`, `.venv`, or `.git` modification.
- Backend independently runs verification commands.
- Human review is required before merge.

## Why The CLI Tool Is Disabled

During Windows testing, Gitclaw's shell-oriented `cli` tool repeatedly attempted commands such as `grep`, `find`, `Get-Content`, and `Select-String`, and those commands were unreliable in the local workflow. BroPilot therefore disables the Gitclaw `cli` tool in the SDK runner, nudges the agent toward read/write-style behavior, and lets the backend run verification itself.

This keeps local runs safer, more deterministic, and easier to audit.