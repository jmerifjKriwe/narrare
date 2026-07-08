"""Verbatim intent documentation — Chat operations category.

Full original docstring text (Scope/Input/Output/NOT) for the
conversational writing assistant and research synthesis intents.
Aggregated into :data:`narrare_core.llm.intents.INTENT_DOCS`.

Split out of the former monolithic ``intents.py`` per RULE-04. The text
here is preserved word-for-word from the original member docstrings.
"""

from __future__ import annotations

from narrare_core.llm.intents._enums import LLMIntent

CHAT_INTENT_DOCS: dict[LLMIntent, str] = {
    LLMIntent.CHAT: """\
General story assistant chat.

Scope: Conversational mode. Answers questions about the author's
project, writing craft, worldbuilding, and story structure.
Does NOT generate prose unless explicitly requested. Uses
conversation history for continuity.
Input: {{conversation_history}}, project/KB context, user message.
Output: Conversational response in natural prose.
NOT: Generate chapter prose (use WRITE). NOT: Structured analysis
(use ANALYSE or BETA_READ).
""",
    LLMIntent.RESEARCH: """\
Web research synthesis.

Scope: Synthesize web search results into actionable writing
research. Combines multiple search results into coherent,
story-relevant insights.
Input: Search query, search results, project context.
Output: Synthesized research summary.
NOT: General chat (use CHAT). NOT: Analysis of existing text
(use ANALYSE).
""",
}
