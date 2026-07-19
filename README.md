# BroPilot Workbench

Review-ready AI workflows for high-trust automation.

BroPilot Workbench is a local-first prototype that turns ambiguous work into structured, verified, human-reviewable outputs. It applies the same review-first workflow to three different domains:

```text
Context Intake -> Scoped Plan -> Constrained Agent -> Independent Verification -> Flight Recorder -> Human Review
```

BroPilot does not automatically merge code, push branches, make investment decisions, or execute operating changes. It prepares evidence and artifacts for a person to review and approve.

## Table of Contents

- [What BroPilot Includes](#what-bropilot-includes)
- [How the Workflows Operate](#how-the-workflows-operate)
- [Architecture](#architecture)
- [Technology Stack](#technology-stack)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Using the Workbench](#using-the-workbench)
- [API Reference](#api-reference)
- [Local Data and Recovery](#local-data-and-recovery)
- [Safety and Privacy](#safety-and-privacy)
- [Development and Validation](#development-and-validation)
- [Troubleshooting](#troubleshooting)
- [Current Limitations](#current-limitations)
- [Future Roadmap](#future-roadmap)
- [Additional Documentation](#additional-documentation)

## What BroPilot Includes

### Code Pilot

Code Pilot turns an engineering request into a review-ready change in a local Git repository.

It can:

- inspect a local target repository and its current Git state;
- preload relevant repository context and lessons from earlier runs;
- infer explicitly requested file scope from the task;
- let an OpenAI Agents SDK agent read and edit files through constrained tools;
- retry when the first attempt produces no changes;
- run `python -m pytest` independently of the coding agent;
- make one focused repair attempt when tests fail;
- capture changed files, before/after contents, diff statistics, and safety signals;
- generate reviewer notes and copy-ready pull request text;
- save a local run record and a pre-run checkpoint; and
- restore the target repository to that checkpoint after confirmation.

The included demo uses a separate target repository: [jualam/broPilot-demo](https://github.com/jualam/broPilot-demo). BroPilot expects it at `D:\bropilot-demo` by default, though Code Pilot accepts another local repository path in the UI.

### Memo Pilot

Memo Pilot turns company documents and notes into a diligence memo draft. It is intended to organize diligence, not make an investment decision.

It supports:

- up to eight PDFs per run, with an 8 MB limit per file;
- text and table extraction from text-based PDFs;
- manual call notes, management notes, metrics, and observations;
- evidence cards tied to named sources;
- evidence coverage and source summaries;
- AI-assisted memo planning, drafting, risk review, and gap review;
- deterministic fallback output when an AI call is unavailable or rejected by guardrails;
- separate facts, assumptions, risks, missing evidence, and diligence questions; and
- browser-generated Markdown and print/PDF exports, with or without an evidence appendix.

### Ops Pilot

Ops Pilot turns operating notes, PDFs, and a workflow screenshot into an operations improvement plan. It identifies candidates for review; it does not implement workflows or guarantee ROI.

It supports:

- manual operating notes;
- PNG, JPEG, WebP, or BMP image, up to 8 MB;
- PDFs, up to 8 MB each;
- local image OCR through Tesseract;
- text and table extraction from PDFs;
- deterministic operational signal extraction;
- typed AI-agent output for bottlenecks, automation opportunities, and prioritization;
- a recommended first workflow, 30-day plan, metrics, risks, and open questions;
- deterministic fallback output when AI generation is unavailable; and
- browser-generated Markdown and print/PDF exports.

## How the Workflows Operate

Every workflow exposes its process through a Flight Recorder rather than returning an unexplained answer.

### Code Pilot stages

| Stage | Execution | Purpose |
| --- | --- | --- |
| Analyzer | Deterministic | Records the starting repository and Git state. |
| Planner | AI-assisted with deterministic guardrails | Loads context and repo memory, chooses a model, derives scope, and prepares instructions. |
| Coder | AI agent | Reads and edits files through repository-scoped tools. |
| Tester | Deterministic | Runs backend-owned `python -m pytest` verification. |
| Reviewer | Deterministic and AI-assisted | Captures the final diff, safety signals, test result, and review notes. |

If a normal coding request produces no file changes, Code Pilot makes a fallback attempt. If tests fail, it supplies the failure output and changed-file list to one repair attempt, then runs the tests again. A failure remains visible and review-required.

### Memo Pilot stages

| Stage | Execution | Purpose |
| --- | --- | --- |
| Document Intake | Deterministic | Receives PDFs, company information, sector, and notes. |
| Text Extraction | Deterministic | Extracts PDF text and tables with source names. |
| Evidence Extraction | Deterministic | Builds source-backed evidence items. |
| Memo Planner | AI agent | Maps evidence into a diligence structure. |
| Draft Generator | AI agent | Produces a grounded memo draft. |
| Risk Checker | Hybrid | Reviews risks and assumptions, then normalizes the result. |
| Evidence Gap Review | Hybrid | Checks grounding, missing evidence, and decision-language guardrails. |
| Human Review Artifact | Deterministic | Packages the memo, appendix, reviewer notes, and exports. |

### Ops Pilot stages

| Stage | Execution | Purpose |
| --- | --- | --- |
| Ops Intake | Deterministic | Receives images, PDFs, workflow information, and notes. |
| OCR / Text Extraction | Deterministic | Uses local OCR and PDF parsing to recover source text. |
| Signal Extraction | Deterministic | Converts source material into structured operational signals. |
| Bottleneck Analyst | AI agent | Identifies bottlenecks, evidence, and root causes. |
| Automation Planner | AI agent | Proposes opportunities and concrete workflow steps. |
| Prioritization | AI agent | Ranks opportunities and prepares a first workflow and plan. |
| Risk & Guardrail Review | Hybrid | Produces risks and questions and validates blocked claims. |
| Human Review Artifact | Deterministic | Packages the review and export-ready Markdown. |

Memo Pilot and Ops Pilot label whether their content is `llm_grounded` or a `deterministic_fallback`. A fallback reason is also returned, making degraded behavior visible rather than silent.

## Architecture

```text
Browser
  |
  v
Next.js 16 frontend (localhost:3000)
  |
  | HTTP / multipart form data
  v
FastAPI backend (127.0.0.1:8000)
  |
  |-- Code Pilot
  |   |-- local Git repository inspection
  |   |-- constrained OpenAI Agents SDK execution
  |   |-- independent pytest verification
  |   |-- local checkpoints and repo memory
  |   `-- run artifact and review generation
  |
  |-- Memo Pilot
  |   |-- pdfplumber text/table extraction
  |   |-- deterministic evidence construction
  |   |-- typed AI-assisted memo workflow
  |   `-- Markdown and browser print/PDF output
  |
  `-- Ops Pilot
      |-- Tesseract OCR and pdfplumber extraction
      |-- deterministic signal extraction
      |-- typed AI-assisted planning workflow
      `-- Markdown and browser print/PDF output
```

The frontend currently calls a backend fixed at `http://127.0.0.1:8000`. The backend CORS configuration allows `http://localhost:3000`.

## Technology Stack

| Layer | Main technologies |
| --- | --- |
| Frontend | Next.js 16, React 19, TypeScript, Tailwind CSS 4 |
| Backend | Python 3.12, FastAPI, Pydantic, Uvicorn |
| AI orchestration | OpenAI Agents SDK and OpenAI Responses API |
| Repository operations | GitPython and Git CLI |
| Verification | pytest executed as a subprocess in the target repo |
| Documents | pdfplumber, Pillow, pytesseract |
| Persistence | Local JSON files under `backend/data` |

## Project Structure

```text
BroPilot/
|-- backend/
|   |-- app/
|   |   |-- main.py                 # FastAPI app, CORS, and router registration
|   |   |-- routes/                 # Code, review, memo, and ops endpoints
|   |   |-- schemas/                # Request and response models
|   |   `-- services/               # Agents, parsing, Git, tests, memory, checkpoints
|   |-- data/
|   |   |-- checkpoints/            # Code Pilot pre-run repository snapshots
|   |   |-- memory/                 # Learned per-repository context, created on use
|   |   `-- runs/                   # Code Pilot run records, created on use
|   |-- .env                        # Local secrets; never commit this file
|   `-- requirements.txt
|-- frontend/
|   |-- public/                     # Logos and static assets
|   |-- src/app/                    # Next.js App Router pages
|   `-- package.json
|-- demo-materials/                 # Sample Memo Pilot and Ops Pilot inputs
|-- scripts/
|   `-- reset-demo.ps1              # Destructively resets only the demo target repo
|-- tools/                          # Optional local Tesseract installation
|-- DEMO.md                         # Reproducible Code Pilot walkthrough
|-- SETUP.md                        # Short Windows setup guide
`-- README.md
```

## Prerequisites

- Windows PowerShell for the documented setup and reset script
- Python 3.12
- Node.js 20 or newer and npm
- Git available on `PATH`
- an OpenAI API key for Code Pilot and AI-grounded outputs
- Tesseract OCR only if using image extraction in Ops Pilot

Memo Pilot and Ops Pilot can generate deterministic fallback output without an API key. Code Pilot requires an API key because its core operation is agent-driven code editing.

## Quick Start

### 1. Clone the application

```powershell
git clone https://github.com/jualam/BroPilot.git D:\BroPilot
cd D:\BroPilot
```

### 2. Install and configure the backend

```powershell
cd D:\BroPilot\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Create `backend\.env` and add your key:

```dotenv
OPENAI_API_KEY=sk-your-key-here
```

Do not paste a real key into source code, documentation, screenshots, issues, or commits.

Start FastAPI from the backend directory:

```powershell
cd D:\BroPilot\backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```

Verify it in another terminal:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Expected response:

```json
{
  "status": "ok",
  "service": "bropilot-api"
}
```

Interactive FastAPI documentation is available at `http://127.0.0.1:8000/docs`.

### 3. Install and run the frontend

Open a second PowerShell window:

```powershell
cd D:\BroPilot\frontend
npm install
npm run dev
```

Open `http://localhost:3000`.

### 4. Optional: install OCR support

Ops Pilot expects the Tesseract executable at:

```text
D:\BroPilot\tools\Tesseract-OCR\tesseract.exe
```

Install Tesseract into that directory, then verify it:

```powershell
cd D:\BroPilot
.\tools\Tesseract-OCR\tesseract.exe --version
```

PDF extraction does not require Tesseract. It is only needed for image OCR.

### 5. Optional: prepare the Code Pilot demo repository

```powershell
git clone https://github.com/jualam/broPilot-demo.git D:\bropilot-demo
cd D:\BroPilot
powershell -ExecutionPolicy Bypass -File .\scripts\reset-demo.ps1
```

The reset script performs a hard reset and clean inside `D:\bropilot-demo`, resets it to baseline commit `d672866`, deletes and recreates the local `demo-working` branch, and runs pytest. Do not point it at a repository containing work you need to keep.

## Configuration

The backend loads variables from `backend/.env` through `python-dotenv`.

| Variable | Required | Default | Purpose |
| --- | --- | --- | --- |
| `OPENAI_API_KEY` | Code Pilot: yes; Memo/Ops: no | none | Authenticates OpenAI requests. Memo and Ops use fallback output when absent. |
| `BROPILOT_OPENAI_AGENT_MODEL` | No | application default | Model used by the Code Pilot coding and repair agent. |
| `BROPILOT_REVIEW_MODEL` | No | `gpt-4o-mini` | Model used for the single-file diff explanation endpoint. |
| `BROPILOT_MEMO_AGENT_MODEL` | No | application default | Model used for Memo Pilot agent stages. |
| `BROPILOT_OPS_AGENT_MODEL` | No | application default | Model used for Ops Pilot agent stages. |

Example optional overrides:

```dotenv
BROPILOT_OPENAI_AGENT_MODEL=your-supported-model
BROPILOT_REVIEW_MODEL=your-supported-model
BROPILOT_MEMO_AGENT_MODEL=your-supported-model
BROPILOT_OPS_AGENT_MODEL=your-supported-model
```

Use model names available to your OpenAI project. Restart Uvicorn after changing `.env`. Model overrides affect cost, latency, and output behavior.

Currently the frontend API base URL and backend CORS origin are defined in source rather than environment variables. See the roadmap for configurable deployment support.

## Using the Workbench

### Code Pilot walkthrough

1. Open `http://localhost:3000/code-pilot`.
2. Enter the absolute path to a local Git repository. For the demo, use `D:\bropilot-demo`.
3. Confirm the repository status shown by the UI. Starting from a clean working tree makes review and recovery clearer.
4. Write a narrow task that states the behavior, expected tests, and permitted files.
5. Select **Run Code Pilot** and wait for agent execution and pytest verification.
6. Review the Flight Recorder, changed files, before/after diff, test output, safety panel, memory panel, and PR summary.
7. Keep the changes for normal manual Git review, or use **Revert this run** to restore the pre-run checkpoint.

Example task:

```text
Add a /status endpoint that returns {"status": "ready"} and add tests.
Update only main.py and tests/test_main.py. Do not modify skills/.
Make python -m pytest pass.
```

Code Pilot modifies the currently checked-out working tree. It does not create a commit, push a branch, or open a pull request.

### Memo Pilot walkthrough

1. Open `http://localhost:3000/memo-pilot`.
2. Add a company name and sector.
3. Upload one or more text-based PDFs and/or paste manual notes.
4. Review the extraction preview to confirm readable text and tables were recovered.
5. Select **Generate Memo**.
6. Review the evidence table, coverage indicators, memo sections, risks, assumptions, missing evidence, and diligence questions.
7. Export Markdown or use the print-ready PDF option, optionally including the evidence appendix.

Sample inputs are available under `demo-materials/MemoPilot-demo-materials`.

### Ops Pilot walkthrough

1. Open `http://localhost:3000/ops-pilot`.
2. Add a company name and workflow area.
3. Upload a workflow screenshot, supporting PDFs, and/or paste operating notes.
4. Review the OCR and PDF extraction preview before generation.
5. Select **Generate Ops Review**.
6. Review operational signals, bottlenecks, opportunities, priority ranking, recommended workflow, 30-day plan, metrics, risks, and open questions.
7. Export the copy-ready Markdown or print/PDF artifact.

Sample inputs are available under `demo-materials/OpsPilot-demo-materials`.

### Frontend routes

| Route | Page |
| --- | --- |
| `/` | Workbench overview |
| `/code-pilot` | Code Pilot |
| `/memo-pilot` | Memo Pilot |
| `/ops-pilot` | Ops Pilot |
| `/architecture` | Shared workflow pattern |

## API Reference

All endpoints are local by default at `http://127.0.0.1:8000`.

| Method | Endpoint | Description |
| --- | --- | --- |
| `GET` | `/health` | Backend health check. |
| `POST` | `/api/runs/start` | Start a synchronous Code Pilot run with JSON `repo_path` and `task`. |
| `GET` | `/api/runs/repo-status?repo_path=...` | Inspect the target repository working tree. |
| `GET` | `/api/runs/{run_id}` | Retrieve a saved Code Pilot run. |
| `POST` | `/api/runs/{run_id}/revert` | Restore the pre-run local checkpoint. |
| `POST` | `/api/review/file-diff` | Generate a concise explanation of one file's before/after contents. |
| `POST` | `/api/memo-pilot/extract` | Preview PDF and manual-note extraction. |
| `POST` | `/api/memo-pilot/generate` | Generate the full diligence artifact. |
| `POST` | `/api/ops-pilot/extract` | Preview image OCR, PDF extraction, and notes. |
| `POST` | `/api/ops-pilot/generate` | Generate the full operations review. |

Start a Code Pilot run from PowerShell:

```powershell
$body = @{
  repo_path = "D:\bropilot-demo"
  task = "Add a /status endpoint and tests. Update only main.py and tests/test_main.py."
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/api/runs/start `
  -ContentType "application/json" `
  -Body $body
```

The start endpoint is synchronous: the HTTP request remains open while the agent, tests, optional repair, and reviewer run. Code Pilot has a 20-minute agent timeout and pytest has a 10-minute timeout. A production deployment should move these runs to a background job system.

Memo and Ops endpoints accept `multipart/form-data`. Use `/docs` for an interactive request form and the exact generated OpenAPI schema.

## Local Data and Recovery

Code Pilot writes JSON data locally:

- `backend/data/runs/<run_id>.json` stores the completed run and review information;
- `backend/data/checkpoints/<run_id>.json` stores a base64-encoded pre-run file snapshot; and
- `backend/data/memory/<repo>-data.json` stores up to 12 lessons and metadata for up to 10 recent runs.

Checkpoints exclude `.git`, `.env`, virtual environments, dependency directories, caches, and build output. They are snapshots, not Git commits, and their base64 content is not encryption.

The revert endpoint restores checkpointed files and removes files created after the checkpoint when those files are within the checkpoint scanner's included scope. It leaves the run artifact in place for auditability. Review existing changes before running Code Pilot because a checkpoint captures the entire eligible working tree state, not only files later edited by the agent.

Memo Pilot and Ops Pilot return generated artifacts to the browser and do not currently have a backend database or run-history API.

## Safety and Privacy

BroPilot is built around review-first automation:

- no automatic commit, push, merge, investment decision, or production action;
- Code Pilot tools are scoped to the selected repository;
- agent instructions protect `.env`, `.venv`, `.git`, `.gitagent`, `workspace`, `skills/`, `node_modules`, and generated artifacts;
- path resolution prevents scoped agent tools from escaping the target repository;
- pytest is executed independently by the backend after edits;
- task-specified file scope and protected-path changes produce safety signals;
- changed files and relevant before/after content remain visible for review;
- Memo and Ops distinguish source evidence from assumptions and missing evidence;
- typed structured outputs and deterministic validation reject malformed or unsafe AI output; and
- local checkpoints provide a recovery path for Code Pilot.

Important privacy considerations:

- Content supplied to AI-backed stages is sent to the configured OpenAI API. Do not use sensitive source code, documents, screenshots, or notes unless your organization's policies allow it.
- Local run and checkpoint JSON may contain source code, diffs, task text, repository paths, or extracted information. Protect and clean `backend/data` appropriately.
- `.env` is excluded from Code Pilot checkpoints and is listed in `.gitignore`, but you remain responsible for secret handling.
- BroPilot is a prototype and does not include authentication, authorization, encryption at rest, tenant isolation, retention policies, or an audit-grade append-only store.

## Development and Validation

Run the frontend checks:

```powershell
cd D:\BroPilot\frontend
npm run lint
npm run build
```

Run a basic backend import and syntax check:

```powershell
cd D:\BroPilot\backend
.\.venv\Scripts\python.exe -m compileall app
.\.venv\Scripts\python.exe -c "from app.main import app; print(app.title)"
```

Run the target demo repository tests:

```powershell
cd D:\bropilot-demo
python -m pytest
```

When changing an API shape, update both the FastAPI route/service and the corresponding TypeScript types in the frontend. When changing local ports, update both the frontend API constants and backend CORS configuration.

## Troubleshooting

### The frontend says it cannot reach FastAPI

- Confirm Uvicorn is running from `D:\BroPilot\backend`.
- Open `http://127.0.0.1:8000/health` and confirm it returns `status: ok`.
- Keep the frontend at `http://localhost:3000`; the current CORS configuration does not include alternate origins such as `127.0.0.1:3000`.
- Confirm port 8000 is not already used by another process.

### `OPENAI_API_KEY is not set`

- Confirm the file is named exactly `backend\.env`, not `.env.txt`.
- Confirm it contains `OPENAI_API_KEY=...` without placeholder text.
- Restart Uvicorn after editing it.
- Never print or share the value while debugging.

### A configured model is rejected

Remove the optional model override to use the application default, or set it to a model available to your OpenAI project. Restart the backend after changing the environment.

### Code Pilot reports that the repository is missing or invalid

- Use an absolute path to an existing local directory.
- Confirm the directory contains a `.git` repository.
- Run `git status` in that directory and resolve any Git errors.

### Code Pilot tests fail

The target repository must have Python and pytest available to the backend process because verification always runs `python -m pytest`. Review the captured stdout/stderr. A failed run is expected to remain review-required even after the automatic repair attempt.

### The demo reset script removed changes

The script is intentionally destructive within the selected demo target repository. By default it hard-resets `D:\bropilot-demo`, cleans selected generated paths, resets to commit `d672866`, and recreates `demo-working`. Recover important work from a commit, another branch, backup, or reflog if available.

### Memo Pilot cannot read a PDF

- Confirm the file is under 8 MB and is actually a PDF.
- Text-based PDFs work best.
- Scanned documents require OCR before Memo Pilot can extract their text; Memo Pilot does not currently OCR PDF pages.
- Use the extraction preview and add manual notes for missing content.

### Ops Pilot image OCR is empty or unavailable

- Confirm Tesseract exists at `tools\Tesseract-OCR\tesseract.exe`.
- Run the executable with `--version`.
- Use a clear, high-contrast image.
- Continue with PDFs and manual notes if OCR is unavailable.

### A run is slow

Code Pilot performs agent execution, Git capture, pytest, a possible repair, and review in one request. Memo and Ops can run several sequential agent stages. Network latency, model choice, input size, and target test duration all affect completion time.

## Current Limitations

- This is a local, single-user prototype rather than a hosted multi-user service.
- The frontend backend URL and CORS origin are hard-coded for local development.
- Code Pilot runs synchronously and has no job queue, cancellation, progress streaming, or resumable execution.
- Code Pilot is optimized for the small Python/FastAPI demo and always verifies with `python -m pytest`.
- Repository context preloading currently favors a small known set of files.
- Checkpoints are full eligible-file snapshots stored as local JSON, which is not efficient for large repositories.
- Checkpoint restore is not a substitute for committing or backing up existing work.
- Memo Pilot works best with text-based PDFs and does not OCR scanned PDF pages.
- Ops Pilot image OCR depends on a local Windows Tesseract path.
- Memo and Ops exports are created in the browser; there is no server-side document archive.
- There is no user authentication, role-based access, database, telemetry dashboard, or production deployment configuration.
- Human review is required before using any generated artifact.

## Future Roadmap

The following are ideas for later development, not currently implemented features.

### GitHub integration

- Connect through a GitHub App or OAuth instead of requiring only a local path.
- Select repositories, branches, issues, and pull requests from the UI.
- Create a dedicated branch and draft pull request from an approved Code Pilot run.
- Post test results, safety findings, and the Flight Recorder summary as PR checks.
- Import issue acceptance criteria and link each generated change back to its issue.
- Respect protected branches, required checks, repository permissions, and CODEOWNERS.
- Require an explicit human confirmation before any remote branch or PR creation.

### Code Pilot expansion

- Configurable test commands for JavaScript, TypeScript, Go, Rust, and mixed-language repositories.
- Repository-aware context indexing instead of a fixed preload file list.
- User-defined protected paths, allowed commands, diff-size limits, and approval policies.
- Background jobs, live stage streaming, cancellation, retries, and resumable runs.
- Sandboxed execution using containers or disposable worktrees.
- Better support for monorepos, large diffs, binary files, and multiple workspaces.
- Configurable linters, type checkers, security scanners, and coverage gates.
- Run comparison and feedback-driven repository memory management.

### Memo and Ops expansion

- OCR for scanned PDF pages and richer chart/table extraction.
- Source citations that jump to a PDF page, table, note, or screenshot region.
- Editable drafts with reviewer comments, approvals, and version history.
- Server-side DOCX and PDF rendering with reusable organization templates.
- Batch document ingestion and saved projects.
- Connectors for Google Drive, SharePoint, Box, Notion, and email attachments.
- Additional domain templates for customer research, compliance review, and incident analysis.

### Platform and deployment

- Environment-configurable API URLs, CORS origins, storage locations, and OCR executable paths.
- Authentication, role-based authorization, organizations, and tenant isolation.
- Durable database and object storage with encryption and retention controls.
- Queue workers for long-running workflows and webhook/event support.
- Usage, latency, cost, failure, and model-quality observability.
- Automated backend tests, frontend component tests, and end-to-end browser tests.
- Docker Compose and documented cloud deployment profiles.
- Accessibility review, responsive polish, and cross-platform setup scripts.
- Policy administration, audit exports, and approval workflows.

## Additional Documentation

- [SETUP.md](SETUP.md) contains the shorter Windows installation checklist.
- [DEMO.md](DEMO.md) contains a reproducible Code Pilot demo and expected result.
- `frontend/v-DESIGN.md` and `frontend/l-DESIGN.md` contain visual and layout design notes.

## Project Status

BroPilot Workbench is an experimental prototype. Treat generated code, diligence conclusions, operations recommendations, tests, and safety signals as inputs to human review—not as final approval.
