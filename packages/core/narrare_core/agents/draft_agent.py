"""DraftAgent — NarrareAgent für Kapitel-Draft-Generierung.

Post-processing (artifact removal, markdown normalisation, word-target
enforcement) lives in the ADR-035 output validator ``_validate_output``
(deterministic, at the agent boundary) — see ADR-015 Phase 2.2.

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
from narrare_core.agents.draft_types import DraftDeps, DraftOutput
from narrare_core.agents.draft_validators import validate_draft_output
from narrare_core.writing.draft_processor import DraftProcessor

if TYPE_CHECKING:
    from narrare_core.agents.kb_agent import KBAgent


class DraftAgent(NarrareAgent[DraftDeps, DraftOutput]):
    """Agent für Kapitel-Draft-Generierung.

    Features:
    - Output validator: Post-Processing (Artifact-Removal, Markdown-Normalisierung,
      Wortzahl-Target-Enforcement) + ADR-035 Invarianten
    - Tool: KB-Kontext-Abfrage (über ContextAssembler)
    - Capabilities: ToolSearch + KB-Tools (über KBAgent)
    """

    def __init__(
        self,
        model: Any,
        word_target: int | None = None,
        kb_agent: KBAgent | None = None,  # NEU in Phase 3
        system_prompt: str | None = None,
    ) -> None:
        self._word_target = word_target
        self._draft_processor = DraftProcessor()
        self._kb_agent = kb_agent

        # Capabilities bauen: ToolSearch + KB-Tools wenn KBAgent verfügbar
        capabilities: list[Any] = []
        if kb_agent is not None:
            capabilities.append(ToolSearch(strategy="keywords"))
            capabilities.append(Toolset(kb_agent.get_toolset()))

        super().__init__(
            model=model,
            deps_type=DraftDeps,
            output_type=DraftOutput,
            capabilities=capabilities,
            system_prompt=system_prompt,
        )

        self._agent.output_validator(self._validate_output)

        # Tools nach Super-Konstruktor registrieren
        self._agent.tool(self.get_kb_context)

    # ------------------------------------------------------------------
    # Output validator: Post-Processing + Invarianten
    # ------------------------------------------------------------------

    async def _validate_output(
        self,
        ctx: RunContext[DraftDeps],
        output: DraftOutput,
    ) -> DraftOutput:
        """Post-process and validate the draft output.

        Takes over the deterministic post-processing formerly done by the
        deleted output function (see ADR-015 Phase 2.2):
        1. Artifact-Removal
        2. Markdown-Normalisierung
        3. Wortzahl-Berechnung und Target-Enforcement

        Then delegates to :func:`validate_draft_output` for the ADR-035
        module-level invariants (non-empty text, valid scene_breaks,
        word-count match).
        """
        cleaned = self._draft_processor.strip_artifacts(output.text)
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

        processed = output.model_copy(update={"text": normalized, "word_count": word_count})
        return await validate_draft_output(ctx, processed)

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
        return await super().run(prompt, deps, **kwargs)
