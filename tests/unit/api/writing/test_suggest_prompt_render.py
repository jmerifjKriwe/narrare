"""Render-level tests for the inline_suggest composed prompt (R2 Slice B').

Before R2-B' (2026-09-11): the inline_suggest template's rogue ``## Do NOT``
level-2 header truncated the System Prompt at parse time (extract_section
boundary), so Story Context, the KB blocks, Dialogue Awareness and the
XML-wrapped {{text_before}}/{{text_after}} cursor blocks never rendered.
The service mapped ``text_before`` → ``author_instructions`` instead, and
the composer's L170 fallback passed the RAW manuscript text through the
user channel — bypassing the template's XML injection defense (RULE-22 §6).

R2-B' demotes the header (template v2.4.0 → v2.5.0) and rewires the service:
``text_before``/``text_after`` are supplied as extra variables so the
governed template renders them XML-wrapped in the SYSTEM channel;
``kb_characters`` renders empty (lean ruling — no KB assembly on the
<500 ms suggest path); the ``author_instructions`` mapping is removed so
the raw manuscript text no longer duplicates into the user channel.

Methodology mirrors ``test_draft_prompt_kb_enrichment.py``: the exact
PromptContext the fixed service builds is composed through the REAL
``PromptRegistry`` + ``PromptComposer``. The service-level wiring is
pinned separately in ``test_suggest_inline.py`` to guard against drift
between this builder and the production construction.
"""

from __future__ import annotations

from uuid import uuid4

from narrare_core.llm.intents import LLMIntent
from narrare_core.prompts.composer import ComposedPrompt, PromptComposer
from narrare_core.prompts.context import PromptContext
from narrare_core.prompts.registry import PromptRegistry

_SENTINEL_BEFORE = "The old house stood at the edge of the cliff, its windows dark."
_SENTINEL_AFTER = "Rain hammered the tiles above her."


def _service_context(
    text_before: str,
    text_after: str | None,
) -> PromptContext:
    """Exact PromptContext the R2-B' suggest_service builds (lean ruling)."""
    return PromptContext(
        language="en",
        mode="inline_suggest",
        extra={
            "user_id": str(uuid4()),
            "chapter_id": str(uuid4()),
            "text_before": text_before,
            "text_after": text_after or "",
            "chapter_context": "Chapter: Test Chapter",
            "kb_characters": "",
        },
    )


async def _compose(text_before: str, text_after: str | None) -> ComposedPrompt:
    """Compose the inline_suggest prompt via the real registry + composer."""
    composer = PromptComposer(PromptRegistry())
    return await composer.build(LLMIntent.SUGGEST, _service_context(text_before, text_after))


class TestSuggestPromptRender:
    """R2-B': the full inline_suggest system prompt renders + is injection-safe."""

    async def test_system_contains_xml_wrapped_text_before_sentinel(self) -> None:
        """(a) text_before renders XML-wrapped in the SYSTEM channel."""
        prompt = await _compose(_SENTINEL_BEFORE, _SENTINEL_AFTER)
        assert (
            f'<user_provided_text role="before_cursor">{_SENTINEL_BEFORE}'
            "</user_provided_text>" in prompt.system
        )

    async def test_system_contains_after_cursor_block(self) -> None:
        """(a) text_after renders XML-wrapped after the before_cursor block."""
        prompt = await _compose(_SENTINEL_BEFORE, _SENTINEL_AFTER)
        assert (
            f'<user_provided_text role="after_cursor">{_SENTINEL_AFTER}'
            "</user_provided_text>" in prompt.system
        )
        before_idx = prompt.system.index('role="before_cursor"')
        after_idx = prompt.system.index('role="after_cursor"')
        assert before_idx < after_idx

    async def test_user_channel_does_not_contain_raw_text_before(self) -> None:
        """(b) Un-mapping pin: composer L170 fallback yields an empty user
        channel — the raw manuscript text must NOT duplicate there."""
        prompt = await _compose(_SENTINEL_BEFORE, _SENTINEL_AFTER)
        assert prompt.user == ""
        assert _SENTINEL_BEFORE not in prompt.user

    async def test_system_renders_demoted_region_sections(self) -> None:
        """(c) Story Context, Characters and Dialogue Awareness render —
        proof the demoted tail region is inside the parsed System Prompt."""
        prompt = await _compose(_SENTINEL_BEFORE, _SENTINEL_AFTER)
        for section in (
            "### Story Context",
            "### Characters",
            "### Dialogue Awareness",
            "### Do NOT",
        ):
            assert section in prompt.system

    async def test_empty_text_after_renders_empty_after_cursor_wrapper(self) -> None:
        """(d) Honest degradation pin: with no text_after the wrapper still
        renders EMPTY (substitution is as-is; the engine never drops the
        template-level XML tags). Production text_before is never empty
        (validate_suggest), so only the after-side can be empty."""
        prompt = await _compose(_SENTINEL_BEFORE, None)
        assert '<user_provided_text role="after_cursor"></user_provided_text>' in prompt.system
