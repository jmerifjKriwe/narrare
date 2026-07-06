<!-- Context: narrare-dev/examples/python-patterns | Priority: P2 | Source: docs/development/coding-standards.md | Updated: 2026-06-12 -->

# Python Patterns

Python 3.14 patterns for Narrare backend. All code follows these conventions enforced by `check_architecture.py`.

## Typing

```python
# Unions: use | not Union
def process(value: str | None) -> str | None: ...

# Type aliases
type NovelId = UUID
type ChapterContent = str

# Self for fluent APIs
from typing import Self
class QueryBuilder:
    def filter(self, **kwargs) -> Self: ...

# Never use Any except in approved adapter code
# Never use cast() without a comment explaining why
```

## Naming & Imports

- **Classes**: `PascalCase` → `ChapterWritingService`
- **Functions/variables**: `snake_case` → `write_chapter`, `chapter_content`
- **Constants**: `UPPER_SNAKE` → `MAX_CHAPTER_LENGTH`
- **Private**: single `_` prefix → `self._gateway`, `async def _build_context()`
- **Protocols**: end with `Protocol` → `ChapterServiceProtocol`
- **Enums**: `PascalCase` class, `UPPER_SNAKE` members

Import order: **stdlib → third-party → core → api**, separated by blank lines, alphabetical within groups.

## Error Handling

Domain errors form a typed hierarchy. Convert external exceptions at service boundaries. Never use bare `except:` or `except Exception: pass`.

```python
class NarrareError(Exception):
    def __init__(self, message: str, *, code: str | None = None) -> None: ...
class WritingError(NarrareError): ...
class KBError(NarrareError): ...
class LLMGatewayError(NarrareError): ...
```

## Result Type

```python
@dataclass(frozen=True)
class Ok(Generic[T]):
    value: T
@dataclass(frozen=True)
class Err(Generic[E]):
    error: E
type Result[T, E] = Ok[T] | Err[E]
```

Services return `Result[T, E]` across boundaries. Callers pattern-match: `match result: case Ok(v): ... case Err(e): ...`. Never return `Err` with a bare string.

## Dependency Injection

All deps injected via `__init__`, never instantiated inside methods. Routers create services with `FastAPI Depends`.

```python
class ChapterWritingService:
    def __init__(self, registry: ModelRegistry, config: ResolvedModelConfig,
                 repo: ChapterRepository) -> None:
        self._registry = registry
        self._config = config
        self._repo = repo
```

**RULE-19**: Use `SessionDep` (not bare `AsyncSession`) in dependency factories — prevents 422 in production.

## Logging

```python
import structlog
logger = structlog.get_logger(__name__)
logger.info("chapter_written", chapter_id=str(cid), tokens_used=42)
# Never interpolate strings. Never logger.exception() — use logger.error(..., exc_info=True)
```

## Pydantic Models

```python
class WriteChapterRequest(BaseModel):
    model_config = ConfigDict(frozen=True)  # immutable requests
    chapter_id: UUID
    mode: WritingMode

class ChapterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)  # ORM → schema
    id: UUID
    title: str
```

## SQLAlchemy & Repository

- Use `DeclarativeBase` + `Mapped[]` for all columns
- Repositories: DB queries only, no business logic. Receive `AsyncSession`, return domain objects
- Use `select().where()` queries, `flush()` to get IDs without committing

## Migration Discipline (RULE-14)

Every model change requires a matching Alembic migration: model → migration → upgrade/downgrade → cross-table check → regression test → integration test.

## Docstrings

Google style for all public functions: `Args:`, `Returns:`, `Raises:` sections.

**Reference**: `docs/development/coding-standards.md`
**Related**: narrare-dev/examples/typescript-patterns · narrare-dev/examples/testing-patterns · narrare-dev/lookup/directory-structure
