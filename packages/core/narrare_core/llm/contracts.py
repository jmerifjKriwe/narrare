"""
Contracts for the LLM subsystem.

Every LLM call goes through the gateway — CONSTRAINTS.md RULE-01b.
Contract-first design — CONSTRAINTS.md RULE-03.

``ModelRegistryProtocol`` lives in
:mod:`narrare_core.llm._registry_protocol` (RULE-04 split) and is
re-exported here — this module stays the public contracts surface.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from narrare_core.llm._registry_protocol import ModelRegistryProtocol

if TYPE_CHECKING:
    from narrare_core.llm.intents import LLMIntent
    from narrare_core.llm.model_calibration import ModelLimitCalibration
    from narrare_core.llm.model_listing import ModelCatalogEntry
    from narrare_core.llm.model_suitability import ModelSuitabilityResult

__all__ = [
    "ModelCatalogProtocol",
    "ModelLimitCalibrationProviderProtocol",
    "ModelRegistryProtocol",
    "ModelSuitabilityEvaluatorProtocol",
]


@runtime_checkable
class ModelCatalogProtocol(Protocol):
    """Contract for listing available models from a provider's catalog API.

    Separate from ``ModelRegistryProtocol`` (which handles LLM inference).
    Catalog queries are read-only GET requests to provider REST APIs —
    they do not invoke LLM inference.

    RULE-08 compliance: provider catalog APIs are external integrations
    abstracted behind this protocol.

    See Also
    --------
    CONSTRAINTS.md RULE-08 — External integrations are abstracted.
    CONSTRAINTS.md RULE-03 — Contracts before implementation.
    """

    async def list_models(
        self,
        provider: str,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> list[ModelCatalogEntry]:
        """List available models for a given provider.

        Parameters
        ----------
        provider:
            Provider name (e.g. ``"anthropic"``, ``"openai"``, ``"ollama"``).
            Passed as a plain string — core has no dependency on apps/.
        api_key:
            Provider API key.  Required for cloud providers.  ``None`` for Ollama.
        base_url:
            Optional base URL override (e.g. Ollama URL, custom endpoint).

        Returns
        -------
        list[ModelCatalogEntry]
            Available models from the provider's catalog.

        Raises
        ------
        ModelCatalogError
            If the provider API is unreachable or returns an error.
        """
        ...


@runtime_checkable
class ModelLimitCalibrationProviderProtocol(Protocol):
    """Contract for resolving model-limit calibration evidence.

    Implementations may use cache, remote provider metadata, or test fakes, but
    they must return a typed result that distinguishes fresh/stale/unknown and
    offline states instead of collapsing them into ``None``.
    """

    def get_model_limit_calibration(
        self,
        provider: str,
        model_id: str,
    ) -> ModelLimitCalibration:
        """Return typed model-limit calibration evidence for provider/model."""
        ...


@runtime_checkable
class ModelSuitabilityEvaluatorProtocol(Protocol):
    """Contract for CR-08 model suitability evaluation."""

    def evaluate(
        self,
        *,
        intent: LLMIntent,
        calibration: ModelLimitCalibration,
        requested_output_tokens: int,
        effective_output_tokens: int | None = ...,
        model_capability_tier: str | None = ...,
        required_input_tokens: int | None = ...,
    ) -> ModelSuitabilityResult:
        """Return advisory/warning/hard-block suitability result."""
        ...
