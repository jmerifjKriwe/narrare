"""Route + runtime-adoption tests for the governed scene-plan PLAN modes (PLAN-001 T7).

Two new ADR-049 D11 context modes on ``LLMIntent.PLAN`` (ADR-096 / spec §6.1):
``scene_plan_draft`` (chapter-level proposal of N scenes) and
``scene_plan_refine`` (single-scene constrained rewrite). Templates are
EN-only (planning convention); chapter/scene data is category-3 run-prompt
data — never templated (spec §6.2).

INFRA-013 runtime evidence (spec §10): each mode must compose through the
REAL PromptComposer cascade (route table → registry → variable engine), and
the resolved route — template path + frontmatter version — is recorded in
the test output. Static manifest presence alone is insufficient.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, ClassVar

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from narrare_core.llm.intents import LLMIntent
from narrare_core.prompts.composer import PromptComposer
from narrare_core.prompts.context import PromptContext
from narrare_core.prompts.registry import PromptRegistry
from narrare_core.prompts.route_table import ROUTE_CONFIGS
from narrare_core.prompts.routes import resolve_prompt_route
from narrare_core.shared.errors import PromptRouteNotConfiguredError
from narrare_core.shared.frontmatter import parse_frontmatter
from tests.unit.core._bundled import bundled_prompts_root

# Distinctive role markers — prove the RIGHT template rendered per mode.
_DRAFT_MARKER = "story structure planner"
_REFINE_MARKER = "scene refinement specialist"

# Distinctive task markers from each template's Instructions/Output Format.
# (RUF001: the en dash is intentional — the marker must match the template text.)
_DRAFT_GUIDANCE = "3–8 scenes"  # noqa: RUF001
_DRAFT_CHANGE_RULE = "each scene must change something"
_REFINE_SINGLE_RULE = "exactly one scene object"

# Output-contract field names shared by both templates (SceneProposal shape,
# 8 fields — review round 1 finding 1: "title" was missing).
_PROPOSAL_FIELDS = (
    "title",
    "pov_character_name",
    "location_name",
    "present_characters",
    "purpose",
    "conflict",
    "resolution",
    "beats",
)

_MODES = ("scene_plan_draft", "scene_plan_refine")
_ROLE_MARKERS: dict[str, str] = {
    "scene_plan_draft": _DRAFT_MARKER,
    "scene_plan_refine": _REFINE_MARKER,
}
_PLACEHOLDER_RE = re.compile(r"\{\{(\w+)\}\}")


def _template_path(mode: str) -> Path:
    return bundled_prompts_root() / "planning" / "en" / mode / "system.md"


def _route_context(mode: str) -> PromptContext:
    """Governed PLAN route context mirroring the service seam (spec §6.2).

    No required template variables: ``project_title`` / ``genre`` /
    ``writing_language`` are optional template data; chapter/scene data
    arrives as category-3 XML-wrapped run-prompt data, never templated.
    """
    return PromptContext(language="en", mode=mode)


class TestScenePlanRouteGovernance:
    """ADR-096 §6.1 — the two modes are governed PLAN context routes."""

    @pytest.mark.parametrize("mode", _MODES)
    def test_mode_is_routeable(self, mode: str) -> None:
        route = resolve_prompt_route(LLMIntent.PLAN, context_mode=mode)
        assert route.category == "planning"
        assert route.mode == mode

    def test_allowed_context_modes_include_scene_plan_modes(self) -> None:
        modes = ROUTE_CONFIGS[LLMIntent.PLAN].allowed_context_modes
        assert {"scene_plan_draft", "scene_plan_refine"} <= set(modes)

    def test_ungoverned_mode_still_rejected(self) -> None:
        with pytest.raises(PromptRouteNotConfiguredError):
            resolve_prompt_route(LLMIntent.PLAN, context_mode="scene_plan")


class TestScenePlanRuntimeAdoption:
    """INFRA-013 — runtime evidence via the real composer cascade (EN)."""

    @pytest.mark.parametrize("mode", _MODES)
    async def test_composer_build_succeeds_and_records_resolved_route(self, mode: str) -> None:
        """Each mode composes through the real cascade; the resolved route
        (bundled template path + prompt_version) is recorded as runtime
        evidence in the test output."""
        prompt = await PromptComposer(PromptRegistry()).build(LLMIntent.PLAN, _route_context(mode))
        assert prompt.system.strip(), f"empty system prompt for {mode}"

        resolved = await PromptRegistry().resolve(category="planning", language="en", mode=mode)
        print(
            f"[INFRA-013] PLAN/{mode} -> {_template_path(mode)} "
            f"(source={resolved.source}, "
            f"prompt_version={resolved.metadata.get('prompt_version')})"
        )
        assert resolved.source == "bundled"
        assert str(resolved.metadata.get("prompt_version")) == "1.0.0"
        assert _template_path(mode).is_file()

    async def test_draft_composed_system_carries_task_markers(self) -> None:
        prompt = await PromptComposer(PromptRegistry()).build(
            LLMIntent.PLAN, _route_context("scene_plan_draft")
        )
        assert _DRAFT_MARKER in prompt.system.lower()
        assert _DRAFT_GUIDANCE in prompt.system
        assert _DRAFT_CHANGE_RULE in prompt.system.lower()
        for field in _PROPOSAL_FIELDS:
            assert field in prompt.system, f"draft output contract missing {field!r}"

    async def test_refine_composed_system_carries_task_markers(self) -> None:
        prompt = await PromptComposer(PromptRegistry()).build(
            LLMIntent.PLAN, _route_context("scene_plan_refine")
        )
        assert _REFINE_MARKER in prompt.system.lower()
        assert _REFINE_SINGLE_RULE in prompt.system.lower()
        for field in _PROPOSAL_FIELDS:
            assert field in prompt.system, f"refine output contract missing {field!r}"

    @pytest.mark.parametrize("mode", _MODES)
    async def test_bare_context_composes_without_required_variables(self, mode: str) -> None:
        """No required template variables: a context with every optional
        variable at its dataclass default composes without
        PromptVariableError and leaves zero placeholder residue."""
        prompt = await PromptComposer(PromptRegistry()).build(LLMIntent.PLAN, _route_context(mode))
        assert "{{" not in prompt.system, "placeholder residue in render"


class TestScenePlanTemplateGovernance:
    """PROMPT-L2-HEADERS + frontmatter house contract (planning category)."""

    _CASES: ClassVar[list[str]] = list(_MODES)

    @pytest.mark.parametrize("mode", _CASES)
    def test_source_has_only_system_prompt_l2_header(self, mode: str) -> None:
        """After frontmatter, the only ``^## `` line is ``## System Prompt``."""
        body = parse_frontmatter(_template_path(mode).read_text(encoding="utf-8")).content
        l2_lines = [ln for ln in body.splitlines() if ln.startswith("## ")]
        assert l2_lines == ["## System Prompt"]

    @pytest.mark.parametrize("mode", _CASES)
    def test_frontmatter_matches_planning_category(self, mode: str) -> None:
        parsed = parse_frontmatter(_template_path(mode).read_text(encoding="utf-8"))
        assert parsed.metadata.get("prompt_type") == "planning"
        assert parsed.metadata.get("prompt_language") == "en"
        assert parsed.metadata.get("prompt_version") == "1.0.0"

    # Planning-category optional context variables (temporal_consistency
    # pattern): the metadata triple plus the three adaptive context slots the
    # prompt-structure gate mandates for category 'planning'
    # (check_prompt_structure.py REQUIRED_VARS_BY_CATEGORY:
    # culture_guidelines = composer seam, user_preferences /
    # avoidance_patterns = PromptContext dataclass fields). All six are
    # declared optional in the prompt-surface manifest entries.
    _ALLOWED_TEMPLATE_VARS: ClassVar[frozenset[str]] = frozenset(
        {
            "project_title",
            "genre",
            "writing_language",
            "culture_guidelines",
            "user_preferences",
            "avoidance_patterns",
        }
    )

    @pytest.mark.parametrize("mode", _CASES)
    def test_template_declares_only_optional_context_variables(self, mode: str) -> None:
        """Spec §6.2 — every template placeholder is a governed optional
        context variable (temporal_consistency pattern): the metadata triple
        plus the planning-category adaptive context slots. Chapter/scene data
        stays category-3 run-prompt data — never templated."""
        body = parse_frontmatter(_template_path(mode).read_text(encoding="utf-8")).content
        placeholders = set(_PLACEHOLDER_RE.findall(body))
        assert placeholders <= self._ALLOWED_TEMPLATE_VARS


class TestScenePlanLocaleFallback:
    """Planning templates are EN-only: non-English locales fall back to the
    bundled EN template (registry cascade convention)."""

    @pytest.mark.parametrize("mode", _MODES)
    async def test_non_english_locale_falls_back_to_bundled_en(self, mode: str) -> None:
        resolved = await PromptRegistry().resolve(category="planning", language="de", mode=mode)
        assert resolved.source == "bundled_en"
        assert resolved.system_prompt.strip()
        assert _ROLE_MARKERS[mode] in resolved.system_prompt.lower()
