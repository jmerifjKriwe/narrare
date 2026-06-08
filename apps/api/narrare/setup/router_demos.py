"""Demo discovery routes — ONBOARD-001."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends

from narrare._app.database import get_async_session
from narrare.setup.demo_loader import DemoLoader
from narrare.setup.schemas import DemoListResponse

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(tags=["setup"])


def _get_demo_loader(
    session: AsyncSession = Depends(get_async_session),
) -> DemoLoader:
    return DemoLoader(session)


@router.get("/demos", response_model=DemoListResponse)
async def list_demos(
    demo_loader: DemoLoader = Depends(_get_demo_loader),
) -> DemoListResponse:
    """List all available demo projects with metadata.

    No auth required — demo discovery is needed before login during setup.
    """
    demos = demo_loader.all_demo_info()
    return DemoListResponse(demos=demos)
