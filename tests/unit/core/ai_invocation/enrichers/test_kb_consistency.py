"""Tests for KBConsistencyEnricher.

Covers: not applicable (no checker, no project_id), consistent and
inconsistent results, and detail payload structure.

See: ADR-040, ADR-038, INFRA-013, CONSTRAINTS.md RULE-10.
"""

from __future__ import annotations

import json
from uuid import uuid4

import pytest

from narrare_core.ai_invocation.consistency import (
    ConsistencyStatus,
    EntityType,
    EntityTypeCheck,
    KBConsistencyResult,
)
from narrare_core.ai_invocation.enrichers.consistency import (
    KB_CONSISTENCY_DETAIL_KEY,
    KB_CONSISTENCY_KEY,
    KBConsistencyEnricher,
)
from narrare_core.ai_invocation.models import PromptInvocationContext
from narrare_core.llm.intents import LLMIntent

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_context(**overrides: object) -> PromptInvocationContext:
    """Create a minimal PromptInvocationContext for tests."""
    defaults: dict[str, object] = {
        "feature_id": "test/feature",
        "intent": LLMIntent.WRITE,
        "user_id": uuid4(),
        "project_id": uuid4(),
        "dynamic_inputs": {},
    }
    defaults.update(overrides)
    return PromptInvocationContext(**defaults)  # type: ignore[arg-type]


class FakeKBConsistencyCheck:
    """Async fake KBConsistencyCheck for testing.

    Returns a preconfigured :class:`KBConsistencyResult`.
    Records calls for assertion.
    """

    def __init__(self, result: KBConsistencyResult) -> None:
        self._result = result
        self.calls: list[object] = []

    async def check_consistency(
        self,
        project_id: object,
        *,
        required_types: frozenset[str] | None = None,
    ) -> KBConsistencyResult:
        self.calls.append(project_id)
        return self._result


def _consistent_result() -> KBConsistencyResult:
    """A fully consistent KB result."""
    return KBConsistencyResult(
        entity_type_checks=(
            EntityTypeCheck(
                entity_type=EntityType.CHARACTER,
                status=ConsistencyStatus.PRESENT,
                count=5,
            ),
            EntityTypeCheck(
                entity_type=EntityType.LOCATION,
                status=ConsistencyStatus.PRESENT,
                count=3,
            ),
        ),
        orphan_references=(),
        freshness_warnings=(),
        has_all_required_types=True,
        has_orphan_references=False,
        has_stale_profiles=False,
    )


def _inconsistent_result() -> KBConsistencyResult:
    """An inconsistent KB result with orphans and stale profiles."""
    return KBConsistencyResult(
        entity_type_checks=(
            EntityTypeCheck(
                entity_type=EntityType.CHARACTER,
                status=ConsistencyStatus.PRESENT,
                count=5,
            ),
            EntityTypeCheck(
                entity_type=EntityType.LOCATION,
                status=ConsistencyStatus.MISSING,
                count=0,
            ),
        ),
        orphan_references=("unknown_char_1", "unknown_char_2"),
        freshness_warnings=("stale_profile_char_A",),
        has_all_required_types=False,
        has_orphan_references=True,
        has_stale_profiles=True,
    )


# ---------------------------------------------------------------------------
# 1. Not applicable — no checker configured
# ---------------------------------------------------------------------------


class TestKBConsistencyEnricherNotApplicable:
    """Enricher without checker sets kb_consistency to not_applicable."""

    @pytest.mark.asyncio
    async def test_no_checker_sets_not_applicable(self) -> None:
        """When no checker is configured, status is not_applicable."""
        enricher = KBConsistencyEnricher(consistency_check=None)
        ctx = _make_context()

        result = await enricher.enrich(ctx)

        assert result.dynamic_inputs[KB_CONSISTENCY_KEY] == "not_applicable"

    @pytest.mark.asyncio
    async def test_no_checker_preserves_existing_inputs(self) -> None:
        """Existing dynamic_inputs keys are preserved."""
        enricher = KBConsistencyEnricher(consistency_check=None)
        ctx = _make_context(dynamic_inputs={"existing": "value"})

        result = await enricher.enrich(ctx)

        assert result.dynamic_inputs["existing"] == "value"
        assert result.dynamic_inputs[KB_CONSISTENCY_KEY] == "not_applicable"

    @pytest.mark.asyncio
    async def test_no_checker_no_detail_key(self) -> None:
        """No detail key is added when checker is absent."""
        enricher = KBConsistencyEnricher(consistency_check=None)
        ctx = _make_context()

        result = await enricher.enrich(ctx)

        assert KB_CONSISTENCY_DETAIL_KEY not in result.dynamic_inputs

    @pytest.mark.asyncio
    async def test_default_constructor_no_checker(self) -> None:
        """Default constructor (no args) behaves like no checker."""
        enricher = KBConsistencyEnricher()
        ctx = _make_context()

        result = await enricher.enrich(ctx)

        assert result.dynamic_inputs[KB_CONSISTENCY_KEY] == "not_applicable"


