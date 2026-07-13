# BroPilot Workbench

Review-ready AI workflows for high-trust automation.

BroPilot Workbench is a local-first prototype for turning ambiguous work into structured, verified, human-reviewable outputs. It demonstrates one reusable workflow pattern across code changes, diligence memo drafting, and operations improvement planning:

```text
Context Intake -> Scoped Plan -> Constrained Agent -> Independent Verification -> Flight Recorder -> Human Review
```

The system is intentionally conservative. It does not auto-merge, auto-push, make investment decisions, or take final operating action. Each workflow prepares an artifact for a human reviewer.

## Workflows

### Code Pilot

Code Pilot turns an engineering task into a review-ready code change.

It works against a local target repo, runs constrained OpenAI Agents SDK execution, captures changed files and diffs, runs independent tests, records safety signals, updates repo memory, and produces PR-ready review notes.

The demo target repo is separate from this app:

```text
https://github.com/jualam/broPilot-demo
```

The local demo repo is expected at:

```text
D:\bropilot-demo
```

The reset script restores the demo repo to baseline commit `d672866` and creates a fresh local `demo-working` branch:

```powershell
cd D:\BroPilot
powershell -ExecutionPolicy Bypass -File .\scripts\reset-demo.ps1
```

### Memo Pilot

Memo Pilot turns company PDFs and manual notes into a review-ready diligence memo draft.

It supports multiple text-based PDFs, table-aware PDF extraction, manual notes, evidence cards, evidence coverage, risk review, missing-evidence checks, diligence questions, copy-ready markdown, and PDF-ready export.

Memo Pilot is designed as a human-review workflow. It separates facts, assumptions, risks, missing evidence, and reviewer notes instead of making an investment decision.

### Ops Pilot

Ops Pilot turns operating notes, PDFs, and screenshots into a review-ready operations improvement plan.

It combines deterministic OCR/PDF parsing and signal extraction with typed AI agents for bottleneck analysis, automation planning, prioritization, and risk review. Outputs include operational signals, bottlenecks, automation opportunities, priority ranking, a recommended first workflow, a 30-day plan, metrics, risks, questions, and export-ready artifacts.

Ops Pilot is designed to identify candidate workflows for human review, not to guarantee ROI or automatically implement changes.

## Architecture

```text
Next.js Frontend
  |
  v
FastAPI Backend
  |
  |-- Code Pilot
  |   |-- repo context loading
  |   |-- scoped OpenAI Agents SDK code execution
  |   |-- pytest verification
  |   |-- git diff and checkpoint capture
  |   `-- PR summary and safety review
  |
  |-- Memo Pilot
  |   |-- PDF text/table extraction
  |   |-- evidence construction
  |   |-- AI-assisted memo planning and drafting
  |   |-- risk and missing-evidence review
  |   `-- markdown/PDF-ready export
  |
  `-- Ops Pilot
      |-- image OCR and PDF extraction
      |-- deterministic signal extraction
      |-- typed AI agents for analysis and planning
      |-- guardrail validation
      `-- markdown/PDF-ready export
```

## Flight Recorder Pattern

Each workflow exposes its process through a Flight Recorder rather than a black-box answer.

Code Pilot stages:

```text
Analyzer -> Planner -> Coder -> Tester -> Reviewer
```

Memo Pilot stages:

```text
Document Intake -> Text Extraction -> Evidence Extraction -> Memo Planner -> Draft Generator -> Risk Checker -> Evidence Gap Review -> Human Review Artifact
```

Ops Pilot stages:

```text
Ops Intake -> OCR / Text Extraction -> Signal Extraction -> Bottleneck Analyst Agent -> Automation Planner Agent -> Prioritization Agent -> Risk & Guardrail Review -> Human Review Artifact
```

## Safety Model

BroPilot Workbench is built around review-first automation:

- no automatic merge
- no automatic push
- no automatic production action
- protected paths for secrets, virtual environments, generated artifacts, and git metadata
- constrained Code Pilot file tools
- independent backend verification after Code Pilot edits
- typed structured outputs for Ops Pilot agents
- source-backed evidence and missing-evidence review for Memo Pilot
- local checkpoints for Code Pilot recovery
- human review required before merge, investment use, or operating action

## Project Structure

```text
BroPilot/
|-- backend/
|   |-- app/
|   |   |-- routes/              # FastAPI route modules
|   |   |-- schemas/             # API schemas
|   |   `-- services/            # workflow orchestration and agent services
|   `-- data/                    # local run, memory, and checkpoint data
|-- frontend/
|   |-- public/                  # logo and static assets
|   `-- src/app/                 # Next.js routes
|-- scripts/
|   `-- reset-demo.ps1           # reset local broPilot-demo repo
|-- DEMO.md                      # Code Pilot demo guide
|-- SETUP.md                     # local setup instructions
`-- README.md
```

## Local Setup

See [SETUP.md](SETUP.md).

Short version:

```powershell
cd D:\BroPilot\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

```powershell
cd D:\BroPilot\frontend
npm install
npm run dev
```

Open:

```text
http://localhost:3000
```

## Routes

- `/` - BroPilot Workbench home
- `/code-pilot` - Code Pilot
- `/memo-pilot` - Memo Pilot
- `/ops-pilot` - Ops Pilot
- `/architecture` - Workflow Pattern

## Documentation

- [SETUP.md](SETUP.md) - local installation and OCR setup
- [DEMO.md](DEMO.md) - reproducible Code Pilot demo flow

## Current Limitations

- The system is a local prototype, not a hosted multi-user product.
- Code Pilot is optimized for the small FastAPI demo repo and Python test workflows.
- Memo Pilot works best with text-based PDFs; scanned PDFs may need separate OCR.
- Ops Pilot image OCR requires local Tesseract setup.
- Human review is required before using any generated artifact.

