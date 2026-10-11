"""Core pipeline-request construction for the writing service (RULE-04).

Extracted from ``_helpers.py`` (which sat at its 400-line RULE-04 limit):
the translation between the API layer's generation-request payloads/rows
and the Core :class:`narrare_core.writing.models.GenerationRequest` the
writing pipeline consumes.

Structured scene snapshot (PLAN-001 spec §8.2): ``scenes_payload``
serializes the POST-time ``GenerateRequest.scenes`` into JSONB-ready rows;
``scenes_from_row`` rebuilds the Core ``SceneSpec`` tuple from the
persisted rows at stream time. ``build_pipeline_request`` threads both
into the Core request — the persisted row is the single state carrier
between POST and stream ("what you approved is what streams").
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from narrare_core.writing.requests import SceneSpec

if TYPE_CHECKING:
    from narrare.writing.models import GenerationRequest
    from narrare.writing.schemas import GenerateRequest
    from narrare_core.writing._enums import GenerationMode
    from narrare_core.writing.models import GenerationRequest as CoreGenerationRequest


def scenes_payload(request: GenerateRequest) -> list[dict[str, object]] | None:
    """Serialize the request's optional scenes into JSONB-ready rows.

    Args:
        request: The validated generate request payload.

    Returns:
        One ``model_dump()`` row per scene, or ``None`` when the request
        carries no scenes (legacy requests keep the column NULL — the
        old ``parse_scenes(outline)`` behavior, spec §8.2).
    """
    if not request.scenes:
        return None
    return [scene.model_dump() for scene in request.scenes]


def scenes_from_row(rows: object) -> tuple[SceneSpec, ...] | None:
    """Rebuild the Core ``SceneSpec`` tuple from the persisted row JSON.

    Tolerant by design: JSONB is schemaless, so non-list cells and
    non-dict entries never raise at stream time. Exactly:

    * no usable dict entries (``None``/non-list/empty, or a list whose
      entries are all non-dicts) → ``None`` → the Core pipeline keeps
      the legacy ``parse_scenes`` fallback;
    * a dict with only unrecognized keys → one ``SceneSpec`` with all
      fields at their defaults (deliberate degrade, not ``None``).

    Args:
        rows: The persisted ``generation_requests.scenes`` JSON. Typed as
            ``object`` because a JSONB cell is schemaless at this
            boundary — validation happens here, not at the ORM.

    Returns:
        The scene specs in stored order, or ``None`` for scene-less rows.
    """
    if not isinstance(rows, list):
        return None
    entries = cast("list[object]", rows)
    specs = tuple(spec for entry in entries if (spec := _spec_from_entry(entry)) is not None)
    return specs or None


def build_pipeline_request(
    request_model: GenerationRequest,
    mode: GenerationMode,
) -> CoreGenerationRequest:
    """Build a core GenerationRequest from the ORM model.

    Args:
        request_model: The persisted generation request.
        mode: The resolved generation mode enum.

    Returns:
        A :class:`~narrare_core.writing.models.GenerationRequest` for the
        pipeline, with the persisted scene snapshot (if any) threaded in
        as the Core ``scenes`` tuple.
    """
    from narrare_core.writing.models import GenerationRequest as CoreGenRequest

    return CoreGenRequest(
        id=request_model.id,
        chapter_id=request_model.chapter_id,
        project_id=request_model.novel_id,
        user_id=request_model.user_id,
        mode=mode,
        tone=request_model.tone,
        scenes=scenes_from_row(request_model.scenes),
    )


# -- Tolerant JSONB readers (module-private, RULE-06) ----------------------
# JSONB cells are schemaless at this boundary: every reader takes ``object``
# and validates structurally (pyright-strict clean — no unknowns leak).


def _spec_from_entry(entry: object) -> SceneSpec | None:
    """Build one ``SceneSpec`` from a persisted row (``None`` if not a dict)."""
    if not isinstance(entry, dict):
        return None
    row = cast("dict[str, object]", entry)
    return SceneSpec(
        title=_as_str(row.get("title")),
        pov_character_name=_as_str(row.get("pov_character_name")),
        location_name=_as_str(row.get("location_name")),
        present_characters=_presence_pairs(row.get("present_characters")),
        purpose=_as_str(row.get("purpose")),
        conflict=_as_str(row.get("conflict")),
        resolution=_as_str(row.get("resolution")),
        beats=_as_str_list(row.get("beats")),
        status=_as_str(row.get("status")) or "planned",
    )


def _as_str(value: object) -> str:
    """Coerce a JSONB value to ``str`` (non-string → empty)."""
    return value if isinstance(value, str) else ""


def _as_str_list(value: object) -> tuple[str, ...]:
    """Coerce a JSONB value to a tuple of strings (non-list → empty)."""
    if not isinstance(value, list):
        return ()
    return tuple(item for item in cast("list[object]", value) if isinstance(item, str))


def _presence_pairs(value: object) -> tuple[tuple[str, str], ...]:
    """Coerce persisted ``present_characters`` to ``(name, goal)`` pairs."""
    if not isinstance(value, list):
        return ()
    pairs: list[tuple[str, str]] = []
    for entry in cast("list[object]", value):
        if not isinstance(entry, dict):
            continue
        row = cast("dict[str, object]", entry)
        pairs.append((_as_str(row.get("name")), _as_str(row.get("goal"))))
    return tuple(pairs)
