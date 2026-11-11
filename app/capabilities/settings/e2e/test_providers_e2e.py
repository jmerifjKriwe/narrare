"""The provider cluster's flow on the real stack: providers, models, assignments.

Everything the cluster promises, proven through the UI: a fake provider
seeded through the API — the form offers no fake, the kind is the kernel's
boundary stand-in — two models under it, the default flipped,
``writing.continuation`` assigned to one of them — and the continuation in
the workbench then lands on the assigned model's row in ``llm_calls``, not
the default's. A provider born from a preset carries the flow's second
door: one choice fills the endpoint fields, the key is typed, and the
models hang off the preset's vendor catalog with tasks naming the pair.
The vendor provider answers the connection test (run on its
model) and the model discovery (run on the provider, the row that owns the
endpoint) over real HTTP; its key is shown exactly once, the list shows the
mask, an update with an empty key field keeps the stored one, and deleting
the default model is refused naming the way out. The stack runs the Fernet
keychain tier (``NARRE_SECRET_KEY`` set, ``NARRE_KEYRING=off`` — see the
stack module).
"""

import asyncio
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Locator, Page, expect
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.kernel.db import testsupport
from app.kernel.db.testsupport import url_for
from app.kernel.testing.a11y import assert_accessible
from app.kernel.testing.db_rows import rows as _shared_rows
from app.kernel.testing.stack import API_URL, WEB_URL
from app.kernel.testing.vendor import chat_vendor
from app.kernel.testing.viewport import assert_page_fits

if TYPE_CHECKING:
    from app.kernel.testing.stack import Stack

pytestmark = [pytest.mark.e2e, pytest.mark.timeout(240)]

BASE = WEB_URL
# the settings API the page itself answers to (the knowledge e2e's pattern)
API = API_URL
# this run's stack database (e2e/conftest.py)
DATABASE = testsupport.test_database("narrare_v2_settings_e2e")

VENDOR_KEY = "sk-e2e-key-abcd"  # the last four are the mask the list must show
VENDOR_MASK = "sk-…abcd"

GO_KEY = "sk-go-e2e-abcd"  # the OpenCode Go provider's typed key, mask as below
GO_MASK = "sk-…abcd"

PROVIDERS = "Anbieter"  # the section's heading, in the stack's de
MODELS = "Modelle"
TASKS = "Aufgaben"


def _rows(statement: str, params: dict[str, object] | None = None) -> list[tuple[object, ...]]:
    """Thin wrapper over the shared reader (app/kernel/testing/db_rows)."""
    return _shared_rows(DATABASE, statement, params)


def _run(statement: str, params: dict[str, object] | None = None) -> None:
    """One write against the stack's own database, no rows asked back.

    The read twin `_rows` iterates its result, which a DELETE's cursor
    refuses; a write needs only the execute. Same worker thread, same why.
    """

    async def run() -> None:
        engine = create_async_engine(url_for(DATABASE))
        try:
            async with engine.connect() as connection:
                await connection.execute(text(statement), params or {})
                await connection.commit()
        finally:
            await engine.dispose()

    with ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(asyncio.run, run()).result()


def _model_id(name: str) -> str:
    """The id of the model the UI created, straight from the table."""
    [row] = _rows("SELECT id FROM provider_profiles WHERE name = :name", {"name": name})
    return str(row[0])


def _sweep(*steps: tuple[str, dict[str, object] | None]) -> None:
    """The finally-block cleanups, safe to run over a red test.

    Each delete runs in turn; a cleanup that fails re-raises only when the
    test body itself succeeded. Over a red body the original traceback must
    win — a sweep error would bury the very failure the run is there to
    show. The steps key on the ids captured at creation, so a renamed row
    is still found and nothing is matched by a look-alike name.
    """
    body_failed = sys.exc_info()[0] is not None
    for statement, params in steps:
        try:
            _run(statement, params)
        except Exception:
            if not body_failed:
                raise


def _region(page: Page, name: str) -> Locator:
    """One of the provider page's three labelled sections."""
    return page.get_by_role("region", name=name, exact=True)


