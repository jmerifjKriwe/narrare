"""Scene continuation on the real stack (W4 §5): the SSE door, end to end.

The endpoint ``POST /api/writing/scenes/{id}/continue`` is driven through the
real API and the real Postgres, the fake provider the one permitted boundary
fake (rule 2): the stream's data frames add up to its deterministic prose, the
done event closes it, and the call leaves its audit row. The missing scene is
the honest 404. The coded refusal frames (key-unavailable, prompt-refused incl.
budget) and the foreign-user boundary are pinned byte-for-byte by the
integration oracle (``tests/test_continuation.py``); the UI ghost-text legs —
accept, dismiss, the prompt bar — ride PR4's editor (design G4), so here the
endpoint itself is the subject, on the stack the browser suite shares.
"""

import json
from uuid import uuid4

import pytest

from app.capabilities.writing.e2e.conftest import (
    DATABASE,
    _client,  # pyright: ignore[reportPrivateUsage]  the stack's own client, for the raw body
    continue_scene,
    create_chapter,
    create_novel,
    write_scene,
)
from app.kernel.llm.fake import FakeProvider
from app.kernel.testing.db_rows import rows

pytestmark = [pytest.mark.e2e, pytest.mark.timeout(120)]


def _deltas(body: str) -> list[str]:
    """The text deltas of the SSE data lines, other event payloads ignored."""
    deltas: list[str] = []
    for line in body.splitlines():
        if line.startswith("data: "):
            payload = json.loads(line[len("data: ") :])
            if "delta" in payload:
                deltas.append(payload["delta"])
    return deltas


def test_the_scene_continuation_streams_and_audits(installed: object) -> None:
    """The real stack streams the fake's prose in pieces, closes with done, and
    audits the call against the scene's own novel — free, because fake."""
    novel = create_novel("Der Nebel")
    chapter = create_chapter(str(novel["id"]), "Ankunft")
    scene = write_scene(str(chapter["id"]), "Der Nebel kam von See.")

    response = continue_scene(str(scene["id"]))

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-cache"
    deltas = _deltas(response.text)
    assert len(deltas) > 1  # streamed, not one buffered blob
    assert "".join(deltas) == "".join(FakeProvider.CHUNKS)
    assert "event: done" in response.text
    assert "event: error" not in response.text

    # The honest check: the call left its row, named for the scene's novel.
    audit = rows(
        DATABASE,
        "SELECT task_key, status, novel_id, response_text, cost_usd FROM llm_calls",
    )
    assert len(audit) == 1
    task_key, status, novel_id, response_text, cost_usd = audit[0]
    assert task_key == "writing.continuation"
    assert status == "ok"
    assert str(novel_id) == str(novel["id"])
    assert response_text == "".join(FakeProvider.CHUNKS)
    assert cost_usd == 0.0


def test_a_missing_scene_is_a_404_on_the_real_stack(installed: object) -> None:
    """The plain tier resolves to the fake; a scene that does not exist is the
    honest 404, never a stream."""
    response = continue_scene(str(uuid4()))
    assert response.status_code == 404
    assert response.json()["detail"] == "scene not found"
    assert rows(DATABASE, "SELECT count(*) FROM llm_calls") == [(0,)]


def test_a_prompt_rides_the_real_stack_stream(installed: object) -> None:
    """The optional body (W4 D5) is accepted on the real stack: the stream's
    frames and the audit row are the bare continuation's own — the prompt
    changes the prompt alone, and the fake answers it the same way."""
    novel = create_novel("Der Nebel")
    chapter = create_chapter(str(novel["id"]), "Ankunft")
    scene = write_scene(str(chapter["id"]), "Der Nebel kam von See.")

    response = continue_scene(str(scene["id"]), prompt="Lass Mira am Ufer zögern.")

    assert response.status_code == 200
    assert "".join(_deltas(response.text)) == "".join(FakeProvider.CHUNKS)
    assert "event: done" in response.text
    assert "event: error" not in response.text
    audit = rows(DATABASE, "SELECT task_key, status, novel_id, cost_usd FROM llm_calls")
    assert len(audit) == 1
    task_key, status, novel_id, cost_usd = audit[0]
    assert task_key == "writing.continuation"
    assert status == "ok"
    assert str(novel_id) == str(novel["id"])
    assert cost_usd == 0.0


def test_an_overlong_prompt_is_a_422_on_the_real_stack(installed: object) -> None:
    """The bound refusal is the schema's own on the real stack: a JSON 422
    naming the field before any stream — no partial answer, no audit row."""
    novel = create_novel("Der Nebel")
    chapter = create_chapter(str(novel["id"]), "Ankunft")
    scene = write_scene(str(chapter["id"]), "Der Nebel kam von See.")

    with _client() as client:
        response = client.post(
            f"/api/writing/scenes/{scene['id']}/continue", json={"prompt": "X" * 2001}
        )

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/json")
    assert response.json()["detail"][0]["loc"] == ["body", "prompt"]
    assert rows(DATABASE, "SELECT count(*) FROM llm_calls") == [(0,)]
