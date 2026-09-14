"""Render-level tests for the beta_reader_deepdive composed prompt (R2 Slice 2, D+X).

Before R2 Slice 2 (2026-09-12): the beta_reader_deepdive template's rogue
level-2 headers (## Deep-Dive Category L11, ## Previous Analysis Summary L15,
## Chapter Text L23, ## Instructions L49, ## Output Format L62, ## Do NOT
L87, ## Quality Rules L94) truncated the System Prompt at parse time
(extract_section boundary) — the live system prompt was the single intro
paragraph only; instructions, output contract, and quality rules never
rendered.

R2 Slice 2 is a D+X hybrid (demote + delete), same family as the landed
beta_reader Slice 1:

* DEMOTE the zero-placeholder craft sections (Instructions, Output Format,
  Do NOT, Quality Rules) to level-3 so they render (children shift:
  Constraints → level-4).
* DELETE the placeholder blocks (deepdive_category, phase1_strengths_summary,
  phase1_feedback_summary, chapter_text, kb_characters, kb_locations,
  kb_factions, kb_relationships, category_focus_instructions) — dead
  duplicates of the user channel built by ``build_deepdive_prompt`` from
  ``BetaReaderDeps`` (``deep_dive_deps`` in beta_reader_context.py sets
  deepdive_category / phase1_* ; the mapper renders them as user-message
  parts). Naive demotion alone would raise PromptVariableError: the compose
  context is bare (``PromptContext(language, mode, project_title="")`` —
  ``_invocation_compose.py``), BETA_READ declares ZERO optional variables,
  and none of those nine names is a PromptContext field.
  ``category_focus_instructions`` additionally had NO runtime supplier at
  all. The ``For the category "{{deepdive_category}}"`` lead line is reworded
  to point at the user message, mirroring Slice 1's genre convention.

Pruned with the blocks (variable_registry.py SYSTEM_VARS): deepdive_category,
phase1_strengths_summary, phase1_feedback_summary, category_focus_instructions
— the three former used exclusively by the deleted blocks (deps fields are
user-channel data, outside the registry), the latter never supplied anywhere.
chapter_text / kb_* stay registered (USER_CONTENT hygiene per Slice 1's kept
pin / live in 24+ other templates).

The user-channel path (build_deepdive_prompt / deep_dive_deps /
beta_reader_mapper) is untouched and remains the sole supplier of chapter,
Phase 1, and KB runtime data.
"""

from __future__ import annotations

from narrare_core.llm.intents import LLMIntent
from narrare_core.prompts.composer import PromptComposer
from narrare_core.prompts.context import PromptContext
from narrare_core.prompts.registry import PromptRegistry
from narrare_core.prompts.variable_registry import is_registered_variable
from narrare_core.shared.frontmatter import parse_frontmatter
from tests.unit.core._bundled import bundled_prompts_root

# The nine placeholder blocks deleted from the template — each was a dead
# duplicate of the user channel (or, for category_focus_instructions, had no
# supplier at all).
_DELETED_PLACEHOLDER_VARS = (
    "deepdive_category",
    "phase1_strengths_summary",
    "phase1_feedback_summary",
    "chapter_text",
    "kb_characters",
    "kb_locations",
    "kb_factions",
    "kb_relationships",
    "category_focus_instructions",
)

# Exact header lines of the deleted blocks (must vanish line-exact — note
# the kept "### User Preferences" must NOT match the deleted KB children).
_DELETED_BLOCK_HEADERS = (
    "## Deep-Dive Category",
    "## Previous Analysis Summary",
    "## Chapter Text",
    "### Knowledge Base Context",
    "### Category-Specific Focus",
)

# Registry entries pruned with the deleted blocks (exclusive usage / no
# supplier).
_PRUNED_REGISTRY_VARS = (
    "deepdive_category",
    "phase1_strengths_summary",
    "phase1_feedback_summary",
    "category_focus_instructions",
)

# Registry entries that must survive the prune (user-content hygiene per the
# landed Slice 1 pin, or live in many other templates).
_KEPT_REGISTRY_VARS = (
    "chapter_text",
    "kb_characters",
    "kb_locations",
    "kb_factions",
    "kb_relationships",
)

_PREF_SENTINEL = "PREF: prefers concrete line edits over abstract notes."
_AVOID_SENTINEL = "AVOID: no dream sequences, no head-hopping."


def _prompt_path():
    return bundled_prompts_root() / "analysis" / "en" / "beta_reader_deepdive" / "system.md"


def _bare_context() -> PromptContext:
    """The ``_invocation_compose.py`` shape: bare context, zero optionals."""
    return PromptContext(language="en", mode="beta_reader_deepdive", project_title="")


async def _compose(ctx: PromptContext | None = None):
    """Compose the deep-dive prompt via real registry + composer."""
    return await PromptComposer(PromptRegistry()).build(LLMIntent.BETA_READ, ctx or _bare_context())


class TestDeepdiveHeaderSurgery:
    """R2 Slice 2 (D): the source template has exactly one level-2 header."""

    def test_source_has_only_system_prompt_l2_header(self) -> None:
        """After frontmatter, the only ``^## `` line is ``## System Prompt``."""
        body = parse_frontmatter(_prompt_path().read_text(encoding="utf-8")).content
        l2_lines = [ln for ln in body.splitlines() if ln.startswith("## ")]
        assert l2_lines == ["## System Prompt"]

    async def test_parsed_system_contains_demoted_sections(self) -> None:
        """The registry-parsed System Prompt includes the restored craft
        sections — proof they survive the extract_section boundary."""
        registry = PromptRegistry()
        resolved = await registry.resolve(
            category="analysis", language="en", mode="beta_reader_deepdive"
        )
        for section in (
            "### User Preferences",
            "### Instructions",
            "### Output Format",
            "### Do NOT",
            "### Quality Rules",
            "#### Constraints",
        ):
            assert section in resolved.system_prompt, f"missing {section!r}"

    def test_prompt_version_bumped_to_1_2_0(self) -> None:
        """1.1.0 → 1.2.0: enum/count discipline pins (eval run
        2026-09-14-168945f4-1 found German severity drift + 8 suggestions)."""
        parsed = parse_frontmatter(_prompt_path().read_text(encoding="utf-8"))
        assert parsed.metadata.get("prompt_version") == "1.2.0"


