"""Unit tests for KBConsistencyAnalyzer — entry-internal consistency analysis.

Tests _safe_severity, _build_entry_content, _build_template_structure helpers
and the analyze_entries method with mocked registry.run.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from narrare.kb.consistency_analyzer import (
    KBConsistencyAnalyzer,
    _build_entry_content,
    _build_template_structure,
    _safe_severity,
)
from narrare.kb.worldbuilding_contracts import (
    ConsistencyCategory,
    WorldbuildingSeverity,
)
from narrare_core.llm import ResolvedModelConfig
from narrare_core.llm.gateway import ModelRegistry
from narrare_core.writing._token_utils import default_token_counter

if TYPE_CHECKING:
    from narrare.kb.contracts import KBRepositoryProtocol
    from narrare.kb.models import KBEntry
    from narrare_core.prompts.composer import PromptComposer

# ---------------------------------------------------------------------------
# Fake classes
# ---------------------------------------------------------------------------


class FakeKBEntry:
    """Minimal stand-in for KBEntry used in consistency tests."""

    def __init__(
        self,
        *,
        id: object | None = None,
        name: str = "Test Entity",
        entity_type: str = "character",
        metadata_: dict[str, object] | None = None,
        body: str | None = None,
        tags: list[str] | None = None,
        usage_count: int = 0,
        novel_id: object | None = None,
    ) -> None:
        self.id = id if id is not None else uuid4()
        self.name = name
        self.entity_type = entity_type
        self.metadata_ = metadata_
        self.body = body
        self.tags = tags
        self.usage_count = usage_count
        self.novel_id = novel_id if novel_id is not None else uuid4()


class FakeKBRepo:
    """In-memory KB repo with list_entries pagination."""

    def __init__(self, entries: list[FakeKBEntry] | None = None) -> None:
        self._entries = entries or []

    async def list_entries(
        self,
        novel_id: object,
        entity_type: str | None = None,
        tags: list[str] | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[FakeKBEntry], int]:
        start = (page - 1) * page_size
        end = start + page_size
        return self._entries[start:end], len(self._entries)


class FakeComposedPrompt:
    """Minimal composed prompt with system field."""

    def __init__(
        self,
        system: str = "system",
        user: str = "composer-built user prompt",
    ) -> None:
        self.system = system
        self.user = user


class FakeComposer:
    """Fake PromptComposer returning canned prompts."""

    def __init__(self) -> None:
        self.last_context: object | None = None

    async def build(self, intent: object, ctx: object) -> FakeComposedPrompt:
        self.last_context = ctx
        return FakeComposedPrompt(system="check consistency system prompt")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_analyzer(
    entries: list[FakeKBEntry] | None = None,
) -> tuple[KBConsistencyAnalyzer, dict[str, object]]:
    """Build KBConsistencyAnalyzer with fake dependencies."""
    kb_repo = FakeKBRepo(entries)
    registry = MagicMock(spec=ModelRegistry)
    config = MagicMock(spec=ResolvedModelConfig)
    composer = FakeComposer()

    analyzer = KBConsistencyAnalyzer(
        kb_repo=cast("KBRepositoryProtocol", kb_repo),
        registry=registry,
        config=config,
        composer=cast("PromptComposer", composer),
    )

    return analyzer, {
        "kb_repo": kb_repo,
        "registry": registry,
        "config": config,
        "composer": composer,
    }


# ---------------------------------------------------------------------------
# Tests: _safe_severity
# ---------------------------------------------------------------------------


class TestSafeSeverity:
    """Tests for _safe_severity helper."""

    def test_safe_severity_valid_critical(self) -> None:
        """Valid 'critical' string returns CRITICAL enum."""
        assert _safe_severity("critical") == WorldbuildingSeverity.CRITICAL

    def test_safe_severity_valid_major(self) -> None:
        """Valid 'major' string returns MAJOR enum."""
        assert _safe_severity("major") == WorldbuildingSeverity.MAJOR

    def test_safe_severity_invalid_defaults_to_major(self) -> None:
        """Invalid string defaults to MAJOR."""
        assert _safe_severity("unknown") == WorldbuildingSeverity.MAJOR


# ---------------------------------------------------------------------------
# Tests: _build_entry_content
# ---------------------------------------------------------------------------


class TestBuildEntryContent:
    """Tests for _build_entry_content helper."""

    def test_build_entry_content_correct_dict(self) -> None:
        """Returns dict with name, entity_type, metadata, body, tags."""
        entry = FakeKBEntry(
            name="Alice",
            entity_type="character",
            metadata_={"role": "hero"},
            body="A brave warrior",
            tags=["protagonist"],
        )

        result = _build_entry_content(cast("KBEntry", entry))

        assert result["name"] == "Alice"
        assert result["entity_type"] == "character"
        assert result["body"] == "A brave warrior"
        assert result["tags"] == ["protagonist"]

    def test_build_entry_content_body_under_limit_unchanged(self) -> None:
        """Body under the token budget passes through unchanged."""
        body = " ".join(["word"] * 100)  # ~130 tokens, well under 1500
        entry = FakeKBEntry(body=body)

        result = _build_entry_content(cast("KBEntry", entry))

        assert result["body"] == body

    def test_build_entry_content_body_over_limit_truncated_to_budget(self) -> None:
        """Body over the token budget is truncated to the token limit.

        Proves token-based (not char-based) truncation: the result is
        shorter than the input, fits within the 1500-token budget, and is
        NOT exactly 5000 chars (which would indicate the old char limit).
        """
        long_body = " ".join(["word"] * 2000)  # ~2600 tokens
        entry = FakeKBEntry(body=long_body)

        result = _build_entry_content(cast("KBEntry", entry))
        result_body = cast("str", result["body"])

        assert len(result_body) < len(long_body)
        assert default_token_counter(result_body) <= 1500
        assert len(result_body) != 5000  # token-based, not char-based

    def test_build_entry_content_custom_max_body_tokens(self) -> None:
        """Explicit max_body_tokens caps the body to the given budget."""
        long_body = " ".join(["word"] * 2000)
        entry = FakeKBEntry(body=long_body)

        result = _build_entry_content(cast("KBEntry", entry), max_body_tokens=100)
        result_body = cast("str", result["body"])

        assert default_token_counter(result_body) <= 100
        assert len(result_body) < len(long_body)

    def test_build_entry_content_empty_body(self) -> None:
        """None body becomes empty string."""
        entry = FakeKBEntry(body=None)

        result = _build_entry_content(cast("KBEntry", entry))

        assert result["body"] == ""

    def test_build_entry_content_none_metadata(self) -> None:
        """None metadata becomes empty dict."""
        entry = FakeKBEntry(metadata_=None)

        result = _build_entry_content(cast("KBEntry", entry))

        assert result["metadata"] == {}


# ---------------------------------------------------------------------------
# Tests: KBConsistencyAnalyzer.max_body_tokens config
# ---------------------------------------------------------------------------


class TestAnalyzerMaxBodyTokens:
    """Tests for max_body_tokens configuration on the analyzer."""

    def test_default_max_body_tokens_is_1500(self) -> None:
        """Analyzer without explicit max_body_tokens defaults to 1500."""
        analyzer, _deps = _make_analyzer(entries=[])

        assert analyzer._max_body_tokens == 1500

    def test_custom_max_body_tokens_stored(self) -> None:
        """Analyzer stores an explicitly-provided max_body_tokens."""
        kb_repo = FakeKBRepo([])
        registry = MagicMock(spec=ModelRegistry)
        config = MagicMock(spec=ResolvedModelConfig)
        composer = FakeComposer()

        analyzer = KBConsistencyAnalyzer(
            kb_repo=cast("KBRepositoryProtocol", kb_repo),
            registry=registry,
            config=config,
            composer=cast("PromptComposer", composer),
            max_body_tokens=800,
        )

        assert analyzer._max_body_tokens == 800


# ---------------------------------------------------------------------------
# Tests: _build_template_structure
# ---------------------------------------------------------------------------


class TestBuildTemplateStructure:
    """Tests for _build_template_structure helper."""

    def test_build_template_structure_character(self) -> None:
        """Character entity type returns field-key-to-label dict."""
        result = _build_template_structure("character")

        assert isinstance(result, dict)
        # CharacterMetadata has 'role', 'age', etc.
        assert "role" in result

    def test_build_template_structure_unknown_type(self) -> None:
        """Unknown type falls back to base schema with empty fields."""
        result = _build_template_structure("unknown_type")

        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# Tests: analyze_entries
# ---------------------------------------------------------------------------


class TestAnalyzeEntries:
    """Tests for KBConsistencyAnalyzer.analyze_entries."""

    @pytest.mark.asyncio
    async def test_analyze_entries_empty_returns_empty(self) -> None:
        """No entities returns ([], 0)."""
        analyzer, _deps = _make_analyzer(entries=[])

        issues, count = await analyzer.analyze_entries(uuid4(), None)

        assert issues == []
        assert count == 0

    @pytest.mark.asyncio
    async def test_analyze_entries_single_entity_with_issues(self) -> None:
        """Single entity with LLM issues maps to ConsistencyIssue list."""
        entry = FakeKBEntry(
            name="Alice",
            entity_type="character",
            metadata_={"role": "hero"},
            body="A brave warrior",
        )
        analyzer, deps = _make_analyzer(entries=[entry])

        # Patch list_entities to return our entry
        from narrare.kb.consistency_analyzer import _EntryInternalIssue, _EntryInternalOutput

        llm_output = _EntryInternalOutput(
            issues=[
                _EntryInternalIssue(
                    field_keys=["role", "age"],
                    description="Contradictory age reference",
                    contradiction="Age is both 25 and 30",
                    suggested_resolution="Pick consistent age",
                    severity="major",
                    confidence=0.9,
                )
            ],
            assessment="Minor issues found",
        )

        registry_mock = deps["registry"]
        assert isinstance(registry_mock, MagicMock)
        registry_mock.run = AsyncMock(return_value=llm_output)

        issues, count = await analyzer.analyze_entries(uuid4(), None)

        assert count == 1
        assert len(issues) == 1
        assert issues[0].category == ConsistencyCategory.ENTRY_INTERNAL
        assert issues[0].description == "Contradictory age reference"
        assert issues[0].severity == WorldbuildingSeverity.MAJOR

        registry_mock.run.assert_awaited_once()
        assert registry_mock.run.await_args.kwargs["prompt"] == "composer-built user prompt"

        composer = deps["composer"]
        assert isinstance(composer, FakeComposer)
        ctx = composer.last_context
        assert ctx is not None
        assert getattr(ctx, "entity_name", None) == "Alice"  # pyright: ignore[reportAttributeAccessIssue]
        assert getattr(ctx, "entity_type", None) == "character"  # pyright: ignore[reportAttributeAccessIssue]

    @pytest.mark.asyncio
    async def test_analyze_entries_exception_skips_and_continues(self) -> None:
        """Exception analyzing a single entity is caught and skipped."""
        entry_good = FakeKBEntry(
            name="Alice",
            entity_type="character",
        )
        entry_bad = FakeKBEntry(
            name="Bob",
            entity_type="character",
        )
        analyzer, deps = _make_analyzer(entries=[entry_good, entry_bad])

        from narrare.kb.consistency_analyzer import _EntryInternalOutput

        # First call succeeds, second call raises
        good_output = _EntryInternalOutput(issues=[], assessment="OK")
        registry_mock = deps["registry"]
        assert isinstance(registry_mock, MagicMock)
        registry_mock.run = AsyncMock(
            side_effect=[good_output, RuntimeError("LLM failed")],
        )

        issues, count = await analyzer.analyze_entries(uuid4(), None)

        assert count == 2
        assert len(issues) == 0  # good one has no issues, bad one was skipped
