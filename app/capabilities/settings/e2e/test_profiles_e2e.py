"""The provider cluster's flow on the real stack: providers, models, assignments.

Everything the cluster promises, proven through the UI: a fake provider
created in the browser, two models under it, the default flipped,
``writing.continuation`` assigned to one of them — and the continuation in
the workbench then lands on the assigned model's row in ``llm_calls``, not
the default's. The vendor provider answers the connection test (run on its
model) and the model discovery (run on the provider, the row that owns the
endpoint) over real HTTP; its key is shown exactly once, the list shows the
mask, an update with an empty key field keeps the stored one, and deleting
the default model is refused naming the way out. The stack runs the Fernet
keychain tier (``NARRE_SECRET_KEY`` set, ``NARRE_KEYRING=off`` — see the
stack module).
"""

import asyncio
import re
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Locator, Page, expect
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.kernel.db import testsupport
from app.kernel.db.testsupport import url_for
from app.kernel.testing.a11y import assert_accessible
from app.kernel.testing.stack import WEB_URL
from app.kernel.testing.vendor import chat_vendor

if TYPE_CHECKING:
    from app.kernel.testing.stack import Stack

pytestmark = [pytest.mark.e2e, pytest.mark.timeout(240)]

BASE = WEB_URL
# this run's stack database (e2e/conftest.py)
DATABASE = testsupport.test_database("narrare_v2_settings_e2e")

VENDOR_KEY = "sk-e2e-key-abcd"  # the last four are the mask the list must show
VENDOR_MASK = "sk-…abcd"

PROVIDERS = "Anbieter"  # the section's heading, in the stack's de
MODELS = "Modelle"
TASKS = "Aufgaben"


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


def _model_id(name: str) -> str:
    """The id of the model the UI created, straight from the table."""
    [row] = _rows("SELECT id FROM provider_profiles WHERE name = :name", {"name": name})
    return str(row[0])


def _region(page: Page, name: str) -> Locator:
    """One of the provider page's three labelled sections."""
    return page.get_by_role("region", name=name, exact=True)


def _create_provider(
    page: Page,
    name: str,
    *,
    kind: str = "Fake (deterministisch, ohne Netzwerk)",
    base_url: str | None = None,
    api_key: str | None = None,
) -> Locator:
    """Create one provider through the form, the only way a user can."""
    section = _region(page, PROVIDERS)
    section.get_by_label("Name", exact=True).fill(name)
    # A select's label wraps it, so its text runs "Art <selected option>" —
    # a substring match, which an exact one would never answer.
    section.get_by_label("Art").select_option(label=kind)
    if base_url is not None:
        section.get_by_label("Serveradresse").fill(base_url)
    if api_key is not None:
        section.get_by_label("API-Schlüssel").fill(api_key)
    section.get_by_role("button", name="Anbieter hinzufügen").click()
    row = section.get_by_role("listitem").filter(has_text=name)
    expect(row).to_be_visible()
    return row


def _create_model(
    page: Page,
    name: str,
    provider: str,
    model: str,
    *,
    temperature: str | None = None,
) -> Locator:
    """Create one model under a provider through the form, the only way a user can."""
    section = _region(page, MODELS)
    section.get_by_label("Name", exact=True).fill(name)
    section.get_by_label("Anbieter").select_option(label=provider)
    section.get_by_label("Modell", exact=True).fill(model)
    if temperature is not None:
        section.get_by_label("Temperatur").fill(temperature)
    section.get_by_role("button", name="Modell hinzufügen").click()
    row = section.get_by_role("listitem").filter(has_text=name)
    expect(row).to_be_visible()
    return row


