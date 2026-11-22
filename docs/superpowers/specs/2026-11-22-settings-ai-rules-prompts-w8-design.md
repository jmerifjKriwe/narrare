# Settings AI-Regeln & Prompts W8 — design

> **Date:** 2026-11-22 · **Status:** draft for owner approval
> Extends the W7 split (`2026-11-21-settings-general-w7-design.md`): W8 is the
> second half — the AI-Regeln authority and the prompt override surface. The
> content brief behind both surfaces is
> `2026-11-15-settings-prompts-stitch-brief.md`; its owner decisions 1–8 of
> 2026-11-15 stand except where the W7 split and this wave's rulings narrow
> them. Moves to `docs/superpowers/specs/` at execution start.

## Intent and why

Roadmap Phase 1: after W8 the app is configurable without a `.env` or an API
call — a provider with a key, models, per-task assignment, output profiles,
and every prompt editable with a provider-free preview. The exit: configure a
model, assign it to a task, edit the task's prompt, preview it — all in the
UI, proven by browser legs. "Done means done": surface + backend + E2E +
three catalogs + gap ledger.

## Owner rulings (2026-11-22)

1. **Projekt-Regeln stay in BookSettings.** The AI-Regeln surface carries a
   live pointer door (the Stitch round draws it); no copy, no second editor.
   The W7 gap-ledger row 2 closes with this design.
2. **The opener pays all seven findings** — #933, #733, #734, #739, #745,
   #749, #750 — plus the driver-kind field (ledger row 6) and the
   roadmap/inventory drift W7 left.
3. **Approach A:** one Stitch round (both authorities), then three PRs —
   Opener / AI-Regeln / Prompts.
4. **Hub chrome:** three own routes under the hub — `/settings` (Allgemein,
   byte-stable content, only the chrome is added), `/settings/ai-regeln`,
   `/settings/prompts` — and the Stitch round draws the shared hub chrome
   (section nav/cards) across all three authorities in one owner-approval
   moment. W7's E2E legs keep standing.
5. **Output profiles are realistic, not conservative** — current models carry
   200k–1M-token windows; the named profiles must not read as relics.
6. **Live test:** the editor draft (absent body = the saved effective), gated
   through the render sandbox; real assembled manuscript context, not
   samples; audited under the key's task — the answer and the draft are what
   is never persisted.

## Real fields (the API is the authority)

- **Settings:** `GET/PATCH /api/settings`, `PATCH /api/settings/theme`,
  models CRUD + `POST /models/{id}/test`, providers CRUD + presets +
  `GET /providers/{id}/models`, `GET/PUT /api/settings/assignments/{task_key}`
  (`profile_id` names the model row; `null` clears back down the cascade),
  `GET /api/settings/tasks` (the effective view: `kind`, `assignable`;
  `settings.test` is audit-only).
- **Prompts:** `GET /api/prompts` (optional `novel_id`), `GET/PUT/DELETE
  /api/prompts/{key}`, `GET /api/prompts/{key}/diff`. The registry's key set
  is closed — four keys, one per assignable task: `writing.continuation`,
  `knowledge.extract-entities`, `knowledge.check-consistency`
  (novel-scopable), `chat.ask` (global-only). The save gate renders through
  the sandbox and refuses by name (422).
- **The LLM boundary:** `kernel/llm/resolution.py` merges provider vendor
  defaults with the model row's `context_window`/`max_output_tokens`; the
  WP2b allocator (`kernel/context.py`) stays kernel-owned and is never
  user-redistributed.

## The three backend builds (brief §"Scope consequence")

1. **Novel AI-rules PATCH — done since W4.** The fields ride `NovelUpdate`;
   BookSettings edits them. Nothing to build; ruling 1 keeps it that way.
