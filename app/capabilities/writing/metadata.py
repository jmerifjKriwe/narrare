"""Novel metadata normalization. The service delegates here; the router stays out."""

import re

from app.capabilities.writing.schemas import NovelUpdate  # noqa: TC001


class InvalidNovelUpdateError(ValueError):
    """A metadata edit breaks the novel contract; ``field`` names the offender."""

    def __init__(self, field: str) -> None:
        super().__init__(f"invalid {field}")
        self.field = field


_LANGUAGE_CODE = re.compile(r"[a-z]{2}(-[A-Za-z]{2,})?")
"""A BCP-47-ish language tag: two lowercase letters, then optionally a
region or script after a dash (`de`, `en-GB`). The export writes the tag
into the archive's front matter; anything looser would not round-trip."""


def _normalize_title(value: str | None) -> str:
    title = (value or "").strip()
    if not title or len(title) > 200:
        raise InvalidNovelUpdateError("title")
    return title


def _normalize_genre(value: str | None) -> str | None:
    genre = (value or "").strip() or None
    if genre is not None and len(genre) > 80:
        raise InvalidNovelUpdateError("genre")
    return genre


def _normalize_author(value: str | None) -> str | None:
    author = (value or "").strip() or None
    if author is not None and len(author) > 200:
        raise InvalidNovelUpdateError("author")
    return author


def _normalize_blurb(value: str | None) -> str | None:
    return (value or "").strip() or None


def _normalize_language(value: str | None) -> str | None:
    language = (value or "").strip() or None
    if language is not None:
        # The primary subtag folds to lowercase; the remainder keeps
        # the case it was typed in (spec §2: DE is de, en-GB stays).
        primary, separator, remainder = language.partition("-")
        language = f"{primary.lower()}{separator}{remainder}"
        # The widths are the columns' own (String(16) here,
        # String(200) above) — the interchange path guards the same
        # widths on the way in from an archive.
        if len(language) > 16 or not _LANGUAGE_CODE.fullmatch(language):
            raise InvalidNovelUpdateError("language")
    return language


def normalized_novel_updates(changes: NovelUpdate) -> dict[str, object]:
    """The carried fields as the values `update_novel` writes.

    Only the fields the body carries are the change: ``model_fields_set``
    tells a carried ``null`` — the cleared state — from a missing field.
    """
    provided = changes.model_fields_set
    updates: dict[str, object] = {}
    if "title" in provided:
        updates["title"] = _normalize_title(changes.title)
    if "genre" in provided:
        updates["genre"] = _normalize_genre(changes.genre)
    if "author" in provided:
        updates["author"] = _normalize_author(changes.author)
    if "blurb" in provided:
        updates["blurb"] = _normalize_blurb(changes.blurb)
    if "language" in provided:
        updates["language"] = _normalize_language(changes.language)
    return updates
