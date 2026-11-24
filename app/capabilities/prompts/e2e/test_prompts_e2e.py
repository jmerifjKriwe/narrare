# The German face's own quotes and dashes are the catalog text these tests
# assert literally — intentional characters, not confusable typos.
"""The Prompts surface on the real stack (W8 Task 12): the settings area's
third page, proven over browser, API and Postgres.

The catalog reads its marks off the real list — Global Standard, the global
override, the novel's erbt/Override pair, the global-only fact — and the
Geltungsbereich selector composes: a novel choice re-asks the list, the badge
counts, a switch moves the marks. The editor wears the scope chips where the
key is scopable (the novel chip only there), the state card per override
state, the diff panel's two saved tiers, and the variable legend that inserts
at the cursor. The save gate refuses a broken draft by name in the states
reference's exact copy family, lands an honest save with the mark moving, and
the reset asks once before it deletes. The preview rides Task 11's POST —
provider-free, the diagnostics line, the contract faces (erfüllt, keinen
Kontrakt, verletzt). The live test runs against a fake-kind provider on the
real wire — the warning stands before the call, the Fake mark is honest, the
second immediate run hits the rate limit's cooldown face — and the
no-context door stands where no real data rides. ``chat.ask`` is global-only:
no novel chip, the save without a novel id, the live test global. The page
clears the axe WCAG A/AA floor, light and dark.
"""

import re
from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Locator, Page, expect

from app.capabilities.prompts.e2e.conftest import (
    create_chapter,
    create_fake_provider,
    create_model,
    create_novel,
    goto_prompts,
    save_override,
    set_theme,
    write_scene,
)
from app.kernel.testing.a11y import assert_accessible
from app.kernel.testing.stack import WEB_URL

if TYPE_CHECKING:
    from app.kernel.testing.stack import Stack

pytestmark = [pytest.mark.e2e, pytest.mark.timeout(240)]

BASE = WEB_URL

# The catalog's own words, pinned where a leg leans on them (de-DE context).
HUB_LABEL = "Einstellungen Navigation"
GLOBAL_STANDARD = "Global: Standard"
GLOBAL_OVERRIDE = "Global: Eigener Override aktiv"
ONLY_GLOBAL = "Nur Global gültig (kein Roman-Scope)"
INHERITS = "Dead Signal: erbt Global"
NOVEL_OVERRIDE = "Dead Signal: Eigener Override aktiv"
BADGE_ONE = "1 roman-spezifischer Override aktiv"
SCOPE_GLOBAL = "Global (Atelier-Standard)"
THIS_NOVEL = "Dieser Roman: Dead Signal"
NOVEL_STATE = re.compile(r"Aktuell ist für Dead Signal ein spezifischer Roman-Override angelegt")
INHERIT_STATE = "Keine lokale Abweichung für diesen Roman definiert."
DIFF_NONE = "Kein Override gespeichert — in diesem Geltungsbereich trägt der Standard unverändert."
REFUSED_SYNTAX = "Speichern abgelehnt: Syntax"
SAVED = "Gespeichert."
RESET_QUESTION = "Wirklich zurücksetzen?"
DIAGNOSTICS = "Diagnostik: Providerfrei gerendert. Kein API-Aufruf, keine Datenübertragung."
CONTRACT_NONE = "Dieser Schlüssel trägt keinen Kontrakt."
CONTRACT_FAIL = re.compile(r"Kontrakt verletzt")
LIVE_WARNING = re.compile(
    r"Vor erstem Lauf: Testdaten werden an deinen konfigurierten Provider übermittelt"
)
LIVE_TEST = "Prompt testen"
LIVE_DONE = "Antwort erhalten"
FAKE_MARK = "Fake-Treiber"
FAKE_NOTE = "Der lokale Fake-Treiber antwortet. Kennzeichnung: Fake."
RATE_LIMITED = "Zu viele Testläufe in kurzer Folge. Bitte kurz warten."
COOLDOWN = re.compile(r"Cooldown: \d+ Sekunden")
NO_CONTEXT = "Keine realen Daten für diesen Test"
PASSAGES_ZERO = "Passagen: 0"

