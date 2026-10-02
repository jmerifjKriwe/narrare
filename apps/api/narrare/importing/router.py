"""Import routes — thin, delegates immediately (RULE-06)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile

from narrare._app.dependencies import get_current_user_id
from narrare.importing.contracts import ImportPreviewerProtocol
from narrare.importing.dependencies import get_import_service
from narrare.importing.schemas import ImportPreviewResponse

router = APIRouter(prefix="/import", tags=["import"])


@router.post(
    "/preview",
    response_model=ImportPreviewResponse,
    dependencies=[Depends(get_current_user_id)],
)
async def preview_import(
    files: list[UploadFile] = File(...),
    service: ImportPreviewerProtocol = Depends(get_import_service),
) -> ImportPreviewResponse:
    """Parse uploaded manuscript files — preview only, no DB writes."""
    return await service.preview(files)
