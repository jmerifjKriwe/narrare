# Coding Standards — Narrare

> These standards apply to all Python and TypeScript code in the project.
> They complement `CONSTRAINTS.md` (architecture rules) — this document
> covers style, patterns, and quality within those constraints.
>
> Maintained by: Implementation Agent
>
> Location: `docs/development/coding-standards.md`

---

## Python Standards

### Python Version & Typing

```python
# Python 3.14. Use modern syntax everywhere.

# Type unions: use | not Union
def process(value: str | None) -> str | None: ...

# Use TypeAlias for complex types
type NovelId = UUID
type ChapterContent = str

# Use Self for fluent builders
from typing import Self
class QueryBuilder:
    def filter(self, **kwargs) -> Self: ...

# ParamSpec for decorator typing
from typing import ParamSpec, Concatenate
P = ParamSpec("P")

# Never use Any except in approved adapter code
# Never use cast() without a comment explaining why
```

### Naming

```python
# Classes: PascalCase
class ChapterWritingService: ...

# Functions, methods, variables: snake_case
async def write_chapter(...) -> WriteResult: ...
chapter_content = ""

# Constants: UPPER_SNAKE_CASE
MAX_CHAPTER_LENGTH = 100_000
DEFAULT_RETRY_ATTEMPTS = 3

# Private: single underscore prefix
self._gateway = gateway      # private attribute
async def _build_context():  # private method

# Type parameters: T, K, V or descriptive
T = TypeVar("T")
EntityT = TypeVar("EntityT", bound=KBEntity)

# Protocols: end with Protocol
class ChapterServiceProtocol(Protocol): ...

# Enums: PascalCase class, UPPER_SNAKE members
class LLMIntent(StrEnum):
    WRITE = "write"
    ANALYSE = "analyse"
    EXTRACT = "extract"
```

### Imports

```python
# Order: stdlib → third-party → internal (core) → internal (api)
# Separated by blank lines, sorted alphabetically within groups

import asyncio
import uuid
from pathlib import Path
from typing import AsyncIterator

import structlog
from fastapi import Depends, HTTPException
from pydantic import BaseModel

from core.llm.gateway import LLMGateway
from core.prompts.composer import PromptComposer

from narrare.chapters.contracts import ChapterServiceProtocol
from narrare.chapters.schemas import ChapterResponse
```

### Async

```python
# Everything in the service layer is async
# Never block the event loop — no time.sleep(), no sync file I/O in hot paths

# Correct: async file I/O
import aiofiles
async with aiofiles.open(path) as f:
    content = await f.read()

# Correct: gather for parallel operations
results = await asyncio.gather(
    service.get_chapter(chapter_id),
    service.get_kb_context(novel_id),
)

# Correct: async generator for streaming
async def stream_response() -> AsyncIterator[str]:
    async for chunk in gateway.stream(...):
        yield chunk
```

### Error Handling

```python
# Domain errors: typed, from a hierarchy
# core/shared/errors.py defines the base hierarchy

class NarrareError(Exception):
    """Base for all Narrare domain errors."""
    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.code = code

class WritingError(NarrareError): ...
class KBError(NarrareError): ...
class LLMGatewayError(NarrareError): ...

# Always convert external exceptions to domain errors at service boundaries
try:
    result = await self._gateway.run(...)
except LLMGatewayError as e:
    logger.error("llm_call_failed", intent=intent.value, error=str(e))
    raise WritingError("Chapter generation failed") from e

# Never swallow exceptions silently (RULE-11)
# Never use bare except:
# Never use except Exception: pass
```

### Result Type Pattern

```python
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")
E = TypeVar("E")

@dataclass(frozen=True)
class Ok(Generic[T]):
    value: T

@dataclass(frozen=True)
class Err(Generic[E]):
    error: E

type Result[T, E] = Ok[T] | Err[E]
```

- Services return `Result[T, E]` instead of raising exceptions across boundaries
- Callers must pattern-match: `match result: case Ok(value): ... case Err(error): ...`
- Internal service errors can still use exceptions, but the PUBLIC API uses Result
- Never return Err with a bare string — always use a typed error class
- Example: a service method returns `Result[Chapter, WritingError]`

