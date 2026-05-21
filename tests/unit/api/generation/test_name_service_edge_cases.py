"""Error handling and edge case tests for NameGeneratorService."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from narrare.generation.name_service import NameGeneratorService
    from tests.fakes.fake_llm_gateway import FakeModelRegistry

from narrare.generation.schemas import NameType

from .conftest import (
    _default_request,
    _json_names_response,
)

# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Verify error propagation and graceful degradation."""

    async def test_registry_error_propagates(
        self,
        service: NameGeneratorService,
        fake_registry: FakeModelRegistry,
    ) -> None:
        """If the registry raises, the service should not swallow it."""
        fake_registry.raises(RuntimeError("LLM provider down"))

        with pytest.raises(RuntimeError, match="LLM provider down"):
            await service.generate_names(_default_request())

    async def test_registry_auth_error_propagates(
        self,
        service: NameGeneratorService,
        fake_registry: FakeModelRegistry,
    ) -> None:
        """Auth errors from the registry should propagate."""
        from narrare_core.shared.errors import LLMAuthError

        fake_registry.raises(LLMAuthError("Invalid API key"))

        with pytest.raises(LLMAuthError, match="Invalid API key"):
            await service.generate_names(_default_request())

    async def test_invalid_json_returns_empty_names_not_exception(
        self,
        service: NameGeneratorService,
        fake_registry: FakeModelRegistry,
    ) -> None:
        """Malformed JSON → empty list, not an exception."""
        fake_registry.returns("{invalid json content")

        result = await service.generate_names(_default_request())
        assert result.names == []
        assert result.count == 0

    async def test_response_metadata_preserved_even_on_empty_names(
        self,
        service: NameGeneratorService,
        fake_registry: FakeModelRegistry,
    ) -> None:
        """Even with 0 names, the response should have correct culture/type."""
        fake_registry.returns("not json")

        result = await service.generate_names(
            _default_request(culture="egyptian", name_type=NameType.CHARACTER)
        )
        assert result.culture == "egyptian"
        assert result.name_type == "character"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Miscellaneous edge cases."""

    async def test_single_name_requested(
        self,
        service: NameGeneratorService,
        fake_registry: FakeModelRegistry,
    ) -> None:
        """Count=1 should work correctly."""
        fake_registry.returns(_json_names_response([{"name": "Solo", "meaning": "the only one"}]))

        result = await service.generate_names(_default_request(count=1))
        assert len(result.names) == 1

    async def test_max_count_requested(
        self,
        service: NameGeneratorService,
        fake_registry: FakeModelRegistry,
    ) -> None:
        """Count=50 (maximum per schema) should work."""
        names = [{"name": f"Name{i}", "meaning": f"meaning {i}"} for i in range(50)]
        fake_registry.returns(_json_names_response(names))

        result = await service.generate_names(_default_request(count=50))
        assert len(result.names) == 50

    async def test_extra_fields_in_json_ignored(
        self,
        service: NameGeneratorService,
        fake_registry: FakeModelRegistry,
    ) -> None:
        """LLM might return extra fields — they should be silently ignored."""
        fake_registry.returns(
            _json_names_response(
                [
                    {"name": "Arin", "meaning": "eagle", "extra_field": "ignored"},
                ]
            )
        )

        result = await service.generate_names(_default_request())
        assert len(result.names) == 1
        assert result.names[0].name == "Arin"

    async def test_unicode_names_preserved(
        self,
        service: NameGeneratorService,
        fake_registry: FakeModelRegistry,
    ) -> None:
        """Unicode characters in names should be preserved intact."""
        fake_registry.returns(
            _json_names_response(
                [
                    {"name": "Königin", "meaning": "queen"},
                    {"name": "東京", "meaning": "eastern capital"},
                ]
            )
        )

        result = await service.generate_names(_default_request())
        assert result.names[0].name == "Königin"
        assert result.names[1].name == "東京"

    async def test_numeric_name_converted_to_string(
        self,
        service: NameGeneratorService,
        fake_registry: FakeModelRegistry,
    ) -> None:
        """If LLM returns name as a number, it's converted to string."""
        fake_registry.returns(json.dumps([{"name": 42, "meaning": "the answer"}]))

        result = await service.generate_names(_default_request())
        assert len(result.names) == 1
        assert result.names[0].name == "42"

    async def test_missing_name_key_defaults_to_empty_string(
        self,
        service: NameGeneratorService,
        fake_registry: FakeModelRegistry,
    ) -> None:
        """If LLM returns an object without 'name' key, defaults to empty string."""
        fake_registry.returns(json.dumps([{"meaning": "unknown entity"}]))

        result = await service.generate_names(_default_request())
        assert len(result.names) == 1
        assert result.names[0].name == ""
