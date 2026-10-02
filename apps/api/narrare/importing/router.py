"""Import routes — thin, delegates immediately (RULE-06)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile

from narrare._app.dependencies import CurrentUserIdDep, get_current_user_id
from narrare.importing.contracts import ImportPreviewerProtocol, ImportServiceProtocol
from narrare.importing.dependencies import get_commit_adjustments, get_import_service
from narrare.importing.schemas import (
    ImportCommitAdjustments,
    ImportCommitResponse,
    ImportPreviewResponse,
)

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


@router.post("/commit", response_model=ImportCommitResponse)
async def commit_import(
    user_id: CurrentUserIdDep,
    adjustments: Annotated[ImportCommitAdjustments, Depends(get_commit_adjustments)],
    service: ImportServiceProtocol = Depends(get_import_service),
    files: list[UploadFile] = File(...),
    novel_id: uuid.UUID = Form(...),
) -> ImportCommitResponse:
    """Re-parse files and append chapters atomically (ADR-091 contract)."""
    return await service.commit(files, novel_id, uuid.UUID(user_id), adjustments)