def test_providers_models_assign_and_audit_end_to_end(page: Page, stack: Stack) -> None:
    """The whole provider cluster, driven as a user drives it."""
    with chat_vendor() as vendor:
        # The gear in the top bar is the door to the settings; the hub names
        # the clusters, and the Anbieter card is the door to the provider
        # page, where the whole flow below happens. The gear is scoped to
        # the banner: the rail's Settings anchor (P8) is the settings
        # area's own twin, and an unscoped name query finds both.
        page.goto(BASE + "/")
        page.get_by_role("banner").get_by_role("link", name="Einstellungen").click()
        expect(page).to_have_url(re.compile(r"/settings$"))
        expect(page.get_by_role("heading", name="Einstellungen")).to_be_visible()
        assert_accessible(page)
        page.get_by_role("region", name="Anbieter").get_by_role("link", name="Anbieter").click()
        expect(page).to_have_url(re.compile(r"/settings/provider$"))
        expect(_region(page, PROVIDERS).get_by_role("heading", name=PROVIDERS)).to_be_visible()
        expect(_region(page, MODELS).get_by_role("heading", name=MODELS)).to_be_visible()
        expect(_region(page, TASKS).get_by_role("heading", name=TASKS)).to_be_visible()

        # One fake provider carries both models; the first model becomes
        # the default on its own.
        _create_provider(page, "Fake Anbieter")
        eins = _create_model(page, "Fake Eins", "Fake Anbieter", "modell-eins")
        expect(eins.get_by_text("Standard", exact=True)).to_have_count(1)
        zwei = _create_model(page, "Fake Zwei", "Fake Anbieter", "modell-zwei")
        expect(zwei.get_by_text("Standard", exact=True)).to_have_count(0)

        # The default flips in one action: Zwei takes the badge, Eins loses it.
        zwei.get_by_role("button", name="Zum Standard machen").click()
        expect(zwei.get_by_text("Standard", exact=True)).to_have_count(1)
        expect(eins.get_by_text("Standard", exact=True)).to_have_count(0)

        # The task tier beats the default: continuation serves from Fake Eins.
        # The option names provider and model together — the pair a task
        # actually points at.
        continuation = _region(page, TASKS).get_by_label("Weiterschreiben")
        continuation.select_option(label="Fake Anbieter · modell-eins")
        # The PUT's refetch is what moves the select; wait for it before
        # leaving, or the reload below could race the stored row.
        expect(continuation).not_to_have_value("")
        # A fresh visit shows the stored assignment: the mount itself must
        # load it, not the first mutation's refetch.
        page.reload()
        expect(_region(page, TASKS).get_by_role("heading", name=TASKS)).to_be_visible()
        continuation = _region(page, TASKS).get_by_label("Weiterschreiben")
        expect(continuation).to_have_value(_model_id("Fake Eins"))
        # The task list names the model that actually serves the task — the
        # assigned one, not a bare "Automatic" the cascade may contradict.
        expect(page.get_by_text("über Fake Anbieter · modell-eins")).to_be_visible()
        # The audit-only key is labelled and explained: never printed as its
        # internal key, never offered as an assignment, never given a model.
        expect(page.get_by_text("Verbindungstest")).to_be_visible()
        expect(
            page.get_by_text("Der Einstellungstest prüft das Modell, das du auswählst")
        ).to_be_visible()
        expect(page.get_by_text("settings.test")).to_have_count(0)

        # A vendor provider carries the masked-key round-trip and the
        # endpoint's probes; its model carries the tuning the edit clears.
        vendor_row = _create_provider(
            page,
            "Vendor Anbieter",
            kind="OpenAI-kompatibler Chat",
            base_url=vendor.base_url,
            api_key=VENDOR_KEY,
        )
        # The create answer is the one response that shows the full key.
        expect(page.get_by_text(VENDOR_KEY)).to_be_visible()
        page.get_by_role("button", name="Verstanden").click()
        expect(page.get_by_text(VENDOR_KEY)).to_have_count(0)
        expect(vendor_row).to_contain_text(VENDOR_MASK)
        # No rendered surface shows the key again — not the list, not anywhere.
        expect(page.locator("body")).not_to_contain_text(VENDOR_KEY)

        _create_model(page, "Vendor Test", "Vendor Anbieter", "vendor-mini", temperature="0.7")

        # The probes run where their facts live, visibly: the connection
        # test on the model (it asks for the model's string), discovery on
        # the provider (the row that owns the endpoint).
        vendor_model = _region(page, MODELS).get_by_role("listitem").filter(has_text="Vendor Test")
        vendor_model.get_by_role("button", name="Verbindung testen").click()
        expect(vendor_model.get_by_text(re.compile("Die Verbindung funktioniert"))).to_be_visible()
        vendor_row.get_by_role("button", name="Modelle anzeigen").click()
        expect(vendor_row).to_contain_text("vendor-max")
        expect(vendor_row).to_contain_text("vendor-mini")

        # An update with an empty key field keeps the stored key: the mask
        # survives a provider rename untouched. A cleared tuning column on
        # the model really clears — an explicit null, not a silent keep.
        vendor_row.get_by_role("button", name="Bearbeiten").click()
        _region(page, PROVIDERS).get_by_label("Name", exact=True).fill("Vendor Umbenannt")
        page.get_by_role("button", name="Änderungen speichern").click()
        renamed_provider = (
            _region(page, PROVIDERS).get_by_role("listitem").filter(has_text="Vendor Umbenannt")
        )
        expect(renamed_provider).to_contain_text(VENDOR_MASK)

        vendor_model.get_by_role("button", name="Bearbeiten").click()
        _region(page, MODELS).get_by_label("Name", exact=True).fill("Vendor Prüfling")
        _region(page, MODELS).get_by_label("Temperatur").fill("")
        page.get_by_role("button", name="Änderungen speichern").click()
        renamed_model = (
            _region(page, MODELS).get_by_role("listitem").filter(has_text="Vendor Prüfling")
        )
        expect(renamed_model).to_be_visible()

        # The cleared column stayed cleared: the re-opened edit reads the
        # row back, and a silently kept 0.7 would reappear right here.
        renamed_model.get_by_role("button", name="Bearbeiten").click()
        expect(_region(page, MODELS).get_by_label("Temperatur")).to_have_value("")
        page.get_by_role("button", name="Abbrechen").click()

        # The default model cannot be deleted; the error names the way out.
        zwei.get_by_role("button", name="Löschen").click()
        expect(page.get_by_role("alert")).to_contain_text(
            "Lege ein zweites Modell an, mache es zum Standard"
        )
        expect(zwei).to_be_visible()

    # The workbench continuation runs on the assigned model, in the real
    # database's audit — the default model never answers this task.
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

    # The audit row names the assigned model and its free-text model string —
    # not the default's, which is the whole point of the assignment tier.
    [(profile_id, model, cost)] = _rows(
        "SELECT c.profile_id, c.model, c.cost_usd FROM llm_calls c"
        " JOIN novels n ON c.novel_id = n.id"
        " WHERE n.title = 'Die Anbieterprobe' AND c.task_key = 'writing.continuation'"
    )
    assert str(profile_id) == _model_id("Fake Eins")
    assert model == "modell-eins"
    assert cost == 0.0  # a fake provider is free, not unknown

    # The connection test was audited as settings.test, priced at the local
    # vendor's real 0.0.
    [(test_model, test_status, test_cost)] = _rows(
        "SELECT model, status, cost_usd FROM llm_calls WHERE task_key = 'settings.test'"
    )
    assert (test_model, test_status) == ("vendor-mini", "ok")
    assert test_cost == 0.0


