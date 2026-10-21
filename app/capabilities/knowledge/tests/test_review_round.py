"""Review-round regressions: upload ceiling and the setup guard."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.api.main import app
from app.kernel.db.session import Session

pytestmark = pytest.mark.timeout(60)

MAX_UPLOAD_BYTES = 1_000_000


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _remove_users() -> None:
    async with Session() as session:
        await session.execute(text("DELETE FROM users"))
        await session.commit()


async def test_an_oversized_upload_is_rejected() -> None:
    big = "x" * (MAX_UPLOAD_BYTES + 1)
    async with _client() as client:
        response = await client.post(
            "/api/knowledge/documents",
            files={"file": ("riesig.txt", big.encode("utf-8"), "text/plain")},
        )
        assert response.status_code == 413
        assert response.json()["detail"] == "document too large"


async def test_a_document_cannot_be_ingested_before_setup() -> None:
    await _remove_users()
    async with _client() as client:
        response = await client.post(
            "/api/knowledge/documents",
            files={"file": ("notizen.txt", b"Ein Satz.", "text/plain")},
        )
        assert response.status_code == 409
        assert response.json()["detail"] == "setup required"
