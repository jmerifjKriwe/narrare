"""Import service FastAPI factories (RULE-19: SessionDep, never bare AsyncSession)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare._app.dependencies import SessionDep  # noqa: TC001 - needed at runtime for FastAPI DI
from narrare.importing.contracts import build_import_service

if TYPE_CHECKING:
    from narrare.importing.contracts import ImportPreviewerProtocol


def get_import_service(
    session: SessionDep,
) -> ImportPreviewerProtocol:
    return build_import_service(session)
