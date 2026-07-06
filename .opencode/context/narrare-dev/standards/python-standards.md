<!-- Context: narrare-dev/standards/python-standards | Priority: high | Source: docs/development/coding-standards.md (Python section) | Updated: 2026-06-12 -->

# Python Standards — Quick Reference

Concise code patterns. Full reference: `docs/development/coding-standards.md`.

---

## Python 3.14 Typing

```python
# Type unions: use | not Union
def process(value: str | None) -> str | None: ...

# Use TypeAlias for complex types
type NovelId = UUID

# Self for fluent builders; no Any except adapter code
from typing import Self
class QueryBuilder:
    def filter(self, **kwargs) -> Self: ...
```

---

## Naming

```python
class ChapterWritingService: ...          # PascalCase
async def write_chapter(...) -> ...: ...  # snake_case
MAX_CHAPTER_LENGTH = 100_000              # UPPER_SNAKE_CASE
self._gateway = gateway                   # private: single underscore

class ChapterServiceProtocol(Protocol): ...  # Protocols: suffix Protocol
```

---

## Imports

```python
# Order: stdlib → third-party → core → api (blank lines between)

import asyncio
import uuid
from typing import AsyncIterator

import structlog
from fastapi import Depends

from narrare_core.llm.gateway import ModelRegistry

from narrare.chapters.contracts import ChapterServiceProtocol
```

---

## Async

```python
# Everything async in service layer. Never block the event loop.
# Parallel operations:
results = await asyncio.gather(
    service.get_chapter(chapter_id),
    service.get_kb_context(novel_id),
)

# Agent via ModelRegistry:
model = await registry.get_model(config)
agent = ChapterSummaryAgent(model=model)
result = await agent.run(prompt="...", deps=SummaryDeps())
```

---

## Error Handling (NarrareError hierarchy)

```python
class NarrareError(Exception):
    def __init__(self, message: str, *, code: str | None = None) -> None: ...

class WritingError(NarrareError): ...
class KBError(NarrareError): ...
class LLMGatewayError(NarrareError): ...

# Convert external exceptions at service boundaries (RULE-11)
try:
    result = await agent.run(prompt=prompt, deps=deps)
except Exception as exc:
    logger.error("llm_call_failed", error=str(exc))
    raise WritingError("Operation failed") from exc
```

---

## Result Type Pattern

```python
type Result[T, E] = Ok[T] | Err[E]

# Services return Result across boundaries. Callers pattern-match.
```

---

## Service DI Pattern

```python
class ChapterWritingService:
    def __init__(self, registry: ModelRegistry, config: ResolvedModelConfig,
                 repo: ChapterRepository) -> None:
        self._registry = registry
        self._config = config
        self._repo = repo

# All deps via __init__. Never instantiate inside methods. Routers create via FastAPI Depends.
```

---

## FastAPI DI (SessionDep)

```python
# CORRECT: SessionDep includes Depends() marker
from narrare._app.dependencies import SessionDep

def get_kb_service(session: SessionDep) -> KBService:
    return KBService(repo=KBRepository(session), ...)

# WRONG: bare AsyncSession → FastAPI treats as query param → 422 (RULE-19)
def get_kb_service(session: AsyncSession) -> KBService: ...
```

---

## Logging (structlog)

```python
logger = structlog.get_logger(__name__)
logger.info("chapter_written", chapter_id=str(chapter_id), tokens_used=result.usage.total_tokens)
```
Never interpolate strings. Never `print()`. Never `logger.exception()` — use `error(exc_info=True)`.

---

## Pydantic Models

```python
class WriteChapterRequest(BaseModel):
    model_config = ConfigDict(frozen=True)  # immutable requests
    chapter_id: UUID
    mode: WritingMode
    language: str = Field(default="en", min_length=2, max_length=5)
    author_instructions: str | None = Field(default=None, max_length=2000)

```

---

## SQLAlchemy Models

```python
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase): pass

class Chapter(Base):
    __tablename__ = "chapters"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    novel_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("novels.id"), index=True)
    title: Mapped[str] = mapped_column(String(500))
    content: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())
```
Always use `Mapped[]` for all columns. Never legacy `Column()`.

---

## Migration Discipline

Every model change requires Alembic migration (RULE-14): Model → Migration → upgrade() → downgrade() → Cross-table check → Regression test → Integration test.

---

## Repository Pattern

Repositories receive `AsyncSession`, return domain objects or `None`. DB queries only, no business logic. Methods: `get_by_id`, `list_by_*`, `create`, `update`, `delete`. Use `flush()` (not `commit()`) to get IDs without committing.

---

## Docstrings (Google style)

Every public function in `core/` and service files. Format: one-line summary, blank line, `Args:`, `Returns:`, `Raises:` sections. See full examples in `docs/development/coding-standards.md`.

---

**Reference**: `docs/development/coding-standards.md` (601 lines) · `narrare-dev/examples/python-patterns` · `narrare-dev/standards/typescript-standards`
