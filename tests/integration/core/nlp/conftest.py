"""Shared fixtures and module-level skip for NLP integration tests.

These tests require real spaCy models (en_core_web_md, de_core_news_md,
fr_core_news_md).  The module-level skip ensures a clear error message
when models are missing instead of cryptic import errors.
"""

from __future__ import annotations

import importlib.util as _util

import pytest

# ---------------------------------------------------------------------------
# Module-level skip: require spaCy + all model packages
# ---------------------------------------------------------------------------

if not _util.find_spec("spacy"):
    pytest.skip("spaCy not installed", allow_module_level=True)

from spacy.util import get_installed_models  # pyright: ignore[reportMissingImports]

_REQUIRED_MODELS = {"en_core_web_md", "de_core_news_md", "fr_core_news_md"}
_INSTALLED_MODELS = set(get_installed_models())
_MISSING = _REQUIRED_MODELS - _INSTALLED_MODELS
if _MISSING:
    pytest.skip(f"Missing spaCy models: {_MISSING}", allow_module_level=True)

from narrare_core.nlp.provider_spacy import SpacyNLPProvider  # noqa: E402

# ---------------------------------------------------------------------------
# Provider fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def provider() -> SpacyNLPProvider:
    """A fresh SpacyNLPProvider instance for each test."""
    return SpacyNLPProvider()
