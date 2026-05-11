"""
Property-based tests for shared/result.py using Hypothesis.

Verifies that Ok and Err result types obey their invariants for
arbitrary values and errors.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from narrare_core.shared.errors import NarrareError
from narrare_core.shared.result import Err, Ok

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Any Python value that could be wrapped in Ok
any_value = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(),
    st.floats(allow_nan=False, allow_infinity=False),
    st.text(),
    st.lists(st.integers(), max_size=5),
    st.tuples(st.integers(), st.text()),
)

# Any exception that could be wrapped in Err
any_exception = st.one_of(
    st.builds(ValueError, st.text(max_size=50)),
    st.builds(TypeError, st.text(max_size=50)),
    st.builds(RuntimeError, st.text(max_size=50)),
    st.builds(NarrareError, st.text(max_size=50)),
    st.builds(
        NarrareError,
        st.text(max_size=50),
        code=st.text(min_size=1, max_size=20, alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ_"),
    ),
)


# ---------------------------------------------------------------------------
# Tests: Ok invariants
# ---------------------------------------------------------------------------


class TestOkProperties:
    @given(any_value)
    @settings(max_examples=200, deadline=None)
    def test_ok_is_ok(self, value: object) -> None:
        """Ok.is_ok() always returns True."""
        result = Ok(value)
        assert result.is_ok() is True

    @given(any_value)
    @settings(max_examples=200, deadline=None)
    def test_ok_is_not_err(self, value: object) -> None:
        """Ok.is_err() always returns False."""
        result = Ok(value)
        assert result.is_err() is False

    @given(any_value)
    @settings(max_examples=200, deadline=None)
    def test_ok_is_ok_and_err_are_mutually_exclusive(self, value: object) -> None:
        """is_ok() and is_err() are never both True or both False."""
        result = Ok(value)
        assert result.is_ok() != result.is_err()

    @given(any_value)
    @settings(max_examples=200, deadline=None)
    def test_ok_unwrap_returns_value(self, value: object) -> None:
        """Ok.unwrap() returns the wrapped value."""
        result = Ok(value)
        assert result.unwrap() == value

    @given(any_value)
    @settings(max_examples=200, deadline=None)
    def test_ok_unwrap_err_raises(self, value: object) -> None:
        """Ok.unwrap_err() always raises ValueError."""
        result = Ok(value)
        with pytest.raises(ValueError, match="unwrap_err on Ok"):
            result.unwrap_err()

    @given(any_value)
    @settings(max_examples=200, deadline=None)
    def test_ok_is_truthy(self, value: object) -> None:
        """Ok always evaluates to True in a boolean context."""
        assert bool(Ok(value)) is True


# ---------------------------------------------------------------------------
# Tests: Err invariants
# ---------------------------------------------------------------------------


class TestErrProperties:
    @given(any_exception)
    @settings(max_examples=200, deadline=None)
    def test_err_is_err(self, error: Exception) -> None:
        """Err.is_err() always returns True."""
        result = Err(error)
        assert result.is_err() is True

    @given(any_exception)
    @settings(max_examples=200, deadline=None)
    def test_err_is_not_ok(self, error: Exception) -> None:
        """Err.is_ok() always returns False."""
        result = Err(error)
        assert result.is_ok() is False

    @given(any_exception)
    @settings(max_examples=200, deadline=None)
    def test_err_is_ok_and_err_are_mutually_exclusive(self, error: Exception) -> None:
        """is_ok() and is_err() are never both True or both False."""
        result = Err(error)
        assert result.is_ok() != result.is_err()

    @given(any_exception)
    @settings(max_examples=200, deadline=None)
    def test_err_unwrap_raises_contained_error(self, error: Exception) -> None:
        """Err.unwrap() raises the wrapped exception."""
        result = Err(error)
        with pytest.raises(type(error)):
            result.unwrap()

    @given(any_exception)
    @settings(max_examples=200, deadline=None)
    def test_err_unwrap_err_returns_error(self, error: Exception) -> None:
        """Err.unwrap_err() returns the wrapped exception."""
        result = Err(error)
        assert result.unwrap_err() is error

    @given(any_exception)
    @settings(max_examples=200, deadline=None)
    def test_err_is_falsy(self, error: Exception) -> None:
        """Err always evaluates to False in a boolean context."""
        assert bool(Err(error)) is False


# ---------------------------------------------------------------------------
# Tests: Frozen dataclass property
# ---------------------------------------------------------------------------


class TestFrozenProperties:
    @given(any_value)
    @settings(max_examples=50, deadline=None)
    def test_ok_is_frozen(self, value: object) -> None:
        """Ok is frozen — attribute assignment raises AttributeError."""
        result = Ok(value)
        with pytest.raises(AttributeError):
            result.value = "new_value"  # pyright: ignore[reportAttributeAccessIssue]

    @given(any_exception)
    @settings(max_examples=50, deadline=None)
    def test_err_is_frozen(self, error: Exception) -> None:
        """Err is frozen — attribute assignment raises AttributeError."""
        result = Err(error)
        with pytest.raises(AttributeError):
            result.error = RuntimeError("new")  # pyright: ignore[reportAttributeAccessIssue]


# ---------------------------------------------------------------------------
# Tests: Equality property
# ---------------------------------------------------------------------------


class TestEqualityProperties:
    @given(any_value)
    @settings(max_examples=200, deadline=None)
    def test_ok_equal_to_itself(self, value: object) -> None:
        """Ok(x) == Ok(x) for the same x (value equality via dataclass)."""
        assert Ok(value) == Ok(value)

    @given(any_value, any_value)
    @settings(max_examples=200, deadline=None)
    def test_ok_equality_depends_on_value(self, a: object, b: object) -> None:
        """Ok(a) == Ok(b) iff a == b."""
        result_a = Ok(a)
        result_b = Ok(b)
        assert (result_a == result_b) == (a == b)
