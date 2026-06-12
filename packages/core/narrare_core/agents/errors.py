"""NarrareAgent error classification.

Translates pydantic-ai exceptions into typed Narrare domain errors so that
callers (services, API layer) can react appropriately without coupling to
pydantic-ai internals.

All error classes are privacy-safe: they never expose prompt text,
user content, or model response bodies in log output.

Mapping (pydantic-ai → Narrare):

    ModelHTTPError / ModelAPIError        → ModelExecutionError
    UnexpectedModelBehavior               → ModelExecutionError
    UsageLimitExceeded                    → ModelExecutionError
    asyncio.CancelledError                → AgentCancelledError
    asyncio.TimeoutError                  → AgentTimeoutError
    Anything else                         → AgentError (catch-all)

``ModelRetry`` is NOT translated here because pydantic-ai consumes it
internally — tools/validators raise it, and the framework retries
automatically. If retries are exhausted the framework raises
``UnexpectedModelBehavior`` instead, which we *do* translate.
"""

from __future__ import annotations


class AgentError(Exception):
    """Base for all NarrareAgent runtime errors.

    Attributes:
        agent_name: Qualified class name of the agent that raised the error.
        error_type: Machine-readable classification (e.g. ``"model_execution"``).
        original: The underlying exception (for chaining / debugging).
    """

    def __init__(
        self,
        message: str,
        *,
        agent_name: str = "",
        error_type: str = "agent_error",
        original: BaseException | None = None,
    ) -> None:
        super().__init__(message)
        self.agent_name = agent_name
        self.error_type = error_type
        self.original = original

    def __repr__(self) -> str:
        parts = [str(self)]
        if self.agent_name:
            parts.append(f"agent={self.agent_name!r}")
        parts.append(f"type={self.error_type!r}")
        return f"{self.__class__.__name__}({', '.join(parts)})"

    @property
    def log_attrs(self) -> dict[str, str]:
        """Privacy-safe attributes for structlog / OTel spans.

        Deliberately excludes ``original`` message bodies and any
        prompt / response content.
        """
        return {
            "error_type": self.error_type,
            "agent_name": self.agent_name,
        }


class ModelExecutionError(AgentError):
    """LLM provider or model-level failure.

    Covers: HTTP errors, API failures, unexpected model behavior,
    usage limit exceeded, content filtering.
    """

    def __init__(
        self,
        message: str,
        *,
        agent_name: str = "",
        original: BaseException | None = None,
        provider_code: str | None = None,
    ) -> None:
        super().__init__(
            message,
            agent_name=agent_name,
            error_type="model_execution",
            original=original,
        )
        self.provider_code = provider_code

    @property
    def log_attrs(self) -> dict[str, str]:
        attrs = super().log_attrs
        if self.provider_code:
            attrs["provider_code"] = self.provider_code
        return attrs


class ModelRetryExhaustedError(AgentError):
    """Model retry limit exhausted — the model could not produce valid output.

    pydantic-ai handles ``ModelRetry`` internally.  When retries are
    exhausted the framework raises ``UnexpectedModelBehavior``, which
    we map to this error.
    """

    def __init__(
        self,
        message: str,
        *,
        agent_name: str = "",
        original: BaseException | None = None,
    ) -> None:
        super().__init__(
            message,
            agent_name=agent_name,
            error_type="model_retry_exhausted",
            original=original,
        )


class AgentTimeoutError(AgentError):
    """Agent run exceeded its time budget."""

    def __init__(
        self,
        message: str = "Agent run timed out",
        *,
        agent_name: str = "",
        original: BaseException | None = None,
    ) -> None:
        super().__init__(
            message,
            agent_name=agent_name,
            error_type="agent_timeout",
            original=original,
        )


class AgentCancelledError(AgentError):
    """Agent run was cancelled (user abort / disconnect)."""

    def __init__(
        self,
        message: str = "Agent run was cancelled",
        *,
        agent_name: str = "",
        original: BaseException | None = None,
    ) -> None:
        super().__init__(
            message,
            agent_name=agent_name,
            error_type="agent_cancelled",
            original=original,
        )
