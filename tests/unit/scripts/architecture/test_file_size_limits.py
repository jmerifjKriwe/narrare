"""Tests for the shared RULE-04 file-size SSOT (scripts/architecture/file_size_limits.py).

Historical defect (fixed 2026-08-19): the two RULE-04 gates —
``scripts/architecture/_checkers/file_size.py`` (architecture-constraints
hook) and ``scripts/check_python_file_size.py`` (python-size ratchet) —
carried separate classification predicates and limit vocabularies that had
drifted apart (router predicate overbreadth, missing script/dependency
categories on one side, missing repository/contracts/gateway/composer on
the other, and a models 200-vs-500 value split). Two checkers asserting
the same rule with different truths is the defect; the fix is ONE shared
classification+limit module whose VALUES come from
``pyproject.toml [tool.narrare.architecture.file_size_limits]`` (the SSOT)
and whose predicates live exactly once.

These tests pin the reconciled vocabulary and the reconciliation values
(authority per category documented in
``.superpowers/sdd/2026-08-18-preexisting-fixes/task-gate-unification-report.md``).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.architecture.file_size_limits import (  # noqa: E402
    CANONICAL_CATEGORIES,
    CATEGORY_ORDER,
    FileSizeLimitsError,
    classify,
    load_limits,
    validate_limits,
)

# ---------------------------------------------------------------------------
# Reconciled limit values (pyproject SSOT table)
# ---------------------------------------------------------------------------

_EXPECTED_LIMITS: dict[str, int] = {
    "test": 400,
    "script": 600,
    "router": 150,
    "dependency": 200,
    "service": 300,
    "agent": 200,
    "config_schema": 200,
    "models": 200,
    "repository": 250,
    "contracts": 200,
    "gateway": 300,
    "composer": 250,
    "general": 400,
}


class TestCanonicalVocabulary:
    """The canonical category set — one vocabulary for both gates."""

    def test_category_order_is_complete_and_unique(self) -> None:
        assert len(CATEGORY_ORDER) == len(set(CATEGORY_ORDER))
        assert frozenset(CATEGORY_ORDER) == CANONICAL_CATEGORIES

    def test_pyproject_table_defines_exactly_the_canonical_categories(self) -> None:
        """The pyproject SSOT table must match the canonical vocabulary —
        no missing key (silent fallback risk) and no stale key (drift)."""
        limits = load_limits()
        assert set(limits) == CANONICAL_CATEGORIES

    def test_pyproject_table_carries_the_reconciled_values(self) -> None:
        limits = load_limits()
        assert limits == _EXPECTED_LIMITS


class TestValidateLimits:
    """Table validation — invalid config must fail loudly (RULE-11)."""

    def test_complete_table_passes(self) -> None:
        assert validate_limits(_EXPECTED_LIMITS) == _EXPECTED_LIMITS

    def test_missing_key_is_rejected(self) -> None:
        partial = dict(_EXPECTED_LIMITS)
        del partial["script"]
        with pytest.raises(FileSizeLimitsError, match="script"):
            validate_limits(partial)

    def test_unknown_stale_key_is_rejected(self) -> None:
        stale = dict(_EXPECTED_LIMITS, schemas=200)  # pre-unification key name
        with pytest.raises(FileSizeLimitsError, match="schemas"):
            validate_limits(stale)

    def test_non_positive_limit_is_rejected(self) -> None:
        bad = dict(_EXPECTED_LIMITS, router=0)
        with pytest.raises(FileSizeLimitsError, match="router"):
            validate_limits(bad)

    def test_non_int_limit_is_rejected(self) -> None:
        bad = dict(_EXPECTED_LIMITS, models="200")
        with pytest.raises(FileSizeLimitsError, match="models"):
            validate_limits(bad)


# ---------------------------------------------------------------------------
# Classification predicates (the single reconciliation)
# ---------------------------------------------------------------------------


class TestClassifyPredicates:
    """Every predicate branch of the unified classifier, with near-misses."""

    def _assert(self, rel_path: str, category: str, limit: int) -> None:
        assert classify(rel_path, _EXPECTED_LIMITS) == (category, limit)

    # test — first-match priority, wins over every suffix/prefix rule
    def test_test_prefix_first(self) -> None:
        self._assert("tests/unit/x/test_export_service.py", "test", 400)

    def test_test_prefix_wins_over_scripts_path(self) -> None:
        self._assert("scripts/test_assertion_audit/test_x.py", "test", 400)

    # script — path-based, applies to any filename under scripts/
    def test_scripts_path(self) -> None:
        self._assert("scripts/check_architecture.py", "script", 600)

    def test_scripts_path_beats_models_name(self) -> None:
        self._assert("scripts/test_assertion_audit/models.py", "script", 600)

    # router — precise py-gate predicate; plural/gerund near-misses are general
    def test_router_exact(self) -> None:
        self._assert("apps/api/narrare/chat/router.py", "router", 150)

    def test_router_prefix(self) -> None:
        self._assert("apps/api/narrare/writing/router_drafts.py", "router", 150)

    def test_routers_py_is_general_not_router(self) -> None:
        self._assert("apps/api/narrare/routers.py", "general", 400)

    def test_routering_py_is_general_not_router(self) -> None:
        self._assert("apps/api/narrare/routering.py", "general", 400)

    # dependency
    def test_deps_exact(self) -> None:
        self._assert("apps/api/narrare/writing/deps.py", "dependency", 200)

    def test_dependencies_exact(self) -> None:
        self._assert("apps/api/narrare/series/dependencies.py", "dependency", 200)

    def test_deps_prefix(self) -> None:
        self._assert("apps/api/narrare/writing/deps_kb.py", "dependency", 200)

    # service
    def test_service_exact(self) -> None:
        self._assert("apps/api/narrare/writing/service.py", "service", 300)

    def test_service_suffix(self) -> None:
        self._assert("apps/api/narrare/writing/draft_service.py", "service", 300)

    # agent — suffix predicate; an ``agent_*`` prefix is NOT the category
    def test_agent_exact(self) -> None:
        self._assert("packages/core/narrare_core/wiki/agent.py", "agent", 200)

    def test_agent_suffix(self) -> None:
        self._assert("packages/core/narrare_core/wiki/wiki_agent.py", "agent", 200)

    def test_agent_prefix_is_general(self) -> None:
        self._assert("packages/core/narrare_core/wiki/agent_chapter.py", "general", 400)

    # config_schema — py-gate predicate (config/settings joined schemas at 200)
    def test_config_exact(self) -> None:
        self._assert("apps/api/narrare/_app/config.py", "config_schema", 200)

    def test_settings_exact(self) -> None:
        self._assert("packages/core/narrare_core/settings.py", "config_schema", 200)

    def test_schemas_exact(self) -> None:
        self._assert("apps/api/narrare/kb/schemas.py", "config_schema", 200)

    def test_schemas_suffix(self) -> None:
        self._assert("apps/api/narrare/writing/schemas.py", "config_schema", 200)

    def test_schemas_suffix_compound(self) -> None:
        self._assert("apps/api/narrare/planning/timeline_schemas.py", "config_schema", 200)

    # models — pyproject per-path entry (200) is the authority
    def test_models_exact(self) -> None:
        self._assert("evals/models.py", "models", 200)

    # repository — arch-only category retained at its stricter limit
    def test_repository_exact(self) -> None:
        self._assert("apps/api/narrare/writing/repository.py", "repository", 250)

    def test_repository_suffix(self) -> None:
        self._assert("tests/fakes/fake_chapter_repo.py", "repository", 250)

    # contracts / gateway / composer — arch-only categories retained
    def test_contracts_exact(self) -> None:
        self._assert("apps/api/narrare/writing/contracts.py", "contracts", 200)

    def test_gateway_exact(self) -> None:
        self._assert("packages/core/narrare_core/llm/gateway.py", "gateway", 300)

    def test_composer_exact(self) -> None:
        self._assert("packages/core/narrare_core/prompts/composer.py", "composer", 250)

    # general — everything else
    def test_plain_module_is_general(self) -> None:
        self._assert("apps/api/narrare/main.py", "general", 400)

    def test_router_like_plural_is_general(self) -> None:
        self._assert("apps/api/narrare/routing.py", "general", 400)


class TestClassifyExplicitLimitsValidation:
    """Explicit tables are validated too — no silent per-key fallbacks."""

    def test_partial_explicit_table_raises(self) -> None:
        partial = {"test": 400}
        with pytest.raises(FileSizeLimitsError, match="script"):
            classify("apps/api/narrare/main.py", partial)

    def test_empty_table_means_no_override(self) -> None:
        """``{}`` is "no override" — the validated pyproject SSOT applies
        (a genuinely absent table still fails loudly inside load_limits)."""
        assert classify("apps/api/narrare/main.py", {}) == ("general", 400)

    def test_default_uses_validated_pyproject_table(self) -> None:
        """limits=None loads the pyproject SSOT (validated complete)."""
        category, limit = classify("apps/api/narrare/main.py")
        assert category == "general"
        assert limit == 400

    def test_full_table_with_override_is_applied(self) -> None:
        limits = dict(_EXPECTED_LIMITS, test=320)
        assert classify("tests/unit/x/test_export_service.py", limits) == ("test", 320)