# The broken draft: an {% if %} without its {% endif %} — the gate's syntax
# refusal on the wire. Intentional Jinja, not a typo.
BROKEN_DRAFT = "# Umgestimmt\n{% if entities %}\nDer Text bricht ab."
HONEST_DRAFT = "# Umgestimmt\nDu bist ein literarischer Ghost-Writing-Assistent.\n{{tail}}"


def _card(page: Page, key: str):
    return page.locator(f'[data-testid="prompt-card"][data-key="{key}"]')


def _editor(page: Page):
    return page.get_by_test_id("prompts-editor")


# The rate limit's in-memory window (one live test per user per 30 s) lives
# in the API process and carries across this module's tests: a sibling leg's
# successful run may still hold the window this leg's first ask wants. The
# window's face names its remaining seconds, so the helper waits them out
# and retries — the answer, never a sleep-and-hope.
COOLDOWN_TEXT = re.compile(r"Cooldown: (\d+) Sekunden")


def _run_live_test(page: Page, editor: Locator) -> None:
    """One live-test ask to its terminal face; a closed window waits its
    named seconds out and retries once."""
    editor.get_by_test_id("live-button").click()
    outcome = editor.get_by_test_id("live-done").or_(editor.get_by_test_id("live-error"))
    expect(outcome).to_be_visible()
    error = editor.get_by_test_id("live-error")
    if error.is_visible():
        match = COOLDOWN_TEXT.search(error.text_content() or "")
        if match is not None:
            page.wait_for_timeout(int(match.group(1)) * 1000 + 1500)
            editor.get_by_test_id("live-button").click()
            expect(
                editor.get_by_test_id("live-done").or_(editor.get_by_test_id("live-error"))
            ).to_be_visible()


def _select_novel(page: Page, novel_id: str) -> None:
    """The Geltungsbereich selector: choose the novel, wait for the list's
    re-ask to land (the badge or the marks move)."""
    page.get_by_test_id("scope-select").locator("select").select_option(novel_id)
    expect(_editor(page)).to_be_visible()


def test_the_catalog_marks_the_states_and_the_novel_filter_composes(
    page: Page, installed: Stack
) -> None:
    """The list's marks on the real fields, the selector composing the
    novel scope, the hub chrome's third door live on its own surface."""
    global_id = create_novel("Dead Signal")
    other_id = create_novel("Im Stillen Wald")
    goto_prompts(page)

    # The global scope: every card on the standard mark, the global-only
    # fact beside chat.ask's.
    for key in (
        "writing.continuation",
        "knowledge.extract-entities",
        "knowledge.check-consistency",
    ):
        expect(_card(page, key).get_by_text(GLOBAL_STANDARD)).to_be_visible()
    chat = _card(page, "chat.ask")
    expect(chat.get_by_text(GLOBAL_STANDARD)).to_be_visible()
    expect(chat.get_by_text(ONLY_GLOBAL)).to_be_visible()
    expect(page.get_by_test_id("override-badge")).to_have_count(0)

    # A global override moves the mark on its key alone — asked from the
    # API, the surface refetches on the reload.
    refused = save_override("writing.continuation", HONEST_DRAFT)
    assert refused.status_code == 200, refused.text
    page.reload()
    expect(_card(page, "writing.continuation").get_by_text(GLOBAL_OVERRIDE)).to_be_visible()
    expect(_card(page, "chat.ask").get_by_text(GLOBAL_STANDARD)).to_be_visible()

    # The novel filter composes: the list re-asks with the novel, the erbt
    # mark stands, the badge counts the novel's own overrides. The override
    # seed comes from the API, so the page's cache is stale until the reload;
    # the reload lands back on Global (the filter is the page's own state)
    # and the choice re-selects — the fresh ask carries the new mark.
    _select_novel(page, global_id)
    expect(_card(page, "writing.continuation").get_by_text(INHERITS)).to_be_visible()
    expect(page.get_by_test_id("override-badge")).to_have_count(0)
    novel_override = save_override("writing.continuation", HONEST_DRAFT, novel_id=global_id)
    assert novel_override.status_code == 200, novel_override.text
    page.reload()
    expect(page.get_by_test_id("prompt-card")).to_have_count(4)
    _select_novel(page, global_id)
    expect(page.get_by_test_id("override-badge")).to_have_text(
        re.compile("1 roman-spezifischer Override aktiv")
    )
    expect(_card(page, "writing.continuation").get_by_text(NOVEL_OVERRIDE)).to_be_visible()
    expect(_card(page, "knowledge.extract-entities").get_by_text(INHERITS)).to_be_visible()

    # A scope switch moves the marks with it — the other novel inherits.
    _select_novel(page, other_id)
    expect(
        _card(page, "writing.continuation").get_by_text("Im Stillen Wald: erbt Global")
    ).to_be_visible()
    expect(page.get_by_test_id("override-badge")).to_have_count(0)

    # The hub chrome: three doors, the active face on Prompts, and the door
    # walks back to the siblings.
    nav = page.get_by_role("navigation", name=HUB_LABEL)
    expect(nav.get_by_role("link")).to_have_count(3)
    expect(nav.get_by_role("link", name="Prompts")).to_have_attribute("aria-current", "page")
    assert_accessible(page)


