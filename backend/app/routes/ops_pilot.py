from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.services.ops_pilot_service import (
    extract_ops_inputs_preview,
    generate_ops_pilot_response_async,
)


router = APIRouter(prefix="/api/ops-pilot", tags=["ops-pilot"])

MAX_IMAGES = 1
MAX_PDFS = 4
MAX_UPLOAD_BYTES = 8 * 1024 * 1024
IMAGE_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp", "image/bmp"}
PDF_TYPES = {"application/pdf", "application/octet-stream"}


@router.post("/generate")
async def generate_ops_review(
    image: Annotated[UploadFile | None, File()] = None,
    pdfs: Annotated[list[UploadFile] | None, File()] = None,
    manual_notes: Annotated[str, Form()] = "",
    company_name: Annotated[str, Form()] = "",
    workflow_area: Annotated[str, Form()] = "",
):
    prepared_image = await _prepare_image(image)
    prepared_pdfs = await _prepare_pdfs(pdfs)

    if not prepared_image and not prepared_pdfs and not manual_notes.strip():
        raise HTTPException(
            status_code=400,
            detail="Add manual notes or upload an image/PDF before generating Ops Pilot.",
        )

    try:
        return await generate_ops_pilot_response_async(
            company_name=company_name,
            workflow_area=workflow_area,
            manual_notes=manual_notes,
            image=prepared_image,
            pdfs=prepared_pdfs,
        )
    except RuntimeError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error


@router.post("/extract")
async def extract_ops_inputs(
    image: Annotated[UploadFile | None, File()] = None,
    pdfs: Annotated[list[UploadFile] | None, File()] = None,
    manual_notes: Annotated[str, Form()] = "",
):
    prepared_image = await _prepare_image(image)
    prepared_pdfs = await _prepare_pdfs(pdfs)

    if not prepared_image and not prepared_pdfs and not manual_notes.strip():
        raise HTTPException(
            status_code=400,
            detail="Add manual notes or upload an image/PDF before extracting Ops Pilot inputs.",
        )

    try:
        return extract_ops_inputs_preview(
            manual_notes=manual_notes,
            image=prepared_image,
            pdfs=prepared_pdfs,
        )
    except RuntimeError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error


async def _prepare_image(image: UploadFile | None) -> dict | None:
    if not image:
        return None
    if image.content_type not in IMAGE_TYPES:
        raise HTTPException(status_code=400, detail=f"{image.filename} is not a supported image upload.")
    content = await image.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail=f"{image.filename} exceeds the 8 MB demo limit.")
    return {"filename": image.filename or "uploaded-image", "content": content}


async def _prepare_pdfs(pdfs: list[UploadFile] | None) -> list[dict]:
    pdfs = pdfs or []
    if len(pdfs) > MAX_PDFS:
        raise HTTPException(status_code=400, detail=f"Upload at most {MAX_PDFS} PDFs for a single Ops Pilot run.")

    prepared = []
    for pdf in pdfs:
        if pdf.content_type not in PDF_TYPES:
            raise HTTPException(status_code=400, detail=f"{pdf.filename} is not a PDF upload.")
        content = await pdf.read()
        if len(content) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=400, detail=f"{pdf.filename} exceeds the 8 MB demo limit.")
        prepared.append({"filename": pdf.filename or "uploaded.pdf", "content": content})
    return prepared
