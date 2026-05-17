"""Shared helpers for fake repository implementations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CallRecord:
    """Record of a single method call on a Fake."""

    method: str
    args: tuple[Any, ...] = ()
    kwargs: dict[str, Any] = field(default_factory=dict)

    def matches(self, expected_kwargs: dict[str, Any]) -> bool:
        """Check if this call's kwargs contain all expected key-value pairs."""
        return all(self.kwargs.get(k) == v for k, v in expected_kwargs.items())


def _apply_setattr(obj: Any, updates: dict[str, Any]) -> None:  # pyright: ignore[reportUnusedFunction]
    """Set attributes on a SQLAlchemy model instance."""
    from sqlalchemy.orm.attributes import set_attribute

    for key, value in updates.items():
        set_attribute(obj, key, value)