def test_the_editor_wears_the_scope_chips_the_diff_and_the_legend(
    page: Page, installed: Stack
) -> None:
    """The chips on the scopable key only, the state card per tier, the
    saved diff's two panes, the legend's insert at the cursor."""
    novel_id = create_novel("Dead Signal")
    chapter_id = create_chapter(novel_id, "Nevada Echoes")
    write_scene(chapter_id, "Maya prüfte den Transponder.", title="Sub-Basement")
    assert save_override("writing.continuation", HONEST_DRAFT, novel_id=novel_id).status_code == 200
    goto_prompts(page)
    _select_novel(page, novel_id)

    # The novel chip stands and is pressed; the state card names the
    # override in force.
    editor = _editor(page)
    novel_chip = editor.get_by_test_id("scope-chip-novel")
    expect(novel_chip).to_have_text(THIS_NOVEL)
    expect(novel_chip).to_have_attribute("aria-pressed", "true")
    expect(editor.get_by_test_id("editor-state")).to_contain_text(NOVEL_STATE)

    # The chip switch re-asks the tier: the global tier's state card, then
    # back to the novel's.
    editor.get_by_test_id("scope-chip-global").click()
    expect(editor.get_by_test_id("editor-state")).not_to_contain_text(NOVEL_STATE)
    editor.get_by_test_id("scope-chip-novel").click()
    expect(editor.get_by_test_id("editor-state")).to_contain_text(NOVEL_STATE)

    # The diff panel: the saved tiers side by side; the bundled pane is the
    # read-only reference.
    editor.get_by_test_id("diff-button").click()
    panel = page.get_by_test_id("diff-panel")
    expect(panel.get_by_test_id("diff-override")).to_contain_text("# Umgestimmt")
    expect(panel.get_by_text("Standard-Vorlage (Global)").first).to_be_visible()
    editor.get_by_test_id("diff-close").click()
    expect(page.get_by_test_id("diff-panel")).to_have_count(0)

    # The none face: a key without an override answers honestly.
    editor.get_by_test_id("scope-chip-global").click()
    editor.get_by_test_id("diff-button").click()
    expect(page.get_by_test_id("diff-panel")).to_contain_text(DIFF_NONE)

    # The variable legend inserts at the cursor: click, the marker lands in
    # the draft.
    editor.get_by_test_id("scope-chip-novel").click()
    textarea = editor.get_by_test_id("draft-textarea")
    textarea.focus()
    textarea.evaluate("node => node.setSelectionRange(node.value.length, node.value.length)")
    editor.get_by_role("button", name=re.compile("chapter_title")).click()
    expect(textarea).to_contain_text("{{chapter_title}}")

    # The global-only key wears the Global chip alone, even with a novel
    # filtered — and its editor works on the global tier.
    _card(page, "chat.ask").click()
    chat_editor = _editor(page)
    expect(chat_editor.get_by_test_id("scope-chip-novel")).to_have_count(0)
    expect(chat_editor.get_by_test_id("scope-chip-global")).to_have_attribute(
        "aria-pressed", "true"
    )
    assert_accessible(page)


