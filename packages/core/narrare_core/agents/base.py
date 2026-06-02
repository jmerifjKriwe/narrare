"""NarrareAgent — Basis-Klasse für alle Narrare-Agents.

Stellt sicher:
- Model kommt aus ModelRegistry (nie direkt instantiiert)
- Standard-Capabilities werden immer injected (z.B. Observability)
- Meta-Prompt wird via with_meta() automatisch geladen
- Fehler werden einheitlich klassifiziert

Usage:
    # Direct instantiation (system_prompt from caller — tests, PromptComposer):
    model = await registry.get_model(config)
    agent = MyAgent(model=model, deps_type=MyDeps, output_type=MyOutput)
    result = await agent.run(prompt, deps=MyDeps(...))

    # With meta-prompt prepended (direct agent use outside PromptComposer):
    from narrare_core.prompts.meta import MetaPromptLoader
    loader = MetaPromptLoader()
    agent = await MyAgent.with_meta(
        model=model, deps_type=MyDeps, output_type=MyOutput,
        meta_loader=loader, meta_variables={"project_title": "My Novel", ...},
    )
    result = await agent.run(prompt, deps=MyDeps(...))
"""

from __future__ import annotations

from abc import ABC
from typing import TYPE_CHECKING, Any

from pydantic_ai import Agent

from narrare_core.agents.capabilities import NarrareObservability, NarrareUniversalRules

if TYPE_CHECKING:
    from pydantic_ai.models import Model
    from pydantic_ai.output import OutputSpec

    from narrare_core.prompts.meta import MetaPromptLoader


class NarrareAgent[DepsT, OutputT](ABC):  # noqa: B024 — abstract methods in Phase 2+
    """Basis-Klasse für alle Narrare-Agents.

    Stellt sicher:
    - Model kommt aus ModelRegistry (nie direkt instantiiert)
    - Standard-Capabilities werden immer injected (z.B. Observability)
    - Meta-Prompt kann via with_meta() geladen werden
    - Fehler werden einheitlich klassifiziert

    Usage:
        # Direct instantiation (system_prompt from caller):
        agent = MyAgent(model=model, deps_type=MyDeps, output_type=MyOutput)

        # With meta-prompt prepended:
        agent = await MyAgent.with_meta(
            model=model, deps_type=MyDeps, output_type=MyOutput,
            meta_loader=loader, meta_variables={...},
        )
    """

    def __init__(
        self,
        model: Model,
        deps_type: type[DepsT],
        output_type: OutputSpec[OutputT] | None = None,
        capabilities: list[Any] | None = None,
        system_prompt: str | None = None,
    ) -> None:
        # Build Agent kwargs: pydantic-ai does not accept None for
        # output_type or system_prompt, so only pass when explicitly set.
        agent_kwargs: dict[str, Any] = {
            "model": model,
            "deps_type": deps_type,
            "capabilities": [
                NarrareObservability(),  # immer
                NarrareUniversalRules(),  # immer — ADR-026
                *(capabilities or []),
            ],
        }
        if output_type is not None:
            agent_kwargs["output_type"] = output_type
        if system_prompt is not None:
            agent_kwargs["system_prompt"] = system_prompt

        self._agent = Agent(**agent_kwargs)

    @classmethod
    async def with_meta(
        cls,
        model: Model,
        deps_type: type[DepsT],
        meta_loader: MetaPromptLoader,
        meta_variables: dict[str, str] | None = None,
        *,
        output_type: OutputSpec[OutputT] | None = None,
        capabilities: list[Any] | None = None,
        system_prompt: str | None = None,
    ) -> NarrareAgent[DepsT, OutputT]:
        """Factory: create an agent with the meta-prompt prepended.

        Loads the Narrare meta-prompt via MetaPromptLoader and prepends
        it to the agent-specific system_prompt (if any). Use this when
        the agent is instantiated outside of PromptComposer (which already
        handles meta-prompt prepending).

        Args:
            model: LLM model from ModelRegistry.
            deps_type: Dependencies type for the agent.
            meta_loader: Loader for the meta-prompt.
            meta_variables: Variables for meta-prompt substitution
                (project_title, genre, tone, language, etc.).
            output_type: Output specification.
            capabilities: Additional capabilities.
            system_prompt: Agent-specific system prompt (appended AFTER meta).

        Returns:
            NarrareAgent instance with meta-prompt prepended.
        """
        language = (meta_variables or {}).get("language", "en")
        meta = await meta_loader.load(language=language, variables=meta_variables)
        combined = system_prompt or ""
        if meta:
            combined = f"{meta}\n\n{combined}" if combined else meta
        return cls(
            model=model,
            deps_type=deps_type,
            output_type=output_type,
            capabilities=capabilities,
            system_prompt=combined or None,
        )

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
