"""RULE-17 contract tests for WRITE-005 WebSocket session messages.

The frontend consumes ``SessionResponse`` from ``packages/web/lib/api/generation.ts``.
ADR-052 added stop/recovery WebSocket messages, so the backend payload keys for
those messages must remain representable by the TypeScript contract.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SESSION_RESPONSE_PATH = REPO_ROOT / "packages/web/lib/api/generation.ts"
BACKEND_MESSAGE_SOURCES = (
    REPO_ROOT / "apps/api/narrare/writing/ws_payloads.py",
    REPO_ROOT / "apps/api/narrare/writing/ws_message_router.py",
    REPO_ROOT / "apps/api/narrare/writing/ws_handler.py",
)
ADR_052_MESSAGE_TYPES = frozenset(
    {
        "generation_stopped",
        "session_recovered",
        "recovery_failed",
        "connection_lost",
    }
)


def _extract_session_response_fields() -> set[str]:
    """Extract top-level field names from the frontend SessionResponse type."""
    source = SESSION_RESPONSE_PATH.read_text(encoding="utf-8")
    match = re.search(
        r"export\s+interface\s+SessionResponse\s*\{(?P<body>.*?)\n\}",
        source,
        re.DOTALL,
    )
    assert match is not None, "SessionResponse interface not found"

    fields: set[str] = set()
    for line in match.group("body").splitlines():
        field_match = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)\??\s*:", line)
        if field_match is not None:
            fields.add(field_match.group(1))
    return fields


def _extract_backend_payload_fields() -> dict[str, set[str]]:
    """Collect payload keys for ADR-052 backend WebSocket message dicts."""
    payloads: dict[str, set[str]] = {message_type: set() for message_type in ADR_052_MESSAGE_TYPES}

    for source_path in BACKEND_MESSAGE_SOURCES:
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Dict):
                continue
            literal_keys = [
                key.value if isinstance(key, ast.Constant) else None for key in node.keys
            ]
            if "type" not in literal_keys:
                continue
            type_index = literal_keys.index("type")
            value_node = node.values[type_index]
            if not isinstance(value_node, ast.Constant) or not isinstance(value_node.value, str):
                continue
            message_type = value_node.value
            if message_type not in payloads:
                continue
            payloads[message_type].update(key for key in literal_keys if isinstance(key, str))

    return payloads


def test_adr_052_backend_payload_fields_are_declared_in_session_response() -> None:
    """Frontend ``SessionResponse`` must declare every ADR-052 backend payload key."""
    frontend_fields = _extract_session_response_fields()
    backend_payloads = _extract_backend_payload_fields()

    missing_by_type = {
        message_type: sorted(fields - frontend_fields)
        for message_type, fields in backend_payloads.items()
        if fields - frontend_fields
    }

    assert missing_by_type == {}, (
        "SessionResponse is missing backend WebSocket payload fields for ADR-052 "
        f"messages: {missing_by_type}. Update the TS contract or normalize the "
        "backend payload names so stop/recovery messages stay RULE-17 aligned."
    )


def test_session_response_declares_required_stop_recovery_message_types() -> None:
    """Frontend message type union includes all ADR-052 stop/recovery messages."""
    source = SESSION_RESPONSE_PATH.read_text(encoding="utf-8")
    declared_types = set(re.findall(r'\|\s+"([a-z_]+)"', source))

    assert declared_types >= ADR_052_MESSAGE_TYPES