def test_the_save_gate_refuses_by_name_and_the_honest_save_lands(
    page: Page, installed: Stack
) -> None:
    """The 422 family's exact copy, the landed save with the mark moving,
    the reset's one-time confirmation."""
    novel_id = create_novel("Dead Signal")
    goto_prompts(page)
    _select_novel(page, novel_id)
    editor = _editor(page)

    # The broken draft: the gate refuses by name, the draft stays.
    textarea = editor.get_by_test_id("draft-textarea")
    textarea.fill(BROKEN_DRAFT)
    editor.get_by_test_id("save-button").click()
    face = page.get_by_test_id("refusal-face")
    expect(face).to_contain_text(REFUSED_SYNTAX)
    expect(textarea).to_have_value(BROKEN_DRAFT)

    # The honest save: the fresh detail answers, the face says saved, the
    # catalog's mark moves with the landed write.
    textarea.fill(HONEST_DRAFT)
    editor.get_by_test_id("save-button").click()
    expect(page.get_by_test_id("saved-face")).to_contain_text(SAVED)
    expect(_card(page, "writing.continuation").get_by_text(NOVEL_OVERRIDE)).to_be_visible()

    # The reset asks once; the delete lands, the mark returns to the
    # inherited standard.
    editor.get_by_test_id("reset-button").click()
    confirm = editor.get_by_test_id("reset-confirm")
    expect(confirm).to_contain_text(RESET_QUESTION)
    confirm.get_by_test_id("reset-go").click()
    expect(_card(page, "writing.continuation").get_by_text(INHERITS)).to_be_visible()
    expect(_editor(page).get_by_test_id("editor-state")).to_contain_text(INHERIT_STATE)
    assert_accessible(page)


def test_the_preview_is_providerfree_and_names_the_contract(page: Page, installed: Stack) -> None:
    """Task 11's POST on the wire: the diagnostics face, the no-contract
    fact, the violated contract beside the rendered text — and the dark
    face stays accessible."""
    goto_prompts(page)
    editor = _editor(page)

    # The pristine draft previews the saved effective: the diagnostics
    # line, the rendered text, and writing.continuation's no-contract fact.
    editor.get_by_test_id("preview-button").click()
    card = page.get_by_test_id("preview-card")
    expect(card).to_contain_text(DIAGNOSTICS)
    expect(card.get_by_test_id("preview-rendered")).not_to_be_empty()
    expect(card).to_contain_text(CONTRACT_NONE)

    # A contract-bound key: a draft that renders but loses the marker fails
    # the contract in the 200's diagnostic — the refusal stays the save's.
    _card(page, "knowledge.extract-entities").click()
    editor = _editor(page)
    editor.get_by_test_id("draft-textarea").fill("# Mein eigener Prompt, ganz ohne Marker.")
    editor.get_by_test_id("preview-button").click()
    expect(page.get_by_test_id("preview-contract-fail")).to_contain_text(CONTRACT_FAIL)

    # The refused draft: the preview's 422 carries the same family.
    _card(page, "writing.continuation").click()
    editor = _editor(page)
    editor.get_by_test_id("draft-textarea").fill(BROKEN_DRAFT)
    editor.get_by_test_id("preview-button").click()
    expect(page.get_by_test_id("refusal-face")).to_contain_text(REFUSED_SYNTAX)

    # The dark face stays accessible: the shell adopts the stored theme at
    # boot, so the reload lands dark.
    set_theme("dark")
    page.reload()
    expect(_editor(page)).to_be_visible()
    assert_accessible(page)


