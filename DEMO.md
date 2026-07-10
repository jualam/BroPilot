# BroPilot Demo Guide

This guide reproduces the local BroPilot Workbench Code Pilot demo.

The demo uses two repositories:

- **BroPilot app repo**: [jualam/BroPilot](https://github.com/jualam/BroPilot.git), containing the Next.js dashboard and FastAPI backend.
- **Demo target repo**: [jualam/broPilot-demo](https://github.com/jualam/broPilot-demo.git), a small FastAPI app that Code Pilot edits during the demo.

## What This Demo Shows

Code Pilot turns a local repo path and engineering task into a reviewable code change. It uses the OpenAI Agents SDK with scoped read/write tools, records each stage in a Flight Recorder, runs `python -m pytest` independently, captures changed files and diffs, updates repo memory, and produces a copy-ready PR summary.

## Reset The Demo Repo

Clone or place the BroPilot app repo at:

```powershell
D:\BroPilot
```

The demo target repo is expected at:

```powershell
D:\bropilot-demo
```

Reset it to the known baseline and recreate the disposable demo branch:

```powershell
cd D:\BroPilot
powershell -ExecutionPolicy Bypass -File .\scripts\reset-demo.ps1
```

Code Pilot edits whichever branch is currently checked out in `D:\bropilot-demo`, so the reset script switches the repo to `demo-working`.

## Run BroPilot Locally

Start the backend:

```powershell
cd D:\BroPilot\backend
uvicorn app.main:app --reload
```

Start the frontend:

```powershell
cd D:\BroPilot\frontend
npm run dev
```

Open the frontend and go to:

```text
http://localhost:3000/code-pilot
```

Keep the repo path as:

```text
D:\bropilot-demo
```

## Demo Task

Paste this task:

```text
Add a /status endpoint that returns {"status": "ready"} and add tests. Update only main.py and tests/test_main.py. Do not modify skills/. Make python -m pytest pass.
```

## Expected Result

The successful demo run should show:

- Status: `completed`
- Changed files: `main.py` and `tests/test_main.py`
- Tests: `python -m pytest passed`
- Safety signal: `low`
- Copy-ready PR markdown generated
- No automatic commit, push, or merge

## Demo Highlights

- The Flight Recorder shows Analyzer, Planner, Coder, Tester, and Reviewer stages.
- The backend runs `python -m pytest` independently after Code Pilot edits files.
- The Changed Files panel opens a side-by-side diff.
- The Safety Panel flags protected-path and unexpected-file behavior.
- The Memory Panel shows repo-specific lessons loaded into the prompt and new lessons learned after verification.
- The PR Summary is ready for human review, but BroPilot does not auto-merge or push.

## Optional Failure And Repair Flow

BroPilot is designed to make failures visible. If a Code Pilot run produces a broken patch, BroPilot still captures the changed files, shows the pytest failure, and keeps the result review-required.

When pytest fails, the backend can run a focused repair attempt using the failure output. The safety story stays the same: BroPilot helps agents prepare code, but it does not pretend a failing or risky change is ready.
