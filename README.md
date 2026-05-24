# BroPilot

Safe PR builder for agentic code changes.

BroPilot is a local-first multi-agent PR builder powered by Gitclaw. Give it a repository path and an engineering task, and it runs a constrained agent workflow that produces a reviewable code change, runs tests independently, captures the diff, records repo memory, and packages the result for human review.

BroPilot does not auto-merge, auto-push, or bypass human review.

## What BroPilot Does

BroPilot turns this:

```text
Repo path: D:\bropilot-demo
Task: Add a /status endpoint that returns {"status": "ready"} and add tests
```

Into a local review workflow:

- Analyzer records the starting git state.
- Planner builds a constrained Gitclaw prompt with repo memory and preloaded file context.
- Coder runs Gitclaw through the SDK with shell commands disabled.
- Tester runs `python -m pytest` from the backend.
- Reviewer captures changed files, diff stats, safety signals, and a copy-ready PR summary.

The dashboard presents the run as an Agent Flight Recorder instead of a black-box agent response.

## Why This Is Useful

AI coding agents can edit files quickly, but they often hide too much of the workflow. BroPilot makes the change reviewable by showing:

- what the agent was asked to do
- which files were preloaded and changed
- whether tests passed
- whether the agent touched unexpected files
- what repo memory was used and learned
- what a reviewer can copy into a PR

The goal is not automatic merging. The goal is safer, observable, review-ready code generation.

## Key Features

- **Gitclaw SDK runner**: BroPilot invokes Gitclaw through `backend/scripts/gitclaw_runner.mjs`.
- **CLI tool disabled**: Gitclaw runs with `disallowedTools: ["cli"]` for safer Windows-compatible local runs.
- **Preloaded repo context**: known repo files are loaded into the prompt so Gitclaw does not need shell discovery.
- **Agent Flight Recorder**: the Next.js dashboard shows Analyzer, Planner, Coder, Tester, and Reviewer stages.
- **Independent pytest verification**: the FastAPI backend runs `python -m pytest` after Gitclaw finishes.
- **Test repair attempt**: when pytest fails, BroPilot can run a focused Gitclaw repair attempt using the failure output.
- **Changed files and diff viewer**: file cards show additions/deletions and open a side-by-side before/after diff.
- **Review Assistant**: on-demand AI summary for a single opened file diff.
- **Safety warnings**: BroPilot flags protected paths and unexpected file changes outside the task boundary.
- **Repo memory**: bounded repo-specific lessons are stored locally and loaded into future Gitclaw prompts.
- **Copy-ready PR summary**: generated markdown summarizes the patch, verification, and review requirements.
- **Demo reset script**: `scripts/reset-demo.ps1` resets the demo repo to a known baseline.
- **Curated Gitclaw-native agent spec**: `agents/bropilot-agent/` documents BroPilot's intended identity, rules, duties, memory, skills, and hooks.

## Architecture

```text
User
  |
  v
Next.js Dashboard (frontend/)
  |
  | POST /api/runs/start
  v
FastAPI Orchestrator (backend/)
  |
  | load repo memory
  | preload known files
  | create temporary Gitclaw scaffold in target repo
  v
Node Gitclaw SDK Runner (backend/scripts/gitclaw_runner.mjs)
  |
  | query({ dir, prompt, model, disallowedTools: ["cli"] })
  v
Target Repo (example: D:\bropilot-demo)
  |
  | cleanup scaffold/runtime files
  | run python -m pytest
  | capture git status/diff
  | update repo memory
  v
Agent Flight Recorder Response
  |
  v
Next.js Dashboard
```

Review Assistant uses a separate backend endpoint:

```text
Diff modal -> POST /api/review/file-diff -> OpenAI Responses API
```

It summarizes only the currently opened file diff and does not invoke Gitclaw.

## Project Structure