# ---------------------------------------------------------------------------
# 2. No project_id — not applicable
# ---------------------------------------------------------------------------


class TestKBConsistencyEnricherNoProjectId:
    """Enricher with checker but no project_id returns not_applicable."""

    @pytest.mark.asyncio
    async def test_no_project_id_sets_not_applicable(self) -> None:
        """When project_id is None, status is not_applicable."""
        fake_check = FakeKBConsistencyCheck(_consistent_result())
        enricher = KBConsistencyEnricher(consistency_check=fake_check)
        ctx = _make_context(project_id=None)

        result = await enricher.enrich(ctx)

        assert result.dynamic_inputs[KB_CONSISTENCY_KEY] == "not_applicable"

    @pytest.mark.asyncio
    async def test_no_project_id_does_not_call_checker(self) -> None:
        """Checker is not invoked when project_id is None."""
        fake_check = FakeKBConsistencyCheck(_consistent_result())
        enricher = KBConsistencyEnricher(consistency_check=fake_check)
        ctx = _make_context(project_id=None)

        await enricher.enrich(ctx)

        assert len(fake_check.calls) == 0

    @pytest.mark.asyncio
    async def test_no_project_id_no_detail_key(self) -> None:
        """No detail key is added when project_id is None."""
        fake_check = FakeKBConsistencyCheck(_consistent_result())
        enricher = KBConsistencyEnricher(consistency_check=fake_check)
        ctx = _make_context(project_id=None)

        result = await enricher.enrich(ctx)

        assert KB_CONSISTENCY_DETAIL_KEY not in result.dynamic_inputs


# ---------------------------------------------------------------------------
# 3. Consistent result
# ---------------------------------------------------------------------------


class TestKBConsistencyEnricherConsistent:
    """Enricher with consistent result sets kb_consistency to consistent."""

    @pytest.mark.asyncio
    async def test_consistent_status(self) -> None:
        """When checker returns consistent, status is 'consistent'."""
        fake_check = FakeKBConsistencyCheck(_consistent_result())
        enricher = KBConsistencyEnricher(consistency_check=fake_check)
        ctx = _make_context()

        result = await enricher.enrich(ctx)

        assert result.dynamic_inputs[KB_CONSISTENCY_KEY] == "consistent"

    @pytest.mark.asyncio
    async def test_consistent_detail_present(self) -> None:
        """Detail payload is present even for consistent results."""
        fake_check = FakeKBConsistencyCheck(_consistent_result())
        enricher = KBConsistencyEnricher(consistency_check=fake_check)
        ctx = _make_context()

        result = await enricher.enrich(ctx)

        assert KB_CONSISTENCY_DETAIL_KEY in result.dynamic_inputs

    @pytest.mark.asyncio
    async def test_checker_called_with_project_id(self) -> None:
        """Checker receives the project_id from the context."""
        project_id = uuid4()
        fake_check = FakeKBConsistencyCheck(_consistent_result())
        enricher = KBConsistencyEnricher(consistency_check=fake_check)
        ctx = _make_context(project_id=project_id)

        await enricher.enrich(ctx)

        assert len(fake_check.calls) == 1
        assert fake_check.calls[0] == project_id

    @pytest.mark.asyncio
    async def test_preserves_existing_dynamic_inputs(self) -> None:
        """Existing dynamic_inputs keys are preserved."""
        fake_check = FakeKBConsistencyCheck(_consistent_result())
        enricher = KBConsistencyEnricher(consistency_check=fake_check)
        ctx = _make_context(dynamic_inputs={"preference": "some_text"})

        result = await enricher.enrich(ctx)

        assert result.dynamic_inputs["preference"] == "some_text"
        assert result.dynamic_inputs[KB_CONSISTENCY_KEY] == "consistent"


