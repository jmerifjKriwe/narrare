# The W8 settings AI-Regeln & prompts capability — what is still a placeholder, and what replaces it

> **Status:** living document, opened with the settings AI-Regeln & prompts
> wave W8's PR 3 (2026-11-24, the gap ledger landing; PRs 1 #939 and 2
> #944 merged before it, PR 3 rides `feat/prompts-rebuild`). Keep it
> current: when a row's trigger lands, update the row in the same commit
> that replaces the interim. This is the single English list of every
> element of the capability's surfaces — the AI-Regeln page
> (`/settings/ai-regeln`: Provider, Modelle, Aufgaben, System-Diagnose,
> the BookSettings pointer door), the prompts page (`/settings/prompts`:
> the four-key catalog, the editor, the preview, the live test) and the
> shared hub chrome — that ships as a placeholder, a deliberate omission
> or a draft drift because the backend, the surface or the corrected
> draft does not exist yet.
>
> **Authority:** the owner-approved round — `screens/shell/`
> `settings-ai-rules-2` (B, the AI-Regeln authority),
> `ai-prompts-overrides` (C) and `ai-prompts-states-reference` (D, the
> copy authority for refusals, scope states and tool faces), beside the
> unchanged `settings-allgemein-2` (A). Light drafts win; the dark faces
> ride the shell's token ladder. The gap contract is the W8 design's
> owner rulings (2026-11-22) and the Stitch round's owner checkpoint
> (2026-11-22): the round ported as committed, finding 6 decided
> CORRECT-AT-PORT, no invented numbers, no invented metrics, no dead
> promises. The table's format follows the W7 ledger
> ([`2026-11-21-settings.md`](2026-11-21-settings.md)).
>
> The wave's index issue is **#947** (the
> [`follow-ups.md`](../../superpowers/follow-ups.md) row carries its
> number). The filed children are **#940**, **#945** and
> **#946**; #933 closed with the W8 opener. Rows whose trigger is a
> later wave, a product or owner decision record their trigger here and
> carry no issue — the ledger is their home until that trigger fires.

## Why placeholders exist

The owner's condition, carried from W3–W7: fidelity to the drafts
without lies. A feature the backend cannot serve keeps the draft's
geometry with an honest neutral — never an invented number, never a
fabricated state. The W8 wave adds four rules of its own. The no-metrics
rule: a card or tile states a fact only on a read that answers it — no
handshake, no heartbeat, no „zuletzt geprüft", no token estimate, no
duration the wire does not carry. The resolved-truth rule: Aufgaben
shows the resolved number (profile target capped at a stored ceiling,
computed, never invented) with the Fake mark, never the draft's offline
zero. The audit rule: the live test's draft and answer persist in no
domain table — the call's own `llm_calls` row is the house's
log-of-record and carries what every audited call carries. The
dead-promise rule: a link, chip or card claiming a fact or feature that
does not exist ships nowhere. The drafts' mock figures („Claude 3.5
Sonnet", „~214 Tokens", „0.8s", the four sample books) are draft data,
never shipping data — the real row answers everywhere.

## The gap list

„Drafted" is what the round authority draws (or, for the filed rows,
what a complete surface asks). „Shipped in W8" is the interim the wave
commits to. „Trigger" is the surface, field or decision that must exist
before the interim can become the drafted value. „Wave/issue" names the
owner of the trigger and the row's child under the wave's index.

