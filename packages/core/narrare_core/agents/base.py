"""NarrareAgent — Basis-Klasse für alle Narrare-Agents.

Stellt sicher:
- Model kommt aus ModelRegistry (nie direkt instantiiert)
- Standard-Capabilities werden immer injected (Observability, UniversalRules, Meta)
- Fehler werden einheitlich klassifiziert (agents/errors.py, error_translator.py)

Usage:
    # Direct instantiation (system_prompt from caller — tests, PromptComposer):
    model = await registry.get_model(config)
    agent = MyAgent(model=model, deps_type=MyDeps, output_type=MyOutput)
    result = await agent.run(prompt, deps=MyDeps(...))

    # Streaming (conversational agents):
    async for event in agent.run_stream(prompt, deps=MyDeps(...)):
        if event.type == "token":
            print(event.text, end="")
        elif event.type == "done":
            print(f"\nUsage: {event.usage}")

The Narrare meta-prompt is always injected via the NarrareMeta Capability
(NarrareAgent adds it to every instance automatically). No need for
with_meta() or manual meta-prompt loading.
"""

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pydantic_ai import Agent

from narrare_core.agents.capabilities import (
    NarrareMeta,
    NarrareObservability,
    NarrareUniversalRules,
)
from narrare_core.agents.error_translator import classify_error
from narrare_core.agents.history_policy import HistoryPolicy

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable

    from pydantic_ai import RunContext
    from pydantic_ai.models import Model
    from pydantic_ai.output import OutputSpec


@dataclass
class StreamEvent:
    """An event yielded during streaming agent execution.

    Attributes:
        type: Event type — ``"token"`` for text chunks, ``"done"`` for completion.
        text: The text content (partial for ``"token"``, full for ``"done"``).
        usage: Token usage information — available in the ``"done"`` event.
        new_messages: New message history from this run — available in the
            ``"done"`` event. Use this with ``ProcessHistory`` to maintain
            conversational context across turns.
    """

    type: str  # "token" or "done"
    text: str = ""
    usage: dict[str, int] | None = None
    new_messages: list[Any] | None = None


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
        # Default mirrors pydantic_ai.Agent.__init__ (`output_type: OutputSpec[OutputDataT] = str`)
        # so text agents may omit it; explicit ``None`` (tool-provider agents such as KBAgent)
        # falls back to the same pydantic-ai ``str`` default at runtime. Both spellings keep
        # pyright >=1.1.412 happy: the old ``= None`` default surfaced as ``TypeForm[None]``
        # at call sites that omit the parameter (PEP 747 TypeForm default-on).
        output_type: OutputSpec[OutputT] | None = str,
        capabilities: list[Any] | None = None,
        system_prompt: str | None = None,
        instructions: (
            str
            | Callable[[RunContext[DepsT]], str | None]
            | Callable[[RunContext[DepsT]], Awaitable[str | None]]
            | None
        ) = None,
        history_policy: HistoryPolicy = HistoryPolicy.NONE,
        retries: int | None = None,
    ) -> None:
        """Initialise the NarrareAgent wrapper.

        Args:
            model: Pydantic-AI model instance supplied by ``ModelRegistry``.
            deps_type: The dependency type for this agent.
            output_type: Output spec for structured output. Defaults to
                ``str`` (same as ``pydantic_ai.Agent``); explicit ``None``
                is accepted and resolves to that same ``str`` default at
                runtime (used by tool-provider agents, e.g. ``KBAgent``).
            capabilities: Additional capabilities beyond the always-injected
                ``NarrareObservability``, ``NarrareUniversalRules``, and
                ``NarrareMeta``.
            system_prompt: Optional static system prompt. Prefer the
                ``core/prompts/`` cascade via the service layer for
                user-customisable content (RULE-02a §1).
            instructions: Optional dynamic per-invocation instructions
                (RULE-02a §3). Accepts a string or a callable that receives
                a ``RunContext[DepsT]`` and returns the instructions string
                for the current run. Use this for content that varies per
                invocation and depends on Deps (e.g. pre-composed prompts,
                KB context, style profiles). Passed straight through to
                ``pydantic_ai.Agent``.
            history_policy: History policy for this agent (ADR-034).
            retries: Retry budget for tool-call and output validation
                failures. Pass a higher value for models that intermittently
                produce schema-invalid output. ``None`` (default) uses the
                pydantic-ai default of 1.
        """
        # Build Agent kwargs: pydantic-ai does not accept None for
        # output_type, system_prompt, or instructions. output_type now
        # defaults to `str` (the pydantic-ai default — forwarding it
        # explicitly is behaviorally identical to omitting it); an explicit
        # None skips the kwarg, which lands on the same pydantic-ai default.
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
        if instructions is not None:
            agent_kwargs["instructions"] = instructions
        if retries is not None:
            agent_kwargs["retries"] = retries

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
        Alle Exceptions werden in typisierte NarrareAgent-Fehler
        übersetzt (siehe ``agents/errors.py``).
        """
        try:
            result = await self._agent.run(prompt, deps=deps, **kwargs)
            return result.output
        except BaseException as exc:
            # CancelledError is BaseException, not Exception — must be
            # caught here to translate into AgentCancelledError.
            # KeyboardInterrupt/SystemExit are re-raised as-is.
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            raise classify_error(exc, agent_name=type(self).__qualname__) from exc

    async def run_stream(
        self,
        prompt: str,
        deps: DepsT,
        *,
        message_history: list[Any] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[StreamEvent]:
        """Stream the agent's response text.

        Yields ``StreamEvent`` objects:
        - ``StreamEvent(type="token", text=...)`` for each text chunk
        - ``StreamEvent(type="done", text=full_response, usage=..., new_messages=...)``
          on completion

        Args:
            prompt: The input prompt text.
            deps: Agent dependencies.
            message_history: Optional pydantic-ai message history for continuation.
                Use ``ProcessHistory.messages`` to maintain conversational context.
            **kwargs: Passed to pydantic-ai ``run_stream``.

        Yields:
            StreamEvent events for each token and final done event.

        Usage:
            .. code-block:: python

                history = ProcessHistory()
                async for event in agent.run_stream(prompt, deps, message_history=history.messages):
                    if event.type == "token":
                        print(event.text, end="")
                    elif event.type == "done" and event.new_messages:
                        history.add(event.new_messages)
        """
        try:
            async with self._agent.run_stream(
                prompt,
                deps=deps,
                message_history=message_history,
                **kwargs,
            ) as result:
                full_text = ""
                async for text in result.stream_text():
                    full_text += text
                    yield StreamEvent(type="token", text=text)

                usage_obj = result.usage
                usage: dict[str, int] | None = None
                if usage_obj:
                    usage = {
                        "input_tokens": usage_obj.input_tokens or 0,
                        "output_tokens": usage_obj.output_tokens or 0,
                        "total_tokens": usage_obj.total_tokens or 0,
                    }
                yield StreamEvent(
                    type="done",
                    text=full_text,
                    usage=usage,
                    new_messages=result.new_messages(),
                )
        except BaseException as exc:
            # CancelledError is BaseException, not Exception — must be
            # caught here to translate into AgentCancelledError.
            # KeyboardInterrupt/SystemExit are re-raised as-is.
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            raise classify_error(exc, agent_name=type(self).__qualname__) from exc
