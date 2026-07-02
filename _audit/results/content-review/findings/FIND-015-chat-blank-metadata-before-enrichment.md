# FIND-015 — Chat Composes Project-Aware System Prompt with Blank Metadata Before Enrichment

> **Status:** `identified` (open)
> **Priority:** P1
> **Source:** CR-02 System Prompt (2026-06-30), carried by CR-03, CR-04
> **Related:** CR-AUFG-02-08, CR-AUFG-03-08, CR-AUFG-04-13
> **Lifecycle:** `docs/development/finding-lifecycle.md`

---

## Problem

`ChatService.ask()` builds the chat `PromptContext` with `project_title=""`,
`genre=""`, `language="en"` **before** composing the system prompt via
`PromptComposer.build(LLMIntent.CHAT, ...)`. Later `compose_chat_invocation()`
may return an enriched context for `ChatDeps`, but `ChatAgent` has no dynamic
instructions reading `ChatDeps`; the already-composed
`writing/en/chat/system.md` therefore sees blank/English project metadata and
no post-enrichment KB/preference values.

The free assistant exists and is system-channel compliant (ADR-049 closed
FIND-010), but its "project-aware" system prompt is underfed in production.

## Code References

- **Blank context at composition:** `apps/api/narrare/chat/chat_service.py:122-126` — `build_chat_context(project_title="", genre="", language="en")`.
- **Composition before enrichment:** `chat_service.py:129-133` — `composer.build(LLMIntent.CHAT, context, ...)` immediately after blank context.
- **Enrichment flows to ChatDeps only:** `chat_service.py:180-201`; `apps/api/narrare/chat/_invocation.py:100-152` — `compose_chat_invocation()` returns enriched `PromptContext` but it flows to `ChatDeps`, not back into the already-composed system prompt.
- **ChatDeps not consumed by dynamic instructions:** `packages/core/narrare_core/chat/chat_deps.py:18-33` — no `@agent.instructions` reads `ChatDeps`.
- **Chat prompt template:** `packages/core/narrare_core/prompts/_bundled/writing/en/chat/system.md` — references project title, genre, KB context, preferences that are blank at composition time.

## Impact

- The chat assistant's system prompt promises project-awareness but receives empty project metadata, English language, and no KB/preference context.
- For non-English projects, chat may respond in English despite the project's `writing_language`.
- The assistant cannot leverage KB entries, preferences, or project profile because they arrive after composition.
- This is a runtime-context-ordering gap, not a budget or adoption-infrastructure gap.

## Prioritized Remediation

1. **Populate `PromptContext` with real project data before composition:** fetch project profile, KB summaries, writing language, and preferences before `PromptComposer.build(LLMIntent.CHAT, ...)`.
2. **Or move composition after enrichment:** preserve system/user channel separation while ensuring enriched context reaches the template.
3. **Add regression test:** prove that changing project metadata changes the composed chat system prompt.

## Alternatives Considered

- **Add a global prepend prompt.** Rejected: reintroduces the monolithic anti-pattern ADR-026 removed; bypasses capability/cascade separation.
- **Accept current behavior.** Rejected: the chat prompt template explicitly references project fields that are blank, creating a coherence gap between prompt promise and runtime reality.