| Nr | Element | Drafted | Shipped in W8 | Trigger | Wave/issue |
|---|---|---|---|---|---|
| 1 | Provider health on the cards | a per-provider test button and „Zuletzt geprüft" stamps beside every provider | not ported — no read answers provider health, no column stores a tested-at stamp; the cards carry mask, vault note, inline edit, delete. Modelle has the real per-model test (running/ok/fail) and the stored `last_error`/`in_catalog` marks — the facts that exist | a backend read naming provider health or a tested-at column — then the cards state it; or a corrected draft that drops the claims | model wave · no issue |
| 2 | The discovery button's home | the page header's model-discovery button | relocated, not ported as drawn — a header button names no provider, so it could not answer honestly; the discovery door (200/502/409-no-endpoint states) stands in the register form beside the provider select it asks about | a corrected draft drawing the door beside its provider — the relocation is the honest port; nothing else waits | draft gap · no issue |
| 3 | The „Atelier Disziplin" card | a card claiming KI-Vorschläge wait in a Ghost-Buffer until `[Tab]` | ships nowhere — a UX fact that does not exist: no ghost-buffer, no Tab-acceptance, no read behind it | the feature actually existing (no code, no design draws it), or the owner dropping the card from the authority | draft gap · no issue |
| 4 | The invented storage chips | „Lokaler Speicher verifiziert" on the AI-Regeln hub; „Lokaler Prompt-Speicher" on the prompts header | not ported — invented chrome; no read verifies or names either store. The prompts header keeps the Geltungsbereich selector and the override badge | a read the chips could state truthfully, or corrected drafts that drop them | draft gap · no issue |
| 5 | The chat task row's token chip | „0 Tok. (Offline)" on the chat row | the resolved truth: the chat row shows the effective read's resolved number with the Fake mark, the cap note only when computed (`resolved < target`), a custom above a known ceiling refused with the answer kept | an offline state the backend names — none exists: a not-configured instance answers through the fake driver, and the Fake mark is the honest word for it | draft gap · no issue |
| 6 | The footers | the AI-Regeln footer's Souveränitäts-Manifest, Kausalitäts-Garantie and OS-Keystore Schnittstelle links; the prompts footer beside them | no footer on either surface — all three prompts links (and the AI-Regeln three) lead nowhere; dead promises do not ship | real targets existing for the links, or the owner dropping them from the authorities | draft gap · no issue |
| 7 | The preview's token estimate | „~214 Tokens" beside the preview's diagnostics | not ported — the diagnostics carry chars and lines, the only figures a render answers; nothing counts tokens | a token estimate the backend answers (a tokenizer read), or a corrected draft that drops the figure | model wave · no issue |
| 8 | The per-variable „Herkunft" labels | Roman-Metadaten / Lore-Graph / Manuskript-Puffer beside each variable | not ported — the preview's provenance is `{name, value, used}`; the used/unused mark is the honest fact, no source field exists per variable | the preview answering a per-variable source — then the labels state it | model wave · no issue |
| 9 | The live-test card's timing and idle success bar | „Antwort erhalten (0.8s)" and a permanent „Prüfung erfolgreich" bar | not ported — the wire carries no duration, and no client-side Jinja check exists, so a standing success line would be a lie; the Ablehnungsgründe expander stands instead and the preview's and save's outcomes answer with their own faces | a duration the wire carries; a real client-side contract check; or corrected drafts that drop them | draft gap · no issue |
| 10 | The invented model and flavor words | „Modell: Claude 3.5 Sonnet (Standard)", „Antik-Terminal Streaming" | the context frame answers the provider KIND — the fake with its honest mark and note, no invented model name (the anti-goal); the card reads „Test-Antwort (Streaming)" | the anti-goal is the answer; a corrected draft that drops the words closes the row | draft gap · no issue |
| 11 | The live test's persistence footprint | the design's ruling 6: the draft and the answer are never persisted | exactly that, in the domain tables — no override row carries the draft, no scene/message/suggestion/finding row carries the answer (pinned by `test_the_editor_draft_rides_the_wire_and_is_never_persisted`, which checks `prompt_templates` and `scenes` after a draft test). The call's own `llm_calls` audit row carries `prompt_text`/`response_text` — the house's every-call design (chat, writing, the knowledge jobs, the settings probe ride the same columns; the models' `last_error` marks and the cost accounting live on the row) | an owner call that live-test audit rows be text-free — a fork of `kernel/llm/audit.py` nobody has asked for; this row is the disclosure's home until then | owner decision · no issue |
| 12 | The rate limiter's scope | one live test per user per 30 s | in memory, per process — multi-instance deployments share nothing (the worst case is one extra provider call; the claim's benign check-then-set race is named in the docstring) | multi-instance hosting existing — the pocket wave's hosting decision; then a shared store replaces the in-memory window | hosting decision · no issue |
| 13 | The consistency live test's coverage | (undrafted; the endpoint's own contract) | one pass — the first packed chapter group, one provider call, one rate-limit window, where the nightly job runs map-reduce over all groups; the facts frame names the chapters the pass carries, and a novel whose every chapter is over the bound refuses no-context rather than sending a half-read lie | whole-book coverage wanted in a live test — a longer window or a multi-call design (an owner call); until then the facts frame is the coverage statement | product decision · no issue |
| 14 | The live test's context picks | (undrafted; the endpoint rides the capabilities' real assemblies) | honest stand-ins, stated in the docstrings and the facts frame: the writer's edge is `updated_at desc` (production names the open scene; the endpoint carries none), the chat question is the sample question shown verbatim (chat persists no questions, D14), the extraction rides the latest chapter | an endpoint naming the open scene; the assistant-sessions wave giving chat a real last question | assistant-sessions wave · no issue |
| 15 | The dirty draft across a scope switch | the drafted editor following the scope chips | the draft belongs to the tier it edits: the switch remounts the editor at the new tier's baseline and discards the other tier's dirty draft — an unpinned draft silently following the switch would lie about what a save writes. Disclosed product decision, no guard: no „Verwerfen?" asks before a switch | an owner call on a guard (ask on a dirty switch) or a per-tier draft store | owner decision · no issue |
| 16 | The Diff on an unsaved draft | the draft's diff of what you type | the saved tiers' diff — the endpoint's `bundled_content` vs `override_content` is the truth the diff endpoint serves; the button keeps the draft's wording. An unsaved keystroke is previewed, not diffed | a draft-diff face the owner wants (a client-side draft-vs-bundled render), or a corrected draft that draws the saved-tiers diff | settings polish · no issue |

