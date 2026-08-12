"""Core contracts for the manuscript export pipeline (IO-001 / ADR-081).

Home of the pure-Narrare layer: the normalizer Protocol plus the data shapes
it produces. **Pure Core** (RULE-05: no ``apps/`` imports, no I/O, no
subprocess — testable in isolation).

Non-LLM call-out (applies to this entire package)
-------------------------------------------------
Export defines *no* ``LLMIntent``, *no* ``PromptContext``, *no* agent, *no*
``ModelRegistry``/``PromptComposer`` injection. The normalizer is a pure
transformation; the renderers are subprocess adapters; the service is job
orchestration. None of these is an LLM operation. Importing
``narrare_core.agents`` or ``narrare_core.prompts`` here is a layering
violation of the IO-001 plan.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol
from uuid import UUID  # noqa: TC003 — needed at runtime for Pydantic model resolution

from pydantic import BaseModel


class Language(StrEnum):
    """Primary manuscript language. Drives Typst text(lang:) + hyphenation.

    The three languages the DialogueMark extension detects quotes for (de/en/fr).
    Per-span languages inside the manuscript are carried inline as lang="xx"
    attributes in ``NormalizedManuscript.semantic_html`` — NOT as a separate
    structure — so pandoc and Typst handle them natively.
    """

    DE = "de"
    EN = "en"
    FR = "fr"


class ChapterMeta(BaseModel):
    """Per-chapter metadata, in position order."""

    chapter_id: UUID
    title: str  # scalar string (F-7)
    position: int  # 0-based, ordering source
    volume_id: UUID | None  # None = ungrouped


class ManuscriptMetadata(BaseModel):
    """Manuscript-level metadata assembled by the Backend from novel/project data.

    The Backend reads this (read-only, RULE-22) from the novels/chapters/settings
    features and hands it to the Core normalizer. All fields are scalar strings
    (F-7: never arrays) so they pass straight through to the Typst wrapper.
    """

    title: str
    author: str
    language: Language
    # Optional EPUB metadata (ignored by the PDF/MD renderers):
    isbn: str | None = None
    description: str | None = None


class NormalizedManuscript(BaseModel):
    """Clean semantic form of a manuscript, free of editor artifacts.

    GUARANTEE (asserted by a unit test per custom TipTap mark — Slice 1):
    ``semantic_html`` NEVER contains AIAnnotation or GhostText residue.
    SceneBreak and DialogueMark are normalized to clean semantic equivalents.
    """

    semantic_html: str  # clean HTML (AIAnnotation + GhostText stripped)
    title: str  # scalar string (F-7)
    author: str  # scalar string (F-7)
    language: Language  # primary language; per-span langs inline in HTML
    chapters: list[ChapterMeta]  # ordering + per-chapter metadata


class ManuscriptNormalizer(Protocol):
    """TipTap HTML → clean semantic HTML (Core, pure, no I/O).

    The strip-guarantee is the contract's central invariant:
      - AIAnnotation  (``<span data-ai-generated="true" ...>``)        → STRIPPED
      - GhostText     (decoration-based; defensively stripped if any residue) → STRIPPED
      - SceneBreak    (``<p class="scene-break">* * *</p>`` | ``<hr class="scene-break">``)
                                                                       → normalized scene break
      - DialogueMark  (``<span class="dialogue">…</span>``)            → clean dialogue
    The four exact selector strings are part of this contract; the strip-guarantee
    unit tests assert each one.
    """

    async def normalize(
        self,
        raw_tiptap_html: str,
        metadata: ManuscriptMetadata,
    ) -> NormalizedManuscript: ...
