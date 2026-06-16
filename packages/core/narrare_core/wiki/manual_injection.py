"""Manual-injection declarations for wiki agent calls (ADR-048 Mode 2).

WikiGenerationAgent and WikiChapterGenerator compose their prompts internally
via WikiPromptLoader. These declarations are the typed evidence trail per
ADR-045 Decision 3 Option C and ADR-048.
"""

from narrare_core.ai_invocation import ManualInjectionDeclaration

WIKI_ENTITY_GENERATION_MANUAL_INJECTION = ManualInjectionDeclaration(
    reason=(
        "WikiGenerationAgent composes its entity prompt internally from "
        "WikiGenerationDeps via WikiPromptLoader. The service delegates to "
        "agent.generate_entity() which loads and renders bundled wiki prompts."
    ),
    variables=("entity_body", "entity_metadata", "relationships", "chapter_context"),
    injection_mechanism="agent_deps",
    precedence_level="generated_suggestion",
)

WIKI_CHAPTER_GENERATION_MANUAL_INJECTION = ManualInjectionDeclaration(
    reason=(
        "WikiChapterGenerator composes its chapter prompt internally from "
        "WikiGenerationDeps via WikiPromptLoader. The service delegates to "
        "agent.generate_chapter() which loads and renders bundled wiki prompts."
    ),
    variables=("entity_body", "chapter_context"),
    injection_mechanism="agent_deps",
    precedence_level="generated_suggestion",
)