## Resolved this wave (recorded so nobody re-opens them as gaps)

- **The Souveränitäts-Garantie card's storage claim** (Stitch round
  finding 6, owner ruling CORRECT-AT-PORT): the drafted
  `.narrare/prompts/` claim is replaced by the local-database copy, and
  the states reference's reset fact „Die Datei dead-signal.j2 wird
  archiviert" is not ported for the same reason — the reset deletes the
  override row.
- **The round audit's dispositions** (findings 1–5 and 7, owner
  checkpoint 2026-11-22): no dead promises (row 6), no invented numbers
  (row 5), the W7 user-block menu stays the truth, the chat row's
  profile select carries „Benutzerdefiniert". The rows above are their
  record.
- **The live-test trigger's single door** (Task 12, deviation 7): the
  overrides draft's toolbar button („Werkzeug 2: Live-Test (mit
  Provider)") folds into the live-test card's own „Prompt testen", so
  the warning precedes the call in DOM order; the states reference's
  Werkzeug 02 is the canonical drawing.
- **The reset confirmation** (deviation 12): a two-step inline confirm
  per the states reference's „einmalige Bestätigung", not a modal — the
  settings area has no modal precedent for destructive confirms.
- **The editor's editorial line** (deviation 11): the draft's „Passe an,
  wie …" sentence is replaced by the key's real description — per-key
  i18n copy, the catalog's own words.
- **The provider key's once-only moment** (Task 9): the create's
  response is the only plaintext carrier; the grid refetches the mask;
  the vitest suite pins the plaintext appearing exactly once, the E2E
  re-asks the API and boots fresh — mask only.

## Known-pattern notes (no row owed — the pattern is the record)