def _seed_fake_provider(page: Page, name: str, base_url: str | None = None) -> str:
    """Seed a fake provider through the API, its id returned.

    The create form offers no fake: the kind is the kernel's boundary
    stand-in, not a configuration a user writes, so the rows the flows
    below need arrive the way every other client arrives — the same API the
    page itself speaks to. Called before the page mounts, the list the
    sections read already carries the row.
    """
    body: dict[str, object] = {"name": name, "kind": "fake"}
    if base_url is not None:
        body["base_url"] = base_url
    response = page.request.post(f"{API}/api/settings/providers", data=body)
    assert response.ok, response.text()
    return str(response.json()["id"])


def _create_provider(
    page: Page,
    name: str,
    *,
    base_url: str | None = None,
    api_key: str | None = None,
) -> Locator:
    """Create one provider through the form, the only way a user can.

    The form offers the two remote kinds; the default select lands on the
    OpenAI-chat one, which is the kind every form-created provider here
    carries.
    """
    section = _region(page, PROVIDERS)
    section.get_by_label("Name", exact=True).fill(name)
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
        # The fake provider is seeded before the page mounts (the form
        # offers no fake); everything below drives the real UI.
        _seed_fake_provider(page, "Fake Anbieter")
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
        # The PUT's refetch is what moves the page: the effective line is
        # the wait — it renders only once the assignment was stored and
        # read back, so the reload below cannot race the stored row.
        expect(page.locator('[id="settings-task-effective-writing.continuation"]')).to_contain_text(
            "über Fake Anbieter · modell-eins"
        )
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
        vendor_row.get_by_role("button", name="Modelle laden").click()
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


