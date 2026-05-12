"""Tests for shared/result.py — Ok and Err result types."""

from __future__ import annotations

import pytest

from narrare_core.shared.result import Err, Ok


class TestOk:
    def test_is_ok_returns_true(self) -> None:
        result = Ok(42)
        assert result.is_ok() is True

    def test_is_err_returns_false(self) -> None:
        result = Ok("hello")
        assert result.is_err() is False

    def test_unwrap_returns_value(self) -> None:
        result = Ok("value")
        assert result.unwrap() == "value"

    def test_unwrap_err_raises(self) -> None:
        result = Ok(42)
        with pytest.raises(ValueError, match="unwrap_err on Ok"):
            result.unwrap_err()

    def test_bool_is_true(self) -> None:
        assert bool(Ok(42)) is True

    def test_frozen(self) -> None:
        result = Ok(42)
        with pytest.raises(AttributeError):
            result.value = 99  # pyright: ignore[reportAttributeAccessIssue]

    def test_equality(self) -> None:
        assert Ok(42) == Ok(42)
        assert Ok(42) != Ok(43)


class TestErr:
    def test_is_ok_returns_false(self) -> None:
        result = Err(ValueError("oops"))
        assert result.is_ok() is False

    def test_is_err_returns_true(self) -> None:
        result = Err(ValueError("oops"))
        assert result.is_err() is True

    def test_unwrap_raises_the_error(self) -> None:
        error = ValueError("oops")
        result = Err(error)
        with pytest.raises(ValueError, match="oops"):
            result.unwrap()

    def test_unwrap_err_returns_error(self) -> None:
        error = ValueError("oops")
        result = Err(error)
        assert result.unwrap_err() is error

    def test_bool_is_false(self) -> None:
        assert bool(Err(ValueError("oops"))) is False

    def test_frozen(self) -> None:
        result = Err(ValueError("oops"))
        with pytest.raises(AttributeError):
            result.error = RuntimeError("new")  # pyright: ignore[reportAttributeAccessIssue]

    def test_same_error_type_and_message(self) -> None:
        # Two Err with same error type/message — they are equal as dataclasses
        err1 = Err(ValueError("a"))
        err2 = Err(ValueError("a"))
        # Python Exception does not implement value equality
        # Err uses frozen dataclass equality, which compares fields
        # Since exceptions are compared by identity, these won't be equal
        assert err1 != err2  # different exception instances

    def test_same_instance_is_equal(self) -> None:
        err = ValueError("a")
        result = Err(err)
        assert result == Err(err)  # same error instance


class TestResultUsagePattern:
    """Test that Result works correctly in typical service patterns."""

    async def test_pattern_ok_branch(self) -> None:
        async def fake_service() -> Ok[str] | Err[ValueError]:
            return Ok("generated text")

        result = await fake_service()
        match result:
            case Ok(value):
                assert value == "generated text"
            case Err(_):
                pytest.fail("Should not reach Err branch")

    async def test_pattern_err_branch(self) -> None:
        async def fake_service() -> Ok[str] | Err[ValueError]:
            return Err(ValueError("LLM timeout"))

        result = await fake_service()
        match result:
            case Ok(_):
                pytest.fail("Should not reach Ok branch")
            case Err(error):
                assert "LLM timeout" in str(error)
