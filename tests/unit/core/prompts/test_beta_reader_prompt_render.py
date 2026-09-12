"""Render-level tests for the beta_reader composed prompt (R2 Slice 1, D+X).

Before R2 Slice 1 (2026-09-12): the beta_reader template's rogue level-2
headers (## Analysis Framework L13, ## Context L57, ## Severity Guidelines
L113, ## Output Format L119, ## Quality Rules L172) truncated the System
Prompt at parse time (extract_section boundary) — the live system prompt was
the two intro paragraphs only; the entire craft tail never rendered.

R2 Slice 1 is a D+X hybrid (demote + delete):

* DEMOTE the zero-placeholder craft sections (Analysis Framework, Severity
  Guidelines, Output Format, Quality Rules) to level-3 so they render.
* DELETE the ``## Context`` placeholder blocks (chapter_text, chapter_titles,
  word_count, previous_summaries, kb_characters, kb_locations, kb_factions,
  kb_relationships, genre, focus_categories) — dead duplicates of the user
  channel built by ``build_budgeted_prompt`` (beta_reader_prompt.py). Naive
  demotion alone would raise PromptVariableError: the compose context is bare
  (``PromptContext(language, mode, project_title="")`` —
  ``_invocation_compose.py``), BETA_READ declares ZERO optional variables,
  and none of those ten names is a PromptContext field.

Pruned with the blocks (variable_registry.py SYSTEM_VARS): chapter_titles,
word_count, previous_summaries, focus_categories — used exclusively by the
deleted blocks. kb_* / genre / chapter_text stay registered (live in other
templates / user-content hygiene).

The user-channel budgeted prompt path (build_budgeted_prompt) is untouched
and remains the sole supplier of chapter/KB runtime data.
"""

from __future__ import annotations

from narrare_core.llm.intents import LLMIntent
from narrare_core.prompts.composer import PromptComposer
from narrare_core.prompts.context import PromptContext
from narrare_core.prompts.registry import PromptRegistry
from narrare_core.prompts.variable_registry import is_registered_variable
from narrare_core.shared.frontmatter import parse_frontmatter
from tests.unit.core._bundled import bundled_prompts_root

# The ten placeholder blocks deleted from the ## Context section — each was a
# dead duplicate of the user channel (or, for kb_factions/kb_relationships,
# had no supplier at all).
_DELETED_PLACEHOLDER_VARS = (
    "chapter_text",
    "chapter_titles",
    "word_count",
    "previous_summaries",
    "kb_characters",
    "kb_locations",
    "kb_factions",
    "kb_relationships",
    "genre",
    "focus_categories",
)

# Exact header lines of the deleted blocks (must vanish line-exact — note
# "### Genre" must NOT match the kept "### Genre-Sensitive Assessment").
_DELETED_BLOCK_HEADERS = (
    "### Chapter Text",
    "### Chapter Titles",
    "### Word Count",
    "### Previous Chapter Summaries",
    "### Known Characters (from Knowledge Base)",
    "### Known Locations (from Knowledge Base)",
    "### Known Factions (from Knowledge Base)",
    "### Character Relationships",
    "### Genre",
    "### Focus Categories",
)

# Registry entries pruned with the deleted blocks (exclusive usage).
_PRUNED_REGISTRY_VARS = (
    "chapter_titles",
    "word_count",
    "previous_summaries",
    "focus_categories",
)

# Registry entries that must survive the prune (used by other templates or
# user-content hygiene).
_KEPT_REGISTRY_VARS = (
    "chapter_text",
    "kb_characters",
    "kb_locations",
    "kb_factions",
    "kb_relationships",
    "genre",
)

_PREF_SENTINEL = "PREF: prefers concrete line edits over abstract notes."
_AVOID_SENTINEL = "AVOID: no dream sequences, no head-hopping."


def _prompt_path():
    return bundled_prompts_root() / "analysis" / "en" / "beta_reader" / "system.md"


def _bare_context() -> PromptContext:
    """The ``_invocation_compose.py`` shape: bare context, zero optionals."""
    return PromptContext(language="en", mode="beta_reader", project_title="")


