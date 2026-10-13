"""Deterministic AI-response catalog for the E2E suite (spec §3, §10).

Browser-layer mocks: one valid response per validator-strict AI surface,
installed via ``page.route()`` by ``tests/e2e/helpers/llm_mocks.mock_llm``.
The factory layer (``NARRARE_E2E_TEST=1`` → pydantic_ai.TestModel) stays
active for everything NOT intercepted here (audit E04: TestModel is
insufficient exactly for these surfaces).

Contract (spec §10 — drift ratchet):
- JSON bodies validate against the REAL app pydantic model (module
  ``validate()`` functions below run in unit tests AND at session start
  from tests/e2e/conftest.py).
- SSE bodies are structurally checked (every ``data:`` line JSON-or-[DONE],
  terminal [DONE]) and event envelopes validate against their stream-event
  model where one exists.
- UUID-typed response fields carry REAL UUIDs (pydantic rejects fakes).

Route-handler interplay: handlers installed by mock_llm use
``route.fallback()`` on method mismatch or url_exclude hit, so they compose
with the auth-proxy route (``**/api/v1/**``) installed by session fixtures
regardless of registration order.

Route decision: the generation START POST
(``/writing/chapters/{id}/generate``) is NOT mocked — it creates the real
request row so accept/reject keep working end-to-end; only the stream GET
is intercepted. That GET is exactly where the validator-strict agent dies
under TestModel (audit E04).
"""

from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass(frozen=True)
class RouteSpec:
    """One deterministic browser-layer response for an AI surface."""

    capability: str
    variant: str  # "happy" | "error"
    pattern: str  # Playwright glob matched against the full URL
    method: str  # "GET" | "POST"
    status: int = 200
    content_type: str = "application/json"
    body: str = ""
    url_exclude: str | None = None  # handler falls back when this is in the URL


def assert_sse_body_wellformed(body: str) -> list[dict[str, object]]:
    """Structural SSE check: JSON-or-[DONE] data lines + terminal [DONE]."""
    events: list[dict[str, object]] = []
    saw_done = False
    for raw_line in body.splitlines():
        if not raw_line.startswith("data: "):
            continue
        payload = raw_line[len("data: ") :]
        if payload == "[DONE]":
            saw_done = True
            continue
        events.append(json.loads(payload))
    if not saw_done:
        raise ValueError("SSE body missing terminal 'data: [DONE]'")
    return events


def entries_for(capability: str, variant: str) -> list[RouteSpec]:
    """All specs for one capability+variant; raises listing known names."""
    specs = [s for s in CATALOG if s.capability == capability and s.variant == variant]
    if not specs:
        known = sorted({f"{s.capability}/{s.variant}" for s in CATALOG})
        raise ValueError(f"Unknown capability/variant: {capability!r}/{variant!r}. Known: {known}")
    return specs


def _concat_catalogs() -> list[RouteSpec]:
    from tests.e2e.mocks import catalog_analysis, catalog_kb, catalog_writing

    return [
        *catalog_writing.SPECS,
        *catalog_analysis.SPECS,
        *catalog_kb.SPECS,
    ]


def validate_catalog() -> None:
    """Run every module validator (spec §10 drift ratchet). Raises loudly."""
    from tests.e2e.mocks import catalog_analysis, catalog_kb, catalog_writing

    for module_name, validate in (
        ("catalog_writing", catalog_writing.validate),
        ("catalog_analysis", catalog_analysis.validate),
        ("catalog_kb", catalog_kb.validate),
    ):
        try:
            validate()
        except Exception as exc:
            # Re-raise with catalog context (RULE-11: never silent).
            raise RuntimeError(f"Mock catalog validation failed in {module_name}: {exc}") from exc
    # SSE capabilities must ship an error variant (spec §3: failure-path
    # tests). Capabilities with no specs yet (stubs during catalog growth)
    # are skipped — the check arms itself as entries land.
    for capability in (
        "generation_stream",
        "coreference_stream",
        "character_voice_stream",
        "consistency_stream",
    ):
        variants = {s.variant for s in CATALOG if s.capability == capability}
        if not variants:
            continue
        assert {"happy", "error"} <= variants, (
            f"{capability}: SSE capabilities need happy+error variants, has {variants}"
        )


# Imported lazily above to avoid import cycles at module import time.
CATALOG: list[RouteSpec] = _concat_catalogs()
