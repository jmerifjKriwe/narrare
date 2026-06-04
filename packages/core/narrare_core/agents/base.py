"""NarrareAgent — Basis-Klasse für alle Narrare-Agents.

Stellt sicher:
- Model kommt aus ModelRegistry (nie direkt instantiiert)
- Standard-Capabilities werden immer injected (Observability, UniversalRules, Meta)
- Fehler werden einheitlich klassifiziert

Usage:
    # Direct instantiation (system_prompt from caller — tests, PromptComposer):
    model = await registry.get_model(config)
    agent = MyAgent(model=model, deps_type=MyDeps, output_type=MyOutput)
    result = await agent.run(prompt, deps=MyDeps(...))

The Narrare meta-prompt is always injected via the NarrareMeta Capability
(NarrareAgent adds it to every instance automatically). No need for
with_meta() or manual meta-prompt loading.
"""

from __future__ import annotations

from abc import ABC
from typing import TYPE_CHECKING, Any

from pydantic_ai import Agent

from narrare_core.agents.capabilities import (
    NarrareMeta,
    NarrareObservability,
    NarrareUniversalRules,
)
from narrare_core.agents.history_policy import HistoryPolicy

if TYPE_CHECKING:
    from pydantic_ai.models import Model
    from pydantic_ai.output import OutputSpec


class NarrareAgent[DepsT, OutputT](ABC):  # noqa: B024 — abstract methods in Phase 2+
    """Basis-Klasse für alle Narrare-Agents.

    Stellt sicher:
    - Model kommt aus ModelRegistry (nie direkt instantiiert)
    - Standard-Capabilities werden immer injected:
      * NarrareObservability — Metriken & Logging
      * NarrareUniversalRules — Fiction guidelines, conflict resolution
      * NarrareMeta — Narrare identity, approach, role flexibility
    - Fehler werden einheitlich klassifiziert

    Usage:
        agent = MyAgent(model=model, deps_type=MyDeps, output_type=MyOutput)
        result = await agent.run(prompt, deps=MyDeps(...))
    """

    def __init__(
        self,
        model: Model,
        deps_type: type[DepsT],
        output_type: OutputSpec[OutputT] | None = None,
        capabilities: list[Any] | None = None,
        system_prompt: str | None = None,
        history_policy: HistoryPolicy = HistoryPolicy.NONE,
    ) -> None:
        # Build Agent kwargs: pydantic-ai does not accept None for
        # output_type or system_prompt, so only pass when explicitly set.
        agent_kwargs: dict[str, Any] = {
            "model": model,
            "deps_type": deps_type,
            "capabilities": [
                NarrareObservability(),  # immer
                NarrareUniversalRules(),  # immer — ADR-026 Phase 1
                NarrareMeta(),  # immer — ADR-026 Phase 3
                *(capabilities or []),
            ],
        }
        if output_type is not None:
            agent_kwargs["output_type"] = output_type
        if system_prompt is not None:
            agent_kwargs["system_prompt"] = system_prompt

        self._agent = Agent(**agent_kwargs)
        self._history_policy = history_policy

    @property
    def history_policy(self) -> HistoryPolicy:
        """History policy for this agent (ADR-034).

        Task agents default to NONE (no ProcessHistory).
        Conversational agents declare CONVERSATIONAL explicitly.
        """
        return self._history_policy

    async def run(
        self,
        prompt: str,
        deps: DepsT,
        **kwargs: Any,
    ) -> OutputT:
        """Führe den Agent aus.

        Delegiert an pydantic-ai run() mit Fehlerklassifizierung.
        """
        try:
            result = await self._agent.run(prompt, deps=deps, **kwargs)
            return result.output
        except Exception:
            # Phase 1: Ersetzen durch klassifizierte Fehler
            raise
