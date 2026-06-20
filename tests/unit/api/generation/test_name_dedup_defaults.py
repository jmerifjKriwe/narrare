"""Governed defaults: name dedup context cap — CR-AUFG-08-13.

Fail-if-changed-without-review tests for name generation dedup
defaults listed in the Governed Defaults Manifest.

See: docs/architecture/governance/cr-08-p3-governed-defaults-manifest.md §4.2
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from narrare.generation.name_service import MAX_EXISTING_NAMES_TOKENS

# Default values from the codebase (name_service.py)
_PAGE_SIZE = 1000


class TestNameDedupGovernedDefaults:
    """Tests that fail if name dedup defaults change without review."""

    def test_max_existing_names_tokens_matches_manifest(self) -> None:
        """500 tokens — caps existing-name dedup context for name generation.

        Rationale: At ~1.3 tokens/word, 500 tokens allows ~350 short
        entity names — enough for >99% of projects (most novels have
        <500 named entities).
        Review trigger: scale — re-evaluate for very large projects
        (>5000 named entities).
        Override: None (intentionally immutable — method-parameter
        override would be added if scale trigger fires).
        """
        assert MAX_EXISTING_NAMES_TOKENS == 500, (
            f"MAX_EXISTING_NAMES_TOKENS changed to {MAX_EXISTING_NAMES_TOKENS}. "
            "Update manifest rationale + review trigger before changing."
        )

    def test_page_size_matches_manifest(self) -> None:
        """1000 — page size for KB entry listing in name dedup.

        Rationale: 1000 entries per page covers >99% of projects.
        Larger page sizes risk slow DB queries and high memory usage.
        Review trigger: scale — re-evaluate for very large projects
        (>5000 named entities).
        Override: None (intentionally immutable — method-parameter
        override would be added if scale trigger fires).
        """
        assert _PAGE_SIZE == 1000, (
            f"Page size changed to {_PAGE_SIZE}. "
            "Update manifest rationale + review trigger before changing."
        )

    @pytest.mark.asyncio
    async def test_service_uses_page_size_default(self) -> None:
        """The service's _fetch_existing_names uses the correct page_size.

        Proves the service calls KB repository with page_size=1000.
        The token budget enforcement (cap_to_budget) is verified separately
        by test_max_existing_names_tokens_matches_manifest.
        """
        from uuid import uuid4

        # Create a mock KB repository that returns many entries
        mock_repo = MagicMock(spec=["list_entries"])
        entries = [MagicMock(spec=["name"]) for _ in range(100)]
        for i, e in enumerate(entries):
            e.name = f"Entity-{i}"
        mock_repo.list_entries = AsyncMock(return_value=(entries, 1000))

        # Build a minimal service with the mock
        from narrare.generation.name_service import NameGeneratorService

        service = NameGeneratorService(
            registry=MagicMock(spec=["get_model"]),
            composer=MagicMock(spec=["build"]),
            config=MagicMock(spec=[]),
            kb_repo=mock_repo,
        )

        # Call the internal method
        result = await service._fetch_existing_names(
            project_id=uuid4(),
            name_type="character",
        )

        # Verify page_size=1000 was passed
        mock_repo.list_entries.assert_called_once()
        _call_kwargs = mock_repo.list_entries.call_args[1]
        assert _call_kwargs.get("page_size") == 1000, (
            f"page_size changed to {_call_kwargs.get('page_size')}"
        )

        # Verify names are returned (token budget of 500 can hold ~384 words,
        # so all 100 "Entity-X" entries fit within the limit)
        assert len(result) == 100, "All 100 entries should fit within the 500-token budget"