def test_a_provider_carries_models_and_tasks_use_them(page: Page, stack: Stack) -> None:
    """The preset flow, end to end: a provider born from the OpenCode Go
    preset carries models from its vendor's catalog, and the task rows
    read the pair that serves them.

    One choice fills the create form — name, kind, both URLs — and
    the key is the one field the hand still types. The vendor is the
    preset's, sent with the create and pinned on the stored row via the
    API read; the form shows no vendor field. Nothing presses
    *Verbindung testen* or *Modelle laden*: no vendor is called anywhere in
    this flow. Creation is local, and the model vocabulary — the created
    provider's suggestion and the input's datalist — is the vendored
    catalog, so both models arrive from local facts. The task rows then
    name ``OpenCode Go · <model>``, the pair a task actually points at.
    """
    page.goto(BASE + "/settings/provider")
    expect(_region(page, PROVIDERS).get_by_role("heading", name=PROVIDERS)).to_be_visible()
    providers = _region(page, PROVIDERS)
    models = _region(page, MODELS)

    # The ids the finally-cleanup deletes by, captured at creation: an
    # id that was never minted is None, and the sweep deletes only what
    # exists — no name look-alike, and no NameError over a red body.
    go_provider_id: str | None = None
    go_flash_id: str | None = None
    go_52_id: str | None = None
    try:
        # The preset fills the endpoint fields in one choice; the key is typed.
        # The vendor is no form field — its stored value is read back from
        # the API below, after the row exists.
        providers.get_by_label("Vorlage").select_option(label="OpenCode Go")
        expect(providers.get_by_label("Name", exact=True)).to_have_value("OpenCode Go")
        expect(providers.get_by_label("Art")).to_have_value("openai-chat")
        expect(providers.get_by_label("Serveradresse")).to_have_value(
            "https://opencode.ai/inference/go/openai/v1"
        )
        expect(providers.get_by_label("Modellliste-URL")).to_have_value(
            "https://opencode.ai/inference/go/v1/models"
        )
        providers.get_by_label("API-Schlüssel").fill(GO_KEY)
        providers.get_by_role("button", name="Anbieter hinzufügen").click()
        go_row = providers.get_by_role("listitem").filter(has_text="OpenCode Go")
        expect(go_row).to_be_visible()
        # The stored row carries what the form never showed: the preset's
        # vendor, on the openai-chat kind the row keeps. The read is the
        # API's own answer — the row's fact line shows the vendor too, but
        # the stored value is the fact this test pins.
        stored = page.request.get(f"{API}/api/settings/providers")
        assert stored.ok, stored.text()
        [go_stored] = [row for row in stored.json() if row["name"] == "OpenCode Go"]
        go_provider_id = str(go_stored["id"])
        assert go_stored["vendor"] == "opencode-go"
        assert go_stored["kind"] == "openai-chat"
        # The vendor is the fact the model form's catalog speaks through; the
        # mask is the key's only later face.
        expect(go_row).to_contain_text("opencode-go")
        expect(go_row).to_contain_text(GO_MASK)
        expect(page.get_by_text(GO_KEY)).to_be_visible()
        page.get_by_role("button", name="Verstanden").click()
        expect(page.locator("body")).not_to_contain_text(GO_KEY)

        # The created provider hands its preset's model to the model form: the
        # suggestion is the vendor's catalog word, there before any keystroke.
        expect(models.get_by_label("Modell", exact=True)).to_have_value("glm-5.3-flash")
        models.get_by_label("Name", exact=True).fill("Go Flash")
        models.get_by_role("button", name="Modell hinzufügen").click()
        flash_row = models.get_by_role("listitem").filter(has_text="Go Flash")
        expect(flash_row).to_be_visible()
        go_flash_id = _model_id("Go Flash")
        # The row reads the pair — provider · model — the facts a task points at.
        expect(flash_row).to_contain_text("OpenCode Go · glm-5.3-flash")

        # The second model comes from the datalist the vendor's catalog feeds:
        # the input suggests the snapshot's ids, free text untouched.
        models.get_by_label("Anbieter").select_option(label="OpenCode Go")
        expect(page.locator("datalist option[value='glm-5.2']")).to_have_count(1)
        models.get_by_label("Name", exact=True).fill("Go 5.2")
        models.get_by_label("Modell", exact=True).fill("glm-5.2")
        models.get_by_role("button", name="Modell hinzufügen").click()
        zwei_row = models.get_by_role("listitem").filter(has_text="Go 5.2")
        expect(zwei_row).to_be_visible()
        go_52_id = _model_id("Go 5.2")
        expect(zwei_row).to_contain_text("OpenCode Go · glm-5.2")

        # Two tasks, one per model; the options and the rows beneath them read
        # the pair — provider · model — never the model row's own name. The
        # effective lines are the wait: they render only once the PUT's
        # refetch has the stored assignment, which is what the database
        # reads below lean on.
        tasks = _region(page, TASKS)
        continuation = tasks.get_by_label("Weiterschreiben")
        continuation.select_option(label="OpenCode Go · glm-5.3-flash")
        chat = tasks.get_by_label("Chat, Fragen")
        chat.select_option(label="OpenCode Go · glm-5.2")
        # The effective lines, per row: the run's shuffled order decides
        # whether the unassigned tasks also resolve to one of these models
        # (the default tier answers them when this test runs first), so a
        # page-wide text query can collide — the row's own paragraph is the
        # fact this test owns.
        expect(page.locator('[id="settings-task-effective-writing.continuation"]')).to_have_text(
            "über OpenCode Go · glm-5.3-flash"
        )
        expect(page.locator('[id="settings-task-effective-chat.ask"]')).to_have_text(
            "über OpenCode Go · glm-5.2"
        )
        # The stored assignments name the two model rows, not a look-alike.
        [(stored_continuation,)] = _rows(
            "SELECT a.profile_id FROM task_assignments a WHERE a.task_key = 'writing.continuation'"
        )
        assert str(stored_continuation) == _model_id("Go Flash")
        [(stored_chat,)] = _rows(
            "SELECT a.profile_id FROM task_assignments a WHERE a.task_key = 'chat.ask'"
        )
        assert str(stored_chat) == _model_id("Go 5.2")

        # The tasks read names the serving providers' kinds on both
        # effective rows — the API's own answer, the same field the page's
        # task rows render from.
        tasks_read = page.request.get(f"{API}/api/settings/tasks")
        assert tasks_read.ok, tasks_read.text()
        kinds = {row["task_key"]: row["kind"] for row in tasks_read.json()}
        assert kinds["writing.continuation"] == "openai-chat"
        assert kinds["chat.ask"] == "openai-chat"

        # A fresh visit reads the stored assignments back: the mount loads them
        # and the rows keep naming the pair.
        page.reload()
        expect(_region(page, TASKS).get_by_role("heading", name=TASKS)).to_be_visible()
        expect(page.locator('[id="settings-task-effective-writing.continuation"]')).to_have_text(
            "über OpenCode Go · glm-5.3-flash"
        )
        expect(page.locator('[id="settings-task-effective-chat.ask"]')).to_have_text(
            "über OpenCode Go · glm-5.2"
        )
        assert_accessible(page)
    finally:
        # The module's stack is one user for every test in the file: what this
        # page drove is removed again — on a red assertion too, so the stack
        # stays unpolluted — and the flow test's fresh-stack assumption ("the
        # first model becomes the default on its own") stays true in either
        # run order. The assignments cascade away with the models; the
        # deletes key on the ids captured at creation, never on names.
        cleanup: list[tuple[str, dict[str, object] | None]] = []
        for model_id in (go_flash_id, go_52_id):
            if model_id is not None:
                # One delete per id that exists: a death between the two
                # creations must not skip the first model's row.
                cleanup.append(
                    (f"DELETE FROM provider_profiles WHERE id = '{model_id}'", None)  # noqa: S608
                )
        if go_provider_id is not None:
            cleanup.append(
                (f"DELETE FROM llm_providers WHERE id = '{go_provider_id}'", None)  # noqa: S608
            )
        _sweep(*cleanup)


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
        # The grid is the subject; wait for it to be applied before reading
        # boxes. A single read after visibility can measure the stacked form
        # the first paint still shows — under a loaded runner that read is
        # what flaked (#775).
        expect(control).to_have_css("height", "28px")
        expect(control.locator("xpath=..")).to_have_css(
            "grid-template-columns", re.compile(r"^128px(\s|$)")
        )
        label_box = scope.get_by_text(label_text, exact=True).bounding_box()
        control_box = control.bounding_box()
        assert label_box is not None and control_box is not None
        # One row: label and control share the row's vertical centre.
        label_centre = label_box["y"] + label_box["height"] / 2
        control_centre = control_box["y"] + control_box["height"] / 2
        assert abs(label_centre - control_centre) <= 1.5

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


