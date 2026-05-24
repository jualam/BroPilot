import os

import requests
from fastapi import APIRouter, HTTPException

from app.schemas.review import FileDiffReviewRequest, FileDiffReviewResponse


router = APIRouter(prefix="/api/review", tags=["review"])

OPENAI_API_URL = "https://api.openai.com/v1/responses"
DEFAULT_REVIEW_MODEL = "gpt-4o-mini"
REVIEW_MODEL_ENV = "BROPILOT_REVIEW_MODEL"
MAX_CONTEXT_CHARS = 12000


@router.post("/file-diff", response_model=FileDiffReviewResponse)
def review_file_diff(payload: FileDiffReviewRequest):
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=400,
            detail="OPENAI_API_KEY is not set in the backend environment.",
        )

    model = os.environ.get(REVIEW_MODEL_ENV, DEFAULT_REVIEW_MODEL).strip()
    prompt = _build_prompt(payload)

    try:
        response = requests.post(
            OPENAI_API_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "input": prompt,
                "max_output_tokens": 220,
            },
            timeout=45,
        )
    except requests.RequestException as error:
        raise HTTPException(
            status_code=502,
            detail=f"Review assistant request failed: {error}",
        ) from error

    if response.status_code >= 400:
        raise HTTPException(
            status_code=502,
            detail=f"Review assistant returned HTTP {response.status_code}: {_compact(response.text, 500)}",
        )

    summary = _extract_summary(response.json())
    if not summary:
        raise HTTPException(
            status_code=502,
            detail="Review assistant returned an empty summary.",
        )

    return FileDiffReviewResponse(summary=summary, model=model)


def _build_prompt(payload: FileDiffReviewRequest) -> str:
    return "\n\n".join(
        [
            "You are BroPilot's Review Assistant.",
            (
                "Explain this single-file code diff for a human reviewer. "
                "Be concise. Use 2 short bullets: 'What changed' and "
                "'Why it matters'. Do not mention unrelated files."
            ),
            f"Task:\n{payload.task.strip() or 'Not provided.'}",
            f"File:\n{payload.path}",
            f"Before HEAD:\n{_compact(payload.before_contents, MAX_CONTEXT_CHARS)}",
            f"After working tree:\n{_compact(payload.after_contents, MAX_CONTEXT_CHARS)}",
        ]
    )


def _extract_summary(payload: dict) -> str:
    output_text = payload.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    parts = []
    for item in payload.get("output", []):
        for content in item.get("content", []):
            text = content.get("text")
            if isinstance(text, str) and text.strip():
                parts.append(text.strip())

    return "\n".join(parts).strip()


def _compact(value: str, limit: int) -> str:
    cleaned = value.strip()
    if len(cleaned) <= limit:
        return cleaned

    return f"{cleaned[: limit - 3]}..."
