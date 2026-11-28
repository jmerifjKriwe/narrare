# The German face's own quotes and dashes are the catalog text these tests
# assert literally — intentional characters, not confusable typos.
"""The AI-Regeln surface on the real stack (W8 Task 9): the settings
capability's second page, proven over browser, API and Postgres.

The provider create round-trip walks the key-once contract on the wire — the
create response is the only carrier of the plaintext, the face shows it
exactly once, and every read after (the grid, the API asked directly, a fresh
boot) answers the mask. The model test face runs through a fake-kind provider
(the fake answers locally, audited as ``settings.test`` — no network ever
leaves). The assignment leg walks the Aufgaben row's two selects on the real
cascade: a model assigned, a profile chosen, the resolved number rendered as
the backend answers it — capped at the stored ceiling when one bounds the
target, the cap noted, the custom number above the ceiling refused by the
wire and the answers kept. ``settings.test`` renders as the audit row it is:
never a dropdown. The pointer door walks to the book's workspace with the
dialog's deep link and the Buch-Einstellungen dialog stands open — the
ruling-1 record, no second editor. The hub chrome carries the settings
area's three routes on BOTH settings pages, the active face exact, and the
direct AI-Regeln load names Atelier / Einstellungen in the topbar, never the
shelf crumb. Every rendered face also clears the axe WCAG A/AA floor, light
and dark.
"""

import re
from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Page, expect

from app.capabilities.settings.e2e.conftest import (
    await_assignments,
    await_tasks,
    create_fake_provider,
    create_model,
    create_novel,
    create_provider,
    expect_ai_rules,
    goto_ai_rules,
    goto_settings,
    read_providers,
    set_theme,
)
from app.kernel.testing.a11y import assert_accessible
from app.kernel.testing.stack import WEB_URL

if TYPE_CHECKING:
    from app.kernel.testing.stack import Stack

pytestmark = [pytest.mark.e2e, pytest.mark.timeout(240)]

BASE = WEB_URL

# The catalog's own words, pinned where a leg leans on them (de-DE context).
HUB_LABEL = "Einstellungen Navigation"
GENERAL = "Allgemein"
AI_RULES = "KI-Regeln"
ATELIER = "Atelier"
SETTINGS_LABEL = "Einstellungen"
SHELF_LABEL = "Das Bücherregal"
PROVIDERS_HEADING = "1. Provider & Schnittstellen"
CREATE_SUBMIT = "+ Provider anlegen"
KEY_ONCE_NOTE = re.compile(r"nur jetzt sichtbar")
DONE = "Fertig"
FAKE_TILE = "100 % lokal"
OFFLINE_TITLE = "Standard: Offline-Betrieb"
NO_ACTION = "Keine Aktion erforderlich · Aktiv"
TEST_BUTTON = "Verbindung testen"
TEST_OK = re.compile(r"Test bestanden · \d[\d.]* ms")
FAKE_MARK = "Offline-Treiber"
EFFECTIVE_4096 = "Effektiv: 4.096 Tok."
EFFECTIVE_8192 = "Effektiv: 8.192 Tok."
CAPPED_NOTE = "* am Modell-Deckel begrenzt"
MODEL_LABEL = "Zugewiesenes Modell"
PROFILE_LABEL = "Ausgabe-Profil"
PROFILE_DISABLED_NOTE = re.compile(r"Ein Ausgabe-Profil speichert mit der Modell-Zuweisung")
AUDIT_BADGE = "Prüfaufgabe"
REFUSED = "Das Atelier hat diese Änderung abgelehnt. Prüfe deine Angaben."
KEY = "sk-test-keyonce-7a3f"


def _task_row(page: Page, task_key: str):
    return page.locator(f'[data-testid="task-row"][data-task-key="{task_key}"]')


