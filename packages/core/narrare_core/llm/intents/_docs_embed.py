"""Verbatim intent documentation — Embeddings category.

Full original docstring text for the embedding intent, which is handled
separately from the model routing cascade. Aggregated into
:data:`narrare_core.llm.intents.INTENT_DOCS`.

Split out of the former monolithic ``intents.py`` per RULE-04. The text
here is preserved word-for-word from the original member docstring.
"""

from __future__ import annotations

from narrare_core.llm.intents._enums import LLMIntent

EMBED_INTENT_DOCS: dict[LLMIntent, str] = {
    LLMIntent.EMBED: """\
Text embedding (not routed via gateway).

Scope: Generate vector embeddings for text. Handled entirely by
core/embeddings/ — does NOT go through the model routing cascade
or the LLM gateway.
Input: Text to embed.
Output: Vector embedding.
NOT: Routed through gateway. NOT: An LLM intent in the traditional sense.
""",
}
