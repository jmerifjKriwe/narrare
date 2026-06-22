"""PROMPT-003 (CR-AUFG-07-16) — RULE-17 contract test.

Proves the wire-format contract between the FastAPI Pydantic schemas in
``apps/api/narrare/prompts/schemas.py`` and the TypeScript client types in
``packages/web/types/prompts.ts``. If either side drifts (a field is added,
renamed, or dropped), the affected test fails with a precise diff instead of
a runtime frontend parse error.

Contracts covered (Pydantic model <-> TS interface):

* ``PreviewResponse``        <-> ``PromptPreview``
* ``ResetResponse``          <-> ``PromptResetResult``
* ``LiveTestStartedResponse`` <-> ``PromptLiveTestStarted``

Each test asserts exact set equality of:

1. the top-level JSON keys produced by ``TypeAdapter(Model).dump_json(...)``,
2. the field names declared in the matching TS ``interface``.

A mismatch on either side (or between the two sides) is a contract violation.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from pydantic import TypeAdapter

from narrare.prompts.schemas import (
    LiveTestStartedResponse,
    PreviewResponse,
    ResetResponse,
)

_ROOT = Path(__file__).parents[4]
_TS_PROMPTS = (_ROOT / "packages" / "web" / "types" / "prompts.ts").read_text(encoding="utf-8")

# `interface <Name> {` — captures the declaration line of a TS interface.
_INTERFACE_RE = re.compile(r"interface\s+(?P<name>[A-Za-z_$][\w$]*)\s*\{")
# A single interface member: optional `readonly`, a field name, an optional
# `?`, then `:`. Matches `readonly first_message: string | null;` etc.
_FIELD_RE = re.compile(r"^\s*(?:readonly\s+)?(?P<field>[A-Za-z_$][\w$]*)\??\s*:")


def _ts_interface_fields(source: str, name: str) -> set[str]:
    """Return the field names declared in a named TypeScript interface.

    Uses brace matching so nested ``{ ... }`` (object literal types) are not
    confused with the interface body. None of the PROMPT-003 interfaces nest,
    but the helper stays correct if that changes.
    """
    for match in _INTERFACE_RE.finditer(source):
        if match.group("name") != name:
            continue
        body_start = match.end()  # index just past the opening `{`
        depth = 1
        i = body_start
        while i < len(source) and depth > 0:
            char = source[i]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
            i += 1
        body = source[body_start : i - 1]
        fields: set[str] = set()
        for line in body.splitlines():
            field_match = _FIELD_RE.match(line)
            if field_match is not None:
                fields.add(field_match.group("field"))
        return fields
    raise AssertionError(f"TS interface '{name}' not found in packages/web/types/prompts.ts")


def _assert_parity(
    label: str,
    json_keys: set[str],
    ts_interface: str,
    expected: set[str],
) -> None:
    """Assert Pydantic JSON keys and TS interface fields both equal ``expected``."""
    ts_fields = _ts_interface_fields(_TS_PROMPTS, ts_interface)
    assert json_keys == expected, (
        f"{label}: Pydantic JSON keys drift — expected={sorted(expected)} got={sorted(json_keys)}"
    )
    assert ts_fields == expected, (
        f"{label}: TS '{ts_interface}' fields drift — "
        f"expected={sorted(expected)} got={sorted(ts_fields)}"
    )
    # RULE-17: both sides of the contract agree on the exact field set.
    assert json_keys == ts_fields, (
        f"{label}: Pydantic keys {sorted(json_keys)} != TS '{ts_interface}' {sorted(ts_fields)}"
    )


def test_preview_response_keys_match_ts_prompt_preview() -> None:
    sample = PreviewResponse(
        system_prompt="s",
        user_prompt="u",
        first_message=None,
        cascade_source="bundled",
        variables=[],
        diagnostics=[],
    )
    payload = json.loads(TypeAdapter(PreviewResponse).dump_json(sample))
    assert isinstance(payload, dict)
    _assert_parity(
        label="PreviewResponse",
        json_keys=set(payload),
        ts_interface="PromptPreview",
        expected={
            "system_prompt",
            "user_prompt",
            "first_message",
            "cascade_source",
            "variables",
            "diagnostics",
        },
    )


def test_reset_response_keys_match_ts_prompt_reset_result() -> None:
    sample = ResetResponse(
        reset=True,
        effective_source="bundled",
        effective_content="default",
    )
    payload = json.loads(TypeAdapter(ResetResponse).dump_json(sample))
    assert isinstance(payload, dict)
    _assert_parity(
        label="ResetResponse",
        json_keys=set(payload),
        ts_interface="PromptResetResult",
        expected={"reset", "effective_source", "effective_content"},
    )


def test_live_test_started_response_keys_match_ts_prompt_live_test_started() -> None:
    sample = LiveTestStartedResponse(
        prompt_id="writing/en/new_chapter",
        intent="SUMMARIZE",
        model_id="claude-3-5-haiku",
        rate_limit_remaining=4,
    )
    payload = json.loads(TypeAdapter(LiveTestStartedResponse).dump_json(sample))
    assert isinstance(payload, dict)
    _assert_parity(
        label="LiveTestStartedResponse",
        json_keys=set(payload),
        ts_interface="PromptLiveTestStarted",
        expected={"prompt_id", "intent", "model_id", "rate_limit_remaining"},
    )
