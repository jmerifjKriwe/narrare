"""Shared utilities — pure functions, no I/O dependencies."""

from narrare_core.shared.errors import (
    NarrareError,
    LLMGatewayError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMServiceUnavailableError,
    LLMAuthError,
    LLMContextTooLargeError,
    LLMInvalidRequestError,
    PromptError,
    PromptNotFoundError,
    PromptVariableError,
    WritingError,
    KBError,
    ContextAssemblyError,
    EmbeddingError,
    ValidationError,
)
from narrare_core.shared.result import Ok, Err, Result
from narrare_core.shared.frontmatter import (
    ParsedFrontmatter,
    parse_frontmatter,
    strip_frontmatter,
    extract_section,
)
from narrare_core.shared.pagination import PaginationParams, PaginatedResponse

__all__ = [
    "NarrareError",
    "LLMGatewayError",
    "LLMRateLimitError",
    "LLMTimeoutError",
    "LLMServiceUnavailableError",
    "LLMAuthError",
    "LLMContextTooLargeError",
    "LLMInvalidRequestError",
    "PromptError",
    "PromptNotFoundError",
    "PromptVariableError",
    "WritingError",
    "KBError",
    "ContextAssemblyError",
    "EmbeddingError",
    "ValidationError",
    "Ok",
    "Err",
    "Result",
    "ParsedFrontmatter",
    "parse_frontmatter",
    "strip_frontmatter",
    "extract_section",
    "PaginationParams",
    "PaginatedResponse",
]
