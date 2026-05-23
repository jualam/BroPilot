# BroPilot

Your repo's AI teammate for safe, reviewable code changes.

BroPilot is a local-first multi-agent PR builder. Give it a repository path and an engineering task, and it runs a controlled Gitclaw-powered workflow that aims to produce a small, test-backed code change with a clear review trail.

It does not auto-merge, auto-push, or bypass human review. BroPilot prepares reviewable changes and shows exactly what happened.

## What BroPilot Does

BroPilot turns this:

```text
Repo path: D:\bropilot-demo
Task: Fix profile lookup to return 404 for unknown users and add tests
```

Into a local agent run with:

- Gitclaw agent execution through the SDK
- captured agent timeline
- changed file detection
- backend-run `python -m pytest`
- safety cleanup for generated scaffold files
- a PR-style summary for human review

The frontend presents the run as an Agent Flight Recorder so you can inspect the analyzer, planner, coder, tester, and reviewer stages instead of trusting a black box.

## Why This Is Useful

AI coding tools often hide too much. They edit files, run commands, and summarize results without making the decision trail easy to inspect.

BroPilot is built around a different idea: agentic code changes should be observable, constrained, and reviewable. The useful artifact is not just the patch. It is the patch plus the run history, safety posture, test result, changed files, and PR-ready explanation.

## Key Features

- **Gitclaw SDK runner**: the backend invokes Gitclaw through a small Node.js SDK runner instead of relying on the CLI path.
- **CLI tool disabled**: BroPilot runs Gitclaw with `disallowedTools: ["cli"]` for safer Windows-compatible local runs.
- **Agent Flight Recorder**: the Next.js dashboard shows each agent stage, status, summary, and details.
- **Independent pytest verification**: the FastAPI backend runs `python -m pytest` itself after the agent finishes.
- **Changed files and git diff capture**: BroPilot records git status, changed files, and diff summaries for review.
- **Protected path cleanup**: generated Gitclaw scaffold/runtime files are cleaned after each run while preserving existing user files.
- **Curated Gitclaw-native agent config**: `agents/bropilot-agent/` documents BroPilot's intended agent identity, rules, duties, memory, skills, and safety hooks.

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
  | preload known repo files
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
  v
Agent Flight Recorder Response
  |
  v
Next.js Dashboard
```

## Project Structure

```text
BroPilot/
|-- frontend/                         # Next.js dashboard
|-- backend/                          # FastAPI orchestrator
|   |-- app/
|   |   |-- routes/                   # API routes
|   |   |-- schemas/                  # Request schemas
|   |   `-- services/                 # Gitclaw, git, pytest, recorder services
|   |-- scripts/
|   |   `-- gitclaw_runner.mjs        # Node Gitclaw SDK runner
|   `-- data/runs/                    # Local run JSON artifacts
`-- agents/
    |-- README.md
    `-- bropilot-agent/               # Curated Gitclaw-native agent spec
        |-- agent.yaml
        |-- SOUL.md
        |-- RULES.md
        |-- DUTIES.md
        |-- memory/MEMORY.md
        |-- skills/
        `-- hooks/hooks.yaml
```

## Local Setup

### 1. Backend Python setup

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Set your OpenAI key in the backend process environment:

```powershell
$env:OPENAI_API_KEY="sk-..."
```

Optional model override:

```powershell
$env:BROPILOT_GITCLAW_MODEL="openai:gpt-4o"
```

### 2. Backend Node dependency

The Gitclaw SDK runner imports `gitclaw` from the backend Node environment:

```powershell
cd backend
npm install gitclaw
```

### 3. Run the backend

```powershell
cd backend
uvicorn app.main:app --reload --port 8000
```

The API runs at:

```text
http://127.0.0.1:8000
```

### 4. Frontend setup

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

1. Start the backend:

```powershell
cd backend
$env:OPENAI_API_KEY="sk-..."
uvicorn app.main:app --reload --port 8000
```

2. Start the frontend:

```powershell
cd frontend
npm run dev
```

3. Open the dashboard:

```text
http://localhost:3000
```

4. Enter the local demo repo path:

```text
D:\bropilot-demo
```

Demo target repo on GitHub: https://github.com/jualam/broPilot-demo.git

5. Enter the task:

```text
Fix profile lookup to return 404 for unknown users and add tests
```

6. Run BroPilot and inspect the Agent Flight Recorder:

- Analyzer Agent
- Planner Agent
- Coder Agent
- Tester Agent
- Reviewer Agent
- changed files
- test result
- safety notes
- memory panel
- PR summary

## Safety Design

BroPilot is intentionally conservative.

- No automatic merge.
- No direct push to `main`.
- No automatic commit.
- No `.env`, `.venv`, or `.git` modification.
- Backend independently runs verification after the agent run.
- Human review is required before merge.

The backend also cleans up temporary Gitclaw scaffold/runtime files created during local runs, including `.gitagent/` and `workspace/`, while preserving user-owned agent files if they already existed.

## Why BroPilot Disables the Gitclaw CLI Tool

During testing, Gitclaw's shell-oriented CLI tool was unreliable on Windows. The agent repeatedly attempted commands such as:

- `grep`
- `find`
- `Get-Content`
- `Select-String`

Those commands failed in the local workflow, and Gitclaw could exit without producing code changes.

BroPilot solves this by using the Gitclaw SDK runner with:

```js
disallowedTools: ["cli"]
```

That forces read/write-style agent behavior. BroPilot then runs verification itself through the FastAPI backend with `python -m pytest` and captures git status/diff independently.

## Known Limitations

BroPilot is a local-first prototype built for the GitAgent/Gitclaw hiring challenge.

- No GitHub draft PR creation yet.
- No automatic branch management yet.
- No cloud deployment yet.
- Memory growth is represented in the UI and curated agent spec, but persistent repo-history memory is not fully implemented yet.
- Verification currently focuses on Python demo repos using `python -m pytest`.
- Human review is still required before merge.

## Future Improvements

- GitHub draft PR creation.
- Safe branch/session management.
- Persistent repo memory across runs.
- Richer policy hooks and audit logs.
- Support for more repo types and test commands.
- Cloud deployment for shared demos.
- More robust agent retry and self-correction loops.

## Challenge Context

BroPilot was built for a GitAgent/Gitclaw builder challenge focused on execution, product thinking, and agent workflow design.

The core idea is simple: make AI-generated code changes safer by turning the agent run into a visible, reviewable flight recorder.
