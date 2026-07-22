"""DI factories for the ai_assist domain (RULE-04 split).

Production wiring for ``DialogueCoachService`` lives here. The service is
request-scoped (it depends on an ``AsyncSession`` for chapter loading +
evidence writes).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare._app.dependencies import SessionDep  # noqa: TC001 — needed at runtime for FastAPI DI

if TYPE_CHECKING:
    from narrare.ai_assist.contracts import DialogueCoachServiceProtocol


def get_dialogue_coach_service(
    session: SessionDep,
) -> DialogueCoachServiceProtocol:
    """Create a DialogueCoachService with production DI.

    Wires (completed in Task 13 once ``DialogueCoachService`` exists):
    - ChapterRepository (load chapter for project/access control),
    - ModelRegistry + ResolvedModelConfig (analysis-tier model, via
      ``build_system_default_config(SystemModelCategory.ANALYSIS)``),
    - PromptComposer (Mode 1 resolution),
    - InvocationPipeline (evidence),
    - AdaptiveContextProvider (load adaptive context + record snapshot).

    Plan-bug #20 note: the concrete ``DialogueCoachService`` (Task 13)
    does not exist yet. Pyright's ``reportMissingImports`` resolves every
    import statically — including ``if TYPE_CHECKING`` blocks and deferred
    function-body imports — so any reference to
    ``narrare.ai_assist.service`` fails the type checker today. The
    factory therefore returns the Protocol (which exists) and raises
    ``NotImplementedError`` until Task 13 supplies the service. No test
    calls this factory until Task 14.
    """
    raise NotImplementedError(
        "DialogueCoachService is implemented in Task 13 (ADR-069 D17); "
        "this factory body is completed there."
    )
