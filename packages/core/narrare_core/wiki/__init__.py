"""LLM Wiki — Precomputed Context Layer.

Domain types, protocols, agent, and service for the Wiki subsystem.
See ADR-022 for architecture context.

WikiGenerationAgent is intentionally NOT exported from ``agents/__init__.py``
because it is primarily used internally by WikiService. The agent module
is accessible via ``narrare_core.wiki.agent`` for direct use when needed.
"""

from narrare_core.wiki.agent import WikiGenerationAgent
from narrare_core.wiki.contracts import WikiAgentProtocol, WikiServiceProtocol
from narrare_core.wiki.prompt_loader import WikiPromptLoader
from narrare_core.wiki.service import WikiService
from narrare_core.wiki.types import (
    WikiChapterOutput,
    WikiChapterSummaryData,
    WikiEntityOutput,
    WikiGenerationDeps,
    WikiSummaryData,
    WikiSummaryStatus,
)

__all__ = [
    "WikiAgentProtocol",
    "WikiChapterOutput",
    "WikiChapterSummaryData",
    "WikiEntityOutput",
    "WikiGenerationAgent",
    "WikiGenerationDeps",
    "WikiPromptLoader",
    "WikiService",
    "WikiServiceProtocol",
    "WikiSummaryData",
    "WikiSummaryStatus",
]
