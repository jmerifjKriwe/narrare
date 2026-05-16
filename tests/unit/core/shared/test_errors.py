"""Tests for shared/errors.py"""

from __future__ import annotations

from narrare_core.shared.errors import (
    AuthenticationError,
    ConflictError,
    ForbiddenError,
    LLMAuthError,
    LLMContextTooLargeError,
    LLMGatewayError,
    LLMRateLimitError,
    LLMTimeoutError,
    NarrareError,
    NotFoundError,
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


class TestNotFoundError:
    def test_default_message(self) -> None:
        err = NotFoundError()
        assert str(err) == "Resource not found"
        assert err.code == "NOT_FOUND"

    def test_custom_resource(self) -> None:
        err = NotFoundError("Chapter")
        assert str(err) == "Chapter not found"
        assert err.resource == "Chapter"

    def test_resource_with_identifier(self) -> None:
        err = NotFoundError("Novel", identifier="abc-123")
        assert str(err) == "Novel (abc-123) not found"
        assert err.resource == "Novel"
        assert err.identifier == "abc-123"

    def test_resource_without_identifier(self) -> None:
        err = NotFoundError("Volume")
        assert str(err) == "Volume not found"
        assert err.identifier == ""

    def test_is_narrare_error(self) -> None:
        assert issubclass(NotFoundError, NarrareError)

    def test_repr_includes_code(self) -> None:
        err = NotFoundError("Chapter")
        assert "NotFoundError" in repr(err)
        assert "NOT_FOUND" in repr(err)


class TestForbiddenError:
    def test_default_message(self) -> None:
        err = ForbiddenError()
        assert str(err) == "Access denied"
        assert err.code == "FORBIDDEN"

    def test_custom_message(self) -> None:
        err = ForbiddenError("You cannot edit this novel")
        assert str(err) == "You cannot edit this novel"

    def test_is_narrare_error(self) -> None:
        assert issubclass(ForbiddenError, NarrareError)


class TestConflictError:
    def test_default_message(self) -> None:
        err = ConflictError()
        assert str(err) == "Conflict"
        assert err.code == "CONFLICT"

    def test_custom_message(self) -> None:
        err = ConflictError("Email already registered")
        assert str(err) == "Email already registered"

    def test_is_narrare_error(self) -> None:
        assert issubclass(ConflictError, NarrareError)


class TestAuthenticationError:
    def test_default_message(self) -> None:
        err = AuthenticationError()
        assert str(err) == "Authentication required"
        assert err.code == "AUTHENTICATION_ERROR"

    def test_custom_message(self) -> None:
        err = AuthenticationError("Invalid email or password")
        assert str(err) == "Invalid email or password"

    def test_is_narrare_error(self) -> None:
        assert issubclass(AuthenticationError, NarrareError)

    def test_exception_chaining(self) -> None:
        """AuthenticationError can wrap underlying exceptions."""
        original = ValueError("bad token")
        try:
            raise AuthenticationError("Invalid token") from original
        except AuthenticationError as exc:
            assert exc.__cause__ is original
            assert str(exc) == "Invalid token"
