"""CR-08 P2 tests — OLLAMA_DEFAULT_URL single-source enforcement.

Verifies that all 6 occurrences of the Ollama default URL use the
central constant from ``narrare.setup.constants`` instead of a
hardcoded ``"http://localhost:11434"`` string.

See: CR-AUFG-08-06
"""

from __future__ import annotations

from pathlib import Path

# Files known to have contained the hardcoded string
_OLLAMA_FILES: list[str] = [
    "apps/api/narrare/setup/provider_service.py",
    "apps/api/narrare/setup/provider_schemas.py",
    "apps/api/narrare/setup/router.py",
    "apps/api/narrare/settings/user_provider_models_service.py",
]


def test_all_ollama_files_import_constant_instead_of_hardcoding() -> None:
    """Every file that needs an Ollama default must import the constant
    and must NOT contain the raw ``"http://localhost:11434"`` literal.
    """
    narrare_root = Path(__file__).resolve().parents[4]
    for rel_path in _OLLAMA_FILES:
        full_path = narrare_root / rel_path
        assert full_path.exists(), f"File not found: {full_path}"

        source = full_path.read_text()
        # Assert: the file does NOT contain the hardcoded literal
        assert "http://localhost:11434" not in source, (
            f"{rel_path} still contains hardcoded '{'http://localhost:11434'}' — "
            f"must use OLLAMA_DEFAULT_URL from narrare.setup.constants"
        )

        # Assert: the file DOES import the constant
        assert "from narrare.setup.constants import OLLAMA_DEFAULT_URL" in source, (
            f"{rel_path} does not import OLLAMA_DEFAULT_URL"
        )


def test_provider_service_list_models_uses_constant() -> None:
    """provider_service.list_models defaults to OLLAMA_DEFAULT_URL."""
    from narrare.setup.constants import OLLAMA_DEFAULT_URL
    from narrare.setup.provider_service import ProviderService

    svc = ProviderService()
    # ollama_url param should default to the constant
    import inspect

    sig_obj = inspect.signature(svc.list_models)
    default = sig_obj.parameters["ollama_url"].default
    assert default == OLLAMA_DEFAULT_URL, (
        f"Expected list_models ollama_url default to be OLLAMA_DEFAULT_URL "
        f"({OLLAMA_DEFAULT_URL!r}), got {default!r}"
    )


def test_provider_service_validate_connection_uses_constant() -> None:
    """provider_service.validate_connection defaults to OLLAMA_DEFAULT_URL."""
    from narrare.setup.constants import OLLAMA_DEFAULT_URL
    from narrare.setup.provider_service import ProviderService

    svc = ProviderService()
    import inspect

    sig_obj = inspect.signature(svc.validate_connection)
    default = sig_obj.parameters["ollama_url"].default
    assert default == OLLAMA_DEFAULT_URL, (
        f"Expected validate_connection ollama_url default to be "
        f"OLLAMA_DEFAULT_URL ({OLLAMA_DEFAULT_URL!r}), got {default!r}"
    )


def test_provider_schemas_step4_request_uses_constant() -> None:
    """Step4ProviderRequest.ollama_url field default is OLLAMA_DEFAULT_URL."""
    from narrare.setup.constants import OLLAMA_DEFAULT_URL
    from narrare.setup.provider_schemas import Step4ProviderRequest

    field = Step4ProviderRequest.model_fields["ollama_url"]
    assert field.default == OLLAMA_DEFAULT_URL, (
        f"Expected ollama_url default to be OLLAMA_DEFAULT_URL "
        f"({OLLAMA_DEFAULT_URL!r}), got {field.default!r}"
    )


def test_provider_schemas_wizard_state_uses_constant() -> None:
    """WizardState.ollama_url default is OLLAMA_DEFAULT_URL."""
    from narrare.setup.constants import OLLAMA_DEFAULT_URL
    from narrare.setup.provider_schemas import WizardState

    field = WizardState.model_fields["ollama_url"]
    assert field.default == OLLAMA_DEFAULT_URL, (
        f"Expected ollama_url default to be OLLAMA_DEFAULT_URL "
        f"({OLLAMA_DEFAULT_URL!r}), got {field.default!r}"
    )


def test_user_provider_models_service_uses_constant() -> None:
    """user_provider_models_service uses OLLAMA_DEFAULT_URL for fallback."""
    from narrare.settings import user_provider_models_service

    source_path = Path(user_provider_models_service.__file__)
    source = source_path.read_text()
    # Check the constant NAME (not its value) appears in source
    assert "OLLAMA_DEFAULT_URL" in source, f"OLLAMA_DEFAULT_URL constant not used in {source_path}"
    # Verify there's no hardcoded literal (the value is the _variable_, not a string literal)
    assert '"http://localhost:11434"' not in source, (
        f"Hardcoded URL literal still present in {source_path}"
    )