```text
BroPilot/
|-- frontend/                         # Next.js dashboard
|-- backend/                          # FastAPI orchestrator
|   |-- app/
|   |   |-- routes/                   # Run and review APIs
|   |   |-- schemas/                  # Request/response schemas
|   |   `-- services/                 # Gitclaw, git, pytest, memory, recorder services
|   |-- scripts/
|   |   `-- gitclaw_runner.mjs        # Node Gitclaw SDK runner
|   `-- data/                         # Ignored local run and memory artifacts
|-- agents/
|   |-- README.md
|   `-- bropilot-agent/               # Curated Gitclaw-native agent spec
|       |-- agent.yaml
|       |-- SOUL.md
|       |-- RULES.md
|       |-- DUTIES.md
|       |-- memory/MEMORY.md
|       |-- skills/
|       `-- hooks/hooks.yaml
|-- scripts/
|   `-- reset-demo.ps1                # Reset local demo repo
`-- DEMO.md                           # Reproducible demo guide
```

## Local Setup

### Backend Python Setup

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Set the OpenAI key in the backend process environment:

```powershell
$env:OPENAI_API_KEY="sk-..."
```

Optional model overrides:

```powershell
$env:BROPILOT_GITCLAW_MODEL="openai:gpt-4o"
$env:BROPILOT_REVIEW_MODEL="gpt-4o-mini"
```

### Backend Node Dependency

The Gitclaw SDK runner imports `gitclaw` from the backend Node environment:

```powershell
cd backend
npm install gitclaw
```

### Run The Backend

```powershell
cd backend
uvicorn app.main:app --reload --port 8000
```

The API runs at:

```text
http://127.0.0.1:8000
```

### Run The Frontend

```powershell
cd frontend
npm install
npm run dev
```

The dashboard runs at:

```text
http://localhost:3000
```

## Demo Flow

See [DEMO.md](DEMO.md) for the reproducible demo guide.

The main demo task is:

```text
Add a /status endpoint that returns {"status": "ready"} and add tests. Update only main.py and tests/test_main.py. Do not modify skills/. Make python -m pytest pass.
```

Expected successful result:

- `main.py` and `tests/test_main.py` changed
- `python -m pytest` passed
- Safety signal is low unless unexpected files changed
- Diff viewer and Review Assistant are available
- Copy-ready PR markdown is generated

## Safety Design

BroPilot is intentionally conservative.

- No automatic merge.
- No direct push to `main`.
- No automatic commit.
- No `.env`, `.venv`, or `.git` modification.
- No GitHub API or stored API keys.
- Backend independently runs verification after the agent run.
- Human review is required before merge.

BroPilot also cleans up temporary Gitclaw scaffold/runtime files created during local runs, including `.gitagent/`, `workspace/`, `agent.yaml`, `SOUL.md`, and `memory/` when they were created by BroPilot.

If a task says to update only specific files, BroPilot compares that boundary against the final changed files. Unexpected edits are surfaced in the Safety Panel and copied into the PR summary notes.

## Why BroPilot Disables the Gitclaw CLI Tool

During local Windows testing, the direct Gitclaw CLI path was not reliable enough for BroPilot's workflow. The agent could fall back to shell-style discovery commands, which made runs harder to control and sometimes produced no useful code changes.

BroPilot switched to the Gitclaw SDK so the backend can disable the `cli` tool, preload repo context, capture structured output, and keep verification under BroPilot's control.

The runner disables shell execution with:

```js
disallowedTools: ["cli"]
```

That keeps the agent focused on read/write-style file edits while BroPilot handles verification itself by running `python -m pytest` and capturing git status/diff independently.

## Repo Memory

BroPilot stores bounded repo-specific memory under `backend/data/memory/` as local ignored data.

The memory file stores:

- up to 12 lessons
- up to 10 recent run records

Lessons include stable repo facts such as the test command, test location, app entrypoint, changed files, and the latest verification result. Lessons are loaded into future Gitclaw prompts so the agent can adapt to the repo across runs.

The run records are audit history and are not used as a replacement for human review.

## Known Limitations

BroPilot is a local-first prototype.

- No GitHub draft PR creation yet.
- No automatic branch/session management yet.
- No cloud deployment yet.
- Verification currently focuses on Python demo repos using `python -m pytest`.
- Review Assistant summarizes one opened file diff at a time.
- Human review is still required before merge.

## Future Improvements

- GitHub draft PR creation.
- Safe branch/session management.
- Persistent repo memory across cloned sessions.
- Richer policy hooks and audit logs.
- Support for more repo types and test commands.
- Cloud deployment for shared demos.
- Run history browser in the dashboard.
