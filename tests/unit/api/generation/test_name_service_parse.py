"""JSON parsing and duplicate-check tests for NameGeneratorService."""

from __future__ import annotations

import json
import uuid
from typing import TYPE_CHECKING

from narrare.generation.schemas import GeneratedName

if TYPE_CHECKING:
    from narrare.generation.name_service import NameGeneratorService
    from tests.fakes.fake_llm_gateway import FakeLLMGateway

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
        fake_gateway: FakeLLMGateway,
    ) -> None:
        """Standard case: LLM returns a JSON array."""
        fake_gateway.returns(SAMPLE_ARRAY_RESPONSE)

        result = await service.generate_names(_default_request())
        assert len(result.names) == 3

    async def test_parses_json_object_with_names_key(
        self,
        service: NameGeneratorService,
        fake_gateway: FakeLLMGateway,
    ) -> None:
        """LLM wraps the array in {"names": [...]}."""
        fake_gateway.returns(SAMPLE_OBJECT_RESPONSE)

        result = await service.generate_names(_default_request())
        assert len(result.names) == 2
        assert result.names[0].name == "Kaelen"

    async def test_parses_json_object_without_names_key(
        self,
        service: NameGeneratorService,
        fake_gateway: FakeLLMGateway,
    ) -> None:
        """LLM returns a single object without 'names' key — get("names", []) returns []
        which IS a list, so raw_items=[] and result is empty."""
        fake_gateway.returns(json.dumps({"name": "Solara", "meaning": "sun goddess"}))

        result = await service.generate_names(_default_request())
        # default value for "names" key is [] — which is a list → raw_items = []
        assert result.names == []
        assert result.count == 0

    async def test_strips_markdown_code_fences(
        self,
        service: NameGeneratorService,
        fake_gateway: FakeLLMGateway,
    ) -> None:
        """LLM wraps response in ```json ... ``` — must be stripped."""
        fake_gateway.returns(SAMPLE_FENCED_RESPONSE)

        result = await service.generate_names(_default_request())
        assert len(result.names) == 2
        assert result.names[0].name == "Zara"

    async def test_returns_empty_list_for_invalid_json(
        self,
        service: NameGeneratorService,
        fake_gateway: FakeLLMGateway,
    ) -> None:
        """Malformed JSON → graceful empty list, no exception."""
        fake_gateway.returns("This is not JSON at all!")

        result = await service.generate_names(_default_request())
        assert result.names == []
        assert result.count == 0

    async def test_returns_empty_list_for_empty_text(
        self,
        service: NameGeneratorService,
        fake_gateway: FakeLLMGateway,
    ) -> None:
        """Empty LLM response → empty list."""
        fake_gateway.returns("")

        result = await service.generate_names(_default_request())
        assert result.names == []

    async def test_skips_non_dict_items_in_array(
        self,
        service: NameGeneratorService,
        fake_gateway: FakeLLMGateway,
    ) -> None:
        """Array contains non-dict items — they should be skipped."""
        fake_gateway.returns(
            json.dumps(["string_item", {"name": "ValidName", "meaning": "test"}, 42, None])
        )

        result = await service.generate_names(_default_request())
        assert len(result.names) == 1
        assert result.names[0].name == "ValidName"

    async def test_null_name_becomes_empty_string(
        self,
        service: NameGeneratorService,
        fake_gateway: FakeLLMGateway,
    ) -> None:
        """If LLM returns name: null, it becomes empty string."""
        fake_gateway.returns(json.dumps([{"name": None, "meaning": "no name"}]))

        result = await service.generate_names(_default_request())
        assert len(result.names) == 1
        assert result.names[0].name == ""

    async def test_null_pronunciation_becomes_none(
        self,
        service: NameGeneratorService,
        fake_gateway: FakeLLMGateway,
    ) -> None:
        """Explicit null pronunciation → None."""
        fake_gateway.returns(
            json.dumps([{"name": "Lira", "pronunciation": None, "meaning": "song"}])
        )

        result = await service.generate_names(_default_request())
        assert result.names[0].pronunciation is None

    async def test_names_key_is_not_a_list_treats_as_single(
        self,
        service: NameGeneratorService,
        fake_gateway: FakeLLMGateway,
    ) -> None:
        """If {"names": "string"} — not a list — treat the outer dict as a single item.
        Since the outer dict has no "name" key, the name defaults to empty string."""
        fake_gateway.returns(json.dumps({"names": "not a list"}))

        result = await service.generate_names(_default_request())
        assert len(result.names) == 1
        # The dict {"names": "not a list"} has no "name" key → defaults to ""
        assert result.names[0].name == ""

    async def test_non_json_scalar_wraps_as_single(
        self,
        service: NameGeneratorService,
        fake_gateway: FakeLLMGateway,
    ) -> None:
        """A bare non-dict, non-list JSON value (e.g. a string) wraps as a single item."""
        fake_gateway.returns(json.dumps("just a string"))

        result = await service.generate_names(_default_request())
        # "just a string" is not a dict → skipped → empty
        assert result.names == []

    async def test_empty_array_returns_empty_list(
        self,
        service: NameGeneratorService,
        fake_gateway: FakeLLMGateway,
    ) -> None:
        """LLM returns [] → empty names list."""
        fake_gateway.returns("[]")

        result = await service.generate_names(_default_request())
        assert result.names == []
        assert result.count == 0


# ---------------------------------------------------------------------------
# _check_duplicates — placeholder passthrough
# ---------------------------------------------------------------------------


class TestCheckDuplicates:
    """Tests for _check_duplicates — currently a passthrough."""

    async def test_returns_all_names_unchanged(
        self,
        service: NameGeneratorService,
    ) -> None:
        names = [
            GeneratedName(name="Aria", type="character", culture="fantasy"),
            GeneratedName(name="Bjorn", type="character", culture="norse"),
        ]
        result = await service._check_duplicates(names, uuid.uuid4())
        assert result == names
        assert len(result) == 2

    async def test_returns_empty_list_unchanged(
        self,
        service: NameGeneratorService,
    ) -> None:
        result = await service._check_duplicates([], uuid.uuid4())
        assert result == []
