"""Regression: the dormant server-side import_path stub is gone (ADR-091).

``starter="import"`` now means: the wizard creates an empty novel and the
frontend commits files afterwards via ``POST /import/commit``. The
``StarterContent.IMPORT`` enum value stays; only the server-path plumbing
(``Step3StarterRequest.import_path``, ``WizardState.import_path`` and the
filesystem check in ``validate_step3``) is removed.
"""

from __future__ import annotations

from narrare.setup.base_schemas import Step3StarterRequest
from narrare.setup.provider_schemas import WizardState
from tests.fakes import FakeDemoLoader


def test_step3_request_has_no_import_path_field() -> None:
    assert "import_path" not in Step3StarterRequest.model_fields


def test_wizard_state_has_no_import_path_field() -> None:
    assert "import_path" not in WizardState.model_fields


def test_starter_import_enum_value_remains() -> None:
    # The starter CHOICE stays; only the server-path mechanism is gone.
    from narrare.setup.schemas import StarterContent

    assert StarterContent.IMPORT.value == "import"


async def test_validate_step3_accepts_import_without_path() -> None:
    from narrare.setup._validation import validate_step3
    from narrare.setup.schemas import StarterContent

    result = await validate_step3(
        Step3StarterRequest(starter=StarterContent.IMPORT), FakeDemoLoader()
    )
    assert result.valid is True
