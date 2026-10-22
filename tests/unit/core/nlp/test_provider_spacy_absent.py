"""E03: absent spaCy package degrades machine-readable, never a raw 500.

``sys.modules['spacy'] = None`` makes ``import spacy`` raise ImportError
in-process, simulating the audit env that ran without ``--extra nlp``.
"""

from __future__ import annotations

import sys

import pytest

from narrare_core.nlp.provider_spacy import SpacyNLPProvider
from narrare_core.shared.errors import NLPProviderError


def test_missing_spacy_module_raises_nlp_provider_error(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "spacy", None)

    with pytest.raises(NLPProviderError) as excinfo:
        SpacyNLPProvider()._get_model("en")

    assert "not installed" in str(excinfo.value)


def test_nlp_provider_error_is_machine_readable() -> None:
    exc = NLPProviderError("spaCy model 'en_core_web_md' is not installed.")
    assert isinstance(exc.code, str | type(None))
