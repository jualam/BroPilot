from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.services.memo_pilot_service import (
    extract_memo_pilot_preview,
    generate_memo_pilot_response_async,
)


router = APIRouter(prefix="/api/memo-pilot", tags=["memo-pilot"])

MAX_DOCUMENTS = 8
MAX_DOCUMENT_BYTES = 8 * 1024 * 1024


@router.post("/generate")
async def generate_memo(
    documents: Annotated[list[UploadFile] | None, File()] = None,
    manual_notes: Annotated[str, Form()] = "",
    company_name: Annotated[str, Form()] = "",
    sector: Annotated[str, Form()] = "",
):
    prepared_documents = await _prepare_documents(documents)

    if not prepared_documents and not manual_notes.strip():
        raise HTTPException(
            status_code=400,
            detail="Upload at least one text-based PDF or add manual notes.",
        )

    return await generate_memo_pilot_response_async(
        documents=prepared_documents,
        manual_notes=manual_notes,
        company_name=company_name,
        sector=sector,
    )


@router.post("/extract")
async def extract_memo(
    documents: Annotated[list[UploadFile] | None, File()] = None,
    manual_notes: Annotated[str, Form()] = "",
):
    prepared_documents = await _prepare_documents(documents)

    if not prepared_documents and not manual_notes.strip():
        raise HTTPException(
            status_code=400,
            detail="Upload at least one text-based PDF or add manual notes.",
        )

    return extract_memo_pilot_preview(
        documents=prepared_documents,
        manual_notes=manual_notes,
    )


async def _prepare_documents(documents: list[UploadFile] | None) -> list[dict]:
    documents = documents or []
    if len(documents) > MAX_DOCUMENTS:
        raise HTTPException(
            status_code=400,
            detail=f"Upload at most {MAX_DOCUMENTS} PDFs for a single memo run.",
        )

    prepared_documents = []
    for document in documents:
        if document.content_type not in {"application/pdf", "application/octet-stream"}:
            raise HTTPException(
                status_code=400,
                detail=f"{document.filename} is not a PDF upload.",
            )

        content = await document.read()
        if len(content) > MAX_DOCUMENT_BYTES:
            raise HTTPException(
                status_code=400,
                detail=f"{document.filename} exceeds the 8 MB demo limit.",
            )

        prepared_documents.append(
            {
                "filename": document.filename or "uploaded.pdf",
                "content": content,
            }
        )

    return prepared_documents
