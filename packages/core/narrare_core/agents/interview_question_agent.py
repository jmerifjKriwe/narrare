"""InterviewQuestionAgent — single-shot interview question generator.

Generates one round of interview questions to elicit creative direction
from the writer before drafting. Single-shot and stateless (no
``HistoryPolicy.CONVERSATIONAL``): each call composes one prompt, runs
once, and returns the question text as ``str``.

Architectural role
------------------
This agent exists to bring the Writing-Interview path onto the
``NarrareAgent`` layer (ADR-026 capability guarantee) instead of calling
``ModelRegistry.run()`` directly. Earlier the interview path bypassed
``NarrareAgent`` and therefore did not receive ``NarrareMeta`` /
``NarrareUniversalRules`` / ``NarrareObservability`` (see AUFG-03-01).

Like all ``NarrareAgent`` subclasses, the three guaranteed capabilities
are auto-injected by the base class — the system prompt resolved by
``PromptComposer`` is an additional instructions layer on top.

Usage
-----
    model = await registry.get_model(config, api_key=..., base_url=...)
    agent = InterviewQuestionAgent(model=model, system_prompt=composed.system)
    deps = InterviewDeps(language="en")
    result_text: str = await agent.run(prompt=composed.user, deps=deps)

See: ``packages/core/narrare_core/writing/pipeline_interview.py`` for the
production caller.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare_core.agents.base import NarrareAgent

if TYPE_CHECKING:
    from pydantic_ai.models import Model


class InterviewDeps:
    """Minimal runtime dependencies for :class:`InterviewQuestionAgent`.

    The interview prompt is fully composed upstream by ``PromptComposer``
    (Mode 1 — the system prompt is the ``system_prompt`` constructor arg
    and the user prompt is the ``prompt`` arg to :meth:`run`), so the
    agent's deps carry only lightweight contextual hints. A dedicated
    deps type is still required so pydantic-ai can populate
    ``RunContext.deps`` for any future ``@agent.tool`` / system-message
    dynamicisation without a breaking change.
    """

    def __init__(
        self,
        *,
        language: str = "en",
        user_id: str | None = None,
        project_id: str | None = None,
    ) -> None:
        self.language = language
        self.user_id = user_id
        self.project_id = project_id


class InterviewQuestionAgent(NarrareAgent[InterviewDeps, str]):
    """Single-shot interview question generator.

    Output type is ``str`` (the question text). History policy is
    ``NONE`` (the default) — interview questions are generated one round
    at a time; the API layer maintains any multi-turn state.
    """

    def __init__(
        self,
        model: Model,
        *,
        system_prompt: str | None = None,
    ) -> None:
        """Initialise the InterviewQuestionAgent.

        Args:
            model: Pydantic-ai Model instance from ``ModelRegistry``.
            system_prompt: Feature system prompt for the interview
                question round, as resolved by ``PromptComposer.build``
                (``chat/{lang}/system.md`` via ``LLMIntent.CHAT``).
                Injected into the **system channel** (ADR-046). ``None``
                omits the feature prompt — the guaranteed capabilities
                (``NarrareMeta`` / ``NarrareUniversalRules`` /
                ``NarrareObservability``) are always present.
        """
        super().__init__(
            model=model,
            deps_type=InterviewDeps,
            system_prompt=system_prompt,
        )
