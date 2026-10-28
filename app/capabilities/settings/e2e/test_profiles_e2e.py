"""The /settings flow on the real stack: profiles, assignments, the audit.

Everything the provider profiles promise, proven through the UI: two fake
profiles created in the browser, the default flipped, ``writing.continuation``
assigned to the other one — and the continuation in the workbench then lands
on the assigned profile's row in ``llm_calls``, not the default's. The vendor
profile answers the connection test and the model discovery over real HTTP,
its key is shown exactly once (the list shows the mask, an update with an
empty key field keeps the stored one), and deleting the default is refused
naming the way out. The stack runs the Fernet keychain tier
(``NARRE_SECRET_KEY`` set, ``NARRE_KEYRING=off`` — see the stack module).
"""

import asyncio
import re
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Page, expect
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.kernel.db.testsupport import url_for
from app.kernel.testing.a11y import assert_accessible
from app.kernel.testing.vendor import chat_vendor

if TYPE_CHECKING:
    from app.kernel.testing.stack import Stack

pytestmark = [pytest.mark.e2e, pytest.mark.timeout(240)]

BASE = "http://127.0.0.1:3100"
DATABASE = "narrare_v2_settings_e2e"  # this module's own stack (e2e/conftest.py)

VENDOR_KEY = "sk-e2e-key-abcd"  # the last four are the mask the list must show
VENDOR_MASK = "sk-…abcd"


def _rows(statement: str, params: dict[str, object] | None = None) -> list[tuple[object, ...]]:
    """Rows from the stack's own database, as plain tuples.

    Runs in a worker thread: pytest-asyncio keeps a session loop running, and
    asyncio.run refuses to start a second one in the same thread.
    """

    async def run() -> list[tuple[object, ...]]:
        engine = create_async_engine(url_for(DATABASE))
        try:
            async with engine.connect() as connection:
                return [
                    tuple(each) for each in await connection.execute(text(statement), params or {})
                ]
        finally:
            await engine.dispose()

    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, run()).result()


def _profile_id(name: str) -> str:
    """The id of the profile the UI created, straight from the table."""
    [row] = _rows("SELECT id FROM provider_profiles WHERE name = :name", {"name": name})
    return str(row[0])


def _create_profile(
    page: Page,
    name: str,
    model: str,
    *,
    kind: str = "Fake (deterministisch, ohne Netzwerk)",
    base_url: str | None = None,
    api_key: str | None = None,
    temperature: str | None = None,
) -> None:
    """Create one profile through the form, the only way a user can."""
    page.get_by_label("Name", exact=True).fill(name)
    page.get_by_label("Art").select_option(label=kind)
    if base_url is not None:
        page.get_by_label("Serveradresse").fill(base_url)
    page.get_by_label("Modell").fill(model)
    if api_key is not None:
        page.get_by_label("API-Schlüssel").fill(api_key)
    if temperature is not None:
        page.get_by_label("Temperatur").fill(temperature)
    page.get_by_role("button", name="Profil hinzufügen").click()
    expect(page.get_by_role("listitem").filter(has_text=name)).to_be_visible()