def test_the_hub_chrome_carries_the_area_routes_on_both_pages(page: Page, installed: Stack) -> None:
    """The shared nav: Allgemein + KI-Regeln + Prompts (the third door went
    live with its surface in the same commit), the active face exact on the
    route each page stands on, the Allgemein content untouched below it."""
    goto_settings(page)
    nav = page.get_by_role("navigation", name=HUB_LABEL)
    links = nav.get_by_role("link")
    expect(links).to_have_count(3)
    expect(nav.get_by_role("link", name=GENERAL)).to_have_attribute("aria-current", "page")
    expect(nav.get_by_role("link", name=AI_RULES)).not_to_have_attribute("aria-current", "page")
    expect(nav.get_by_role("link", name="Prompts")).not_to_have_attribute("aria-current", "page")
    # The Allgemein content stands below the chrome, byte-stable: the strict
    # read answered, the form opened (the W7 legs' own ready face).
    expect(page.get_by_test_id("settings-page")).to_be_visible()
    expect(page.locator("#settings-author-name")).to_be_visible()

    # The door walks; the active face flips exactly.
    nav.get_by_role("link", name=AI_RULES).click()
    page.wait_for_url(f"{BASE}/settings/ai-regeln")
    expect_ai_rules(page)
    nav = page.get_by_role("navigation", name=HUB_LABEL)
    expect(nav.get_by_role("link", name=AI_RULES)).to_have_attribute("aria-current", "page")
    expect(nav.get_by_role("link", name=GENERAL)).not_to_have_attribute("aria-current", "page")

    # A direct load of the subroute carries the same topbar — the browser's
    # own entry, not only the hub's client-side door. The crumb names the
    # settings location; the shelf is never the place here (#981).
    goto_ai_rules(page)
    topbar = page.get_by_role("banner")
    expect(topbar.get_by_role("link", name=ATELIER)).to_have_attribute("href", "/")
    expect(topbar.get_by_text(SETTINGS_LABEL)).to_be_visible()
    expect(topbar).not_to_contain_text(SHELF_LABEL)
    assert_accessible(page)


def test_the_provider_create_keeps_the_key_exactly_once(page: Page, installed: Stack) -> None:
    """The key-once contract on the wire: the create's response carries the
    plaintext, the face shows it exactly once, and every read after — the
    grid's refetch, the API asked directly, a fresh boot — answers the mask
    ``sk-…`` plus the last four characters."""
    goto_ai_rules(page)

    # The create form's answers: the preset fills the endpoint, the name and
    # the key ride the save.
    page.get_by_label("Name des Providers").fill("Cloud E2E")
    page.get_by_label("API-Schlüssel", exact=True).fill(KEY)
    page.get_by_role("button", name=CREATE_SUBMIT).click()

    # The face holds the plaintext — exactly once on the whole page.
    face = page.get_by_test_id("created-key")
    expect(face).to_have_text(KEY)
    assert page.content().count(KEY) == 1, "the key appeared more than once"
    expect(page.get_by_text(KEY_ONCE_NOTE)).to_be_visible()
    # The grid already answers with the mask beside the face.
    card = page.locator('[data-testid="provider-card"]', has_text="Cloud E2E")
    expect(card.get_by_text("sk-…7a3f")).to_be_visible()

    # Fertig retires the face — the plaintext is gone from the page, the
    # mask keeps standing.
    page.get_by_role("button", name=DONE).click()
    expect(page.get_by_test_id("created-key")).to_have_count(0)
    assert KEY not in page.content(), "the plaintext outlived the one face"

    # The API's own read answers the mask, never the key.
    providers = read_providers()
    assert len(providers) == 1
    assert providers[0]["api_key_mask"] == "sk-…7a3f"

    # A fresh boot: still only the mask.
    page.reload()
    expect_ai_rules(page)
    expect(
        page.locator('[data-testid="provider-card"]', has_text="Cloud E2E").get_by_text("sk-…7a3f")
    ).to_be_visible()
    assert KEY not in page.content()
    assert_accessible(page)


