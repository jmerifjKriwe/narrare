"""E03: POST /analysis/sentiment answers 503 NLP_NOT_CONFIGURED (spec §8).

Pinned via dependency override (deterministic in every environment — the
real provider's absence cannot be staged in-process in CI, which installs
the models).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from narrare.analysis.dependencies import get_sentiment_service
from narrare.analysis.services.sentiment_service import ChapterSentimentService
from narrare_core.shared.errors import NLPProviderError

if TYPE_CHECKING:
    from fastapi import FastAPI
    from httpx import AsyncClient


class TestSentimentNlpDegradation:
    @pytest.mark.asyncio
    async def test_nlp_provider_error_answers_503_with_code(
        self,
        app: FastAPI,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        service = MagicMock(spec=ChapterSentimentService)
        service.analyze_chapters = AsyncMock(side_effect=NLPProviderError("NLP not configured."))

        app.dependency_overrides[get_sentiment_service] = lambda: service
        try:
            resp = await client.post(
                "/api/v1/analysis/sentiment",
                params={"novel_id": str(uuid4())},
                json={"chapter_ids": [str(uuid4())]},
                headers=auth_headers,
            )
        finally:
            # The app fixture is session-scoped — an override left behind
            # leaks into subsequent tests (order-dependent flakiness under
            # pytest-randomly). Same cleanup convention as
            # tests/integration/analysis/test_readability_api.py.
            app.dependency_overrides.pop(get_sentiment_service, None)

        assert resp.status_code == 503, resp.text[:300]
        assert resp.json()["code"] == "NLP_NOT_CONFIGURED"