### Service Dependency Injection

```python
class ChapterWritingService:
    def __init__(
        self,
        gateway: LLMGateway,
        composer: PromptComposer,
        repo: ChapterRepository,
    ) -> None:
        self._gateway = gateway
        self._composer = composer
        self._repo = repo
```

- All dependencies injected via `__init__`, never instantiated inside methods
- Never `import` a concrete dependency inside a method — receive it in constructor
- Routers create services with injected dependencies (using FastAPI Depends)
- This enables testing with MockLLMGateway, MockRepository, etc.
- If a dependency is missing, flag it — do not create a default inline

### Logging

```python
import structlog
logger = structlog.get_logger(__name__)

# Always bind context, never interpolate strings
logger.info(
    "chapter_written",
    chapter_id=str(chapter_id),
    novel_id=str(novel_id),
    mode=mode.value,
    tokens_used=result.usage.total_tokens,
    duration_ms=elapsed_ms,
)

# Log levels:
# DEBUG  — diagnostic info useful during development
# INFO   — normal operation events worth recording
# WARNING — unexpected but recoverable situations
# ERROR  — failures that affect user-visible behavior
# Never logger.exception() — use logger.error(..., exc_info=True) instead
```

### Pydantic Models

```python
# Request/response models: explicit field definitions
class WriteChapterRequest(BaseModel):
    model_config = ConfigDict(frozen=True)  # immutable requests

    chapter_id: UUID
    mode: WritingMode
    language: str = Field(default="en", min_length=2, max_length=5)
    author_instructions: str | None = Field(default=None, max_length=2000)

# Never use model_validate(dict) for user input — use parse_raw or direct construction
# Always use model_config = ConfigDict(from_attributes=True) for ORM → schema conversion

# Response models: include only what the client needs
class ChapterResponse(BaseModel):
    id: UUID
    title: str
    position: int
    word_count: int
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
```

### SQLAlchemy Models

```python
# Always use DeclarativeBase, not legacy declarative_base()
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Text, Integer
import uuid

class Base(DeclarativeBase):
    pass

class Chapter(Base):
    __tablename__ = "chapters"

    # Use Mapped[] for all columns — fully typed
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    novel_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("novels.id"), index=True)
    title: Mapped[str] = mapped_column(String(500))
    content: Mapped[str] = mapped_column(Text, default="")
    position: Mapped[int] = mapped_column(Integer, default=0)
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        default=func.now(), onupdate=func.now()
    )
```

### Repository Pattern

```python
# Repositories: DB queries only, no business logic
# Receive AsyncSession, return domain objects or None

class ChapterRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, chapter_id: UUID) -> Chapter | None:
        result = await self._session.execute(
            select(Chapter).where(Chapter.id == chapter_id)
        )
        return result.scalar_one_or_none()

    async def list_by_novel(
        self, novel_id: UUID, *, limit: int = 100
    ) -> list[Chapter]:
        result = await self._session.execute(
            select(Chapter)
            .where(Chapter.novel_id == novel_id)
            .order_by(Chapter.position)
            .limit(limit)
        )
        return list(result.scalars())

    async def create(self, *, novel_id: UUID, title: str, position: int) -> Chapter:
        chapter = Chapter(novel_id=novel_id, title=title, position=position)
        self._session.add(chapter)
        await self._session.flush()  # get ID without committing
        return chapter
```

### Docstrings

```python
# Every public function/method in core/ and service files
# Format: Google style

async def write_chapter(
    self,
    request: WriteChapterRequest,
    context: PromptContext,
) -> WriteResult:
    """Generate a new chapter draft.

    Args:
        request: Generation parameters including mode, language, and
            optional author instructions.
        context: Assembled prompt context with KB entries and style profile.

    Returns:
        WriteResult with generated text, token usage, and metadata.

    Raises:
        WritingError: If generation fails after all retries.
        ContextTooLargeError: If assembled context exceeds model token limit.
    """
```

---

## TypeScript Standards

### Types

