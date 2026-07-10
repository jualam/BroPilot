# BroPilot Workbench

Review-ready AI workflows for high-trust automation.

BroPilot Workbench is a local-first prototype for turning ambiguous work into structured, verified, human-reviewable outputs. Code Pilot is the deepest workflow today: give it a local repository path and an engineering task, and it prepares a reviewable code change while the backend independently captures tests, diffs, safety signals, repo memory, and PR-ready notes.

BroPilot does not auto-merge, auto-push, or bypass human review.

## Workflows

- **Code Pilot**: safe agentic code changes with scoped context, constrained OpenAI Agents SDK execution, independent tests, diffs, safety checks, and a PR summary.
- **Memo Pilot**: architecture demo placeholder for turning company notes into review-ready memo drafts.
- **Ops Pilot**: architecture demo placeholder for turning operating notes into prioritized action plans.

## What Code Pilot Does

BroPilot turns this:

```text
Repo path: D:\bropilot-demo
Task: Add a /status endpoint that returns {"status": "ready"} and add tests
```

Into a local review workflow:

- Analyzer records the starting git state.
- Planner builds a constrained task prompt with repo memory and preloaded file context.
- Coder runs through the OpenAI Agents SDK with scoped read/write tools.
- Tester runs `python -m pytest` from the backend.
- Reviewer captures changed files, diff stats, safety signals, and a copy-ready PR summary.

The dashboard presents the run as an Agent Flight Recorder instead of a black-box response.

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
  | run constrained Code Pilot agent
  v
OpenAI Agents SDK (read_file/write_file tools only)
  |
  v
Target Repo (example: D:\bropilot-demo)
  |
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
Diff modal -> POST /api/review/file-diff -> OpenAI API
```

It summarizes only the currently opened file diff and does not run Code Pilot.

## Project Structure

```text
BroPilot/
|-- frontend/                         # Next.js dashboard and workflow pages
|-- backend/                          # FastAPI orchestrator
|   |-- app/
|   |   |-- routes/                   # Run and review APIs
|   |   |-- schemas/                  # Request/response schemas
|   |   `-- services/                 # OpenAI agent, git, pytest, memory, recorder services
|   `-- data/                         # Ignored local run and memory artifacts
|-- scripts/
|   `-- reset-demo.ps1                # Reset local demo repo
`-- DEMO.md                           # Reproducible demo guide
```

## Local Setup

### Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Put your OpenAI API key in `backend/.env`:

```text
OPENAI_API_KEY=sk-...
```

Optional model overrides:

```text
BROPILOT_OPENAI_AGENT_MODEL=gpt-5.6-terra
BROPILOT_REVIEW_MODEL=gpt-4o-mini
```

Start the backend:

```powershell
cd backend
uvicorn app.main:app --reload --port 8000
```

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

The dashboard runs at:

```text
http://localhost:3000
```

## Routes

- `/` - BroPilot Workbench landing page
- `/code-pilot` - working Code Pilot demo
- `/memo-pilot` - workflow demo placeholder
- `/ops-pilot` - workflow demo placeholder
- `/architecture` - shared workflow pattern page

## Safety Design

BroPilot is intentionally conservative.

- No automatic merge.
- No direct push.
- No automatic commit.
- No `.env`, `.venv`, `.git`, `node_modules`, or generated artifact edits.
- Code Pilot uses scoped read/write tools instead of shell execution.
- Backend independently runs verification after the agent run.
- Human review is required before merge.

If a task says to update only specific files, BroPilot compares that boundary against the final changed files. Unexpected edits are surfaced in the Safety Panel and copied into the PR summary notes.

## Repo Memory

BroPilot stores bounded repo-specific memory under `backend/data/memory/` as local ignored data.

The memory file stores:

- up to 12 lessons
- up to 10 recent run records

Lessons include stable repo facts such as the test command, test location, app entrypoint, changed files, and latest verification result. Lessons are loaded into future Code Pilot prompts so the workflow can adapt to the repo across runs.

## Known Limitations

- Code Pilot currently focuses on Python demo repos using `python -m pytest`.
- Memo Pilot and Ops Pilot are architecture demo placeholders.
- Review Assistant summarizes one opened file diff at a time.
- No GitHub draft PR creation yet.
- No automatic branch/session management yet.
- Human review is still required before merge.
