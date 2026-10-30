"""The prompts payloads: the list row, the editor's detail, the save, the diff.

The bundled template is the base layer every read shows (``bundled_content``
in the detail, ``bundled_summary`` in the list); the override is the user's
delta on top, and ``effective_content`` is the source a render would use —
the override's text when one is in force, the bundled template otherwise.
"""

from typing import Literal
from uuid import UUID  # noqa: TC003

from pydantic import BaseModel


class PromptVariable(BaseModel):
    """One variable of the template, with the sample value as its example."""

    name: str
    example: str


class PromptOverride(BaseModel):
    """The override in force for the scope: which tier answered, its content."""

    scope: Literal["global", "novel"]
    content: str


class PromptSummary(BaseModel):
    """One bundled key in the list, with its two override tiers as facts.

    ``override_novel`` is meaningful only when the read carried a
    ``novel_id``; without one there is no novel tier to ask.
    """

    key: str
    novel_scopable: bool
    override_global: bool
    override_novel: bool
    bundled_summary: str


class PromptDetail(BaseModel):
    """One key as the editor shows it: the bundled source, the variable
    legend, the override in force, the source a render would use."""

    bundled_content: str
    variables: list[PromptVariable]
    override: PromptOverride | None
    effective_content: str


class PromptSave(BaseModel):
    """One override write. ``novel_id`` absent or null saves the global tier."""

    content: str
    novel_id: UUID | None = None


class PromptDiff(BaseModel):
    """The bundled template against the override in force for the scope."""

    bundled_content: str
    override_content: str | None


class PromptRefusal(BaseModel):
    """The save gate's 422 body: which rule refused, and what it said."""

    reason: str
    detail: str


class PromptKeyNotFound(BaseModel):
    """The 404 body: no bundled prompt carries the key."""

    detail: str


class ValidationItem(BaseModel):
    """One of the framework's request-validation failures, mirrored so the
    documented 422 union covers both bodies a route can answer with."""

    loc: list[str | int]
    msg: str
    type: str


class ValidationBody(BaseModel):
    """The framework's own 422 body, mirrored for the union beside the
    refusal — FastAPI builds its schema from a dict, so nothing imports."""

    detail: list[ValidationItem]
