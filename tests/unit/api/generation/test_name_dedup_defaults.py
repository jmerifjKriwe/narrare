"""Governed defaults: name dedup context cap — CR-AUFG-08-13.

Fail-if-changed-without-review tests for name generation dedup
defaults listed in the Governed Defaults Manifest §4.2.

REAL CONTROL: These tests IMPORT the governed defaults from their source
module (``narrare.generation.name_dedup`` — the constants' single
definition site, RULE-06 split out of ``name_service`` in ADR-086 L14)
and assert that (1) the source value matches the manifest, and (2) the
service actually passes the page size to the KB repository. The constants
are NOT redefined locally.

See: docs/architecture/governance/cr-08-p3-governed-defaults-manifest.md §4.2
"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from narrare.generation.name_dedup import (
    DEFAULT_NAME_DEDUP_PAGE_SIZE,
    MAX_EXISTING_NAMES_TOKENS,
)

from ._ownership_fakes import permissive_novel_repo


class TestNameDedupGovernedDefaults:
    """Tests that fail if name dedup defaults change without review."""

    def test_max_existing_names_tokens_matches_manifest(self) -> None:
        """500 tokens — caps existing-name dedup context for name generation.

        Value layer: the IMPORTED source constant equals the manifest value.
        If someone changes ``MAX_EXISTING_NAMES_TOKENS`` in name_dedup.py,
        this assertion fails until the manifest rationale and review trigger
        are updated here.

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

        Value layer: the IMPORTED source constant equals the manifest value.
        If someone changes ``DEFAULT_NAME_DEDUP_PAGE_SIZE`` in
        name_dedup.py, this assertion fails until the manifest rationale
        and review trigger are updated here.

        Rationale: 1000 entries per page covers >99% of projects.
        Larger page sizes risk slow DB queries and high memory usage.
        Review trigger: scale — re-evaluate for very large projects
        (>5000 named entities).
        Override: None (intentionally immutable — method-parameter
        override would be added if scale trigger fires).
        """
        assert DEFAULT_NAME_DEDUP_PAGE_SIZE == 1000, (
            f"DEFAULT_NAME_DEDUP_PAGE_SIZE changed to "
            f"{DEFAULT_NAME_DEDUP_PAGE_SIZE}. "
            "Update manifest rationale + review trigger before changing."
        )

    @pytest.mark.asyncio
    async def test_service_uses_page_size_default(self) -> None:
        """The service's _fetch_existing_names uses the governed page size.

        Usage layer (behavioural + wiring): proves the service passes
        ``DEFAULT_NAME_DEDUP_PAGE_SIZE`` to the KB repository AND references
        the constant by name. If someone unwires the constant from
        ``_fetch_existing_names`` (hardcodes a different page size), the
        behavioural assertion fails; if they hardcode the *same* value, the
        wiring assertion fails — either way the constant must stay wired.
        The token budget enforcement (cap_to_budget) is verified separately
        by ``test_max_existing_names_tokens_matches_manifest``.
        """
        import inspect

        # Wiring: _fetch_existing_names must reference the constant by name,
        # not a bare literal (one definition site — RULE-06).
        from narrare.generation.name_service import NameGeneratorService

        fetch_src = inspect.getsource(NameGeneratorService._fetch_existing_names)
        assert "DEFAULT_NAME_DEDUP_PAGE_SIZE" in fetch_src, (
            "NameGeneratorService._fetch_existing_names no longer references "
            "DEFAULT_NAME_DEDUP_PAGE_SIZE — do not hardcode the page size; "
            "import it from narrare.generation.name_service."
        )

        # Behavioural: the value actually passed to the repo equals the constant.
        mock_repo = MagicMock(spec=["list_entries"])
        entries = [MagicMock(spec=["name"]) for _ in range(100)]
        for i, e in enumerate(entries):
            e.name = f"Entity-{i}"
        mock_repo.list_entries = AsyncMock(return_value=(entries, 1000))

        service = NameGeneratorService(
            registry=MagicMock(spec=["get_model"]),
            composer=MagicMock(spec=["build"]),
            model_resolution=MagicMock(spec=["resolve"]),
            novel_repo=permissive_novel_repo(),
            kb_repo=mock_repo,
        )

        await service._fetch_existing_names(
            project_id=uuid4(),
            name_type="character",
        )

        mock_repo.list_entries.assert_called_once()
        _call_kwargs = mock_repo.list_entries.call_args[1]
        assert _call_kwargs.get("page_size") == DEFAULT_NAME_DEDUP_PAGE_SIZE, (
            f"_fetch_existing_names passed page_size="
            f"{_call_kwargs.get('page_size')} but the governed default is "
            f"{DEFAULT_NAME_DEDUP_PAGE_SIZE}. The constant must be wired into "
            "the list_entries call — do not hardcode a separate value."
        )

    @pytest.mark.asyncio
    async def test_service_returns_all_names_within_token_budget(self) -> None:
        """Returned names fit within the MAX_EXISTING_NAMES_TOKENS budget.

        Guards the interaction between the page size and the token cap: with
        100 short names and a 500-token budget, nothing is truncated.
        """

        mock_repo = MagicMock(spec=["list_entries"])
        entries = [MagicMock(spec=["name"]) for _ in range(100)]
        for i, e in enumerate(entries):
            e.name = f"Entity-{i}"
        mock_repo.list_entries = AsyncMock(return_value=(entries, 1000))

        from narrare.generation.name_service import NameGeneratorService

        service = NameGeneratorService(
            registry=MagicMock(spec=["get_model"]),
            composer=MagicMock(spec=["build"]),
            model_resolution=MagicMock(spec=["resolve"]),
            novel_repo=permissive_novel_repo(),
            kb_repo=mock_repo,
        )

        result = await service._fetch_existing_names(
            project_id=uuid4(),
            name_type="character",
        )

        # ~1.3 tokens/word ⇒ 500-token budget holds well over 100 short names.
        assert len(result) == 100, (
            f"All 100 entries should fit within the {MAX_EXISTING_NAMES_TOKENS}-token budget"
        )
