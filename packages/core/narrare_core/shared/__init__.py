"""Shared utilities — pure functions, no I/O dependencies."""

from narrare_core.shared.errors import (
    ContextAssemblyError,
    EmbeddingError,
    KBError,
    LLMAuthError,
    LLMContextTooLargeError,
    LLMGatewayError,
    LLMInvalidRequestError,
    LLMRateLimitError,
    LLMServiceUnavailableError,
    LLMTimeoutError,
    NarrareError,
    PromptError,
    PromptNotFoundError,
    PromptVariableError,
    ValidationError,
    WritingError,
)
from narrare_core.shared.frontmatter import (
    ParsedFrontmatter,
    extract_section,
    parse_frontmatter,
    strip_frontmatter,
)
from narrare_core.shared.pagination import PaginatedResponse, PaginationParams
from narrare_core.shared.result import Err, Ok, Result

__all__ = [
    "ContextAssemblyError",
    "EmbeddingError",
    "Err",
    "KBError",
    "LLMAuthError",
    "LLMContextTooLargeError",
    "LLMGatewayError",
    "LLMInvalidRequestError",
    "LLMRateLimitError",
    "LLMServiceUnavailableError",
    "LLMTimeoutError",
    "NarrareError",
    "Ok",
    "PaginatedResponse",
    "PaginationParams",
    "ParsedFrontmatter",
    "PromptError",
    "PromptNotFoundError",
    "PromptVariableError",
    "Result",
    "ValidationError",
    "WritingError",
    "extract_section",
    "parse_frontmatter",
    "strip_frontmatter",
]