def test_the_rows_hold_long_facts_at_the_narrowest_page(page: Page, stack: Stack) -> None:
    """The rows' fact lines wrap at 360 px — a long string widens nothing.

    A provider's base_url, a model's provider·model line and the task rows'
    "served by" caption are the page's longest unbreakable strings; without
    the wrap utilities they pushed main sideways at the narrowest viewport.
    ``assert_page_fits`` measures both scroll faces — a row that overflows
    the panel column fails here at the pixel, not by eye.
    """
    page.set_viewport_size({"width": 360, "height": 800})
    long_url = "https://vendor.example.invalid/v1/" + "segment/" * 24 + "ende"
    long_model = "ein-sehr-langes-modellkennzeichen-" + "x" * 80
    # The fake provider is seeded before the page mounts (the form offers
    # no fake), with the long URL the row must carry.
    lang_provider_id = _seed_fake_provider(page, "Lang", base_url=long_url)
    lang_model_id: str | None = None
    page.goto(BASE + "/settings/provider")
    try:
        _create_model(page, "Lang", "Lang", long_model)
        lang_model_id = _model_id("Lang")
        # The "served by" caption renders the model the cascade actually
        # serves. Without a tier naming the long model, the caption would
        # never render it and this pin would measure nothing — so a task is
        # assigned to the long model first, in default collection order too.
        continuation = _region(page, TASKS).get_by_label("Weiterschreiben")
        continuation.select_option(label=f"Lang · {long_model}")
        # The PUT's refetch is what moves the select (the flow test's lesson);
        # the caption under the very row that was assigned is the wait this
        # page's measure needs.
        expect(page.locator('[id="settings-task-effective-writing.continuation"]')).to_contain_text(
            f"Lang · {long_model}"
        )
        assert_accessible(page)
        assert_page_fits(page)
    finally:
        # The module's stack is one user for every test in the file: what this
        # page drove is removed again — on a red assertion too, so the stack
        # stays unpolluted — and the flow test's fresh-stack assumption ("the
        # first model becomes the default on its own") stays true in either
        # run order. The assignment cascades away with the profile; the
        # deletes key on the ids captured at creation, never on names.
        cleanup: list[tuple[str, dict[str, object] | None]] = []
        if lang_model_id is not None:
            cleanup.append(
                (f"DELETE FROM provider_profiles WHERE id = '{lang_model_id}'", None)  # noqa: S608
            )
        cleanup.append(
            (f"DELETE FROM llm_providers WHERE id = '{lang_provider_id}'", None)  # noqa: S608
        )
        _sweep(*cleanup)