def test_the_provider_surfaces_sit_on_the_label_grid(page: Page, stack: Stack) -> None:
    """The provider surface sits on the 128 px label grid: label and control
    share one row, the control is the field's 28 px, and the label column is
    the row grid's own 128 px track — stacked fields and hand-sized labels
    are what this pin exists to catch.

    Pinned on both forms' name fields and on an assignment row, the three
    grids the provider page owns."""
    page.goto(BASE + "/settings/provider")
    expect(_region(page, PROVIDERS).get_by_role("heading", name=PROVIDERS)).to_be_visible()

    def assert_label_row(scope: Locator, label_text: str, control: Locator) -> None:
        expect(control).to_be_visible()
        label_box = scope.get_by_text(label_text, exact=True).bounding_box()
        control_box = control.bounding_box()
        assert label_box is not None and control_box is not None
        # One row: label and control share the row's vertical centre.
        label_centre = label_box["y"] + label_box["height"] / 2
        control_centre = control_box["y"] + control_box["height"] / 2
        assert abs(label_centre - control_centre) <= 1.5
        # The control height is the density law's field: 28 px.
        assert control_box["height"] == 28
        # The label column is the grid's track, not a sized label.
        columns = control.evaluate("el => getComputedStyle(el.parentElement).gridTemplateColumns")
        assert columns.split(" ")[0] == "128px"

    providers = _region(page, PROVIDERS)
    models = _region(page, MODELS)
    assert_label_row(providers, "Name", providers.get_by_label("Name", exact=True))
    assert_label_row(models, "Name", models.get_by_label("Name", exact=True))

    # The assignments render from the mount's task read.
    tasks = _region(page, TASKS)
    continuation = tasks.get_by_label("Weiterschreiben")
    expect(continuation).to_be_visible()
    assert_label_row(tasks, "Weiterschreiben", continuation)

    assert_accessible(page)