async def _compose(ctx: PromptContext | None = None):
    """Compose the beta_reader prompt via real registry + composer."""
    return await PromptComposer(PromptRegistry()).build(LLMIntent.BETA_READ, ctx or _bare_context())


class TestBetaReaderHeaderSurgery:
    """R2 Slice 1 (D): the source template has exactly one level-2 header."""

    def test_source_has_only_system_prompt_l2_header(self) -> None:
        """After frontmatter, the only ``^## `` line is ``## System Prompt``."""
        body = parse_frontmatter(_prompt_path().read_text(encoding="utf-8")).content
        l2_lines = [ln for ln in body.splitlines() if ln.startswith("## ")]
        assert l2_lines == ["## System Prompt"]

    async def test_parsed_system_contains_demoted_sections(self) -> None:
        """The registry-parsed System Prompt includes the restored craft
        sections — proof they survive the extract_section boundary."""
        registry = PromptRegistry()
        resolved = await registry.resolve(category="analysis", language="en", mode="beta_reader")
        for section in (
            "### Analysis Framework",
            "#### Plot",
            "#### Reader Experience",
            "### Genre-Sensitive Assessment",
            "### Severity Guidelines",
            "### Output Format",
            "#### Do NOT",
            "### Quality Rules",
        ):
            assert section in resolved.system_prompt, f"missing {section!r}"

    def test_prompt_version_bumped_to_1_1_0(self) -> None:
        """Header surgery bumps the template minor version (1.0.0 → 1.1.0)."""
        parsed = parse_frontmatter(_prompt_path().read_text(encoding="utf-8"))
        assert parsed.metadata.get("prompt_version") == "1.1.0"


class TestBetaReaderContextBlockDeletion:
    """R2 Slice 1 (X): the dead placeholder blocks are gone, not demoted."""

    def test_deleted_placeholder_tokens_absent_from_source(self) -> None:
        content = _prompt_path().read_text(encoding="utf-8")
        for var in _DELETED_PLACEHOLDER_VARS:
            token = "{{" + var + "}}"
            assert token not in content, f"dead placeholder {token} still in template"

    def test_deleted_block_headers_absent_line_exact(self) -> None:
        """The deleted blocks' header lines vanish (line-exact, so the kept
        '### Genre-Sensitive Assessment' is not a false positive)."""
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


class TestBetaReaderBareContextCompose:
    """The D+X core contract: the bare invocation context composes cleanly.

    Naive demotion (keeping the Context blocks) would raise
    PromptVariableError on chapter_text — the deletion is what makes the
    restored craft tail reachable with the production compose context.
    """

    async def test_bare_context_compose_succeeds(self) -> None:
        """Bare context (language/mode/project_title='') composes without
        PromptVariableError — mirrors _invocation_compose.py."""
        prompt = await _compose()
        assert "You are an experienced beta reader" in prompt.system

    async def test_composed_system_contains_craft_text(self) -> None:
        """Framework / severity / output-format / quality-rules content
        reaches the composed system prompt."""
        prompt = await _compose()
        for fragment in (
            "### Analysis Framework",
            "Analyze the chapter across these categories:",
            "### Severity Guidelines",
            "Will significantly impair reader experience",
            "### Output Format",
            "Respond with a structured JSON object containing:",
            "#### Do NOT",
            "you are a reader, not an editor",
            "### Quality Rules",
            "Balance honesty with encouragement",
            "### Genre-Sensitive Assessment",
            "A 7 in pacing means different things for a thriller vs. literary fiction.",
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


class TestBetaReaderRegistryPrune:
    """The four exclusively-dead registry entries are pruned; shared ones stay."""

    def test_pruned_vars_unregistered(self) -> None:
        for var in _PRUNED_REGISTRY_VARS:
            assert not is_registered_variable(var), f"{var} should be pruned from the registry"

    def test_kept_vars_still_registered(self) -> None:
        for var in _KEPT_REGISTRY_VARS:
            assert is_registered_variable(var), f"{var} must remain registered"
