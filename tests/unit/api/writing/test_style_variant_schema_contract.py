"""Schema contract-parity test for style-variant regeneration (CR-AUFG-07-22).

RULE-17 (API↔Frontend contract parity): the Python
``StyleVariantRegenerateRequest`` is the single source of truth for the
request body.  The TypeScript mirror lives in
``packages/web/lib/api/generation-streams.ts`` (``StyleVariantRegenerateRequest``)
and is enforced by ``packages/web/lib/api/__tests__/style-variants.test.ts``.

This test pins the backend field set, required/optional classification, and the
``StyleVariant`` enum values so any drift on either side surfaces as a test
failure rather than a silent runtime mismatch.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from narrare.writing.schemas_style_variants import StyleVariantRegenerateRequest
from narrare_core.writing.style_variants import StyleVariant

# Canonical contract (RULE-17 SSOT — backend wins).  Mirrored verbatim by the
# TypeScript interface; keep these two declarations in lock-step.
_REQUIRED_FIELDS: frozenset[str] = frozenset({"source_text", "style_variant"})
_OPTIONAL_FIELDS: frozenset[str] = frozenset(
    {"context_before", "context_after", "tone", "language"}
)
_EXPECTED_VARIANT_VALUES: frozenset[str] = frozenset(
    {
        "leaner",
        "more_lyrical",
        "more_tense",
        "more_intimate",
        "more_dialogue",
        "more_sensory",
    }
)


class TestStyleVariantRegenerateRequestContract:
    """The request schema must expose exactly the contracted fields — no more."""

    def test_model_is_basemodel_subclass(self) -> None:
        assert issubclass(StyleVariantRegenerateRequest, BaseModel)

    def test_field_set_matches_contract_exactly(self) -> None:
        """No field may be added or removed without updating the TS mirror."""
        fields = set(StyleVariantRegenerateRequest.model_fields)
        assert fields == _REQUIRED_FIELDS | _OPTIONAL_FIELDS, (
            f"Field drift detected. Expected {_REQUIRED_FIELDS | _OPTIONAL_FIELDS}, got {fields}."
        )

    def test_required_fields_are_required(self) -> None:
        for name in _REQUIRED_FIELDS:
            field = StyleVariantRegenerateRequest.model_fields[name]
            assert field.is_required(), f"{name!r} must be required"

    def test_optional_fields_have_defaults(self) -> None:
        for name in _OPTIONAL_FIELDS:
            field = StyleVariantRegenerateRequest.model_fields[name]
            assert not field.is_required(), f"{name!r} must be optional"

    def test_optional_context_fields_are_nullable(self) -> None:
        # context_before/context_after accept None (frontend omits them).
        for name in ("context_before", "context_after"):
            assert StyleVariantRegenerateRequest.model_fields[name].default is None, (
                f"{name!r} must default to None"
            )


class TestStyleVariantEnumContract:
    """The StyleVariant enum values are the wire format shared with the TS type."""

    def test_enum_has_exactly_six_members(self) -> None:
        assert len(list(StyleVariant)) == 6

    def test_enum_values_match_contract(self) -> None:
        values = {member.value for member in StyleVariant}
        assert values == _EXPECTED_VARIANT_VALUES, (
            f"Variant value drift. Expected {_EXPECTED_VARIANT_VALUES}, got {values}."
        )

    @pytest.mark.parametrize("value", sorted(_EXPECTED_VARIANT_VALUES))
    def test_each_contracted_value_is_accepted(self, value: str) -> None:
        """Every contracted wire value round-trips through the schema."""
        request = StyleVariantRegenerateRequest(
            source_text="A" * 60,
            style_variant=StyleVariant(value),
        )
        assert request.style_variant.value == value

    def test_unknown_variant_value_is_rejected(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            StyleVariantRegenerateRequest(
                source_text="A" * 60,
                style_variant="more_dramatic",  # type: ignore[arg-type]
            )
