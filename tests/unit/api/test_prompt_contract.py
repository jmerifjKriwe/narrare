"""Regression test: API response field name mismatch (prompt_id vs id).

Bug: The backend PromptInfoResponse schema used field ``id`` instead of
``prompt_id``. The frontend ``PromptInfo`` TypeScript type expects
``prompt_id``, so ``prompt.prompt_id.split("/")`` crashes at runtime because
``prompt_id`` is undefined — the API returns ``id`` instead.

This test ensures the Pydantic schema exposes ``prompt_id`` (not ``id``),
preventing the field-name mismatch from recurring.
"""

from __future__ import annotations


def test_prompt_info_response_has_prompt_id_field() -> None:
    """PromptInfoResponse must expose ``prompt_id`` (not ``id``).

    The frontend consumes ``prompt.prompt_id``. If the backend field is
    named ``id`` instead, the frontend gets ``undefined`` and crashes on
    ``.split("/")``.
    """
    from narrare.prompts.schemas import PromptInfoResponse

    field_names = set(PromptInfoResponse.model_fields.keys())

    assert "prompt_id" in field_names, (
        "PromptInfoResponse is missing the 'prompt_id' field. "
        "Frontend expects prompt.prompt_id — rename 'id' to 'prompt_id'."
    )


def test_prompt_info_response_does_not_have_id_field() -> None:
    """PromptInfoResponse must NOT have a bare ``id`` field.

    Having both ``id`` and ``prompt_id`` would be confusing; having only
    ``id`` is the exact bug this regression test guards against.
    """
    from narrare.prompts.schemas import PromptInfoResponse

    field_names = set(PromptInfoResponse.model_fields.keys())

    assert "id" not in field_names, (
        "PromptInfoResponse has an 'id' field but frontend expects 'prompt_id'. "
        "Rename the field to 'prompt_id' to match the frontend contract."
    )


def test_prompt_id_field_is_str_type() -> None:
    """The prompt_id field must be a string type."""
    from narrare.prompts.schemas import PromptInfoResponse

    field_info = PromptInfoResponse.model_fields.get("prompt_id")
    assert field_info is not None, "Field 'prompt_id' not found on PromptInfoResponse"
    # The annotation should be str
    assert field_info.annotation is str, (
        f"Expected prompt_id annotation to be str, got {field_info.annotation}"
    )