def test_profiles_assign_and_audit_end_to_end(page: Page, stack: Stack) -> None:
    """The whole /settings surface, driven as a user drives it."""
    with chat_vendor() as vendor:
        # The gear in the top bar is the door to the settings.
        page.goto(BASE + "/")
        page.get_by_role("link", name="Einstellungen").click()
        expect(page).to_have_url(re.compile(r"/settings$"))
        expect(page.get_by_role("heading", name="Einstellungen")).to_be_visible()
        assert_accessible(page)

        # Two fake profiles; the first becomes the default on its own.
        _create_profile(page, "Fake Eins", "modell-eins")
        eins = page.get_by_role("listitem").filter(has_text="Fake Eins")
        expect(eins.get_by_text("Standard", exact=True)).to_have_count(1)
        _create_profile(page, "Fake Zwei", "modell-zwei")
        zwei = page.get_by_role("listitem").filter(has_text="Fake Zwei")
        expect(zwei.get_by_text("Standard", exact=True)).to_have_count(0)

        # The default flips in one action: Zwei takes the badge, Eins loses it.
        zwei.get_by_role("button", name="Zum Standard machen").click()
        expect(zwei.get_by_text("Standard", exact=True)).to_have_count(1)
        expect(eins.get_by_text("Standard", exact=True)).to_have_count(0)

        # The task tier beats the default: continuation serves from Fake Eins.
        continuation = page.get_by_label("Weiterschreiben")
        continuation.select_option(label="Fake Eins")
        # The PUT's refetch is what moves the select; wait for it before
        # leaving, or the reload below could race the stored row.
        expect(continuation).not_to_have_value("")
        # A fresh visit shows the stored assignment: the mount itself must
        # load it, not the first mutation's refetch.
        page.reload()
        expect(page.get_by_role("heading", name="Einstellungen")).to_be_visible()
        expect(page.get_by_label("Weiterschreiben")).to_have_value(_profile_id("Fake Eins"))
        # The task list names the profile that actually serves the task — the
        # assigned one, not a bare "Automatic" the cascade may contradict.
        expect(page.get_by_text("über Fake Eins")).to_be_visible()
        # The audit-only key is labelled and explained: never printed as its
        # internal key, never offered as an assignment, never given a provider.
        expect(page.get_by_text("Verbindungstest")).to_be_visible()
        expect(
            page.get_by_text("Der Einstellungstest prüft das Profil, das du auswählst")
        ).to_be_visible()
        expect(page.get_by_text("settings.test")).to_have_count(0)

        # A vendor profile carries the masked-key round-trip and the probes,
        # and a tuning column the edit below will clear.
        _create_profile(
            page,
            "Vendor Test",
            "vendor-mini",
            kind="OpenAI-kompatibler Chat",
            base_url=vendor.base_url,
            api_key=VENDOR_KEY,
            temperature="0.7",
        )
        # The create answer is the one response that shows the full key.
        expect(page.get_by_text(VENDOR_KEY)).to_be_visible()
        page.get_by_role("button", name="Verstanden").click()
        expect(page.get_by_text(VENDOR_KEY)).to_have_count(0)

        vendor_row = page.get_by_role("listitem").filter(has_text="Vendor Test")
        expect(vendor_row).to_contain_text(VENDOR_MASK)
        # No rendered surface shows the key again — not the list, not anywhere.
        expect(page.locator("body")).not_to_contain_text(VENDOR_KEY)

        # An update with an empty key field keeps the stored key: the mask
        # survives a rename untouched. A cleared tuning column really
        # clears — an explicit null, not a silent keep of the stored value.
        vendor_row.get_by_role("button", name="Bearbeiten").click()
        page.get_by_label("Name", exact=True).fill("Vendor Umbenannt")
        page.get_by_label("Temperatur").fill("")
        page.get_by_role("button", name="Änderungen speichern").click()
        renamed = page.get_by_role("listitem").filter(has_text="Vendor Umbenannt")
        expect(renamed).to_contain_text(VENDOR_MASK)

        # The cleared column stayed cleared: the re-opened edit reads the
        # row back, and a silently kept 0.7 would reappear right here.
        renamed.get_by_role("button", name="Bearbeiten").click()
        expect(page.get_by_label("Temperatur")).to_have_value("")
        page.get_by_role("button", name="Abbrechen").click()

        # The probes run against the profile's own endpoint, visibly.
        renamed.get_by_role("button", name="Verbindung testen").click()
        expect(renamed.get_by_text(re.compile("Die Verbindung funktioniert"))).to_be_visible()
        renamed.get_by_role("button", name="Modelle anzeigen").click()
        expect(renamed).to_contain_text("vendor-max")
        expect(renamed).to_contain_text("vendor-mini")

        # The default profile cannot be deleted; the error names the way out.
        zwei.get_by_role("button", name="Löschen").click()
        expect(page.get_by_role("alert")).to_contain_text(
            "Lege ein zweites Profil an, mache es zum Standard"
        )
        expect(zwei).to_be_visible()

    # The workbench continuation runs on the assigned profile, in the real
    # database's audit — the default profile never answers this task.
    # The settings page's own back control, in the reader's language.
    page.get_by_role("link", name="Zurück").click()
    page.get_by_role("button", name="Neues Buch").click()
    page.get_by_label("Titel").fill("Die Anbieterprobe")
    page.get_by_role("button", name="Anlegen").click()
    page.get_by_role("link", name="Die Anbieterprobe").click()
    page.get_by_role("button", name="Neues Kapitel").click()
    editor = page.locator(".ProseMirror")
    editor.click()
    page.keyboard.type("Die Anbieterprobe begann.")
    expect(page.get_by_text("Gespeichert")).to_be_visible()

    page.get_by_role("button", name="Weiterschreiben").click()
    ghost = page.locator(".ProseMirror .ghost")
    expect(ghost).to_contain_text("über die Straße.")
    page.keyboard.press("Tab")
    expect(page.locator(".ProseMirror .ghost")).to_have_count(0)
    expect(page.get_by_text("Gespeichert")).to_be_visible()

    assert_accessible(page)

    # The audit row names the assigned profile and its free-text model —
    # not the default's, which is the whole point of the assignment tier.
    [(profile_id, model, cost)] = _rows(
        "SELECT c.profile_id, c.model, c.cost_usd FROM llm_calls c"
        " JOIN novels n ON c.novel_id = n.id"
        " WHERE n.title = 'Die Anbieterprobe' AND c.task_key = 'writing.continuation'"
    )
    assert str(profile_id) == _profile_id("Fake Eins")
    assert model == "modell-eins"
    assert cost == 0.0  # a fake profile is free, not unknown

    # The connection test was audited as settings.test, priced at the local
    # vendor's real 0.0.
    [(test_model, test_status, test_cost)] = _rows(
        "SELECT model, status, cost_usd FROM llm_calls WHERE task_key = 'settings.test'"
    )
    assert (test_model, test_status) == ("vendor-mini", "ok")
    assert test_cost == 0.0


