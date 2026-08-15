"""CR-08 P1 regression tests — token-profile vocabulary parity with Core.

These tests prove the drift described in
``docs/architecture/governance/cr-08-p1-token-limits-and-suitability-policy.md``:

* Backend must NOT keep an independent profile vocabulary that can drift.
* ``conservative`` is a retired legacy alias: rejected on writes, normalised
  to ``balanced`` at the read boundary, never emitted.
* ``custom`` is a raw ``output_limit`` mode, not a preset.

Catalogue / calibration / suitability metadata tests live in
``test_cr08_p1_token_limit_metadata.py`` (split for RULE-04).

Written RED-first against the pre-fix backend (drift-encoded), then turned
GREEN by deriving the backend vocabulary from Core.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest
from pydantic import ValidationError

from narrare.settings.token_limits._validators import VALID_PROFILES
from narrare.settings.token_limits.contracts import TokenLimitOverrides
from narrare.settings.token_limits.schemas import UpdateTokenLimitsRequest
from narrare_core.context.budget import (
    DEFAULT_SERIES_HISTORY_BUDGET,
    DEFAULT_TOTAL_BUDGET,
)
from narrare_core.llm.token_profiles import (
    PROFILE_OUTPUT_LIMITS,
    TokenLimitProfile,
    public_token_profile_values,
)

# ======================================================================
# In-memory fakes (kept local so this contract test is self-contained)
# ======================================================================


@dataclass
class _FakeLimitsEntity:
    pk: str
    overrides: dict[str, object] = field(default_factory=dict)


@dataclass
class _FakeConfig:
    default_max_tokens: int = 4096
    ws_idle_timeout_seconds: int = 1800
    consistency_max_chapter_tokens: int = 2000
    consistency_max_kb_entries: int = 100
    default_max_selection_words: int = 2000
    context_total_budget: int = DEFAULT_TOTAL_BUDGET
    series_history_budget: int = DEFAULT_SERIES_HISTORY_BUDGET


class _FakeUserRepo:
    def __init__(self, store: dict[str, _FakeLimitsEntity]) -> None:
        self._store = store

    async def get(self, user_id: str) -> _FakeLimitsEntity:
        entity = self._store.get(user_id)
        if not entity:
            entity = _FakeLimitsEntity(pk=user_id)
            self._store[user_id] = entity
        return entity

    async def update(self, user_id: str, overrides: dict[str, object]) -> _FakeLimitsEntity:
        entity = await self.get(user_id)
        current = dict(entity.overrides)
        current.update(overrides)
        entity.overrides = current
        return entity


class _FakeProjectRepo:
    def __init__(self, store: dict[str, _FakeLimitsEntity]) -> None:
        self._store = store

    async def get(self, project_id: str) -> _FakeLimitsEntity:
        entity = self._store.get(project_id)
        if not entity:
            entity = _FakeLimitsEntity(pk=project_id)
            self._store[project_id] = entity
        return entity

    async def update(self, project_id: str, overrides: dict[str, object]) -> _FakeLimitsEntity:
        entity = await self.get(project_id)
        current = dict(entity.overrides)
        current.update(overrides)
        entity.overrides = current
        return entity


@dataclass
class _FakeStore:
    users: dict[str, _FakeLimitsEntity] = field(default_factory=dict)
    projects: dict[str, _FakeLimitsEntity] = field(default_factory=dict)

    def seed_user(self, user_id: str, overrides: dict[str, object]) -> None:
        self.users[user_id] = _FakeLimitsEntity(pk=user_id, overrides=overrides)

    def seed_project(self, project_id: str, overrides: dict[str, object]) -> None:
        self.projects[project_id] = _FakeLimitsEntity(pk=project_id, overrides=overrides)


def _make_service(store: _FakeStore, *, config: _FakeConfig | None = None) -> Any:
    from narrare.settings.token_limits.service import TokenLimitsService

    return TokenLimitsService(
        user_repo=_FakeUserRepo(store.users),  # pyright: ignore[reportArgumentType]
        project_repo=_FakeProjectRepo(store.projects),  # pyright: ignore[reportArgumentType]
        config=config or _FakeConfig(),  # pyright: ignore[reportArgumentType]
    )


# ======================================================================
# D1 — backend vocabulary must equal Core's public profile values
# ======================================================================


class TestBackendVocabularyMatchesCore:
    """The backend may not keep an independent profile set that can drift."""

    def test_validator_profiles_equal_core_public_values(self) -> None:
        expected = set(public_token_profile_values())
        assert expected == VALID_PROFILES

    def test_validator_profiles_exclude_legacy_conservative(self) -> None:
        assert "conservative" not in VALID_PROFILES

    def test_validator_profiles_include_exactly_five_public_values(self) -> None:
        assert len(VALID_PROFILES) == 5
        for member in TokenLimitProfile:
            assert member.value in VALID_PROFILES


# ======================================================================
# D2 — conservative is rejected on writes
# ======================================================================


class TestSchemaRejectsConservative:
    """New writes with the retired alias must fail schema validation."""

    def test_conservative_rejected_by_request_schema(self) -> None:
        with pytest.raises(ValidationError):
            UpdateTokenLimitsRequest(token_profile="conservative")

    @pytest.mark.parametrize(
        "profile", ["quick", "balanced", "long_texts", "comprehensive", "custom"]
    )
    def test_only_public_profiles_accepted(self, profile: str) -> None:
        req = UpdateTokenLimitsRequest(token_profile=profile)
        assert req.token_profile == profile

    def test_unknown_profile_rejected(self) -> None:
        with pytest.raises(ValidationError):
            UpdateTokenLimitsRequest(token_profile="ultra")


class TestServiceRejectsConservative:
    """The service-layer validator (write boundary) also rejects conservative."""

    async def test_service_rejects_conservative_write(self) -> None:
        from narrare_core.shared.errors import ValidationError as DomainValidationError

        service = _make_service(_FakeStore())
        with pytest.raises(DomainValidationError):
            await service.update_user_limits("u1", {"token_profile": "conservative"})


# ======================================================================
# D2 — persisted conservative normalises to balanced at the read boundary
# ======================================================================


class TestResolvedLimitsNeverEmitConservative:
    """Stored legacy ``conservative`` must surface as ``balanced``, never itself."""

    async def test_stored_user_conservative_normalises_to_balanced(self) -> None:
        store = _FakeStore()
        store.seed_user("u", {"token_profile": "conservative"})
        service = _make_service(store)

        limits = await service.get_resolved_limits(user_id="u")

        assert limits.token_profile == "balanced"

    async def test_stored_project_conservative_normalises_to_balanced(self) -> None:
        store = _FakeStore()
        store.seed_project("p", {"token_profile": "conservative"})
        service = _make_service(store)

        limits = await service.get_resolved_limits(user_id="u", project_id="p")

        assert limits.token_profile == "balanced"

    async def test_resolved_view_never_contains_conservative(self) -> None:
        store = _FakeStore()
        store.seed_user("u", {"token_profile": "conservative"})
        service = _make_service(store)

        limits = await service.get_resolved_limits(user_id="u")

        # The resolved view (and therefore any response built from it) never
        # carries the retired alias.
        assert limits.token_profile != "conservative"


# ======================================================================
# D3 — exact custom semantics
# ======================================================================


class TestCustomSemantics:
    """``custom`` is a raw output-limit mode; presets use their preset limit."""

    async def test_explicit_output_limit_without_profile_resolves_custom(self) -> None:
        store = _FakeStore()
        store.seed_user("u", {"output_limit": 12345})
        service = _make_service(store)

        limits = await service.get_resolved_limits(user_id="u")

        assert limits.token_profile == "custom"
        assert limits.effective_output_limit == 12345

    async def test_preset_profile_uses_preset_effective_limit(self) -> None:
        store = _FakeStore()
        store.seed_user("u", {"token_profile": "balanced"})
        service = _make_service(store)

        limits = await service.get_resolved_limits(user_id="u")

        assert limits.token_profile == "balanced"
        assert limits.effective_output_limit == PROFILE_OUTPUT_LIMITS["balanced"]

    async def test_custom_profile_uses_raw_output_limit(self) -> None:
        store = _FakeStore()
        store.seed_user("u", {"token_profile": "custom", "output_limit": 9999})
        service = _make_service(store)

        limits = await service.get_resolved_limits(user_id="u")

        assert limits.token_profile == "custom"
        assert limits.effective_output_limit == 9999

    async def test_each_preset_profile_effective_matches_core_preset(self) -> None:
        for profile, preset in PROFILE_OUTPUT_LIMITS.items():
            store = _FakeStore()
            store.seed_user("u", {"token_profile": profile})
            service = _make_service(store)

            limits = await service.get_resolved_limits(user_id="u")

            assert limits.token_profile == profile
            assert limits.effective_output_limit == preset


# ======================================================================
# Sanity: effective_output_limit is a resolved-view concern
# ======================================================================


class TestTokenLimitOverridesEffectiveLimit:
    """``TokenLimitOverrides`` exposes the effective (preset-or-raw) limit."""

    def test_preset_profile_effective_uses_preset(self) -> None:
        overrides = TokenLimitOverrides(token_profile="long_texts", output_limit=99999)
        assert overrides.effective_output_limit == PROFILE_OUTPUT_LIMITS["long_texts"]

    def test_custom_profile_effective_uses_raw(self) -> None:
        overrides = TokenLimitOverrides(token_profile="custom", output_limit=4321)
        assert overrides.effective_output_limit == 4321
