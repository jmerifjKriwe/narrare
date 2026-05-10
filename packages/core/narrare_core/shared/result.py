"""
Result type for explicit error handling at service boundaries.

Usage:
    async def write(...) -> Result[ChapterDraft, WritingError]:
        try:
            draft = await _generate(...)
            return Ok(draft)
        except LLMGatewayError as e:
            return Err(WritingError("Generation failed") from e)

    # Caller:
    result = await service.write(request)
    match result:
        case Ok(draft):
            return draft
        case Err(error):
            raise HTTPException(status_code=500, detail=str(error))
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Never, TypeVar

T = TypeVar("T")
E = TypeVar("E", bound=Exception)


@dataclass(frozen=True, slots=True)
class Ok[T]:
    """Successful result containing a value."""

    value: T

    def is_ok(self) -> bool:
        return True

    def is_err(self) -> bool:
        return False

    def unwrap(self) -> T:
        return self.value

    def unwrap_err(self) -> Never:  # type: ignore[return]
        raise ValueError("Called unwrap_err on Ok")

    def __bool__(self) -> bool:
        return True


@dataclass(frozen=True, slots=True)
class Err[E: Exception]:
    """Failed result containing an error."""

    error: E

    def is_ok(self) -> bool:
        return False

    def is_err(self) -> bool:
        return True

    def unwrap(self) -> Never:  # type: ignore[return]
        raise self.error

    def unwrap_err(self) -> E:
        return self.error

    def __bool__(self) -> bool:
        return False


# Result[T, E] is either Ok[T] or Err[E]
type Result[T, E: Exception] = Ok[T] | Err[E]


__all__ = ["Err", "Ok", "Result"]
