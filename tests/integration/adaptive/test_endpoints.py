"""Integration tests for the adaptive REST endpoints.

Covers the 200 / 401 / 422 paths per RULE-10. Uses the real DB session
(real Alembic migration, not create_all) and real service DI chain.

Requires: ``just dev-services`` running (PostgreSQL on port 5433).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

if TYPE_CHECKING:
    from httpx import AsyncClient


async def _create_project(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> str:
    """Create a novel + project_settings row; return the project_id."""
    novel_resp = await client.post(
        "/api/v1/novels",
        json={"title": "Adaptive Test Novel", "language": "en"},
        headers=auth_headers,
    )
    assert novel_resp.status_code == 201
    return novel_resp.json()["id"]


class TestGetContext:
    """GET /adaptive/{project_id}/context."""

    @pytest.mark.asyncio
    async def test_returns_defaults_when_no_settings(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """No prior settings row → defaults (enabled=True, weights=spec)."""
        project_id = await _create_project(client, auth_headers)
        response = await client.get(
            f"/api/v1/adaptive/{project_id}/context",
            headers=auth_headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["enabled"] is True
        assert body["weights"]["preference"] == 0.7
        assert body["weights"]["voice_fidelity"] == 0.9
        assert body["has_any_signal"] is False
        assert body["sources"]["preference_text"] == ""

    @pytest.mark.asyncio
    async def test_401_without_auth(
        self,
        client: AsyncClient,
    ) -> None:
        response = await client.get(f"/api/v1/adaptive/{uuid4()}/context")
        assert response.status_code == 401


class TestToggle:
    """POST /adaptive/{project_id}/toggle."""

    @pytest.mark.asyncio
    async def test_toggle_off_then_on(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        project_id = await _create_project(client, auth_headers)

        # Toggle off:
        off = await client.post(
            f"/api/v1/adaptive/{project_id}/toggle",
            json={"enabled": False},
            headers=auth_headers,
        )
        assert off.status_code == 200
        assert off.json()["enabled"] is False

        # Verify persisted (GET reflects the toggle):
        ctx = await client.get(
            f"/api/v1/adaptive/{project_id}/context",
            headers=auth_headers,
        )
        assert ctx.json()["enabled"] is False

        # Toggle back on:
        on = await client.post(
            f"/api/v1/adaptive/{project_id}/toggle",
            json={"enabled": True},
            headers=auth_headers,
        )
        assert on.status_code == 200
        assert on.json()["enabled"] is True

    @pytest.mark.asyncio
    async def test_422_when_body_missing(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        project_id = await _create_project(client, auth_headers)
        response = await client.post(
            f"/api/v1/adaptive/{project_id}/toggle",
            json={},
            headers=auth_headers,
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_401_without_auth(
        self,
        client: AsyncClient,
    ) -> None:
        response = await client.post(
            f"/api/v1/adaptive/{uuid4()}/toggle",
            json={"enabled": True},
        )
        assert response.status_code == 401


class TestSetWeights:
    """POST /adaptive/{project_id}/weights."""

    @pytest.mark.asyncio
    async def test_clamps_out_of_range(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        project_id = await _create_project(client, auth_headers)
        response = await client.post(
            f"/api/v1/adaptive/{project_id}/weights",
            json={
                "preference": -0.5,
                "voice_fidelity": 2.0,
                "style_constraints": 0.5,
                "avoidance": 0.5,
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["weights"]["preference"] == 0.0
        assert body["weights"]["voice_fidelity"] == 1.0
        assert body["weights"]["style_constraints"] == 0.5

        # Persisted:
        ctx = await client.get(
            f"/api/v1/adaptive/{project_id}/context",
            headers=auth_headers,
        )
        assert ctx.json()["weights"]["preference"] == 0.0

    @pytest.mark.asyncio
    async def test_preserves_enabled_flag(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Updating weights MUST NOT silently reset the enabled flag."""
        project_id = await _create_project(client, auth_headers)

        # Toggle off first:
        await client.post(
            f"/api/v1/adaptive/{project_id}/toggle",
            json={"enabled": False},
            headers=auth_headers,
        )

        # Update weights:
        response = await client.post(
            f"/api/v1/adaptive/{project_id}/weights",
            json={"preference": 0.3},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["enabled"] is False  # preserved
        assert response.json()["weights"]["preference"] == 0.3

    @pytest.mark.asyncio
    async def test_401_without_auth(
        self,
        client: AsyncClient,
    ) -> None:
        response = await client.post(
            f"/api/v1/adaptive/{uuid4()}/weights",
            json={"preference": 0.5},
        )
        assert response.status_code == 401


class TestVoiceProfilesTextPopulated:
    """Phase 4 Task 15 — voice_profiles_text populated from KB character data.

    Closes the Phase 2 boundary gap: ``profile_provider`` was None in
    Phase 2/3; Task 15 wires the real Backend ProfileProvider. After this
    task, GET /adaptive/{project_id}/context returns a non-empty
    ``sources.voice_profiles_text`` whenever the project has at least one
    character KB entity with populated ``speech.voice_analysis``.

    Cross-connection seeding: ``BackendProfileProvider`` reads via
    ``get_session_factory()`` (a connection separate from the request's
    transaction-wrapped ``db_session``). The test DB's rollback-isolation
    fixture means data on ``db_session`` is NEVER visible to a separate
    connection — so the populated test seeds user+novel+KBEntry through a
    committed factory session (mirroring the provider's own read path).
    This mirrors the production reality where the singleton/pipeline
    provider reads via its own session.
    """

    @pytest.mark.asyncio
    async def test_voice_profiles_text_non_empty_when_kb_has_voice_analysis(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        from sqlalchemy import text

        from narrare._app.database import get_session_factory
        from narrare.auth.models import User
        from narrare.kb.models import KBEntry
        from narrare.novels.models import Novel

        novel_id = uuid4()
        user_id = uuid4()
        factory = get_session_factory()
        # Seed user + novel + character KBEntry in ONE committed session so
        # all FKs hold and the provider's separate connection can read them.
        async with factory() as session:
            session.add(
                User(
                    id=user_id,
                    email=f"voice-{user_id.hex[:12]}@example.com",
                    hashed_password="unused-jwt-auth",
                )
            )
            session.add(Novel(id=novel_id, user_id=user_id, title="Voice Profile Test"))
            # Flush so the user + novel rows exist before the KBEntry insert
            # (no ORM relationship() to auto-order the FK dependency).
            await session.flush()
            session.add(
                KBEntry(
                    novel_id=novel_id,
                    entity_type="character",
                    name="Alice",
                    slug="alice",
                    metadata_={
                        "speech": {
                            "voice_analysis": {
                                "formality": 0.7,
                                "vocabulary_level": "complex",
                                "sentence_profile": "measured",
                            }
                        }
                    },
                )
            )
            await session.commit()

        try:
            # auth_headers is JWT-based (no DB user lookup), so it works even
            # though the request user differs from the seeded novel owner —
            # the endpoint does not check novel ownership.
            response = await client.get(
                f"/api/v1/adaptive/{novel_id}/context",
                headers=auth_headers,
            )
            assert response.status_code == 200
            body = response.json()
            # Task 15 contract: voice_profiles_text is non-empty + signals.
            assert body["has_any_signal"] is True
            assert "Alice" in body["sources"]["voice_profiles_text"]
            # ADR-055/057 boundary: numeric metrics never reach the text.
            assert "cadence_wpm" not in body["sources"]["voice_profiles_text"]
        finally:
            # CASCADE removes the KBEntry; remove the user explicitly.
            async with factory() as cleanup:
                await cleanup.execute(
                    text("DELETE FROM novels WHERE id=:id"), {"id": str(novel_id)}
                )
                await cleanup.execute(text("DELETE FROM users WHERE id=:id"), {"id": str(user_id)})
                await cleanup.commit()

    @pytest.mark.asyncio
    async def test_voice_profiles_text_empty_when_kb_has_no_voice_analysis(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Regression guard: no characters with voice_analysis → empty."""
        project_id = await _create_project(client, auth_headers)
        response = await client.get(
            f"/api/v1/adaptive/{project_id}/context",
            headers=auth_headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["sources"]["voice_profiles_text"] == ""
