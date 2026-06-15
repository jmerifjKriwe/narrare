"""Manual-injection declaration for agent-internal prompt composition.

Per ADR-045 Decision 3 Option C and ADR-048, features that compose
their prompts internally (via agent deps, capabilities, or instructions)
declare this exception so the invocation pipeline records accurate evidence
instead of a placeholder prompt.

This module has one responsibility (RULE-06): define the typed declaration
that a service owns prompt composition. The orchestration that consumes it
lives in :mod:`narrare_core.ai_invocation.non_writing_adapter`.

See:
    ADR-045 Decision 3, ADR-048, CONSTRAINTS.md RULE-02a/RULE-03.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ManualInjectionDeclaration(BaseModel):
    """Declares that an agent owns prompt composition internally.

    Per ADR-045 Decision 3 Option C, features may bypass the automatic
    :class:`~narrare_core.prompts.context.PromptContext` merge when the agent
    composes its own prompt from deps/capabilities. This declaration is the
    typed evidence trail.

    Required for Mode 2 (agent-internal) invocations. Forbidden for
    Mode 1 (composer-driven) invocations.

    The declaration must be validated against the adoption registry:
    only declared, tested manual-injection exceptions are allowed.
    """

    model_config = ConfigDict(frozen=True)

    reason: str = Field(
        min_length=10,
        description="Human-readable explanation of why composition is agent-internal.",
    )
    variables: tuple[str, ...] = Field(
        min_length=1,
        description="Dynamic-input variable names the agent consumes internally.",
    )
    injection_mechanism: str = Field(
        description=(
            "How variables reach the agent: 'agent_deps', "
            "'capability_dynamic_instructions', 'agent_instructions_decorator'."
        ),
    )
    precedence_level: str = Field(
        default="generated_suggestion",
        description="RULE-22 precedence: where this data ranks in conflict resolution.",
    )
