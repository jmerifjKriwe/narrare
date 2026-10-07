"""
Narrare Model Registry — provides configured Model instances for Agents.

This is the Gateway v2.  Instead of creating ephemeral Agents and calling
``run_sync()``, the registry returns configured ``Model`` instances.
Agents obtain their Model here, then call ``agent.run()`` themselves.

**RULE-01b**: ``from pydantic_ai import Agent`` is restricted in ``core/llm/``.
The convenience ``run()`` and ``stream()`` methods — moved to
:mod:`narrare_core.llm.registry_run` and mixed in via ``RegistryRunMixin`` —
are the only approved exceptions; they create ephemeral Agents for simple
calls.

See CONSTRAINTS.md RULE-01b and ADR-015.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare_core.llm._model_settings import (
    build_runtime_model_settings,
)
from narrare_core.llm._model_settings import (
    get_cache_settings as _get_cache_settings,
)
from narrare_core.llm._prepared_call import PreparedModelCall
from narrare_core.llm._providers.registry import get as get_provider
from narrare_core.llm.budget import check_budget
from narrare_core.llm.registry_run import RegistryRunMixin
from narrare_core.llm.run_limits import profile_to_usage_limits
from narrare_core.llm.usage_events import usage_user_id

if TYPE_CHECKING:
    from pydantic_ai.models import Model
    from pydantic_ai.settings import ModelSettings
    from pydantic_ai.usage import UsageLimits

    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm.intents import LLMIntent

# Public API
__all__ = ["ModelRegistry", "PreparedModelCall"]


class ModelRegistry(RegistryRunMixin):
    """Gateway v2 — provides configured Model instances for Agents.

    Agents obtain their Model here, then call ``agent.run()`` themselves.
    The registry handles:

    * Provider resolution — which factory for a given ``provider_name``
    * Credential injection — ``api_key`` + ``base_url`` for per-user secrets
    * ``UsageLimits`` pre-configuration — prepared for Phase 1 of ADR-015

    Simple use cases (health checks, name generation) can use the
    convenience :meth:`run` and :meth:`stream` methods, which create
    ephemeral Agents.  Complex use cases (writing pipeline) should use
    :meth:`get_model` + their own Agent definition in
    :mod:`~narrare_core.agents`.
    """

    @staticmethod
    def _profile_to_limits(profile: str) -> UsageLimits | None:
        """Convert a named token limit profile to UsageLimits.

        These profiles are stored in user_ai_settings and project_settings
        as the ``token_limit_profile`` column.

        Args:
            profile: Public token profile. Retired legacy aliases are handled
                by the run-limit compatibility helper.

        Returns:
            Configured UsageLimits, or None if the profile is unknown.
        """
        return profile_to_usage_limits(profile)

    async def get_model(
        self,
        config: ResolvedModelConfig,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        usage_limits: UsageLimits | None = None,
    ) -> Model:
        """Return a configured Model instance with credentials.

        Args:
            config: Fully resolved model configuration
                (provider, model, parameters).
            api_key: Optional API key — overrides the environment variable
                when provided.  ``None`` lets the factory fall back to the
                default env var (for dev/test).
            base_url: Optional base URL — overrides the provider default.
            usage_limits: If provided, usage limits are passed through to
                the model's Agent at run time.

        Returns:
            Configured pydantic-ai Model instance ready for use with ``Agent``.

        Raises:
            KeyError: If ``config.provider_name`` is not registered in the
                :mod:`~narrare_core.llm._providers` registry.
        """
        # ADR-094 pre-call budget gate — may raise BudgetExceededError (the
        # one controlled inversion of ADR-093 D1; do NOT wrap).
        check_budget(usage_user_id.get())

        # Auto-convert token_limit_profile to UsageLimits if not explicitly set
        if usage_limits is None:
            profile = getattr(config, "token_limit_profile", None) or ""
            if profile:
                usage_limits = self._profile_to_limits(profile)

        factory = get_provider(config.provider_name)
        return factory(config.model_id, api_key=api_key, base_url=base_url)

    async def prepare(
        self,
        config: ResolvedModelConfig,
        *,
        intent: LLMIntent | None = None,
        usage_limits: UsageLimits | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> PreparedModelCall:
        """Single assembly point: model + settings + limits as a coherent triple."""
        model = await self.get_model(
            config, api_key=api_key, base_url=base_url, usage_limits=usage_limits
        )
        settings = build_runtime_model_settings(config, usage_limits, intent=intent)
        return PreparedModelCall(model=model, model_settings=settings, usage_limits=usage_limits)

    def get_cache_settings(self, config: ResolvedModelConfig) -> ModelSettings:
        """Build provider-specific ModelSettings for prompt caching.

        Delegates to
        :func:`narrare_core.llm._model_settings.get_cache_settings`.
        Returned as kwargs dict for ``Agent.run(model_settings=...)``.
        """
        return _get_cache_settings(config)
