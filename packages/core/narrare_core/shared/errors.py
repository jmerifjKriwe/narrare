"""
Narrare domain error hierarchy.

All application errors derive from NarrareError.
External exceptions are always wrapped at service boundaries.

Usage:
    raise WritingError("Chapter generation failed") from original_error
    raise LLMGatewayError("Timeout", code="TIMEOUT")
"""

from __future__ import annotations


class NarrareError(Exception):
    """Base for all Narrare domain errors."""

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.code = code

    def __repr__(self) -> str:
        code = f", code={self.code!r}" if self.code else ""
        return f"{self.__class__.__name__}({str(self)!r}{code})"


# ---------------------------------------------------------------------------
# LLM errors
# ---------------------------------------------------------------------------


class LLMGatewayError(NarrareError):
    """Raised when the LLM Gateway fails to complete a request."""


class LLMRateLimitError(LLMGatewayError):
    """Provider rate limit exceeded. Retryable."""

    def __init__(self, message: str = "Rate limit exceeded") -> None:
        super().__init__(message, code="RATE_LIMIT")


class LLMTimeoutError(LLMGatewayError):
    """Request timed out. Retryable."""

    def __init__(self, message: str = "Request timed out") -> None:
        super().__init__(message, code="TIMEOUT")


class LLMServiceUnavailableError(LLMGatewayError):
    """Provider temporarily unavailable. Retryable."""

    def __init__(self, message: str = "Service unavailable") -> None:
        super().__init__(message, code="SERVICE_UNAVAILABLE")


class LLMAuthError(LLMGatewayError):
    """Invalid API key or authentication failed. Not retryable."""

    def __init__(self, message: str = "Authentication failed") -> None:
        super().__init__(message, code="AUTH_FAILED")


class LLMContextTooLargeError(LLMGatewayError):
    """Context exceeds model token limit. Not retryable."""

    def __init__(self, message: str = "Context too large") -> None:
        super().__init__(message, code="CONTEXT_TOO_LARGE")


class LLMInvalidRequestError(LLMGatewayError):
    """Invalid request parameters. Not retryable."""

    def __init__(self, message: str = "Invalid request") -> None:
        super().__init__(message, code="INVALID_REQUEST")


# ---------------------------------------------------------------------------
# Prompt errors
# ---------------------------------------------------------------------------


class PromptError(NarrareError):
    """Base for prompt system errors."""


class PromptNotFoundError(PromptError):
    """No prompt found for the given category/language/mode."""

    def __init__(self, category: str, language: str, mode: str = "") -> None:
        detail = f"{category}/{language}"
        if mode:
            detail += f"/{mode}"
        super().__init__(f"Prompt not found: {detail}", code="PROMPT_NOT_FOUND")
        self.category = category
        self.language = language
        self.mode = mode


class PromptRouteNotConfiguredError(PromptError):
    """PromptComposer has no governed route for the requested intent."""

    def __init__(self, intent: str, reason: str) -> None:
        super().__init__(
            f"Prompt route not configured for intent '{intent}': {reason}",
            code="PROMPT_ROUTE_NOT_CONFIGURED",
        )
        self.intent = intent
        self.reason = reason


class PromptVariableError(PromptError):
    """Required prompt variable is missing or invalid."""

    def __init__(self, variable: str, prompt_id: str = "") -> None:
        detail = f"'{variable}'"
        if prompt_id:
            detail += f" in {prompt_id}"
        super().__init__(f"Missing required prompt variable {detail}", code="MISSING_VARIABLE")
        self.variable = variable


# ---------------------------------------------------------------------------
# Domain errors
# ---------------------------------------------------------------------------


class WritingError(NarrareError):
    """Error in the writing service."""


class KBError(NarrareError):
    """Error in the Knowledge Base service."""


class ContextAssemblyError(NarrareError):
    """Error assembling prompt context."""


class EmbeddingError(NarrareError):
    """Error generating or storing embeddings."""


class NarrareMemoryError(NarrareError):
    """Error in the Narrare memory layer (mem0 adapter).

    Named NarrareMemoryError to avoid shadowing Python's built-in MemoryError.
    """


class ValidationError(NarrareError):
    """Domain validation error (distinct from Pydantic's ValidationError)."""


class InvocationValidationError(NarrareError):
    """Raised when invocation pipeline validation fails.

    Domain-agnostic counterpart to :class:`WritingError` for the non-writing
    invocation adapter (ADR-048). Raised when variable validation or final
    prompt validation fails in Mode 1 (composer-driven) invocations routed
    through :func:`~narrare_core.ai_invocation.non_writing_adapter.compose_invocation`.

    See: ADR-045 Decision 3, ADR-048, CONSTRAINTS.md RULE-11.
    """


class ConfigurationError(NarrareError):
    """Missing or invalid configuration.

    Raised when a required configuration value (e.g. encryption key,
    AI provider) is absent or invalid.

    Services should catch this and return appropriate HTTP responses
    (typically 422 or 500 depending on context).
    """

    def __init__(self, message: str = "Configuration error", *, code: str | None = None) -> None:
        super().__init__(message, code=code)


# ---------------------------------------------------------------------------
# Resource / request errors
# ---------------------------------------------------------------------------


class NotFoundError(NarrareError):
    """Requested resource was not found."""

    def __init__(self, resource: str = "Resource", *, identifier: str = "") -> None:
        detail = resource
        if identifier:
            detail += f" ({identifier})"
        super().__init__(f"{detail} not found", code="NOT_FOUND")
        self.resource = resource
        self.identifier = identifier


class ForbiddenError(NarrareError):
    """User does not have permission to access this resource."""

    def __init__(self, message: str = "Access denied") -> None:
        super().__init__(message, code="FORBIDDEN")


class ConflictError(NarrareError):
    """Resource already exists or state conflict."""

    def __init__(self, message: str = "Conflict") -> None:
        super().__init__(message, code="CONFLICT")


class AuthenticationError(NarrareError):
    """Authentication failed or not provided."""

    def __init__(self, message: str = "Authentication required") -> None:
        super().__init__(message, code="AUTHENTICATION_ERROR")


# ---------------------------------------------------------------------------
# NLP errors
# ---------------------------------------------------------------------------


class NLPProviderError(NarrareError):
    """Raised when the NLP provider fails (model not found, processing error)."""
