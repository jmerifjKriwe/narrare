"""Regression test: Generation router must not hardcode provider/model.

Bug: ``_get_service()`` in ``apps/api/narrare/generation/router.py``
hardcoded ``provider_name="anthropic"`` and
``model_id="claude-haiku-3-5-20241022"``. When the user configured a
different provider (e.g. Z.AI), the generation endpoint crashed with an
internal server error because there was no Anthropic API key available.

The provider and model should come from configuration (user settings,
environment, or dependency injection), not be hardcoded in the router.

This test reads the source code of ``_get_service`` and asserts that no
hardcoded provider/model strings are present.
"""

from __future__ import annotations

import inspect


def test_get_service_does_not_hardcode_anthropic_provider() -> None:
    """_get_service must not contain the hardcoded string 'anthropic'.

    If it does, users configured with a different LLM provider will get
    internal server errors.
    """
    from narrare.generation.router import _get_service

    source = inspect.getsource(_get_service)

    assert '"anthropic"' not in source, (
        "_get_service() hardcodes provider_name='anthropic'. "
        "Provider should come from configuration, not be hardcoded."
    )
    assert "'anthropic'" not in source, (
        "_get_service() hardcodes provider_name='anthropic'. "
        "Provider should come from configuration, not be hardcoded."
    )


def test_get_service_does_not_hardcode_model_id() -> None:
    """_get_service must not contain a hardcoded claude model identifier.

    If it does, users configured with a different model will still hit
    Anthropic, causing auth failures or unexpected costs.
    """
    from narrare.generation.router import _get_service

    source = inspect.getsource(_get_service)

    assert '"claude-haiku' not in source, (
        "_get_service() hardcodes a claude-haiku model ID. "
        "Model should come from configuration, not be hardcoded."
    )
    assert "'claude-haiku" not in source, (
        "_get_service() hardcodes a claude-haiku model ID. "
        "Model should come from configuration, not be hardcoded."
    )
