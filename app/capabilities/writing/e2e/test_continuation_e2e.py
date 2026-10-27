"""Weiterschreiben proposes a ghost: Tab takes it into the text, Esc leaves nothing.

The continuation stream renders as tentative decoration at the caret; the
chapter only owns the text once Tab commits it (the debounced autosave then
persists it) — and a discarded ghost must never reach the database, which the
reload proves in both directions.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Page, expect
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.kernel.db.testsupport import url_for
from app.kernel.testing.a11y import assert_accessible

if TYPE_CHECKING:
    from app.kernel.testing.stack import Stack

pytestmark = [pytest.mark.e2e, pytest.mark.timeout(240)]

DATABASE = "narrare_v2_e2e"  # the stack's own database (e2e/conftest.py)


def _continuation_audit(title: str) -> tuple[str, str, int, int, str, float | None]:
    """The llm_calls row of the novel a test created, from the stack's database.

    Runs in a worker thread: pytest-asyncio keeps a session loop running, and
    asyncio.run refuses to start a second one in the same thread.
    """

    async def run() -> tuple[str, str, int, int, str, float | None] | None:
        """Read the named novel audit using a fresh async engine, or return None."""
        engine = create_async_engine(url_for(DATABASE))
        async with engine.connect() as connection:
            row = (
                await connection.execute(
                    text(
                        "SELECT status, task_key, input_tokens, output_tokens, response_text,"
                        " cost_usd FROM llm_calls c"
                        " JOIN novels n ON c.novel_id = n.id WHERE n.title = :title"
                    ),
                    {"title": title},
                )
            ).one_or_none()
        await engine.dispose()
        if row is None:
            return None
        return (
            row.status,
            row.task_key,
            row.input_tokens,
            row.output_tokens,
            row.response_text,
            row.cost_usd,
        )

    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, run()).result() or ("", "", 0, 0, "", 0.0)


def _write_a_line(page: Page, title: str, line: str) -> None:
    """Create a novel the only way a user can, open it, and write a line.

    The module's database is shared, so every test owns a title no other uses.
    """
    page.goto("http://127.0.0.1:3100/")
    page.get_by_role("button", name="Neues Buch").click()
    page.get_by_label("Titel").fill(title)
    page.get_by_role("button", name="Anlegen").click()
    page.get_by_role("link", name=title).click()
    page.get_by_role("button", name="Neues Kapitel").click()
    editor = page.locator(".ProseMirror")
    editor.click()
    page.keyboard.type(line)
    expect(page.get_by_text("Gespeichert")).to_be_visible()


def test_the_ghost_is_committed_by_tab_and_survives_reload(page: Page, stack: Stack) -> None:
    """Verify Tab accepts the streamed ghost, autosave persists it, and the call is audited."""
    _write_a_line(page, "Die Windrose", "Die Windrose stand offen.")

    page.get_by_role("button", name="Weiterschreiben").click()

    # The stream becomes a ghost: visible at the caret, decorative until
    # taken. Waiting for the final words proves the whole stream arrived.
    ghost = page.locator(".ProseMirror .ghost")
    expect(ghost).to_contain_text("über die Straße.")
    expect(ghost).to_be_visible()
    # The offer is not invisible: the live region names its arrival.
    expect(page.locator("[data-live-announcer]")).to_contain_text("Am Cursor wartet ein Vorschlag.")

    page.keyboard.press("Tab")

    # The ghost is spent; its text belongs to the document now.
    expect(page.locator(".ProseMirror .ghost")).to_have_count(0)
    expect(page.locator(".ProseMirror")).to_contain_text("über die Straße.")
    expect(page.locator("[data-live-announcer]")).to_contain_text("Vorschlag übernommen.")

    # The accepted text schedules the debounced save; the indicator names
    # its landing, and the reload is the proof it persisted — nothing else
    # writes the chapter.
    expect(page.get_by_text("Gespeichert")).to_be_visible()
    page.reload()
    expect(page.locator(".ProseMirror")).to_contain_text("Die Windrose stand offen.")
    expect(page.locator(".ProseMirror")).to_contain_text("über die Straße.")

    # The call behind the ghost is audited in the real database (plan §3.4):
    # one ok continuation for this novel, tokens counted, the fake free at 0.0.
    status, task_key, input_tokens, output_tokens, response_text, cost_usd = _continuation_audit(
        "Die Windrose"
    )
    assert task_key == "writing.continuation"
    assert status == "ok"
    assert input_tokens > 0
    assert output_tokens > 0
    assert "über die Straße." in response_text
    assert cost_usd == 0.0

    assert_accessible(page)


def test_the_ghost_is_discarded_by_escape_and_leaves_no_trace(page: Page, stack: Stack) -> None:
    """Verify Escape discards the ghost without persisting text or disrupting focus controls."""
    _write_a_line(page, "Die Barkasse", "Die Barkasse legte ab.")

    page.get_by_role("button", name="Weiterschreiben").click()
    ghost = page.locator(".ProseMirror .ghost")
    expect(ghost).to_contain_text("über die Straße.")

    page.keyboard.press("Escape")

    # Gone everywhere, announced as gone, and the written text untouched.
    expect(page.locator(".ProseMirror .ghost")).to_have_count(0)
    expect(page.locator(".ProseMirror")).not_to_contain_text("Der Nebel")
    expect(page.locator("[data-live-announcer]")).to_contain_text("Vorschlag verworfen.")

    # The seam, both directions: the editor's Esc never stepped the focus —
    # the workbench is still at depth 0, rail open, no ?focus in the URL …
    expect(page.get_by_role("complementary")).to_be_visible()
    assert "focus=" not in page.url
    # … and a ghost-free Esc still steps it back, so the window handler did
    # not stand down for good. (The URL names focus=0 explicitly after the
    # step; only focus=1 would be the wrong depth.)
    page.keyboard.press("F9")
    expect(page.get_by_role("complementary")).to_have_count(0)
    assert "focus=1" in page.url
    page.keyboard.press("Escape")
    expect(page.get_by_role("complementary")).to_be_visible()
    assert "focus=1" not in page.url

    # Discarded means never written: the reload shows the line, not the ghost.
    page.reload()
    expect(page.locator(".ProseMirror")).to_contain_text("Die Barkasse legte ab.")
    expect(page.locator(".ProseMirror")).not_to_contain_text("über die Straße.")

    assert_accessible(page)