2. **Output profiles** (decision 2 + ruling 5). Vocabulary
   `quick | balanced | long_texts | comprehensive | custom`, kernel-owned
   constants — **realistic targets** (my call under ruling 5):
   `quick=1024, balanced=4096, long_texts=12288, comprehensive=32768` output
   tokens. **Per task, not per model** (my call): the assignment carries the
   profile — the same model serves a short continuation and a long
   extraction. Resolution at the LLM boundary: the profile's target capped by
   the model's `max_output_tokens` when one is stored — `min(profile,
   ceiling)`, never above a known ceiling; with no stored ceiling the
   profile's target stands uncapped and Aufgaben shows it as is (no invented
   ceiling). `custom` is an explicit number. Absent profile = `balanced`
   (the column defaults, the migration backfills `balanced` — no
   two-state semantics). The Aufgaben effective view states the resolved
   number (the honesty seam). `PUT /assignments/{task_key}` grows
   `output_profile`; `GET /tasks` answers profile name + resolved output.
   No budget-tier slider, ever.
3. **Prompt preview + live test** (decision 6, ruling 6).
   - **Preview — provider-free:** `GET /api/prompts/{key}/preview?novel_id=…`
     with an optional body content (absent = the saved effective content)
     renders at sample scope through the same sandbox the save gate uses;
     answers rendered text, variable provenance, diagnostics. No model call,
     nothing persisted.
   - **Live test — gated:** `POST /api/prompts/{key}/live-test`, SSE after
     the chat/writing precedent. Body carries the editor draft (absent =
     the saved effective); the draft passes the render sandbox before any
     provider call. Rides the key's task assignment (the four keys are the
     four tasks) and the **real assembled context** each capability builds
     for that task today — the assembly seams are reused, not rebuilt; if
     one proves disproportionate at plan time, the fallback lands as a
     disclosed ledger row, never silently. Kind `fake` answers locally with
     its honest mark. Provider/secret-gated (the named 502/503 faces),
     rate-limited, a token/privacy warning before the call. The call is
     **audited under the key's task** (`settings.test` and the models'
     `last_error` marks live on the audit; cost accounting stays true) —
     what is never persisted is the streamed answer and the draft.

## Driver kind (W7 ledger row 6)

A read naming the instance's serving truth: `GET /api/settings/driver` →
`{kind}` — `"fake"` while every assignable task's serving tier is the fake
adapter, else `"configured"`. The W7 offline card switches from inferring
across the task cascade to reading this field: the card stands only on
`kind: "fake"`; hide-on-configured and hide-on-unanswered stay.

## Surfaces

1. **The hub chrome** (ruling 4): one Stitch round draws the shared section
   nav/cards across all three authorities — the Allgemein page keeps its
   content byte-stable and gains only the chrome; W7's settings E2E legs keep
   standing (a leg that still breaks adapts in the same commit as the chrome).
2. **AI-Regeln** (`/settings/ai-regeln`, its own route under the hub) from
   `settings-ai-rules-2.html` (already token-harmonized; the round adds the
   hub chrome, the pointer door and the output-profile placement): Provider
   (masks `sk-…xxxx`, the 9 presets with their snapshot honesty mark, the
   key-returns-once create moment, model-discovery states, the 409 naming the
   models still pointing, the 503 key-store face), Modelle (default handover,
   test running/ok/fail, the delete guard, `in_catalog` and `last_error`
   facts read-only), Aufgaben (the four assignable tasks, the effective view
   with its honest Fake floor and the resolved output number,
   `settings.test` never a dropdown), the pointer door to BookSettings, the
   output-profile selector.
3. **Prompts** (`/settings/prompts`, the hub chrome's door —
   `capability.yaml` already names the path) from
   `ai-prompts-overrides.html` + `ai-prompts-states-reference.html` (the
   token round is owed): the four-key list with override marks and the novel
   filter, the editor with scope chips (novel chip only where scopable), the
   diff against bundled, the 422 refusal faces from the states reference, the
   preview, the live test with its warning and its kein-Provider/disabled
   states.

## Non-goals

No chat surface, no command palette, no shortcuts/backups/typography/quota
(decisions 3–4), no prompt history or update badges (7), no file overrides or
Phase-B scopes (8), no per-novel model overrides (decision 1), no
Projekt-Regeln copy (ruling 1), no new setup or writing surface.

## Anti-goals

Invented model metrics, fake provider names, dead-promise tabs, the key shown
after create, a second locale/theme mechanism, the WP2b slider in any shape,
the old mixed settings draft ported unsplit.

## Constraints

- Standing rules (`CONSTRAINTS.md`); SDD; **PR für PR**; Lane A end to end.
- Seats rev. 7: implementer `glm-5.3-flash`, reviewer `glm-5.3` (until
  qwencloud returns 2026-12-13).
- Stitch alone designs; the owner approves both authorities before porting
  starts.
- i18n: three catalogs, sorted parity, du-tone (fr tu).
- Absent-vs-carried-null everywhere; only dirtied fields ride a save.
- E2E: per-suite DB, de-DE contexts; the kernel expectation grows `prompts`
  in the same commit as its e2e directory; #749 is a migration (its own
  commit, riding the wave).
- The phantom-dir trap after branch switches.

## Approaches (picked in conversation)

- **A — Stitch round, then three PRs** (Opener / AI-Regeln with its backend /
  Prompts with preview + live test). **Owner's pick.** Each surface carries
  its consuming backend; the opener needs no draft and lands first.
- B — Backend-first, four PRs. Rejected: one PR without observable payoff,
  more PR-für-PR overhead.
- C — One PR for the wave. Rejected: against PR-für-PR and the W5/W6 rhythm.

## My calls (settled by me; veto is yours)

- The output profile binds per task; the named targets are
  `1024 / 4096 / 12288 / 32768` under ruling 5; resolution caps at a stored
  ceiling only (`min(profile, ceiling)`), an unknown ceiling leaves the
  target standing and Aufgaben shows it as is; `custom` is bounded to a
  known ceiling at save; absent profile = `balanced` everywhere.
- The live test rides the key's task assignment with the capability's real
  context assembly; the rate limit is a simple per-user in-memory limiter;
  SSE follows the chat precedent; the call is audited under the key's task.
- Driver-kind is `GET /api/settings/driver`.
- The drift fix splits: the opener writes post-W7 truth, the wave-gate commit
  writes post-W8 truth (the roadmap's own rule).

## Left to the builder

- Task breakdown at plan time (the W7 shape: harmonization gate, opener,
  surfaces, E2E legs, ledger, wave gate).
- Exact catalog keys and testids from the harmonized drafts.
- The rate limiter's constants and the SSE event shapes.
- Migration mechanics for #749 inside the revision policy.
