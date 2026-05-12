"""Tests for shared/errors.py"""

from __future__ import annotations

from narrare_core.shared.errors import (
    LLMAuthError,
    LLMContextTooLargeError,
    LLMGatewayError,
    LLMRateLimitError,
    LLMTimeoutError,
    NarrareError,
    PromptNotFoundError,
    PromptVariableError,
    WritingError,
)


class TestNarrareError:
    def test_message_is_accessible(self) -> None:
        err = NarrareError("something failed")
        assert str(err) == "something failed"

    def test_code_is_optional(self) -> None:
        err = NarrareError("msg")
        assert err.code is None

    def test_code_is_stored(self) -> None:
        err = NarrareError("msg", code="TEST_CODE")
        assert err.code == "TEST_CODE"

    def test_repr_includes_class_name(self) -> None:
        err = NarrareError("msg", code="CODE")
        assert "NarrareError" in repr(err)
        assert "CODE" in repr(err)


class TestLLMErrors:
    def test_rate_limit_has_correct_code(self) -> None:
        err = LLMRateLimitError()
        assert err.code == "RATE_LIMIT"

    def test_timeout_has_correct_code(self) -> None:
        err = LLMTimeoutError()
        assert err.code == "TIMEOUT"

    def test_auth_has_correct_code(self) -> None:
        err = LLMAuthError()
        assert err.code == "AUTH_FAILED"

    def test_context_too_large_has_correct_code(self) -> None:
        err = LLMContextTooLargeError()
        assert err.code == "CONTEXT_TOO_LARGE"

    def test_all_are_llm_gateway_errors(self) -> None:
        for cls in [LLMRateLimitError, LLMTimeoutError, LLMAuthError, LLMContextTooLargeError]:
            assert issubclass(cls, LLMGatewayError)

    def test_exception_chaining_works(self) -> None:
        original = ValueError("original")
        wrapped = WritingError("wrapped")
        try:
            raise wrapped from original
        except WritingError as e:
            assert e.__cause__ is original


class TestPromptErrors:
    def test_prompt_not_found_stores_category_and_language(self) -> None:
        err = PromptNotFoundError("writing", "de", "new_chapter")
        assert err.category == "writing"
        assert err.language == "de"
        assert err.mode == "new_chapter"
        assert "writing/de/new_chapter" in str(err)

    def test_prompt_not_found_without_mode(self) -> None:
        err = PromptNotFoundError("kb", "en")
        assert "kb/en" in str(err)
        assert err.mode == ""

    def test_prompt_variable_error_stores_variable_name(self) -> None:
        err = PromptVariableError("project_title")
        assert err.variable == "project_title"
        assert "project_title" in str(err)

    def test_prompt_variable_error_with_prompt_id(self) -> None:
        err = PromptVariableError("language", prompt_id="writing/en/new_chapter")
        assert "writing/en/new_chapter" in str(err)
