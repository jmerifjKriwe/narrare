"""Unit tests for context/integration_contracts.py — Cross-Feature Ref Lifecycle.

Covers (ADR-050 P1-B — CR-AUFG-04-06):
1. ``RefIntegrityIssue`` — frozen dataclass, field construction
2. ``ContradictionPromotionPolicy`` — default promotion sets
3. ``KBEntityLifecycleObserver`` — structural Protocol compatibility
4. ``CrossFeatureRefIndex`` — structural Protocol compatibility
5. Per-consumer specialisations (Timeline, Storyboard, ChapterFrontmatter)
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import Any, cast
from uuid import UUID, uuid4

import pytest

from narrare_core.context.integration_contracts import (
    ChapterFrontmatterRefConsumer,
    ContradictionPromotionPolicy,
    CrossFeatureRefIndex,
    KBEntityLifecycleObserver,
    RefIntegrityIssue,
    RefResolutionStatus,
    StoryboardRefConsumer,
    TimelineRefConsumer,
)

# =====================================================================
# RefIntegrityIssue — dataclass behavior
# =====================================================================


class TestRefIntegrityIssue:
    """RefIntegrityIssue is a frozen dataclass."""

    def test_creation_with_all_fields(self) -> None:
        issue = RefIntegrityIssue(
            consumer_feature="timeline",
            consumer_location="timeline_events[12].character_refs[1]",
            ref_kind="id",
            ref_value="abc-123",
            resolved_status="deprecated",
            reason="deprecated_ref_in_active_context",
            suggested_action="mark_deprecated_in_context",
        )
        assert issue.consumer_feature == "timeline"
        assert issue.ref_kind == "id"
        assert issue.resolved_status == "deprecated"
        assert issue.reason == "deprecated_ref_in_active_context"
        assert issue.suggested_action == "mark_deprecated_in_context"

    def test_creation_with_name_ref_kind(self) -> None:
        issue = RefIntegrityIssue(
            consumer_feature="chapter_frontmatter",
            consumer_location="chapter[3].frontmatter.pov_character",
            ref_kind="name",
            ref_value="Old Name",
            resolved_status="unknown",
            reason="stale_name_ref",
            suggested_action="warn_only",
        )
        assert issue.ref_kind == "name"
        assert issue.reason == "stale_name_ref"

    def test_creation_with_deleted_status(self) -> None:
        issue = RefIntegrityIssue(
            consumer_feature="storyboard",
            consumer_location="scene_plans[0a1b2c3d].purpose",
            ref_kind="name",
            ref_value="Deleted Entity",
            resolved_status="deleted",
            reason="deleted_ref_without_tombstone",
            suggested_action="block_operation",
        )
        assert issue.resolved_status == "deleted"

    def test_is_frozen(self) -> None:
        issue = RefIntegrityIssue(
            consumer_feature="timeline",
            consumer_location="loc",
            ref_kind="id",
            ref_value="x",
            resolved_status="active",
            reason="stale_name_ref",
            suggested_action="warn_only",
        )
        with pytest.raises(FrozenInstanceError):
            cast("Any", issue).consumer_feature = "changed"

    def test_has_no_dict_attribute(self) -> None:
        """slots=True prevents dynamic attributes."""
        issue = RefIntegrityIssue(
            consumer_feature="timeline",
            consumer_location="loc",
            ref_kind="id",
            ref_value="x",
            resolved_status="active",
            reason="stale_name_ref",
            suggested_action="warn_only",
        )
        assert not hasattr(issue, "__dict__")

    def test_equal_instances_are_equal(self) -> None:
        a = RefIntegrityIssue(
            consumer_feature="timeline",
            consumer_location="loc",
            ref_kind="id",
            ref_value="x",
            resolved_status="active",
            reason="stale_name_ref",
            suggested_action="warn_only",
        )
        b = RefIntegrityIssue(
            consumer_feature="timeline",
            consumer_location="loc",
            ref_kind="id",
            ref_value="x",
            resolved_status="active",
            reason="stale_name_ref",
            suggested_action="warn_only",
        )
        assert a == b


# =====================================================================
# ContradictionPromotionPolicy — default promotion sets
# =====================================================================


class TestContradictionPromotionPolicy:
    """ContradictionPromotionPolicy decides issue promotion severity."""

    def test_default_policy_exists(self) -> None:
        policy = ContradictionPromotionPolicy()
        assert isinstance(policy, ContradictionPromotionPolicy)

    def test_error_promotions_contain_hard_contradictions(self) -> None:
        """Hard contradictions that break ref semantics are promoted to error."""
        policy = ContradictionPromotionPolicy()
        assert "deleted_ref_without_tombstone" in policy.promote_to_error
        assert "rename_target_missing" in policy.promote_to_error
        assert "type_drift" in policy.promote_to_error

    def test_warning_promotions_contain_soft_contradictions(self) -> None:
        """Soft contradictions are surfaced as warnings, not errors."""
        policy = ContradictionPromotionPolicy()
        assert "stale_name_ref" in policy.promote_to_warning
        assert "deprecated_ref_in_active_context" in policy.promote_to_warning
        assert "duplicate_after_merge" in policy.promote_to_warning

    def test_error_and_warning_sets_are_disjoint(self) -> None:
        """No reason appears in both promotion sets."""
        policy = ContradictionPromotionPolicy()
        assert policy.promote_to_error.isdisjoint(policy.promote_to_warning)

    def test_promotion_sets_are_frozensets(self) -> None:
        policy = ContradictionPromotionPolicy()
        assert isinstance(policy.promote_to_error, frozenset)
        assert isinstance(policy.promote_to_warning, frozenset)

    def test_policy_is_frozen(self) -> None:
        policy = ContradictionPromotionPolicy()
        with pytest.raises(FrozenInstanceError):
            cast("Any", policy).promote_to_error = frozenset()

    def test_custom_policy_overrides_defaults(self) -> None:
        """Backend can construct a custom policy from settings (RULE-18)."""
        policy = ContradictionPromotionPolicy(
            promote_to_error=frozenset({"type_drift"}),
            promote_to_warning=frozenset({"stale_name_ref"}),
        )
        assert policy.promote_to_error == frozenset({"type_drift"})
        assert policy.promote_to_warning == frozenset({"stale_name_ref"})


# =====================================================================
# KBEntityLifecycleObserver — structural Protocol compatibility
# =====================================================================


class _FakeLifecycleObserver:
    """Fake implementing KBEntityLifecycleObserver."""

    def __init__(self, feature_name: str = "fake_consumer") -> None:
        self._feature = feature_name
        self.rename_calls: list[tuple[UUID, UUID, str, str]] = []
        self.deprecate_calls: list[tuple[UUID, UUID]] = []
        self.delete_calls: list[tuple[UUID, UUID]] = []

    @property
    def consumer_feature(self) -> str:
        return self._feature

    async def on_kb_entity_renamed(
        self, *, novel_id: UUID, entity_id: UUID, old_name: str, new_name: str
    ) -> None:
        self.rename_calls.append((novel_id, entity_id, old_name, new_name))

    async def on_kb_entity_deprecated(self, *, novel_id: UUID, entity_id: UUID) -> None:
        self.deprecate_calls.append((novel_id, entity_id))

    async def on_kb_entity_deleted(self, *, novel_id: UUID, entity_id: UUID) -> None:
        self.delete_calls.append((novel_id, entity_id))


class TestKBEntityLifecycleObserverProtocol:
    """KBEntityLifecycleObserver is a @runtime_checkable structural Protocol."""

    def test_fake_observer_satisfies_protocol(self) -> None:
        observer = _FakeLifecycleObserver()
        assert isinstance(observer, KBEntityLifecycleObserver)

    def test_plain_object_does_not_satisfy(self) -> None:
        assert not isinstance(object(), KBEntityLifecycleObserver)

    @pytest.mark.asyncio
    async def test_observer_methods_are_callable(self) -> None:
        """Verify the fake actually works end-to-end."""
        observer = _FakeLifecycleObserver(feature_name="test")
        novel = uuid4()
        entity = uuid4()
        await observer.on_kb_entity_renamed(
            novel_id=novel, entity_id=entity, old_name="Old", new_name="New"
        )
        await observer.on_kb_entity_deprecated(novel_id=novel, entity_id=entity)
        await observer.on_kb_entity_deleted(novel_id=novel, entity_id=entity)
        assert len(observer.rename_calls) == 1
        assert len(observer.deprecate_calls) == 1
        assert len(observer.delete_calls) == 1


# =====================================================================
# CrossFeatureRefIndex — structural Protocol compatibility
# =====================================================================


class _FakeRefIndex:
    """Fake implementing CrossFeatureRefIndex."""

    def __init__(self, issues: list[RefIntegrityIssue] | None = None) -> None:
        self._issues = issues or []

    async def check_refs(self, *, novel_id: UUID, consumer_feature: str) -> list[RefIntegrityIssue]:
        return [i for i in self._issues if i.consumer_feature == consumer_feature]

    async def resolve_ref(
        self, *, novel_id: UUID, ref_kind: str, ref_value: str
    ) -> RefResolutionStatus:
        return "active"


class TestCrossFeatureRefIndexProtocol:
    """CrossFeatureRefIndex is a @runtime_checkable structural Protocol."""

    def test_fake_index_satisfies_protocol(self) -> None:
        index = _FakeRefIndex()
        assert isinstance(index, CrossFeatureRefIndex)

    def test_plain_object_does_not_satisfy(self) -> None:
        assert not isinstance(object(), CrossFeatureRefIndex)

    @pytest.mark.asyncio
    async def test_check_refs_returns_issues_for_consumer(self) -> None:
        issue = RefIntegrityIssue(
            consumer_feature="timeline",
            consumer_location="loc",
            ref_kind="id",
            ref_value="x",
            resolved_status="deprecated",
            reason="deprecated_ref_in_active_context",
            suggested_action="warn_only",
        )
        index = _FakeRefIndex(issues=[issue])
        result = await index.check_refs(novel_id=uuid4(), consumer_feature="timeline")
        assert len(result) == 1
        assert result[0].reason == "deprecated_ref_in_active_context"

    @pytest.mark.asyncio
    async def test_check_refs_empty_for_other_consumer(self) -> None:
        issue = RefIntegrityIssue(
            consumer_feature="timeline",
            consumer_location="loc",
            ref_kind="id",
            ref_value="x",
            resolved_status="active",
            reason="stale_name_ref",
            suggested_action="warn_only",
        )
        index = _FakeRefIndex(issues=[issue])
        result = await index.check_refs(novel_id=uuid4(), consumer_feature="storyboard")
        assert result == []

    @pytest.mark.asyncio
    async def test_resolve_ref_returns_status(self) -> None:
        index = _FakeRefIndex()
        status = await index.resolve_ref(novel_id=uuid4(), ref_kind="id", ref_value="some-id")
        assert status == "active"


# =====================================================================
# Per-consumer specialisations — structural compatibility + identity
# =====================================================================


class TestTimelineRefConsumer:
    """TimelineRefConsumer specialises KBEntityLifecycleObserver for PLAN-004."""

    def test_fake_timeline_observer_satisfies_base_protocol(self) -> None:
        observer = _FakeLifecycleObserver(feature_name="timeline")
        assert isinstance(observer, KBEntityLifecycleObserver)

    def test_fake_timeline_observer_satisfies_specialisation(self) -> None:
        observer = _FakeLifecycleObserver(feature_name="timeline")
        assert isinstance(observer, TimelineRefConsumer)

    def test_timeline_consumer_feature_is_timeline(self) -> None:
        """The Protocol documents consumer_feature == 'timeline'."""
        observer = _FakeLifecycleObserver(feature_name="timeline")
        assert observer.consumer_feature == "timeline"

    def test_protocol_is_runtime_checkable(self) -> None:
        assert not isinstance(object(), TimelineRefConsumer)


class TestStoryboardRefConsumer:
    """StoryboardRefConsumer specialises for PLAN-005 (no direct refs)."""

    def test_fake_storyboard_observer_satisfies_specialisation(self) -> None:
        observer = _FakeLifecycleObserver(feature_name="storyboard")
        assert isinstance(observer, StoryboardRefConsumer)

    def test_storyboard_consumer_feature_is_storyboard(self) -> None:
        observer = _FakeLifecycleObserver(feature_name="storyboard")
        assert observer.consumer_feature == "storyboard"

    def test_protocol_documents_scene_scan_semantics(self) -> None:
        """The contract documents the scene scan surface (PLAN-001 spec §7)."""
        doc = StoryboardRefConsumer.__doc__ or ""
        assert "scene_plans" in doc
        assert "scene_plans[{id}].{field}" in doc
        for field in (
            "title",
            "purpose",
            "conflict",
            "resolution",
            "beats[]",
            "present_characters[].name",
            "pov_character_ref.name",
            "location_ref.name",
        ):
            assert field in doc, f"scene scan surface must document {field}"

    def test_protocol_documents_never_rewrite(self) -> None:
        """Scene text is user content — the contract mandates no rewrites."""
        doc = StoryboardRefConsumer.__doc__ or ""
        assert "NEVER rewritten" in doc


class TestChapterFrontmatterRefConsumer:
    """ChapterFrontmatterRefConsumer specialises for WRITE-001/KB-001."""

    def test_fake_frontmatter_observer_satisfies_specialisation(self) -> None:
        observer = _FakeLifecycleObserver(feature_name="chapter_frontmatter")
        assert isinstance(observer, ChapterFrontmatterRefConsumer)

    def test_frontmatter_consumer_feature_is_chapter_frontmatter(self) -> None:
        observer = _FakeLifecycleObserver(feature_name="chapter_frontmatter")
        assert observer.consumer_feature == "chapter_frontmatter"