def test_the_new_surfaces_speak_every_language(page: Page, stack: Stack) -> None:
    """The gear and the settings page render in de, en and fr."""
    page.goto(BASE + "/settings")

    # The browser speaks de-DE and nobody chose: German renders.
    expect(page.get_by_role("heading", name="Einstellungen")).to_be_visible()
    expect(page.get_by_role("heading", name="Anbieter")).to_be_visible()
    expect(page.get_by_role("heading", name="Aufgaben")).to_be_visible()
    expect(page.get_by_role("link", name="Einstellungen")).to_be_visible()
    expect(page.get_by_role("link", name="Zurück")).to_be_visible()

    # The bar's quick switch drives the page's language (on /settings the
    # control exists twice; the bar's is the one in the banner).
    switcher = page.get_by_role("banner").get_by_role("combobox")
    switcher.select_option("en")
    expect(page.get_by_role("heading", name="Settings")).to_be_visible()
    expect(page.get_by_role("heading", name="Providers")).to_be_visible()
    expect(page.get_by_role("heading", name="Tasks")).to_be_visible()
    expect(page.get_by_role("link", name="Settings")).to_be_visible()
    expect(page.get_by_role("link", name="Back")).to_be_visible()

    switcher.select_option("fr")
    expect(page.get_by_role("heading", name="Paramètres")).to_be_visible()
    expect(page.get_by_role("heading", name="Fournisseurs")).to_be_visible()
    expect(page.get_by_role("heading", name="Tâches")).to_be_visible()
    expect(page.get_by_role("link", name="Paramètres")).to_be_visible()
    expect(page.get_by_role("link", name="Retour")).to_be_visible()

    switcher.select_option("de")
    expect(page.get_by_role("heading", name="Einstellungen")).to_be_visible()

    assert_accessible(page)
