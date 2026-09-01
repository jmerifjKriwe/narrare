"""Operator-plane subprocess env pins for the hybrid stack (finding #7).

Root cause: system-routed capabilities (kb-extraction and 8 more
domains) resolve their model via the SYSTEM-DEFAULT path —
``build_system_default_config`` reads ``Settings.default_writing_model``
/ ``default_analysis_model``, and the provider factories fall back to
the ``CoreSettings`` operator key vars (ADR-071). The setup wizard's
per-user provider never reaches that path, and the system defaults are
hardcoded anthropic model ids with no operator key → LLM-backed
capabilities fail with 500.

Two-track ruling: the USER-ROUTING migration (system-routed
capabilities resolving the user's wizard provider) is the product gap,
filed and tracked separately. This module implements the LEGITIMATE
benchmark unblock on the operator fallback plane per ADR-071: the
benchmark config's ``llm`` section (which mirrors the wizard's step-4
request) becomes operator env pins for the spawned uvicorn subprocess.

Precedence makes the pins stick: a real env var beats any ``.env``
file in pydantic-settings (same mechanism as the finding-#6
``NARRARE_E2E_TEST=false`` pin). The env names are the plain
``Settings``/``CoreSettings`` field names — neither model has an env
prefix, and ``NARRARE_DEFAULT_*_MODEL`` is read by NO field (verified
empirically against ``Settings``).

Secret discipline: the provider key flows ONLY from
``config.local.yaml`` into the subprocess env — never into logs,
``facts()``, error tails, or reports (``config_schemas`` redaction
masks ``llm.api_key``; the stack failure paths interpolate only
compose output and uvicorn log text, never the env dict).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from benchmark.config_schemas import LlmConfig

_PROVIDER_KEY_ENV_VARS: Final[dict[str, str]] = {
    # Provider id (config.llm.provider, AIProvider enum) → the matching
    # CoreSettings operator fallback key var (ADR-071 §3). ``ollama``
    # needs no key → deliberately absent.
    "anthropic": "ANTHROPIC_API_KEY",
    "google": "GOOGLE_API_KEY",
    "groq": "GROQ_API_KEY",
    "openai": "OPENAI_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "zai": "ZAI_API_KEY",
}


def operator_env_pins(llm: LlmConfig) -> dict[str, str]:
    """Env pins steering the system-default model path to the wizard config.

    Both system-default categories are pinned to the configured model
    (system-routed capabilities are analysis- or writing-category; the
    benchmark measures ONE provider/model), and the configured
    provider's key var carries the configured key. The key is the
    OPERATOR FALLBACK for system-routed calls (they have no user, so
    the operator plane is their only key source); user-routed calls
    keep their per-user DB credential precedence (ADR-001). Providers
    without a key (``ollama``) get no key pin.
    """
    pins: dict[str, str] = {
        "DEFAULT_ANALYSIS_MODEL": llm.model,
        "DEFAULT_WRITING_MODEL": llm.model,
    }
    key_var = _PROVIDER_KEY_ENV_VARS.get(llm.provider)
    if key_var is not None:
        pins[key_var] = llm.api_key
    return pins
