"""OUT-direction capability drivers, authoring-assist surfaces (CAP-OUT-08..10).

The three OUT drivers that ASSIST writing rather than read KB content
(``benchmark.drivers.out_direction`` holds the KB-surface half and the
direction's registration facade; ``benchmark.drivers.out_direction_surfaces``
holds the scope/content read surfaces 05-07):

- CAP-OUT-08 ``ProactiveSuggestionsDriver`` — ranked proactive KB
  suggestions for the target chapter. INVENTORY NOTE (02-out,
  CAP-OUT-08 Notes): this endpoint has NO frontend client yet — it is
  API-mounted only, so the runner drives it normally like any mounted
  route.
- CAP-OUT-09 ``ReferenceResolutionDriver`` — @-mention resolution over
  a deterministic probe text built from the corpus reference.
- CAP-OUT-10 ``TemplatesDriver`` — template-type list + one detail.

Shared retrieval probe: ``probe_name`` derives the deterministic query
term from the corpus reference (first person → place → object →
fallback constant) — no randomness, no wall clock. It lives here (its
heaviest consumer is CAP-OUT-09) and is imported by the CAP-OUT-01/02
drivers in ``out_direction``.

Failure/typing contract: see ``benchmark.drivers.in_parsing`` (the
strict accessors + ``guarded`` are the driver-framework plumbing,
shared by both directions). All ten OUT entries are REST-shaped
(registry-verified) — this direction never opens SSE streams.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from benchmark.drivers.in_parsing import (
    as_bool,
    as_float,
    as_int,
    as_list,
    as_opt_text,
    as_text,
    guarded,
    require_target,
    response_field,
)
from benchmark.drivers.out_records import (
    ReferenceResolutionRecord,
    ResolvedRef,
    Suggestion,
    SuggestionsRecord,
    TemplateDetail,
    TemplateInfo,
    TemplatesRecord,
)
from benchmark.drivers.shapes import invoke_rest

if TYPE_CHECKING:
    from benchmark.drivers.base import CapabilityContext, CapabilityDriver, CapabilityResult

PROBE_FALLBACK: Final[str] = "Benchmark"
"""Deterministic probe when the corpus reference carries no entities."""

SUGGESTIONS_MAX_RESULTS: Final[int] = 100
"""API cap for ``max_results`` (le=100); pinned explicitly for determinism."""


# ---------------------------------------------------------------------------
# Deterministic retrieval probe (shared by CAP-OUT-01/02/09)
# ---------------------------------------------------------------------------


def probe_name(ctx: CapabilityContext) -> str:
    """The deterministic retrieval-probe term from the corpus reference."""
    reference = ctx.corpus.reference()
    for entities in (reference.persons, reference.places, reference.objects):
        if entities:
            return entities[0].name
    return PROBE_FALLBACK


# ---------------------------------------------------------------------------
# CAP-OUT-08 — ProactiveSuggestionsDriver (API-mounted, no frontend client)
# ---------------------------------------------------------------------------


def _suggestion(body: object) -> Suggestion:
    """``KBSuggestionResponse`` row."""
    return Suggestion(
        entry_id=as_text(response_field(body, "entry_id")),
        entry_type=as_text(response_field(body, "entry_type")),
        name=as_text(response_field(body, "name")),
        relevance_score=as_float(response_field(body, "relevance_score")),
        similarity=as_float(response_field(body, "similarity")),
        usage_count=as_int(response_field(body, "usage_count")),
        reason=as_text(response_field(body, "reason")),
    )


def _drive_suggestions(ctx: CapabilityContext) -> SuggestionsRecord:
    chapter_id = require_target(ctx, "chapter_id")
    listed = invoke_rest(
        ctx,
        step="CAP-OUT-08",
        method="GET",
        path=f"/api/v1/novels/{ctx.novel_id}/kb/suggestions/{chapter_id}",
        params={"max_results": str(SUGGESTIONS_MAX_RESULTS)},
    )
    return SuggestionsRecord(
        chapter_id=chapter_id,
        suggestions=tuple(_suggestion(item) for item in as_list(listed, "suggestion list")),
    )


class ProactiveSuggestionsDriver:
    """CAP-OUT-08 — ranked suggestions on ``targets['chapter_id']``."""

    def invoke(self, ctx: CapabilityContext) -> CapabilityResult:
        return guarded("CAP-OUT-08", ctx, _drive_suggestions)


# ---------------------------------------------------------------------------
# CAP-OUT-09 — ReferenceResolutionDriver: probe text from the reference
# ---------------------------------------------------------------------------


def _resolved(body: object) -> ResolvedRef:
    """``ReferenceResolution`` row (unmatched mentions keep null ids)."""
    return ResolvedRef(
        mention=as_text(response_field(body, "mention")),
        entry_id=as_opt_text(response_field(body, "entry_id")),
        entry_name=as_opt_text(response_field(body, "entry_name")),
        entity_type=as_opt_text(response_field(body, "entity_type")),
        slug=as_opt_text(response_field(body, "slug")),
    )


def _drive_resolve_references(ctx: CapabilityContext) -> ReferenceResolutionRecord:
    probe = probe_name(ctx)
    text = f"@{probe} trifft @{PROBE_FALLBACK}."
    body = invoke_rest(
        ctx,
        step="CAP-OUT-09",
        method="POST",
        path=f"/api/v1/novels/{ctx.novel_id}/kb/resolve-references",
        json_body={"text": text},
    )
    return ReferenceResolutionRecord(
        resolved=tuple(
            _resolved(resolution)
            for resolution in as_list(response_field(body, "resolved"), "resolution list")
        ),
        html=as_opt_text(response_field(body, "html")),
    )


class ReferenceResolutionDriver:
    """CAP-OUT-09 — @-mention resolution over the deterministic probe text.

    The probe pairs one reference-entity mention (expected to link)
    with the fallback mention (expected to stay unlinked), exercising
    both resolution paths deterministically.
    """

    def invoke(self, ctx: CapabilityContext) -> CapabilityResult:
        return guarded("CAP-OUT-09", ctx, _drive_resolve_references)


# ---------------------------------------------------------------------------
# CAP-OUT-10 — TemplatesDriver: type list + first-type detail
# ---------------------------------------------------------------------------


def _template_info(body: object) -> TemplateInfo:
    """``TemplateInfoResponse`` row."""
    return TemplateInfo(
        entity_type=as_text(response_field(body, "entity_type")),
        scope=as_text(response_field(body, "scope")),
        schema_version=as_text(response_field(body, "schema_version")),
        has_override=as_bool(response_field(body, "has_override")),
        has_update=as_bool(response_field(body, "has_update")),
    )


def _drive_templates(ctx: CapabilityContext) -> TemplatesRecord:
    base = f"/api/v1/novels/{ctx.novel_id}/kb/templates"
    listed = invoke_rest(ctx, step="CAP-OUT-10:list", method="GET", path=base)
    templates = tuple(_template_info(info) for info in as_list(listed, "template info list"))
    detail: TemplateDetail | None = None
    if templates:
        body = invoke_rest(
            ctx,
            step="CAP-OUT-10:detail",
            method="GET",
            path=f"{base}/{templates[0].entity_type}",
        )
        detail = TemplateDetail(
            entity_type=as_text(response_field(body, "entity_type")),
            scope=as_text(response_field(body, "scope")),
            schema_version=as_text(response_field(body, "schema_version")),
            based_on_version=as_opt_text(response_field(body, "based_on_version")),
            is_overridden=as_bool(response_field(body, "is_overridden")),
        )
    return TemplatesRecord(templates=templates, detail=detail)


class TemplatesDriver:
    """CAP-OUT-10 — template reads; detail YAML content stays in the sink."""

    def invoke(self, ctx: CapabilityContext) -> CapabilityResult:
        return guarded("CAP-OUT-10", ctx, _drive_templates)


ASSIST_OUT_DRIVERS: Final[dict[str, type[CapabilityDriver]]] = {
    "CAP-OUT-08": ProactiveSuggestionsDriver,
    "CAP-OUT-09": ReferenceResolutionDriver,
    "CAP-OUT-10": TemplatesDriver,
}
"""cap_id → driver class for the assist half (facade-assembled)."""
