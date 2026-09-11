"""PreparedModelCall — the coherent call triple produced by ModelRegistry.

Value type for the single assembly point
:meth:`ModelRegistry.prepare <narrare_core.llm.gateway.ModelRegistry.prepare>`,
which returns the model, its runtime model_settings, and the usage limits
as one indivisible result.

Root cause this fixes: call sites obtained a Model via ``get_model()`` and
assembled ``model_settings`` separately — or not at all (the structural
audit found 29 ``agent.run()`` paths that never receive model_settings, so
the thinking policy, cache settings, and output caps silently never
applied). With :meth:`~narrare_core.llm.gateway.ModelRegistry.prepare`
there is no API that yields a Model without the matching settings and
limits.

Split from :mod:`narrare_core.llm.gateway` per RULE-04/06 (one
responsibility per file; gateway.py sits at its hard line limit).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pydantic_ai.models import Model
    from pydantic_ai.settings import ModelSettings
    from pydantic_ai.usage import UsageLimits

__all__ = ["PreparedModelCall"]


@dataclass(frozen=True)
class PreparedModelCall:
    """Coherent triple from :meth:`ModelRegistry.prepare`.

    Pass all three to the Agent call site::

        prepared = await registry.prepare(config, intent=intent)
        result = await agent.run(
            prompt,
            model=prepared.model,
            model_settings=prepared.model_settings,
            usage_limits=prepared.usage_limits,
        )

    Attributes:
        model: Configured pydantic-ai Model (credentials injected).
        model_settings: Runtime ModelSettings — cache policy, the
            ``max_tokens`` output cap (ADR-045), and the intent-aware
            thinking level. ``None`` when no settings apply.
        usage_limits: ``Agent.run(usage_limits=...)`` enforcement limits.
            ``None`` when the caller provided none.
    """

    model: Model
    model_settings: ModelSettings | None
    usage_limits: UsageLimits | None
