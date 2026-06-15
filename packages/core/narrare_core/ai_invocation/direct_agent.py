"""Reusable Core surface for first-class NarrareAgent invocation paths."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from narrare_core.ai_invocation.correlation import (
        BudgetDecisionFingerprint,
        ModelCallMarker,
        PreparedContextFingerprint,
        PromptFingerprint,
    )


class DirectAgentInvocationEvidence(BaseModel):
    """Correlation bundle for direct NarrareAgent call sites."""

    model_config = ConfigDict(frozen=True)

    prepared_context_fingerprint: PreparedContextFingerprint
    prompt_fingerprint: PromptFingerprint | None = None
    budget_decision_fingerprint: BudgetDecisionFingerprint | None = None
    model_call_marker: ModelCallMarker | None = None
    manual_injection_exception: str | None = None


class DirectAgentInvocationStandard(BaseModel):
    """Checklist-backed Core standard for direct-agent integrations."""

    model_config = ConfigDict(frozen=True)

    requires_prepare: bool = True
    requires_prompt_composer_or_manual_exception: bool = True
    requires_finalize: bool = True
    requires_run_limits: bool = True
    requires_model_call_marker: bool = True


def _rebuild_forward_refs() -> None:
    """Resolve Pydantic forward refs for direct-agent evidence."""
    from narrare_core.ai_invocation.correlation import (
        BudgetDecisionFingerprint,
        ModelCallMarker,
        PreparedContextFingerprint,
        PromptFingerprint,
    )

    DirectAgentInvocationEvidence.model_rebuild(
        _types_namespace={
            "BudgetDecisionFingerprint": BudgetDecisionFingerprint,
            "ModelCallMarker": ModelCallMarker,
            "PreparedContextFingerprint": PreparedContextFingerprint,
            "PromptFingerprint": PromptFingerprint,
        }
    )


_rebuild_forward_refs()
