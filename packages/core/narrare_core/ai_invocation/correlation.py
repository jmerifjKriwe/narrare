"""Privacy-safe invocation correlation helpers for ADR-045.

These helpers create stable fingerprints that prove continuity between
prepare(), prompt composition, budget resolution, and the model-call boundary
without storing raw prompts, manuscript prose, or user directions.
"""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from collections.abc import Sequence

    from narrare_core.ai_invocation.budgets import OutputBudgetDecision
    from narrare_core.ai_invocation.models import PromptInvocationContext
    from narrare_core.llm.run_limits import ResolvedRunLimits
    from narrare_core.prompts.composer import ComposedPrompt

_FINGERPRINT_DOMAIN = "narrare:adr045:v1"


class PreparedContextFingerprint(BaseModel):
    """Hash/count evidence for the prepared invocation context."""

    model_config = ConfigDict(frozen=True)

    digest: str = Field(min_length=64, max_length=64)
    dynamic_input_keys: tuple[str, ...] = ()
    dynamic_input_count: int = 0
    feature_id: str
    intent: str
    mode: str | None = None


class PromptFingerprint(BaseModel):
    """Hash/length evidence for a composed prompt."""

    model_config = ConfigDict(frozen=True)

    digest: str = Field(min_length=64, max_length=64)
    system_length: int = Field(ge=0)
    user_length: int = Field(ge=0)
    has_first_message: bool = False


class BudgetDecisionFingerprint(BaseModel):
    """Structured budget evidence without free-form rationale text."""

    model_config = ConfigDict(frozen=True)

    digest: str = Field(min_length=64, max_length=64)
    profile: str | None = None
    max_output_tokens: int | None = None
    source: str


class ModelCallMarker(BaseModel):
    """Privacy-safe marker proving the model boundary was reached."""

    model_config = ConfigDict(frozen=True)

    provider: str
    model: str
    output_budget_profile: str | None = None
    effective_output_tokens: int | None = None
    streaming: bool
    status: str = "prepared"


def fingerprint_prepared_context(
    context: PromptInvocationContext,
) -> PreparedContextFingerprint:
    """Return a privacy-safe fingerprint for prepared dynamic inputs."""
    keys = tuple(sorted(context.dynamic_inputs.keys()))
    value_fingerprints = {
        key: {
            "length": len(value),
            "sha256": _hash_payload({"key": key, "value": value}),
        }
        for key, value in sorted(context.dynamic_inputs.items())
    }
    digest = _hash_payload(
        {
            "feature_id": context.feature_id,
            "intent": context.intent.value,
            "mode": context.mode,
            "dynamic_inputs": value_fingerprints,
        }
    )
    return PreparedContextFingerprint(
        digest=digest,
        dynamic_input_keys=keys,
        dynamic_input_count=len(keys),
        feature_id=context.feature_id,
        intent=context.intent.value,
        mode=context.mode,
    )


def fingerprint_prompt(prompt: ComposedPrompt) -> PromptFingerprint:
    """Return a hash/length fingerprint for a composed prompt."""
    digest = _hash_payload(
        {
            "system": prompt.system,
            "user": prompt.user,
            "first_message": prompt.first_message,
        }
    )
    return PromptFingerprint(
        digest=digest,
        system_length=len(prompt.system),
        user_length=len(prompt.user),
        has_first_message=prompt.first_message is not None,
    )


def fingerprint_budget_decision(
    decision: OutputBudgetDecision | None,
) -> BudgetDecisionFingerprint | None:
    """Return structured budget metadata and a digest, excluding reason text."""
    if decision is None:
        return None
    payload = {
        "profile": decision.budget.profile,
        "max_output_tokens": decision.budget.max_tokens,
        "source": decision.source,
    }
    return BudgetDecisionFingerprint(
        digest=_hash_payload(payload),
        profile=decision.budget.profile,
        max_output_tokens=decision.budget.max_tokens,
        source=decision.source,
    )


def build_model_call_marker(
    *,
    provider: str,
    model: str,
    streaming: bool,
    resolved_limits: ResolvedRunLimits | None,
    status: str = "prepared",
) -> ModelCallMarker:
    """Build a model-call marker from resolved limits and model identity."""
    return ModelCallMarker(
        provider=provider,
        model=model,
        output_budget_profile=(
            resolved_limits.output_budget_profile if resolved_limits is not None else None
        ),
        effective_output_tokens=(
            resolved_limits.effective_output_tokens if resolved_limits is not None else None
        ),
        streaming=streaming,
        status=status,
    )


def fingerprint_chapter_texts(chapter_texts: Sequence[str]) -> str:
    """Privacy-safe staleness fingerprint over a band's ordered chapter texts.

    C2 drift persistence (SERIES-004 Slice 6): reuses the ADR-045 fingerprint
    scheme (:func:`_hash_payload` — SHA-256 over canonical JSON with the
    ``narrare:adr045:v1`` domain separator) — **no new hash scheme**. The
    ``kind`` discriminator keeps drift-staleness digests distinct from
    invocation-correlation digests. Determinism requires callers to pass the
    texts in a stable order with a stable filter: backend callers use
    ``ChapterRepository.list_by_novel`` (position order) filtered to non-empty
    prose — the exact inputs ``SeriesConsistencyService`` analyses. Only the
    digest is persisted; raw prose never is.
    """
    return _hash_payload(
        {"kind": "series_drift_chapter_texts", "chapter_texts": list(chapter_texts)}
    )


def _hash_payload(payload: object) -> str:
    """Hash a JSON-serializable payload with an ADR-045 domain separator."""
    encoded = json.dumps(
        {"domain": _FINGERPRINT_DOMAIN, "payload": payload},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
