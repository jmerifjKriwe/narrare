"""The workbench moves the writing E2E flows share.

Each helper exists because a flow otherwise races the app's own refetches: the
button's click returns before the state it starts has landed, and the next
keystroke or assertion then reads the screen from before it. The helper waits
for the fact the flow depends on, so the flow can say what it proves instead of
sleeping on a clock.
"""

import re
from typing import TYPE_CHECKING

from playwright.sync_api import expect

if TYPE_CHECKING:
    from playwright.sync_api import Page

# The rail row's accessible name: the default label plus its word count.
CHAPTER_ROW = re.compile(r"^Kapitel \d")


def new_chapter(page: Page) -> None:
    """Create a chapter and wait until it is the one the caret reaches.

    A create selects through the chapter list's refetch: the click returns
    before the new row is current, so typing right after it can reach the
    chapter that was open before — or an editor that is about to remount.
    The rail's newest row turning current is the proof the selection landed;
    the caller may type as soon as this returns.
    """
    rail = page.get_by_role("complementary")
    rows = rail.get_by_role("button", name=CHAPTER_ROW)
    before = rows.count()
    before_url = page.url
    page.get_by_role("button", name="Neues Kapitel").click()
    expect(rows).to_have_count(before + 1)
    expect(rows.last).to_have_attribute("aria-current", "true")
    # The row can turn current through the list's fallback before the create's
    # own selection navigates; the address is what proves that navigation
    # landed, so the next click or keystroke cannot race it. The "differs from
    # before" half matters: an earlier create already left a `chapter=`, and
    # the pattern alone would match it.
    expect(page).to_have_url(re.compile(r"[?&]chapter=[^&]+"))
    expect(page).not_to_have_url(before_url)