def test_the_model_test_face_answers_through_the_fake(page: Page, installed: Stack) -> None:
    """A fake-kind provider's model answers locally: the card's tiles read
    the stored columns (the inference tile's honest 100 % lokal), the test
    face runs and passes with the wire's latency, the cascade's chips show
    the resolved number with the fake driver's mark — and the audit key is
    the row that is never a dropdown."""
    provider_id = create_fake_provider()
    create_model(provider_id, name="Lokal-Schreiber", model_id="llama3:8b")
    goto_ai_rules(page)

    card = page.locator('[data-testid="model-card"]', has_text="Lokal-Schreiber")
    expect(card.get_by_text("100 % lokal")).to_be_visible()
    expect(card.get_by_text("Standard")).to_be_visible()  # the first model is the default

    # The diagnose section speaks the driver read's word: offline, active.
    expect(page.get_by_text(OFFLINE_TITLE)).to_be_visible()
    expect(page.get_by_text(NO_ACTION)).to_be_visible()

    # The connection test runs through the fake — audited, answered, ok.
    card.get_by_role("button", name=TEST_BUTTON).click()
    expect(card.get_by_text(TEST_OK)).to_be_visible()

    # The cascade's chips: the resolved number as is, the fake's own mark —
    # never the draft's invented „0 Tok. (Offline)“.
    for task_key in (
        "writing.continuation",
        "chat.ask",
        "knowledge.extract-entities",
        "knowledge.check-consistency",
    ):
        row = _task_row(page, task_key)
        expect(row.get_by_text(EFFECTIVE_4096)).to_be_visible()
        expect(row.get_by_text(FAKE_MARK)).to_be_visible()
        assert "0 Tok." not in (row.text_content() or "")

    # The audit row: stated, not assignable — no select anywhere in it.
    audit = _task_row(page, "settings.test")
    expect(audit.get_by_text(AUDIT_BADGE, exact=True)).to_be_visible()
    assert audit.locator("select").count() == 0
    assert_accessible(page)


def test_a_refused_provider_delete_names_the_models_and_the_remedy(
    page: Page, installed: Stack
) -> None:
    """The provider delete guard names the models still pointed at it and the
    way out, in the reader's language — and the provider stays listed."""
    provider_id = create_provider()
    create_model(provider_id, name="Cloud-Schreiber", model_id="test-model")
    goto_ai_rules(page)

    card = page.locator('[data-testid="provider-card"]', has_text="Cloud")
    card.get_by_role("button", name="Entfernen").click()
    alert = card.get_by_role("alert")
    expect(alert).to_contain_text("test-model")
    expect(alert).to_contain_text("Richte sie auf einen anderen Provider aus")
    expect(card).to_be_visible()
    assert_accessible(page)


