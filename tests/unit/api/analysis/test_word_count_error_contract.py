"""N13 contract: word-count business rules are 422 domain errors.

The beta-reader min/max word-count rules previously escaped as generic
500s (plain ``Exception`` subclasses with no handler). As core
``ValidationError`` subclasses they ride the existing app-level mapping
to HTTP 422 ``{"detail", "code"}`` (audit N13, M06 EMPTY_DRAFT precedent).
"""

from __future__ import annotations

from narrare.analysis.errors import ExcessiveWordCountError, InsufficientWordCountError
from narrare.analysis.validation import validate_word_count
from narrare_core.shared.errors import ValidationError


def test_insufficient_word_count_is_a_422_domain_error() -> None:
    exc = InsufficientWordCountError(
        "Chapter is too short for meaningful analysis (412 words, minimum 1000)."
    )
    assert isinstance(exc, ValidationError)  # → app handler maps to 422
    assert exc.code == "WORD_COUNT_BELOW_MINIMUM"


def test_excessive_word_count_is_a_422_domain_error() -> None:
    exc = ExcessiveWordCountError("Selected chapters exceed the analysis limit.")
    assert isinstance(exc, ValidationError)
    assert exc.code == "WORD_COUNT_ABOVE_MAXIMUM"


def test_validate_word_count_raises_the_typed_error_below_minimum() -> None:
    try:
        validate_word_count(412)
    except InsufficientWordCountError as exc:
        assert "412" in str(exc)
        assert exc.code == "WORD_COUNT_BELOW_MINIMUM"
    else:
        raise AssertionError("validate_word_count(412) must raise")
