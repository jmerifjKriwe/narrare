"""Integration tests for custom tone CRUD API endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare.settings.schemas_tones import CustomTone

if TYPE_CHECKING:
    from httpx import AsyncClient

TONES_URL = "/api/v1/settings/user/tones"


class TestListCustomTones:
    async def test_list_tones_returns_200_empty(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.get(TONES_URL, headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == []

    async def test_list_tones_returns_200_with_tones(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        # Create a tone first
        await client.post(
            TONES_URL,
            json={"name": "Dark", "instructions": "Use dark prose."},
            headers=auth_headers,
        )

        response = await client.get(TONES_URL, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        # Validate each item against the schema
        for item in data:
            tone = CustomTone.model_validate(item)
            assert tone.name
            assert tone.instructions

    async def test_list_tones_returns_401_without_auth(self, client: AsyncClient) -> None:
        response = await client.get(TONES_URL)
        assert response.status_code == 401


class TestCreateCustomTone:
    async def test_create_tone_returns_201(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.post(
            TONES_URL,
            json={"name": "Formal", "instructions": "Write in a formal tone."},
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        tone = CustomTone.model_validate(data)
        assert tone.name == "Formal"
        assert tone.instructions == "Write in a formal tone."
        assert tone.id  # UUID assigned

    async def test_create_tone_returns_401_without_auth(self, client: AsyncClient) -> None:
        response = await client.post(
            TONES_URL,
            json={"name": "NoAuth", "instructions": "Should fail."},
        )
        assert response.status_code == 401

    async def test_create_tone_with_empty_name_returns_422(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.post(
            TONES_URL,
            json={"name": "", "instructions": "Valid instructions."},
            headers=auth_headers,
        )
        assert response.status_code == 422

    async def test_create_tone_with_empty_instructions_returns_422(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.post(
            TONES_URL,
            json={"name": "Valid Name", "instructions": ""},
            headers=auth_headers,
        )
        assert response.status_code == 422

    async def test_create_tone_with_long_name_returns_422(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.post(
            TONES_URL,
            json={"name": "x" * 51, "instructions": "Valid instructions."},
            headers=auth_headers,
        )
        assert response.status_code == 422

    async def test_create_tone_with_long_instructions_returns_422(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.post(
            TONES_URL,
            json={"name": "Valid Name", "instructions": "x" * 501},
            headers=auth_headers,
        )
        assert response.status_code == 422


class TestUpdateCustomTone:
    async def test_update_tone_returns_200(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        # Create a tone first
        create = await client.post(
            TONES_URL,
            json={"name": "Original", "instructions": "Original instructions."},
            headers=auth_headers,
        )
        assert create.status_code == 201
        tone_id = create.json()["id"]

        # Update both fields
        response = await client.put(
            f"{TONES_URL}/{tone_id}",
            json={"name": "Updated", "instructions": "Updated instructions."},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        tone = CustomTone.model_validate(data)
        assert tone.name == "Updated"
        assert tone.instructions == "Updated instructions."
        assert tone.id == tone_id

    async def test_update_tone_name_only(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        # Create a tone first
        create = await client.post(
            TONES_URL,
            json={"name": "Keep Instructions", "instructions": "Stay the same."},
            headers=auth_headers,
        )
        assert create.status_code == 201
        tone_id = create.json()["id"]

        # Update only name
        response = await client.put(
            f"{TONES_URL}/{tone_id}",
            json={"name": "New Name"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        tone = CustomTone.model_validate(data)
        assert tone.name == "New Name"
        assert tone.instructions == "Stay the same."

    async def test_update_tone_returns_401_without_auth(self, client: AsyncClient) -> None:
        response = await client.put(
            f"{TONES_URL}/some-id",
            json={"name": "No Auth"},
        )
        assert response.status_code == 401

    async def test_update_tone_not_found_returns_404_or_422(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.put(
            f"{TONES_URL}/00000000-0000-0000-0000-000000000000",
            json={"name": "Ghost"},
            headers=auth_headers,
        )
        assert response.status_code in (404, 422)


class TestDeleteCustomTone:
    async def test_delete_tone_returns_204(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        # Create
        create = await client.post(
            TONES_URL,
            json={"name": "Delete Me", "instructions": "Use dark prose."},
            headers=auth_headers,
        )
        assert create.status_code == 201
        tone_id = create.json()["id"]

        # Delete
        resp = await client.delete(f"{TONES_URL}/{tone_id}", headers=auth_headers)
        assert resp.status_code == 204

        # Verify gone — list should not contain it
        list_resp = await client.get(TONES_URL, headers=auth_headers)
        assert list_resp.status_code == 200
        ids = [t["id"] for t in list_resp.json()]
        assert tone_id not in ids

    async def test_delete_tone_returns_401_without_auth(self, client: AsyncClient) -> None:
        response = await client.delete(f"{TONES_URL}/some-id")
        assert response.status_code == 401

    async def test_delete_tone_nonexistent_returns_404_or_204(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        """Deleting an already-deleted or nonexistent tone is idempotent."""
        response = await client.delete(
            f"{TONES_URL}/00000000-0000-0000-0000-000000000000",
            headers=auth_headers,
        )
        assert response.status_code in (204, 404)