class TestDeepdiveContractPins:
    """2026-09-14 eval follow-up: severity enum + suggestion-count pins.

    Real run ``2026-09-14-168945f4-1`` (German chapter) measured German
    severity drift ("mittel"/"hoch"/"niedrig") and 8 revision_suggestions.
    The template now pins the English enum literals and the 3-6 count —
    the schema-side enforcement (Literal + field_validator) lives in
    ``beta_reader_types.py`` (``test_beta_reader_types.py``).
    """

    async def test_composed_system_pins_english_severity_literals(self) -> None:
        prompt = await _compose()
        for fragment in (
            "### Severity Guidelines",
            "MUST be exactly one of the English words",
            "`critical`, `moderate`, or `minor`",
            "never translate these words",
        ):
            assert fragment in prompt.system, f"missing {fragment!r}"

    async def test_severity_pin_references_writing_language(self) -> None:
        """The pin explicitly overrides the analysis language for the enum."""
        prompt = await _compose()
        assert "even when you write the analysis in {{writing_language}}" not in prompt.system
        assert "even when you write the analysis in en." in prompt.system

    async def test_composed_system_pins_suggestion_count_contract(self) -> None:
        prompt = await _compose()
        for fragment in (
            "MUST contain exactly 3 to 6 suggestions",
            "never more than 6",
        ):
            assert fragment in prompt.system, f"missing {fragment!r}"


class TestDeepdiveContextBlockDeletion:
    """R2 Slice 2 (X): the dead placeholder blocks are gone, not demoted."""

    def test_deleted_placeholder_tokens_absent_from_source(self) -> None:
        content = _prompt_path().read_text(encoding="utf-8")
        for var in _DELETED_PLACEHOLDER_VARS:
            token = "{{" + var + "}}"
            assert token not in content, f"dead placeholder {token} still in template"

    def test_deleted_block_headers_absent_line_exact(self) -> None:
        """The deleted blocks' header lines vanish (line-exact, so the kept
        '### User Preferences' is not a false positive)."""
        body = parse_frontmatter(_prompt_path().read_text(encoding="utf-8")).content
        lines = {ln.strip() for ln in body.splitlines()}
        for header in _DELETED_BLOCK_HEADERS:
            assert header not in lines, f"deleted block header {header!r} still present"

    async def test_composed_system_contains_no_deleted_placeholders(self) -> None:
        """rg-style containment: none of the deleted placeholder tokens
        appear in the composed system prompt."""
        prompt = await _compose()
        for var in _DELETED_PLACEHOLDER_VARS:
            token = "{{" + var + "}}"
            assert token not in prompt.system, f"placeholder {token} leaked into composition"


class TestDeepdiveBareContextCompose:
    """The D+X core contract: the bare invocation context composes cleanly.

    Naive demotion (keeping the placeholder blocks) would raise
    PromptVariableError on deepdive_category — the deletion is what makes
    the restored craft tail reachable with the production compose context.
    """

    async def test_bare_context_compose_succeeds(self) -> None:
        """Bare context (language/mode/project_title='') composes without
        PromptVariableError — mirrors _invocation_compose.py."""
        prompt = await _compose()
        assert "You are providing a focused deep-dive analysis" in prompt.system

    async def test_composed_system_contains_craft_text(self) -> None:
        """Instructions / output-format / do-not / quality-rules content
        reaches the composed system prompt, with the category pointer
        reworded to the user channel."""
        prompt = await _compose()
        for fragment in (
            "### Instructions",
            "For the deep-dive category supplied in the user message, "
            "provide an exhaustive analysis:",
            "### Output Format",
            "Respond with a structured JSON:",
            "### Do NOT",
            "Do NOT rewrite the chapter — analyze and suggest, don't edit",
            "### Quality Rules",
            "Be granular. Reference exact paragraphs, sentences, or phrases.",
            "#### Constraints",
            "Respect the author's avoidance patterns",
        ):
            assert fragment in prompt.system, f"missing {fragment!r}"

    async def test_composed_system_renders_adaptive_fields(self) -> None:
        """user_preferences / avoidance_patterns (PromptContext fields kept
        live by the demotion) render their adaptive values; writing_language
        falls back to the context language."""
        ctx = _bare_context()
        ctx.user_preferences = _PREF_SENTINEL
        ctx.avoidance_patterns = _AVOID_SENTINEL
        prompt = await _compose(ctx)
        assert _PREF_SENTINEL in prompt.system
        assert _AVOID_SENTINEL in prompt.system
        assert "Write analysis in en." in prompt.system


class TestDeepdiveRegistryPrune:
    """The four dead registry entries are pruned; shared ones stay."""

    def test_pruned_vars_unregistered(self) -> None:
        for var in _PRUNED_REGISTRY_VARS:
            assert not is_registered_variable(var), f"{var} should be pruned from the registry"

    def test_kept_vars_still_registered(self) -> None:
        for var in _KEPT_REGISTRY_VARS:
            assert is_registered_variable(var), f"{var} must remain registered"
