"""JSON parsing and duplicate-check tests for NameGeneratorService."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from narrare.generation.schemas import GeneratedName

if TYPE_CHECKING:
    from narrare.generation.name_service import NameGeneratorService
    from tests.fakes.fake_llm_gateway import FakeModelRegistry

from .conftest import (
    SAMPLE_ARRAY_RESPONSE,
    SAMPLE_FENCED_RESPONSE,
    SAMPLE_OBJECT_RESPONSE,
    _default_request,
)

# ---------------------------------------------------------------------------
# _parse_names — JSON parsing edge cases
# ---------------------------------------------------------------------------


class TestParseNames:
    """Tests for the _parse_names method — all JSON shapes the LLM might return."""

    async def test_parses_json_array(
        self,
        service: NameGeneratorService,
        fake_registry: FakeModelRegistry,
    ) -> None:
        """Standard case: LLM returns a JSON array."""
        fake_registry.returns(SAMPLE_ARRAY_RESPONSE)

        result = await service.generate_names(_default_request())
        assert len(result.names) == 3

    async def test_parses_json_object_with_names_key(
        self,
        service: NameGeneratorService,
        fake_registry: FakeModelRegistry,
    ) -> None:
        """LLM wraps the array in {"names": [...]}."""
        fake_registry.returns(SAMPLE_OBJECT_RESPONSE)

        result = await service.generate_names(_default_request())
        assert len(result.names) == 2
        assert result.names[0].name == "Kaelen"

    async def test_parses_json_object_without_names_key(
        self,
        service: NameGeneratorService,
        fake_registry: FakeModelRegistry,
    ) -> None:
        fake_registry.returns(json.dumps({"name": "Solara", "meaning": "sun goddess"}))

        result = await service.generate_names(_default_request())
        assert result.names == []
        assert result.count == 0

    async def test_strips_markdown_code_fences(
        self,
        service: NameGeneratorService,
        fake_registry: FakeModelRegistry,
    ) -> None:
        fake_registry.returns(SAMPLE_FENCED_RESPONSE)

        result = await service.generate_names(_default_request())
        assert len(result.names) == 2
        assert result.names[0].name == "Zara"

    async def test_returns_empty_list_for_invalid_json(
        self,
        service: NameGeneratorService,
        fake_registry: FakeModelRegistry,
    ) -> None:
        fake_registry.returns("This is not JSON at all!")

        result = await service.generate_names(_default_request())
        assert result.names == []
        assert result.count == 0

    async def test_returns_empty_list_for_empty_text(
        self,
        service: NameGeneratorService,
        fake_registry: FakeModelRegistry,
    ) -> None:
        fake_registry.returns("")

        result = await service.generate_names(_default_request())
        assert result.names == []

    async def test_skips_non_dict_items_in_array(
        self,
        service: NameGeneratorService,
        fake_registry: FakeModelRegistry,
    ) -> None:
        fake_registry.returns(
            json.dumps(["string_item", {"name": "ValidName", "meaning": "test"}, 42, None])
        )

        result = await service.generate_names(_default_request())
        assert len(result.names) == 1
        assert result.names[0].name == "ValidName"

    async def test_null_name_becomes_empty_string(
        self,
        service: NameGeneratorService,
        fake_registry: FakeModelRegistry,
    ) -> None:
        fake_registry.returns(json.dumps([{"name": None, "meaning": "no name"}]))

        result = await service.generate_names(_default_request())
        assert len(result.names) == 1
        assert result.names[0].name == ""

    async def test_null_pronunciation_becomes_none(
        self,
        service: NameGeneratorService,
        fake_registry: FakeModelRegistry,
    ) -> None:
        fake_registry.returns(
            json.dumps([{"name": "Lira", "pronunciation": None, "meaning": "song"}])
        )

        result = await service.generate_names(_default_request())
        assert result.names[0].pronunciation is None

    async def test_names_key_is_not_a_list_treats_as_single(
        self,
        service: NameGeneratorService,
        fake_registry: FakeModelRegistry,
    ) -> None:
        fake_registry.returns(json.dumps({"names": "not a list"}))

        result = await service.generate_names(_default_request())
        assert len(result.names) == 1
        assert result.names[0].name == ""

    async def test_non_json_scalar_wraps_as_single(
        self,
        service: NameGeneratorService,
        fake_registry: FakeModelRegistry,
    ) -> None:
        fake_registry.returns(json.dumps("just a string"))

        result = await service.generate_names(_default_request())
        assert result.names == []

    async def test_empty_array_returns_empty_list(
        self,
        service: NameGeneratorService,
        fake_registry: FakeModelRegistry,
    ) -> None:
        fake_registry.returns("[]")

        result = await service.generate_names(_default_request())
        assert result.names == []
        assert result.count == 0


# ---------------------------------------------------------------------------
# _check_duplicates — placeholder passthrough
# ---------------------------------------------------------------------------


class TestCheckDuplicates:
    """Tests for _check_duplicates — flags names found in existing list."""

    def test_returns_all_names_unchanged_when_no_match(
        self,
        service: NameGeneratorService,
    ) -> None:
        names = [
            GeneratedName(name="Aria", type="character", name_style="fantasy"),
            GeneratedName(name="Bjorn", type="character", name_style="norse"),
        ]
        result = service._check_duplicates(names, ["Elsa", "Anna"])
        assert len(result) == 2
        assert all(not n.is_duplicate for n in result)

    def test_returns_empty_list_unchanged(
        self,
        service: NameGeneratorService,
    ) -> None:
        result = service._check_duplicates([], ["Elsa"])
        assert result == []

    def test_flags_matching_names(
        self,
        service: NameGeneratorService,
    ) -> None:
        names = [
            GeneratedName(name="Aria", type="character", name_style="fantasy"),
            GeneratedName(name="Elsa", type="character", name_style="norse"),
        ]
        result = service._check_duplicates(names, ["Elsa"])
        assert result[0].is_duplicate is False
        assert result[1].is_duplicate is True
