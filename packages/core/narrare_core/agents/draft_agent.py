"""DraftAgent — NarrareAgent für Kapitel-Draft-Generierung.

Ersetzt den bisherigen DraftProcessor durch eine Output Function
im pydantic-ai Agent-Modell (siehe ADR-015 Phase 2.2).

Usage:
    model = await registry.get_model(config)
    agent = DraftAgent(model=model)
    deps = DraftDeps(
        context_assembler=context_assembler,
    )
    result = await agent.run(prompt=prompt, deps=deps)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic_ai import RunContext  # noqa: TC002 — needed at runtime by pydantic_ai internals
from pydantic_ai.capabilities import ToolSearch, Toolset
from pydantic_ai.exceptions import ModelRetry

from narrare_core.agents.base import NarrareAgent
from narrare_core.agents.draft_types import DraftOutput
from narrare_core.writing.draft_processor import DraftProcessor

if TYPE_CHECKING:
    from narrare_core.agents.kb_agent import KBAgent
    from narrare_core.writing.context_assembler import WritingContextAssembler


class DraftDeps:
    """Dependencies for DraftAgent.

    Attributes:
        context_assembler: Provides 5-tier context assembly for writing.
        preference_service: User preferences for style, tone, etc. (Phase 3+).
    """

    def __init__(
        self,
        context_assembler: WritingContextAssembler | None = None,
    ) -> None:
        self.context_assembler = context_assembler


class DraftAgent(NarrareAgent[DraftDeps, DraftOutput]):
    """Agent für Kapitel-Draft-Generierung mit Output Function.

    Features:
    - Output Function: Post-Processing (Artifact-Removal, Markdown-Normalisierung)
    - Tool: KB-Kontext-Abfrage (über ContextAssembler)
    - Capabilities: ToolSearch + KB-Tools (über KBAgent)
    - Validator: Qualitäts-Check (Mindestwortzahl) via ``ModelRetry``
    """

    def __init__(
        self,
        model: Any,
        word_target: int | None = None,
        kb_agent: KBAgent | None = None,  # NEU in Phase 3
    ) -> None:
        self._word_target = word_target
        self._draft_processor = DraftProcessor()
        self._kb_agent = kb_agent

        # Capabilities bauen: ToolSearch + KB-Tools wenn KBAgent verfügbar
        capabilities: list[Any] = []
        if kb_agent is not None:
            capabilities.append(ToolSearch(strategy="keywords"))
            capabilities.append(Toolset(kb_agent.get_toolset()))

        # output_type als Sequence: Output Function + Fallback-Typ
        # Der Callable wird als Output-Tool registriert, den das Modell
        # mit Parametern (text, title) aufrufen kann.
        super().__init__(
            model=model,
            deps_type=DraftDeps,
            output_type=[self._process_draft_output, DraftOutput],
            capabilities=capabilities,
            system_prompt=(
                "You are a creative writing assistant. Generate chapter content "
                "that is engaging, well-structured, and matches the provided context. "
                "You may use the knowledge base tools to look up characters, locations, "
                "and other story elements when you need details."
            ),
        )

        # Tools nach Super-Konstruktor registrieren
        self._agent.tool(self.get_kb_context)

    # ------------------------------------------------------------------
    # Output Function
    # ------------------------------------------------------------------

    async def _process_draft_output(
        self,
        ctx: RunContext[DraftDeps],
        text: str,
        title: str | None = None,
    ) -> DraftOutput:
        """Output Function — Post-Processing + Validierung.

        Führt die Logik des bisherigen ``DraftProcessor`` aus:
        1. Artifact-Removal
        2. Markdown-Normalisierung
        3. Wortzahl-Berechnung und Target-Enforcement

        Bei Streaming (``ctx.partial_output``) wird nur minimal verarbeitet.
        """
        if ctx.partial_output:
            return DraftOutput(text=text)

        # Vollständige Verarbeitung nur beim finalen Output
        cleaned = self._draft_processor.strip_artifacts(text)
        normalized = self._draft_processor.normalise_markdown(cleaned)

        if self._word_target is not None:
            normalized = self._draft_processor.enforce_word_target(normalized, self._word_target)

        word_count = len(normalized.split())

        # Validierung: Mindestwortzahl prüfen
        if self._word_target is not None and word_count < int(self._word_target * 0.5):
            raise ModelRetry(
                f"Output too short ({word_count} words, expected ~{self._word_target}). "
                "Please generate more content."
            )

        return DraftOutput(
            text=normalized,
            title=title,
            word_count=word_count,
        )

    # ------------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------------

    async def get_kb_context(
        self,
        ctx: RunContext[DraftDeps],
        entity_names: list[str],
    ) -> str:
        """Tool: Hole KB-Kontext für die genannten Entitäten.

        Wird vom Modell gerufen, wenn es Details zu Charakteren,
        Orten oder anderen Story-Elementen benötigt.
        """
        if not entity_names:
            return "No entity names provided."

        assembler = ctx.deps.context_assembler if ctx.deps else None
        if assembler is None:
            return "No context assembler available."

        # Build a summary of requested entity names.
        # Full KB lookup happens via KBAgent tools (ToolSearch + Toolset).
        # This tool provides a fallback when KBAgent is not wired up.
        names = ", ".join(entity_names)
        return (
            f"Requested context for: {names}."
            " Use search_kb or get_entity tools for detailed lookup."
        )

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    async def run(
        self,
        prompt: str,
        deps: DraftDeps,
        **kwargs: Any,
    ) -> DraftOutput:
        """Execute the draft agent and return structured output."""
        result = await self._agent.run(prompt, deps=deps, **kwargs)
        return result.output  # type: ignore[return-value]
