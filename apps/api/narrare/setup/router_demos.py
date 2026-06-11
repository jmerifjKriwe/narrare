"""Demo discovery routes — ONBOARD-001."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from narrare._app.dependencies import SessionDep
from narrare.setup.demo_loader import DemoLoader
from narrare.setup.schemas import DemoListResponse

router = APIRouter(tags=["setup"])


def _get_demo_loader(
    session: SessionDep,
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