```typescript
// Prefer interface for object shapes, type for unions/intersections
interface Chapter {
  id: string
  title: string
  position: number
  wordCount: number
  updatedAt: string
}

type WritingMode = "new_chapter" | "extend" | "rewrite" | "interactive"
type LoadingState = "idle" | "loading" | "success" | "error"

// Never use any — use unknown and narrow
// Never use non-null assertion (!) — handle null explicitly
// Always type function return values
const getChapter = async (id: string): Promise<Chapter> => { ... }
```

### React Components

```typescript
// Named exports for components (not default — easier to find with search)
// Exception: Next.js page files require default export
//
// Styling: Tailwind CSS v4 utility classes only. No styled-jsx, no CSS modules.
// Design tokens via CSS variables: bg-[var(--color-accent)], text-[var(--color-text-primary)]
// cn() from @/lib/utils merges Tailwind classes safely

interface ChapterItemProps {
  chapter: Chapter
  isActive: boolean
  onSelect: (id: string) => void
}

export function ChapterItem({ chapter, isActive, onSelect }: ChapterItemProps) {
  // hooks at top
  const t = useTranslations("editor")

  // derived values
  const formattedWordCount = chapter.wordCount.toLocaleString()

  // handlers
  const handleClick = () => onSelect(chapter.id)

  // render — Tailwind classes with CSS variable tokens
  return (
    <button
      onClick={handleClick}
      className={cn(
        "flex-1 flex flex-col items-start py-2 px-3 border-none bg-transparent",
        "cursor-pointer rounded-[var(--radius-md)] text-left min-w-0",
        "hover:bg-[var(--color-bg-secondary)]",
        isActive && "bg-[var(--color-accent-light)] text-[var(--color-accent)]"
      )}
    >
      <span className="text-sm font-medium text-[var(--color-text-primary)] overflow-hidden text-ellipsis whitespace-nowrap w-full">
        {chapter.title}
      </span>
      <span className="text-xs text-[var(--color-text-tertiary)] mt-0.5">
        {formattedWordCount} {t("words")}
      </span>
    </button>
  )
}
```

### API Client

```typescript
// Typed API functions using native fetch — never raw fetch in components
// All in packages/web/lib/api/client.ts

// API calls use the central fetchApi<T>() wrapper with auto token refresh.
// Components never call fetch directly — always use these typed functions.

export const chaptersApi = {
  updateContent: async (novelId: string, chapterId: string, content: string) => {
    const { data } = await fetchApi<Chapter>(
      `/novels/${novelId}/chapters/${chapterId}/content`,
      { method: "PUT", body: JSON.stringify({ content }) },
    )
    return data
  },
}

// For SSE streaming (AI responses), use the streaming client:
import { connectSSE } from "@/lib/api/streaming"
```

### i18n — Non-Negotiable

```typescript
// Every user-facing string uses useTranslations()
// Zero hardcoded English in components

// Wrong:
<button>Save Chapter</button>
<p>Your chapter has been saved.</p>

// Correct:
const t = useTranslations("editor")
<button>{t("saveChapter")}</button>
<p>{t("chapterSaved")}</p>

// Adding a new translation key:
// 1. Add the key to packages/i18n/messages/en/<namespace>.json
// 2. Add the same key to packages/i18n/messages/de/<namespace>.json
// 3. Add the same key to packages/i18n/messages/fr/<namespace>.json
// 4. The validate-i18n.ts script will catch missing keys in CI

// Namespaces: common, auth, wizard, dashboard, editor, errors, settings
// Use the namespace matching the feature area — e.g. editor keys go in editor.json
```

---

## Git Commit Convention

All commits must follow Conventional Commits:

```
<type>(<scope>): <description>

feat(writing): add chapter reorder via drag-and-drop
fix(kb): resolve cascade resolver path mismatch for de locale
docs(features): complete WRITE-002 feature specification
chore(deps): update pydantic-ai to 1.85.0
test(auth): add integration tests for token refresh flow
refactor(core): split writing service into focused sub-services
```

Types: `feat`, `fix`, `docs`, `chore`, `test`, `refactor`, `perf`, `ci`
Scope: domain module name or `core`, `deps`, `infra`
Breaking changes: add `!` after type/scope, add `BREAKING CHANGE:` footer

---

> Maintained by: Implementation Agent + Architecture Agent
> Changes require Architecture session sign-off
