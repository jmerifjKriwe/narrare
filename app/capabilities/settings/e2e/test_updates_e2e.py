# The German face's own quotes and dashes are the catalog text these tests
# assert literally — intentional characters, not confusable typos.
"""The update check on the real stack: banner, notes and dismissal in a browser.

The release source is ``ReleaseVendor`` (a real local HTTP server named by the
settings stack's ``NARRA_UPDATE_CHECK_URL``), so the check, the JSON parse and
the browser's rendering are the product's own, only GitHub is not. The test
changes the vendor's mutable tag to a newer release, sees the banner after the
start check, opens the notes in the modal, ignores the version, and proves the
answer survived a fresh page load — the banner stays away.

The vendor is reset and the dismissal neutralised in ``finally``: the settings
database is shared by every module of this suite, and a later test must not
inherit a standing release.
"""

from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Page, expect

from app.capabilities.settings.e2e.conftest import dismiss_update, expect_settings, goto_settings
from app.kernel.version import __version__

if TYPE_CHECKING:
    from app.kernel.testing.release_vendor import ReleaseVendor
    from app.kernel.testing.stack import Stack

pytestmark = [pytest.mark.e2e, pytest.mark.timeout(240)]

RELEASE_TAG = "v999.0.0"
RELEASE_URL = f"https://example.test/narrare/{RELEASE_TAG}"
RELEASE_NOTES = (
    f"## Was ist neu\n\n"
    f"- Narrare {RELEASE_TAG} nennt seinen Namen im Banner.\n\n"
    f"### Fehler behoben\n\n"
    f"- Nichts, was dich beim Schreiben stört."
)

# The catalog's own words, pinned where the leg leans on them (de-DE context).
BANNER_DE = f"Narrare {RELEASE_TAG} ist verfügbar"
HEADING_DE = f"Was sich in {RELEASE_TAG} geändert hat"
NOTES_HEADING = "Was ist neu"
OPEN_RELEASE = "Die Version auf GitHub öffnen"
NOTES_BUTTON = "Versionshinweise"
IGNORE = "Diese Version ignorieren"


def test_the_newer_release_is_announced_read_and_dismissed(
    page: Page, installed: Stack, release_vendor: ReleaseVendor
) -> None:
    """The whole promise in one walk: the banner names the release, the modal
    reads its Markdown, the dismissal reaches the user row, and a reload keeps
    the banner away — no refresh tricks, the browser drives the real API."""
    release_vendor.state.update(tag=RELEASE_TAG, notes=RELEASE_NOTES, url=RELEASE_URL)
    try:
        goto_settings(page)

        # The start check asks once the shell mounts; the banner names the
        # version the vendor serves.
        banner = page.get_by_test_id("update-banner")
        expect(banner).to_be_visible(timeout=15000)
        expect(banner).to_contain_text(BANNER_DE)

        # The notes door opens the modal on the release body: the dialog's
        # heading, the Markdown's own heading, and the link to the source.
        banner.get_by_role("button", name=NOTES_BUTTON).click()
        dialog = page.get_by_role("dialog")
        expect(dialog).to_be_visible()
        expect(dialog.get_by_role("heading", name=HEADING_DE)).to_be_visible()
        expect(dialog.get_by_role("heading", name=NOTES_HEADING)).to_be_visible()
        expect(dialog.get_by_role("link", name=OPEN_RELEASE)).to_have_attribute("href", RELEASE_URL)

        # Ignore this version: the dialog closes, the strip goes at once, and
        # the write lands on the user row.
        dialog.get_by_role("button", name=IGNORE).click()
        expect(banner).to_have_count(0)

        # A fresh page load asks again (force=true) and shows nothing: the
        # dismissal the browser posted is the server's own answer now.
        with page.expect_response(
            lambda response: "/api/updates" in response.url and "force" in response.url
        ) as read:
            page.reload()
        assert read.value.ok, read.value.status
        expect_settings(page)
        page.wait_for_timeout(300)  # a beat: a rendered banner would stand
        expect(page.get_by_test_id("update-banner")).to_have_count(0)
        expect(page.get_by_test_id("update-toast")).to_have_count(0)
    finally:
        # The suite shares this database and this worker's vendor: leave both
        # as a fresh instance would have them.
        release_vendor.state.update(tag=__version__, notes="", url="")
        dismiss_update(__version__)
