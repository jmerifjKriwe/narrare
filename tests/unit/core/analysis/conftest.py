"""Shared pytest fixtures for sentiment analysis tests.

Fixtures use helpers from ``helpers.py`` (FakeNLPProvider, _make_tokens).
"""

from __future__ import annotations

import pytest

from narrare_core.analysis.sentiment import LexiconSentimentAnalyzer
from tests.unit.core.analysis.helpers import FakeNLPProvider


@pytest.fixture()
def fake_nlp() -> FakeNLPProvider:
    """Default fake NLP provider (available, no custom results)."""
    return FakeNLPProvider()


@pytest.fixture()
def analyzer(fake_nlp: FakeNLPProvider) -> LexiconSentimentAnalyzer:
    """Analyzer with the default fake NLP provider."""
    return LexiconSentimentAnalyzer(nlp_provider=fake_nlp)
