"""AIProvider is the generated catalog enum, not an API-layer re-declaration (ADR-099)."""

from pydantic import TypeAdapter

from narrare.setup.base_schemas import AIProvider as FromBaseSchemas
from narrare.setup.schemas import AIProvider as FromSchemas
from narrare_core.llm._providers.catalog_generated import AIProvider as Generated

EXPECTED = ("anthropic", "openai", "google", "groq", "ollama", "openrouter", "zai")


def test_base_schemas_reexports_the_generated_enum() -> None:
    assert FromBaseSchemas is Generated


def test_setup_schemas_reexports_the_same_object() -> None:
    assert FromSchemas is Generated


def test_openapi_component_name_and_values_are_unchanged() -> None:
    assert FromBaseSchemas.__name__ == "AIProvider"
    assert tuple(m.value for m in FromBaseSchemas) == EXPECTED


def test_openapi_component_carries_no_description() -> None:
    """Pydantic renders a class docstring as the schema `description`.

    The generated enum therefore must stay docstring-free: a docstring would add
    a `description` to `components.schemas.AIProvider`, i.e. change the public
    contract on re-export. The CI drift check would not catch it (the pre-commit
    hook regenerates the artifact), so it is pinned here.
    """
    assert "description" not in TypeAdapter(FromBaseSchemas).json_schema()