- **The hub chrome lives in the shell** (Task 12's disclosed ruling):
  three authorities span two capabilities, and a capability never
  imports another (rule 1) — `web/components/SettingsHub.tsx` is the
  shared chrome's home, the third door joining in the same commit that
  mounts the surface behind it. The prompts route stands root-level
  beside `/settings`, not as a `settingsRoutes` child: the settings host
  route renders without an `Outlet`, so the generator's dormant
  convention would mount a route that cannot render (`settingsPages.ts`
  stays empty; nothing consumes it).
- **The resolved-truth chip** (Task 9 + the whole-branch fix
  `c54cd3ee`): the Aufgaben cap note derives from the effective pair —
  the tasks read's stored profile, the assignments read's stored custom
  number — never the editor's live pick. Comparing the pick against the
  stored read was the caught bug; the rule: a surface note about stored
  truth reads stored truth, in flight and refused alike.
- **The echo re-sync** (Task 9's fix round): an assignment save
  re-syncs the row from the landed ask's own echo (the router's real
  clear shape answers `profile_id: null` / `balanced`), and a refusal
  keeps every answer. The mock answers the wire's shape, not the wish.
- **The identity-keyed draft reset** (Task 12's fix round): the editor
  remounts on `key:tier:novelId`; a refetch that only changes bytes
  never touches the keystrokes typed in flight. The remount's side
  effect — the preview, diff and live-test faces clear on an identity
  switch — is the honest face: those asks answered for the other tier.
- **The outage retry's double ask** (Task 12's fix round): the retry
  refetches the errored reads AND invalidates the `["prompts"]` family,
  so an errored read can be asked twice — the price of covering the
  idle-read case (a read whose earlier throw left it with no ask
  mounted) with one shape. Cosmetic: one GET.
- **The live-test 422 premise** (Task 12's disclosed concern): the
  editor reads every 422 from the live-test route as the save gate's
  refusal — true today, the route's only 422 family. A second 422
  family on that route needs a discriminator before it ships, or it
  surfaces in the refusal family's shape.
- **The rate-limit window across E2E legs**: in memory, per user, per
  API process. A future leg adding a live test uses the `_run_live_test`
  helper (it waits the face's named seconds) or asserts the 429
  deliberately; a context-less refusal spends no claim (the window is
  peeked before the capability's assembly, claimed only when the
  provider call is next).
- **The suite budget** (Task 9's watch-item, sent to this round by the
  dispatch): the AI-Regeln page suite runs at `asyncUtilTimeout: 15_000`
  and `testTimeout: 25_000` — the page mounts six reads and five
  sections. The number is pinned in the file; the question (budget
  against split) stays open for the index owner.
- **The task select's two truths** (Task 9's disclosed choice): on a row
  with a standing default model the select shows the cascade option
  while the chip names the default model that answers — the select edits
  the stored assignment, the chip states the effective truth. The
  draft's conflated select is the alternative the surface refused.

## Handovers

- **The W7 ledger's rows 1, 2, 3, 6 and 7** resolve with W8 — all five
  are marked in the same commit that opens this ledger:
  - Row 1 (the AI-Regeln tabs, the pointer row): **resolved** — W8 built
    the AI-Regeln surface from the parked authority and the prompts
    surface beside it (PRs #939/#944/PR 3); the Allgemein page's chrome
    gained the doors.
  - Row 2 (the Projekt-Regeln fields): **resolved** — the W8 design's
    ruling 1 kept them in BookSettings, and the AI-Regeln surface
    carries the live pointer door
    (`/novels/{id}#buch-einstellungen`, E2E-proven).
  - Row 3 (#933, the locale-carry family): **resolved** — the W8 opener
    (`10f3920f`, `Closes` fired at PR 1's merge `109544ae`) added the
    click-time fresh-cache reads and the language seam's optimistic
    patch; the narrower in-flight class stays open as **#940** under
    this wave's index.
  - Row 6 (the offline card's basis): **resolved** — the driver-kind
    read shipped (`GET /api/settings/driver`) and the card reads it
    (`07315ef8`), hide-on-configured and hide-on-unanswered kept.
  - Row 7 (the 422 refusal face, browser-proven): **resolved** — the
    Aufgaben custom field is a UI path that can send a refusable shape,
    and the settings E2E's assignment leg drives the refusal over the
    real stack (Task 9, `7faa5f54`; merged in PR 2 `c8cbfc45`).
  Rows 4 (the dark card's swatch) and 5 (the goal input's parser) are
  untouched — W8 changed neither the tokens nor the goal input.
- **The W4/W5/W6 and shelf ledgers**: no row resolves with W8 — the
  settings and prompts surfaces were not their subject, and the wave
  added no prose-join, active-novel or extraction copy. Their triggers
  keep standing.
- **#945 and #946** are this wave's filed children from the reports:
  #945 (the catalog output limit is editor-only — raw writes and named
  profiles exceed it kernel-side) from PR 2, #946 (a failed detail
  refetch tears down the prompts editor and its dirty draft) from Task
  12's fix round. Both hang under the wave's index when it opens.

## How a row becomes real

1. Land the trigger the row names (a surface, a field, a corrected draft,
   an owner decision, or user feedback).
2. Replace the interim at the element; a placeholder becomes the real
   thing, an omitted element returns only if its re-open condition is
   met.
3. Update the row here (or remove it if nothing is left) in the same
   commit.
4. Close the row's child from that commit: `Closes #<n>`. The wave's
   index closes with its last child.

No placeholder is removed by deleting its slot — the slot is the draft's,
and it stays. Only the neutral content is replaced.