def test_the_assignment_rides_with_its_profile_and_the_resolved_number(
    page: Page, installed: Stack
) -> None:
    """The Aufgaben row's two selects on the real cascade: the model assigned
    (the PUT carries the model AND the profile), the profile chosen, the
    resolved number rendered as the backend answers it — capped at the
    model's stored ceiling with the cap noted, a custom number above the
    ceiling refused with the answers kept."""
    provider_id = create_provider()
    model_id = create_model(
        provider_id, name="Cloud-Schreiber", model_id="test-model", max_output_tokens=8_192
    )
    goto_ai_rules(page)

    row = _task_row(page, "writing.continuation")
    model_select = row.get_by_label(MODEL_LABEL)
    profile_select = row.get_by_label(PROFILE_LABEL)

    # On the cascade floor the profile select rests with its note — the
    # backend stores no profile without an assignment.
    expect(profile_select).to_be_disabled()
    expect(row.get_by_text(PROFILE_DISABLED_NOTE)).to_be_visible()
    expect(row.get_by_text(EFFECTIVE_4096)).to_be_visible()  # the default tier, uncapped at 4.096

    # The model assignment: the PUT carries the model AND the profile.
    model_select.select_option(label="Cloud-Schreiber")
    # The stored-row proof lands first: the assignment row itself must carry
    # the model and the profile, not merely a cascade that satisfies them.
    assignments = await_assignments("writing.continuation")
    (assignment,) = [row for row in assignments if row["task_key"] == "writing.continuation"]
    assert assignment["profile_id"] == model_id
    assert assignment["output_profile"] == "balanced"

    stored = await_tasks("writing.continuation", profile_id=model_id, output_profile="balanced")
    assert stored["profile_name"] == "Cloud-Schreiber"
    assert stored["kind"] == "openai-chat"

    # The profile select woke with the assignment; „Lange Texte“ rides and
    # the resolved number is the honest min: 12.288 at the stored ceiling of
    # 8.192 → 8.192, the cap noted.
    expect(profile_select).to_be_enabled()
    profile_select.select_option(label="Lange Texte (12.288 Tokens)")
    await_tasks("writing.continuation", output_profile="long_texts", resolved_output_tokens=8_192)
    expect(row.get_by_text(EFFECTIVE_8192)).to_be_visible()
    expect(row.get_by_text(CAPPED_NOTE)).to_be_visible()

    # The custom choice above the stored ceiling: the EDITOR refuses it
    # before any PUT (the stored 8.192 is the effective cap) — the field's
    # own over-limit face stands, the stored truth keeps the last landed
    # choice. A server-side refusal needs an in-cap value the API rejects;
    # that family is pinned in the unit suite.
    profile_select.select_option(label="Benutzerdefiniert (eigener Wert)")
    custom = row.get_by_label("Eigene Token-Zahl")
    custom.fill("999999")
    custom.blur()
    expect(
        row.get_by_text("Über dem bekannten Ausgabe-Limit des Modells (8.192 Tokens)")
    ).to_be_visible()
    expect(custom).to_have_value("999999")  # a refusal never eats the answer
    # The stored truth keeps the last landed choice.
    assert await_tasks(
        "writing.continuation", output_profile="long_texts", resolved_output_tokens=8_192
    )
    assert_accessible(page)


def test_the_pointer_door_walks_to_the_book_settings_dialog(page: Page, installed: Stack) -> None:
    """Ruling 1's record: the door routes to the book whose Buch-Einstellungen
    hold the Projekt-Regeln, with the dialog's own deep link — the dialog
    stands open when the workspace lands. No copy, no second editor here."""
    novel_id = create_novel("Das Signal im Permafrost")
    goto_ai_rules(page)

    door = page.get_by_test_id("pointer-door")
    expect(door).to_contain_text("Roman-Tonalität & Kausalitätsregeln")
    door.click()
    page.wait_for_url(f"**/novels/{novel_id}#buch-einstellungen")
    dialog = page.get_by_role("dialog")
    expect(dialog.get_by_role("heading", name="Buch-Einstellungen")).to_be_visible()
    # The dialog opens on its busy loading face while the series read stands
    # (the fresh boot's ["series"] ask is never cached) — that face holds Esc
    # by the family's own contract (aria-busy, no modal keys bound). Esc
    # answers only once the form stands, so the ready face is waited here
    # exactly like every other read-gated assertion in this suite.
    expect(dialog.get_by_role("button", name="Speichern")).to_be_visible()

    # The walk home is the dialog's own door: Esc closes it, the workspace
    # stays — the AI page carried no editor of its own.
    page.keyboard.press("Escape")
    expect(page.get_by_role("dialog")).to_have_count(0)
    expect(page.get_by_role("heading", name="Das Signal im Permafrost")).to_be_visible()


def test_the_dark_ai_rules_clear_the_axe_floor(page: Page, installed: Stack) -> None:
    """The surface on the tokens' dark halves — the same WCAG A/AA floor the
    light face clears, with the dark boot adopted from the row."""
    set_theme("dark")
    goto_ai_rules(page)
    expect(page.locator("html")).to_have_attribute("data-theme", "dark")
    assert_accessible(page)

    provider_id = create_fake_provider()
    create_model(provider_id, name="Lokal-Schreiber", model_id="llama3:8b")
    page.reload()
    expect_ai_rules(page)
    assert_accessible(page)
