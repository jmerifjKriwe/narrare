"""Novel metadata normalization. The service delegates here; the router stays out."""

from app.capabilities.writing.schemas import NovelUpdate  # noqa: TC001
from app.kernel.contracts.models import (
    AI_ROLES,
    AUTHOR_TYPOLOGIES,
    CANON_STRICTNESS_MAX,
    CANON_STRICTNESS_MIN,
    DRAMATIC_FORM_MAX_LENGTH,
    WORD_GOAL_MAX,
    WORD_GOAL_MIN,
)
from app.kernel.language_tag import fold_language_tag, is_language_tag


class InvalidNovelUpdateError(ValueError):
    """A metadata edit breaks the novel contract; ``field`` names the offender."""

    def __init__(self, field: str) -> None:
        super().__init__(f"invalid {field}")
        self.field = field


NOVEL_STATUSES = ("draft", "revision", "final")
"""The writing states the shelf's pill names (W3): a draft being written,
a revision being worked over, a final that is done. The vocabulary lives
here, at the service boundary the update path already checks — the column
stores a plain string, and the UI maps each value to its localized pill."""


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
        language = fold_language_tag(language)
        # The width and the grammar are the kernel's one home; the
        # interchange path refuses the same values on the way in from
        # an archive.
        if not is_language_tag(language):
            raise InvalidNovelUpdateError("language")
    return language


def _normalize_status(value: str | None) -> str | None:
    status = (value or "").strip() or None
    if status is not None and status not in NOVEL_STATUSES:
        raise InvalidNovelUpdateError("status")
    return status


def _normalize_series_volume(value: int | None) -> int | None:
    # A volume counts from one; zero and below name no book. The ceiling
    # is the Integer column's own (WORD_GOAL_MAX, the target's bound) —
    # refused here rather than overflowing at the flush (review fix).
    # Whether the number has a series to belong to is the service's
    # cross-field check.
    if value is not None and not WORD_GOAL_MIN <= value <= WORD_GOAL_MAX:
        raise InvalidNovelUpdateError("series_volume")
    return value


def _normalize_target_words(value: int | None) -> int | None:
    # The bounds are the kernel contract's own — the same ones setup's
    # request and the new-book dialog carry: a goal counts from one, and the
    # ceiling is the Integer column's, refused here rather than overflowing
    # at the write.
    if value is not None and not WORD_GOAL_MIN <= value <= WORD_GOAL_MAX:
        raise InvalidNovelUpdateError("target_words")
    return value


def _normalize_author_typology(value: str | None) -> str | None:
    # The status rule: trim, whitespace is the honest unset, and the value
    # answers to the shared vocabulary — the one home setup validates against.
    typology = (value or "").strip() or None
    if typology is not None and typology not in AUTHOR_TYPOLOGIES:
        raise InvalidNovelUpdateError("author_typology")
    return typology


def _normalize_dramatic_form(value: str | None) -> str | None:
    # A free string until the template wave pins its vocabulary; the width
    # is the shared bound, the column's own.
    form = (value or "").strip() or None
    if form is not None and len(form) > DRAMATIC_FORM_MAX_LENGTH:
        raise InvalidNovelUpdateError("dramatic_form")
    return form


def _normalize_ai_role(value: str | None) -> str | None:
    role = (value or "").strip() or None
    if role is not None and role not in AI_ROLES:
        raise InvalidNovelUpdateError("ai_role")
    return role


def _normalize_canon_strictness(value: int | None) -> int | None:
    # The wizard's one-to-five track, the shared bounds.
    if value is not None and not CANON_STRICTNESS_MIN <= value <= CANON_STRICTNESS_MAX:
        raise InvalidNovelUpdateError("canon_strictness")
    return value


_COPY_PREFIX = "„"
_COPY_SUFFIX = ' (Kopie)"'
"""The copy's name, as the shelf's plan pins it: ``„<title> (Kopie)"`` —
the German opening quote, the suffix the quick menu's action names."""


def duplicated_title(title: str) -> str:
    """The copy's name for an original title.

    The title column holds 200 characters and the quotes and suffix take
    ten of them, so a long original keeps the first 190 characters of
    itself — the copy always fits, whatever the original's length, and
    duplicating a valid book never fails on its name.
    """
    room = 200 - len(_COPY_PREFIX) - len(_COPY_SUFFIX)
    return f"{_COPY_PREFIX}{title[:room]}{_COPY_SUFFIX}"


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
    if "status" in provided:
        updates["status"] = _normalize_status(changes.status)
    if "series_id" in provided:
        # The id passes through as carried: whether it names a series the
        # user owns needs the database, so the service checks it there.
        updates["series_id"] = changes.series_id
    if "series_volume" in provided:
        updates["series_volume"] = _normalize_series_volume(changes.series_volume)
    if "archived_at" in provided:
        updates["archived_at"] = changes.archived_at
    if "target_words" in provided:
        updates["target_words"] = _normalize_target_words(changes.target_words)
    if "author_typology" in provided:
        updates["author_typology"] = _normalize_author_typology(changes.author_typology)
    if "dramatic_form" in provided:
        updates["dramatic_form"] = _normalize_dramatic_form(changes.dramatic_form)
    if "ai_role" in provided:
        updates["ai_role"] = _normalize_ai_role(changes.ai_role)
    if "canon_strictness" in provided:
        updates["canon_strictness"] = _normalize_canon_strictness(changes.canon_strictness)
    return updates
