"""Unit tests for WritingService.validate_request_access.

Extracted from test_writing_service.py to keep file size under RULE-04 limit.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from narrare.writing.models import GenerationRequest
from narrare_core.shared.errors import NotFoundError

if TYPE_CHECKING:
    from narrare.writing.service import WritingService

# Fixtures (service, mock_repo, etc.) are discovered by pytest from
# conftest.py — no explicit import needed.


class TestValidateRequestAccess:
    async def test_validate_request_access_raises_not_found_for_missing(
        self,
        service: WritingService,
        mock_repo: AsyncMock,
    ) -> None:
        """validate_request_access() raises NotFoundError when request missing.

        Regression test: the SSE stream endpoint must validate before returning
        StreamingResponse, otherwise NotFoundError fires after headers are sent.
        """
        mock_repo.get_by_id.return_value = None
        request_id = uuid4()
        user_id = str(uuid4())

        with pytest.raises(NotFoundError):
            await service.validate_request_access(request_id, user_id)

    async def test_validate_request_access_raises_not_found_for_wrong_user(
        self,
        service: WritingService,
        mock_repo: AsyncMock,
    ) -> None:
        """validate_request_access() raises NotFoundError for wrong user."""
        mock_model = MagicMock(spec=GenerationRequest)
        mock_model.user_id = uuid4()  # Different from caller
        mock_repo.get_by_id.return_value = mock_model

        with pytest.raises(NotFoundError):
            await service.validate_request_access(uuid4(), str(uuid4()))

    async def test_validate_request_access_succeeds_for_valid(
        self,
        service: WritingService,
        mock_repo: AsyncMock,
    ) -> None:
        """validate_request_access() returns None for valid access."""
        user_id = uuid4()
        mock_model = MagicMock(spec=GenerationRequest)
        mock_model.user_id = user_id
        mock_repo.get_by_id.return_value = mock_model

        # Should not raise
        await service.validate_request_access(uuid4(), str(user_id))
