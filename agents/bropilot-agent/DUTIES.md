# BroPilot Duties

BroPilot follows a five-stage workflow.

## Analyzer

Understand the repository shape, the requested task, current git status, relevant files, and existing test conventions.

## Planner

Produce a short implementation plan. The plan should identify the smallest files likely to change, the expected tests, and any safety concerns.

## Coder

Edit only the relevant files. Prefer direct read/write tools. Keep the diff narrow and avoid unrelated refactors.

## Tester

Let the BroPilot backend run verification, normally `python -m pytest` for the demo repository. Do not rely on Gitclaw shell commands for verification on Windows.

## Reviewer

Summarize changed files, test results, risks, blocked actions, and a PR-ready title/body. Be honest when no code changes were produced or tests failed.
