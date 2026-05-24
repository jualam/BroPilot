# BroPilot Demo Guide

This guide reproduces the demo flow used for the GitAgent/Gitclaw hiring challenge submission.

## What This Demo Shows

BroPilot turns a local repo path and engineering task into a reviewable code change. It uses the Gitclaw SDK with the CLI tool disabled, records each agent step in a Flight Recorder, runs `python -m pytest` independently, captures changed files and diffs, updates repo memory, and produces a copy-ready PR summary.

## Reset The Demo Repo

The demo target repo is expected at:

```powershell
D:\bropilot-demo
```

Reset it to the known baseline and recreate the disposable demo branch:

```powershell
cd D:\Applications\BroPilot
powershell -ExecutionPolicy Bypass -File .\scripts\reset-demo.ps1
```

Expected reset result:

```text
Demo repo is ready on branch demo-working at baseline d672866
5 passed
```

BroPilot edits whichever branch is currently checked out in `D:\bropilot-demo`, so the reset script switches the repo to `demo-working`.

## Run BroPilot Locally

Start the backend:

```powershell
cd D:\Applications\BroPilot\backend
uvicorn app.main:app --reload
```

Start the frontend:

```powershell
cd D:\Applications\BroPilot\frontend
npm run dev
```

Open the frontend in the browser and keep the repo path as:

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

The demo run makes these product decisions visible:

- Gitclaw runs through the SDK with the `cli` tool disabled for Windows-compatible local runs.
- The Flight Recorder shows the Analyzer, Planner, Coder, Tester, and Reviewer steps.
- The backend runs `python -m pytest` independently after Gitclaw finishes.
- The Changed Files panel shows additions/deletions and opens a side-by-side diff.
- The Safety Panel flags review-sensitive behavior, including unexpected files if Gitclaw edits outside the task boundary.
- The Memory Panel shows repo-specific lessons loaded into the prompt and new lessons learned after verification.
- The PR Summary is ready for human review, but BroPilot does not auto-merge or push.

## Optional Failure And Repair Flow

BroPilot is designed to make failures visible. If a Gitclaw run produces a broken patch, BroPilot still captures the changed files, shows the pytest failure, and keeps the result review-required.

A follow-up repair task can then use the captured failure context to produce a passing patch. This is the intended safety story: BroPilot helps agents ship code, but it does not pretend a failing or risky change is ready.
