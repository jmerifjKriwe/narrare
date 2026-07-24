"""Governed transport-retry configuration for LLM provider SDK clients.

ADR-060 (Option B): LLM transport retry — transient HTTP 429 / 5xx / timeout
retry at connection / first-token establishment — is governed HERE, at the
provider layer, where the provider SDK clients (OpenAI / Anthropic / Groq /
Google) are constructed. It is **not** a user/project token-limit setting.

Why here, not in the gateway or the settings cascade
-----------------------------------------------------
The provider SDK clients already implement transport retry with their own
backoff (``max_retries``, default 2). Narrare governs the attempt count from a
single operator source so it applies **uniformly** to ``ModelRegistry.run()``
and ``ModelRegistry.stream()`` — including the connection/first-token phase of
streaming, which an operation-level retry (the retired ``with_retry``) cannot
coherently serve once partial SSE output has been emitted (see ADR-060,
rejection of Option A).

Classification: ``operator_default``
------------------------------------
* **Governed default:** :data:`TRANSPORT_MAX_RETRIES_DEFAULT` (2). Matches the
  OpenAI / Anthropic / Groq SDK defaults — a deliberate, conservative balance
  of resilience against user-perceived latency for a local-first single-user
  product. Provider-SDK backoff composes with it; raising it inflates latency
  on rate limits, so the default stays at parity with the SDKs.
* **Operator override:** :data:`TRANSPORT_MAX_RETRIES_ENV_VAR`. Self-hosters
  may raise or lower it; **users may not** — there is no DB/UI surface. This
  removes the former false control (``retry_max_attempts`` /
  ``retry_base_delay``) end-to-end (see ADR-060 Decision).

Per-user transport-retry backoff is intentionally **not** offered: it would
double-retry with the provider SDK (a footgun) and is architecturally
misplaced at the token-limit layer.
"""

from __future__ import annotations

from typing import Final

import structlog
from pydantic import ValidationError

from narrare_core.settings import get_core_settings

logger = structlog.get_logger(__name__)

#: Governed default for provider-SDK transport ``max_retries``.
#:
#: 2 matches the OpenAI / Anthropic / Groq SDK defaults. Kept conservative to
#: avoid inflating latency on rate limits; the provider-SDK backoff composes
#: with it. Proven by ``tests/unit/core/llm/test_transport_retry.py``.
TRANSPORT_MAX_RETRIES_DEFAULT: Final[int] = 2

#: Operator override env var.
#:
#: Distinct from the removed ``NARRARE_RETRY_*`` user surface (the retired
#: operation-level ``with_retry``) to avoid confusion with that false control.
TRANSPORT_MAX_RETRIES_ENV_VAR: Final[str] = "NARRARE_LLM_TRANSPORT_MAX_RETRIES"


def get_transport_max_retries() -> int:
    """Resolve the governed transport-retry ``max_retries`` for provider SDK clients.

    Reads ``get_core_settings().llm_transport_max_retries`` — the ADR-071 typed
    mirror of :data:`TRANSPORT_MAX_RETRIES_ENV_VAR`. Falls back to the governed
    default when unset, empty, or non-parseable. Negative values are rejected
    (the SDK knobs are non-negative).

    The governed-default classification (ADR-060) and the per-value effect
    test (``tests/unit/core/llm/test_transport_retry.py``) are unchanged —
    CoreSettings is the typed source; this accessor preserves the graceful-
    fallback validation that pydantic strict ``int`` parsing alone cannot
    provide (a non-integer env value raises ``ValidationError``, which is
    caught and logged here rather than crashing callers).

    Returns:
        The resolved ``max_retries`` (``>= 0``).
    """
    try:
        value = get_core_settings().llm_transport_max_retries
    except ValidationError:
        logger.warning(
            "transport_retry_invalid_env",
            env_var=TRANSPORT_MAX_RETRIES_ENV_VAR,
            fallback=TRANSPORT_MAX_RETRIES_DEFAULT,
        )
        return TRANSPORT_MAX_RETRIES_DEFAULT
    if value < 0:
        logger.warning(
            "transport_retry_negative_env",
            env_var=TRANSPORT_MAX_RETRIES_ENV_VAR,
            value=value,
            fallback=TRANSPORT_MAX_RETRIES_DEFAULT,
        )
        return TRANSPORT_MAX_RETRIES_DEFAULT
    return value