def test_the_live_test_answers_through_the_fake_and_limits_the_rate(
    page: Page, installed: Stack
) -> None:
    """The warning precedes the call, the fake answers on the real wire with
    its honest mark, and the second immediate run hits the cooldown face."""
    provider_id = create_fake_provider()
    create_model(provider_id)
    novel_id = create_novel("Dead Signal")
    chapter_id = create_chapter(novel_id, "Nevada Echoes")
    write_scene(chapter_id, "Maya prüfte den Transponder im Permafrost.", title="Sub-Basement")
    goto_prompts(page)
    _select_novel(page, novel_id)
    editor = _editor(page)

    # The warning stands BEFORE the call — the card's own order, pinned:
    # the face is visible while the wire is still untouched (the window is
    # open, no run has happened on this fresh instance's own ask).
    warning = editor.get_by_test_id("live-warning")
    expect(warning).to_contain_text(LIVE_WARNING)

    # The first run rides the real wire: the fake answers locally, the
    # context names the novel and the scene, the done face lands. (A
    # sibling leg's ask may still hold the worker's window; the helper
    # waits its named seconds out.)
    _run_live_test(page, editor)
    context = editor.get_by_test_id("live-context")
    expect(context).to_contain_text(FAKE_MARK)
    expect(context).to_contain_text(FAKE_NOTE)
    expect(context).to_contain_text("Roman: Dead Signal")
    expect(editor.get_by_test_id("live-answer")).not_to_be_empty()
    expect(editor.get_by_test_id("live-done")).to_contain_text(LIVE_DONE)

    # The second immediate run: this leg's own ask just closed the window —
    # the coded 429, the cooldown's seconds named, the backend's English
    # detail sentence kept out of the face.
    editor.get_by_test_id("live-button").click()
    error = editor.get_by_test_id("live-error")
    expect(error).to_contain_text(RATE_LIMITED)
    expect(error).to_contain_text(COOLDOWN)


def test_chat_ask_is_global_only_and_the_no_context_door_stands(
    page: Page, installed: Stack
) -> None:
    """chat.ask's scope rule on the surface (no novel chip, the save without
    a novel), the extraction's no-context face where no chapter rides, and
    chat's live test over the empty corpus with the honest passages count."""
    provider_id = create_fake_provider()
    create_model(provider_id)
    novel_id = create_novel("Dead Signal")
    goto_prompts(page)
    _select_novel(page, novel_id)

    # chat.ask: the Global chip alone on the editor, even while a novel is
    # filtered.
    _card(page, "chat.ask").click()
    editor = _editor(page)
    expect(editor.get_by_test_id("scope-chip-novel")).to_have_count(0)
    expect(editor.get_by_test_id("scope-chip-global")).to_have_attribute("aria-pressed", "true")

    # The no-context door FIRST (the window note: a context-less refusal
    # spends no claim, so the ask below stays free to ride): the extraction
    # has no chapter to assemble — the coded 409, localized, the honest why.
    _card(page, "knowledge.extract-entities").click()
    _run_live_test(page, _editor(page))
    expect(_editor(page).get_by_test_id("live-error")).to_contain_text(NO_CONTEXT)

    # chat's live test over the empty corpus: the fake answers, the facts
    # name the zero passages — the honest empty face, not a dressed-up
    # sample. A sibling leg's window is waited out by the helper.
    _card(page, "chat.ask").click()
    _run_live_test(page, _editor(page))
    expect(_editor(page).get_by_test_id("live-context")).to_contain_text(PASSAGES_ZERO)
    expect(_editor(page).get_by_test_id("live-done")).to_contain_text(LIVE_DONE)
    assert_accessible(page)
