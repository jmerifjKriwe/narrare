---
paths:
  - "**/*.py"
---

# Python Code Style

## Type Syntax (Python 3.14)
- Use `|` for unions: `str | None` not `Union[str, None]`
- Use `TypeAlias` for complex types
- Use `Self` for fluent builders
- Never use `Any` except in approved adapters

## Naming
- Classes: PascalCase (ChapterWritingService)
- Functions/variables: snake_case (write_chapter)
- Constants: UPPER_SNAKE_CASE (MAX_CHAPTER_LENGTH)
- Private: _prefix (self._gateway, _build_context)
- Protocols: end with Protocol (ChapterServiceProtocol)

## Imports (order: stdlib → third-party → internal)
```python
# stdlib
import asyncio
from pathlib import Path

# third-party
import structlog
from fastapi import Depends

# core
from core.llm.gateway import LLMGateway

# api
from narrare.writing.contracts import ChapterServiceProtocol
```

## Docstrings
- Google-style docstrings on public functions
```python
async def write(self, request: WriteRequest) -> WriteResult:
    """Generate a new chapter draft.

    Args:
        request: Generation parameters.

    Returns:
        WriteResult with generated text and metadata.

    Raises:
        WritingError: If generation fails.
    """
```

Full documentation: docs/development/coding-standards.md
