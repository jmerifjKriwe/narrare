"""Regression tests — reattach admission BEFORE the S3 ownership gate.

ADR-052 recovery semantics vs. the IDOR S3 handshake gate (added in the
fix range around ``beb352b8``): a reconnect presenting a ``session_id``
must learn the TYPED ``recovery_failed`` reason before the ownership
gate runs. The gate answers a mismatched owner tuple with a generic
4001 close (chapter ∉ claimed project — foreign ≡ unknown), but the
client drops stale session state only on the typed frame: the frontend
``createSessionMessageHandler`` treats ``recovery_failed`` as terminal,
whereas a 4001 close blind-loops ``WritingSessionSocket``'s reconnect
machinery on the same stale ``session_id``.

Pinned by the integration test
``test_reconnect_with_project_mismatch_returns_ownership_mismatch``;
the shared ownership-seeded handshake harness lives in
``ws_test_helpers.py``.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from narrare.auth import ws_tickets
from tests.unit.api.writing.ws_test_helpers import TICKET_USER, run_handshake

RECOVERY_FAILED_CLOSE_CODE = 4404


@pytest.fixture(autouse=True)
def _clean_ticket_registry() -> None:
    """Isolate the process-global ticket registry per test."""
    ws_tickets._TICKETS.clear()


class TestReattachAdmission:
    """Reconnects learn the TYPED recovery failure before the S3 gate."""

    async def test_mismatched_owner_tuple_gets_typed_frame_not_gate_4001(self) -> None:
        """Session of novel A reattached via novel B (both caller-owned):
        the gate would 4001 (chapter ∉ B), but the probe's typed answer
        must win."""
        project, other_novel, chapter, session_id = uuid4(), uuid4(), uuid4(), uuid4()
        run = await run_handshake(
            chapter,
            project,
            novel_owners={project: TICKET_USER, other_novel: TICKET_USER},
            chapter_novels={chapter: other_novel},
            session_id=session_id,
            reattach_outcome={"kind": "ownership_mismatch", "session_id": str(session_id)},
        )
        run.control_service.return_value.reattach_session.assert_awaited_once()
        run.websocket.accept.assert_awaited_once()
        run.websocket.send_json.assert_awaited_once()
        assert run.websocket.send_json.await_args.args[0] == {
            "type": "recovery_failed",
            "reason": "ownership_mismatch",
        }
        assert run.websocket.close.await_args.kwargs["code"] == RECOVERY_FAILED_CLOSE_CODE
        # Typed answer preempts the gate — no limits/routing read, no handler.
        run.token_limits_cls.return_value.get_resolved_limits.assert_not_awaited()
        run.resolver.resolve.assert_not_awaited()
        run.build.assert_not_called()

    async def test_unknown_session_id_maps_to_session_not_found_reason(self) -> None:
        project, chapter, session_id = uuid4(), uuid4(), uuid4()
        run = await run_handshake(
            chapter,
            project,
            novel_owners={project: TICKET_USER},
            chapter_novels={chapter: project},
            session_id=session_id,
            reattach_outcome={"kind": "not_found", "session_id": str(session_id)},
        )
        assert run.websocket.send_json.await_args.args[0] == {
            "type": "recovery_failed",
            "reason": "session_not_found",
        }
        assert run.websocket.close.await_args.kwargs["code"] == RECOVERY_FAILED_CLOSE_CODE
        run.build.assert_not_called()

    async def test_admission_passing_still_runs_gate_and_builds_handler(self) -> None:
        """A passing probe does not bypass the ownership gate or resolution."""
        project, chapter, session_id = uuid4(), uuid4(), uuid4()
        run = await run_handshake(
            chapter,
            project,
            novel_owners={project: TICKET_USER},
            chapter_novels={chapter: project},
            session_id=session_id,
            reattach_outcome={"kind": "recovered", "session_id": str(session_id)},
        )
        run.control_service.return_value.reattach_session.assert_awaited_once()
        run.resolver.resolve.assert_awaited_once()
        run.handler.handle.assert_awaited_once_with(
            run.websocket, chapter, str(TICKET_USER), project, session_id=session_id
        )