# ---------------------------------------------------------------------------
# 4. Inconsistent result
# ---------------------------------------------------------------------------


class TestKBConsistencyEnricherInconsistent:
    """Enricher with inconsistent result sets kb_consistency to inconsistent."""

    @pytest.mark.asyncio
    async def test_inconsistent_status(self) -> None:
        """When checker returns inconsistent, status is 'inconsistent'."""
        fake_check = FakeKBConsistencyCheck(_inconsistent_result())
        enricher = KBConsistencyEnricher(consistency_check=fake_check)
        ctx = _make_context()

        result = await enricher.enrich(ctx)

        assert result.dynamic_inputs[KB_CONSISTENCY_KEY] == "inconsistent"

    @pytest.mark.asyncio
    async def test_inconsistent_detail_present(self) -> None:
        """Detail payload is present for inconsistent results."""
        fake_check = FakeKBConsistencyCheck(_inconsistent_result())
        enricher = KBConsistencyEnricher(consistency_check=fake_check)
        ctx = _make_context()

        result = await enricher.enrich(ctx)

        assert KB_CONSISTENCY_DETAIL_KEY in result.dynamic_inputs

    @pytest.mark.asyncio
    async def test_inconsistent_result_reflects_in_detail(self) -> None:
        """Detail payload reflects inconsistency flags."""
        fake_check = FakeKBConsistencyCheck(_inconsistent_result())
        enricher = KBConsistencyEnricher(consistency_check=fake_check)
        ctx = _make_context()

        result = await enricher.enrich(ctx)
        detail = json.loads(result.dynamic_inputs[KB_CONSISTENCY_DETAIL_KEY])

        assert detail["has_all_required_types"] is False
        assert detail["has_orphan_references"] is True
        assert detail["has_stale_profiles"] is True


# ---------------------------------------------------------------------------
# 5. Detail payload structure
# ---------------------------------------------------------------------------


class TestKBConsistencyEnricherDetail:
    """Detail payload fields are correctly populated."""

    @pytest.mark.asyncio
    async def test_detail_orphan_count(self) -> None:
        """orphan_count matches the number of orphan_references."""
        fake_check = FakeKBConsistencyCheck(_inconsistent_result())
        enricher = KBConsistencyEnricher(consistency_check=fake_check)
        ctx = _make_context()

        result = await enricher.enrich(ctx)
        detail = json.loads(result.dynamic_inputs[KB_CONSISTENCY_DETAIL_KEY])

        assert detail["orphan_count"] == 2

    @pytest.mark.asyncio
    async def test_detail_entity_types_checked(self) -> None:
        """entity_types_checked matches the number of entity_type_checks."""
        fake_check = FakeKBConsistencyCheck(_inconsistent_result())
        enricher = KBConsistencyEnricher(consistency_check=fake_check)
        ctx = _make_context()

        result = await enricher.enrich(ctx)
        detail = json.loads(result.dynamic_inputs[KB_CONSISTENCY_DETAIL_KEY])

        assert detail["entity_types_checked"] == 2

    @pytest.mark.asyncio
    async def test_detail_consistent_all_true(self) -> None:
        """Consistent result has all-positive flags."""
        fake_check = FakeKBConsistencyCheck(_consistent_result())
        enricher = KBConsistencyEnricher(consistency_check=fake_check)
        ctx = _make_context()

        result = await enricher.enrich(ctx)
        detail = json.loads(result.dynamic_inputs[KB_CONSISTENCY_DETAIL_KEY])

        assert detail["has_all_required_types"] is True
        assert detail["has_orphan_references"] is False
        assert detail["has_stale_profiles"] is False
        assert detail["orphan_count"] == 0
        assert detail["entity_types_checked"] == 2

    @pytest.mark.asyncio
    async def test_detail_is_valid_json(self) -> None:
        """Detail payload is valid JSON string."""
        fake_check = FakeKBConsistencyCheck(_consistent_result())
        enricher = KBConsistencyEnricher(consistency_check=fake_check)
        ctx = _make_context()

        result = await enricher.enrich(ctx)

        parsed = json.loads(result.dynamic_inputs[KB_CONSISTENCY_DETAIL_KEY])
        assert isinstance(parsed, dict)