def test_the_new_surfaces_speak_every_language(page: Page, stack: Stack) -> None:
    """The gear, the hub and the provider page render in de, en and fr."""
    page.goto(BASE + "/settings")

    # The browser speaks de-DE and nobody chose: German renders. The hub
    # lists the clusters; the provider surface is a page of its own.
    expect(page.get_by_role("heading", name="Einstellungen")).to_be_visible()
    expect(page.get_by_role("heading", name="Sprache")).to_be_visible()
    expect(page.get_by_role("heading", name="Anbieter")).to_be_visible()
    # The gear's name follows the language — the same element asserted in
    # each of the three below. Found by href and scoped to the banner: the
    # rail's Settings anchor (P8) carries the same word in every language,
    # and a name-filtered locator would stop matching the moment the switch
    # below renames it.
    gear = page.get_by_role("banner").locator('a[href="/settings"]')
    expect(gear).to_be_visible()
    expect(gear).to_have_accessible_name("Einstellungen")
    expect(page.get_by_role("link", name="Zurück")).to_be_visible()

    page.goto(BASE + "/settings/provider")
    expect(_region(page, PROVIDERS).get_by_role("heading", name=PROVIDERS)).to_be_visible()
    expect(_region(page, MODELS).get_by_role("heading", name=MODELS)).to_be_visible()
    expect(_region(page, TASKS).get_by_role("heading", name=TASKS)).to_be_visible()

    # The bar's quick switch drives every page's language.
    switcher = page.get_by_role("banner").locator('select[name="locale"]')
    switcher.select_option("en")
    expect(page.get_by_role("heading", name="Settings")).to_be_visible()
    expect(_region(page, "Providers").get_by_role("heading", name="Providers")).to_be_visible()
    expect(_region(page, "Models").get_by_role("heading", name="Models")).to_be_visible()
    expect(_region(page, "Tasks").get_by_role("heading", name="Tasks")).to_be_visible()
    expect(gear).to_have_accessible_name("Settings")
    expect(page.get_by_role("link", name="Back")).to_be_visible()

    switcher.select_option("fr")
    expect(page.get_by_role("heading", name="Paramètres")).to_be_visible()
    expect(
        _region(page, "Fournisseurs").get_by_role("heading", name="Fournisseurs")
    ).to_be_visible()
    expect(_region(page, "Modèles").get_by_role("heading", name="Modèles")).to_be_visible()
    expect(_region(page, "Tâches").get_by_role("heading", name="Tâches")).to_be_visible()
    expect(gear).to_have_accessible_name("Paramètres")
    expect(page.get_by_role("link", name="Retour")).to_be_visible()

    switcher.select_option("de")
    expect(page.get_by_role("heading", name="Einstellungen")).to_be_visible()

    assert_accessible(page)
