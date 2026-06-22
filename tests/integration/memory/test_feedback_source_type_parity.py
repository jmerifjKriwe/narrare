"""Cross-layer source taxonomy parity (CR-AUFG-07-24).

Asserts the canonical enum, the API Pydantic Literal, and the frontend
TypeScript union all describe the same closed set of source types. A drift in
any one of the three layers must fail CI here.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal, get_args, get_origin

from narrare.memory.schemas import FeedbackRequest
from narrare_core.memory.source_types import FeedbackSourceType

REPO_ROOT = Path(__file__).resolve().parents[3]


def _extract_ts_union() -> set[str]:
    ts_path = REPO_ROOT / "packages" / "web" / "types" / "feedback.ts"
    text = ts_path.read_text(encoding="utf-8")
    match = re.search(
        r"export\s+type\s+FeedbackSourceType\s*=\s*([^;]+);",
        text,
    )
    assert match is not None, "FeedbackSourceType union missing in types/feedback.ts"
    return {
        part.strip().strip('"').strip("'") for part in match.group(1).split("|") if part.strip()
    }


def _literal_string_values(annotation: object) -> set[str]:
    origin = get_origin(annotation)
    if origin is Literal:
        return {arg for arg in get_args(annotation) if isinstance(arg, str)}
    values: set[str] = set()
    for arg in get_args(annotation):
        values.update(_literal_string_values(arg))
    return values


def _extract_api_literal() -> set[str]:
    field = FeedbackRequest.model_fields["source_type"]
    values = _literal_string_values(field.annotation)
    assert values, "FeedbackRequest.source_type is not backed by string Literal values"
    return values


class TestFeedbackSourceTypeParity:
    def test_core_enum_matches_api_literal(self) -> None:
        core = {member.value for member in FeedbackSourceType}
        assert _extract_api_literal() == core

    def test_core_enum_matches_frontend_union(self) -> None:
        core = {member.value for member in FeedbackSourceType}
        assert _extract_ts_union() == core

    def test_frontend_union_matches_api_literal(self) -> None:
        assert _extract_ts_union() == _extract_api_literal()

    def test_required_sources_are_present(self) -> None:
        core = {member.value for member in FeedbackSourceType}
        required = {
            "co_author_change",
            "kb_field_suggest",
            "kb_enhance_field",
            "kb_improve_suggestion",
            "chat_message",
        }
        assert required.issubset(core)
