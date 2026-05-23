import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.schemas.run import StartRunRequest

router = APIRouter(prefix="/api/runs", tags=["runs"])

DATA_DIR = Path("data/runs")


@router.post("/start")
def start_run(payload: StartRunRequest):
    run_id = str(uuid.uuid4())[:8]
    now = datetime.now(timezone.utc).isoformat()

    run_data = {
        "run_id": run_id,
        "status": "completed",
        "repo_path": payload.repo_path,
        "task": payload.task,
        "started_at": now,
        "completed_at": now,
        "agents": [
            {
                "name": "Analyzer Agent",
                "status": "completed",
                "summary": "Scanned the repository and identified the FastAPI app structure.",
                "details": "Found main.py, auth.py, and tests/."
            },
            {
                "name": "Planner Agent",
                "status": "completed",
                "summary": "Created a step-by-step implementation plan.",
                "details": "Planned middleware changes, test coverage, and validation."
            },
            {
                "name": "Coder Agent",
                "status": "completed",
                "summary": "Modified application code and added tests.",
                "details": "Changed main.py and created tests/test_request_logging.py."
            },
            {
                "name": "Tester Agent",
                "status": "completed",
                "summary": "Ran the test suite and verified the implementation.",
                "details": "pytest completed successfully."
            },
            {
                "name": "Reviewer Agent",
                "status": "completed",
                "summary": "Reviewed the code for safety and maintainability.",
                "details": "Risk level is low. Human review recommended before merge."
            }
        ],
        "changed_files": [
            {
                "path": "main.py",
                "change_type": "modified",
                "summary": "Added request logging middleware."
            },
            {
                "path": "tests/test_request_logging.py",
                "change_type": "created",
                "summary": "Added tests for request logging behavior."
            }
        ],
        "tests": {
            "command": "pytest",
            "status": "passed",
            "summary": "8 passed in 1.42s"
        },
        "safety": {
            "risk_score": "low",
            "blocked_actions": [
                {
                    "command": "cat .env",
                    "reason": "Blocked access to sensitive environment file."
                }
            ]
        },
        "memory": {
            "before": ["No repo-specific memory found."],
            "learned": [
                "This repo uses pytest for backend tests.",
                "Application entrypoint is main.py.",
                "Always run pytest before finalizing changes."
            ],
            "used": []
        },
        "pr_summary": {
            "title": "Add request logging middleware",
            "body": [
                "Added FastAPI request logging middleware.",
                "Added tests for request logging behavior.",
                "Verified changes with pytest."
            ]
        }
    }

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    file_path = DATA_DIR / f"{run_id}.json"
    file_path.write_text(json.dumps(run_data, indent=2), encoding="utf-8")

    return run_data


@router.get("/{run_id}")
def get_run(run_id: str):
    file_path = DATA_DIR / f"{run_id}.json"

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Run not found")

    return json.loads(file_path.read_text(encoding="utf-8"))