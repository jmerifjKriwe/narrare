"""CR-AUFG-07-19 Prompt History — contract-shape tests (RULE-03 gate).

Verifies that the ``PromptHistoryServiceProtocol`` exists and exposes the
expected methods BEFORE the service is implemented. Also asserts the wire
schemas exist with the contracted field names so the API↔Frontend parity
(RULE-17) can be locked down early.

Contracts precede services. These tests fail until the Protocol and the
response schemas are declared.
"""

from __future__ import annotations

import inspect

from narrare.prompts.contracts import PromptHistoryServiceProtocol
from narrare.prompts.schemas import SaveOverrideRequest
from narrare.prompts.schemas_prompt_history import (
    PromptHistoryClearedResponse,
    PromptHistoryListResponse,
    PromptHistoryScope,
    PromptRevisionCompareResponse,
    PromptRevisionResponse,
    PromptRevisionRestoredResponse,
)

# ---------------------------------------------------------------------------
# Protocol shape
# ---------------------------------------------------------------------------


def test_protocol_has_save_override_recorded() -> None:
    """PromptHistoryServiceProtocol must expose ``save_override_recorded``."""
    assert hasattr(PromptHistoryServiceProtocol, "save_override_recorded")
    assert inspect.iscoroutinefunction(
        PromptHistoryServiceProtocol.save_override_recorded,
    )


def test_protocol_has_list_history() -> None:
    """PromptHistoryServiceProtocol must expose ``list_history``."""
    assert hasattr(PromptHistoryServiceProtocol, "list_history")
    assert inspect.iscoroutinefunction(PromptHistoryServiceProtocol.list_history)


def test_protocol_has_compare_revisions() -> None:
    """PromptHistoryServiceProtocol must expose ``compare_revisions``."""
    assert hasattr(PromptHistoryServiceProtocol, "compare_revisions")
    assert inspect.iscoroutinefunction(
        PromptHistoryServiceProtocol.compare_revisions,
    )


def test_protocol_has_restore_revision() -> None:
    """PromptHistoryServiceProtocol must expose ``restore_revision``."""
    assert hasattr(PromptHistoryServiceProtocol, "restore_revision")
    assert inspect.iscoroutinefunction(
        PromptHistoryServiceProtocol.restore_revision,
    )


def test_protocol_has_clear_history() -> None:
    """PromptHistoryServiceProtocol must expose ``clear_history``."""
    assert hasattr(PromptHistoryServiceProtocol, "clear_history")
    assert inspect.iscoroutinefunction(PromptHistoryServiceProtocol.clear_history)


# ---------------------------------------------------------------------------
# Wire enum
# ---------------------------------------------------------------------------


def test_scope_enum_has_project_and_user_members() -> None:
    """PromptHistoryScope must expose PROJECT and USER members."""
    assert PromptHistoryScope.PROJECT.value == "project"
    assert PromptHistoryScope.USER.value == "user"


# ---------------------------------------------------------------------------
# Request / response schemas — RULE-17 field parity
# ---------------------------------------------------------------------------


def test_save_override_request_has_optional_change_reason() -> None:
    """SaveOverrideRequest must accept an optional change_reason."""
    fields = SaveOverrideRequest.model_fields
    assert "change_reason" in fields
    # Optional → default is None, not required.
    assert fields["change_reason"].is_required() is False


def test_revision_response_contract_fields() -> None:
    """PromptRevisionResponse exposes the contracted wire fields."""
    fields = set(PromptRevisionResponse.model_fields)
    expected = {
        "id",
        "prompt_id",
        "scope",
        "content",
        "content_hash",
        "actor_id",
        "source",
        "change_reason",
        "restored_from_id",
        "created_at",
        "is_active",
    }
    assert expected <= fields, f"missing fields: {expected - fields}"


def test_history_list_response_contract_fields() -> None:
    """PromptHistoryListResponse exposes pagination + revisions."""
    fields = set(PromptHistoryListResponse.model_fields)
    expected = {"prompt_id", "scope", "total", "limit", "offset", "revisions"}
    assert expected <= fields, f"missing fields: {expected - fields}"


def test_compare_response_contract_fields() -> None:
    """PromptRevisionCompareResponse exposes from/to content + ids."""
    fields = set(PromptRevisionCompareResponse.model_fields)
    expected = {
        "prompt_id",
        "from_id",
        "to_id",
        "from_source",
        "to_source",
        "from_content",
        "to_content",
    }
    assert expected <= fields, f"missing fields: {expected - fields}"


def test_restored_response_contract_fields() -> None:
    """PromptRevisionRestoredResponse exposes the restored revision."""
    fields = set(PromptRevisionRestoredResponse.model_fields)
    expected = {"prompt_id", "restored_revision", "active_content", "previous_active_hash"}
    assert expected <= fields, f"missing fields: {expected - fields}"


def test_cleared_response_contract_fields() -> None:
    """PromptHistoryClearedResponse exposes the deleted count."""
    fields = set(PromptHistoryClearedResponse.model_fields)
    expected = {"prompt_id", "scope", "deleted_count"}
    assert expected <= fields, f"missing fields: {expected - fields}"
