# Settings & Prompt Override — Stitch design brief

> **Date:** 2026-11-15 · **Status:** draft for owner approval
> **Purpose:** the content brief for the next Stitch round (W1 recipe:
> `generate_screen_from_text`, fresh screens). It says what the two screens
> must contain, grounded in the real v2 API and the owner's scope decisions
> of 2026-11-15. Stitch is the sole design authority; this brief feeds it the
> facts it lacked last time, it does not design the UI locally.
> **Design system:** Literary Modernism (light) `assets/485a76ff0aab4fafbc1a7ccf3a1e2deb`,
> Midnight Ink (dark) `assets/ca5cbb89adb2439894e462d599c80ac3`, modelId
> `GEMINI_3_8_FLASH`, deviceType `DESKTOP`.
> **Supersedes:** the drifted drafts `screens/shell/settings-ai-rules` and
> `screens/shell/ai-prompts-overrides` (fictional models, 8 prompt modules,
> a 4-layer cascade). They stay archived; the new screens replace them.

## Owner decisions (2026-11-15)

| # | Topic | Decision |
|---|---|---|
| 0 | Existing drafts | **Redesign fresh** on the real API (not a content swap) |
| 1 | Project level / AI rules | **Editable** KI-Regeln + a new PATCH API |
| 2 | Token limits | **Add output profiles** (quick/balanced/…); no budget-tier slider |
| 3 | Keyboard shortcuts | **Omit** (SET-004 is "later") |
| 4 | Backups / typography / quota | **Omit** (reason rows, no backend) |
| 5 | Settings structure | **One screen + section nav**; Prompts is its own page (WP4) |
| 6 | Prompt preview & live test | **Build both** (full PROMPT-003) |
| 7 | Prompt history / update badges | **Omit** — WP4 non-goal stands |
| 8 | File overrides / source indicators | **v2 scopes only** (Global/Roman); Phase B stays out |

## Scope consequence — three backend builds the wave carries

The designs below show **real target surfaces** for features that do not exist
yet. The wave must build them (or a preceding sub-wave must), otherwise the
ported controls would write nowhere:

1. **Novel AI-rules PATCH** (decision 1). Today `ai_role`, `canon_strictness`,
   `author_typology`, `target_words` are bound only at setup
   (`app/capabilities/setup`); `NovelUpdate` does not carry them. Build: extend
   the novel update path with these fields + validation (role vocabulary
   `archivar|coautor|lektor|sparring`, canon `1..5`, typology
   `plotter|pantser|plantser`, target `>=1`). The settings "Projekt" section
   reads and writes them.
2. **Output-limit profiles** (decision 2). v2 models carry a raw
   `max_output_tokens`; there is no profile vocabulary. Build: a profile layer
   (`quick|balanced|long_texts|comprehensive|custom`) resolved at the model
   boundary, per task or per model (placement left to the plan). **Not** a
   context-budget tier slider — the WP2b allocator stays kernel-owned and is
   never user-redistributed.
3. **PROMPT-003 preview + live test** (decision 6). v2 WP4 validates only at
   save (sample render → 422). Build: a provider-free preview endpoint (expose
   the sample render with provenance/diagnostics, no model call) and a gated
   live test (SSE stream, provider/secret-gated, rate-limited, token/privacy
   warning, result not persisted). The two are visually and semantically
   separate: preview = understanding tool, live test = spends tokens.

Everything else in the brief is backed by the API that exists today.

## Screen 1 — Settings (one screen, section nav)

Shell chrome as the other ported screens (sidebar, breadcrumb, ⌘K, language
switch DE/EN/FR, theme toggle). Left section nav; one content pane. Sections:

### Allgemein
- **Sprache:** DE / EN / FR + "Browser folgen" (`locale: null`). Real:
  `GET/PATCH /api/settings`.
- **Theme:** Hell / Dunkel + "System folgen" (`theme: null`). Real:
  `PATCH /api/settings/theme`.
- Pre-setup structural 409 ("setup required") is a real state — the row does
  not exist before setup; show the honest refusal, not a silent default.

### Provider
- List of the user's providers, each showing the **mask** `sk-…xxxx`, never the
  key. Real: `GET /api/settings/providers`.
- **Create** from the 9 presets (`GET /api/settings/presets`, with catalog
  model ids + `snapshot_date` honesty mark) or free form: name, kind
  (`openai-chat | anthropic | fake`), base_url, models_url, vendor, api_key
  (write-only). The full key returns **once** at create — design that one
  confirmation moment.
- **Model discovery** per provider (`GET /providers/{id}/models`); states:
  loading, list, 409 no-endpoint, 502 unreachable.
- **Edit** (empty api_key keeps the stored one); **delete** guarded — 409 names
  the models still pointing at it. Design the refusal with the named models.
- Key-store unavailable = 503 state.

### Modelle
- List, default first. Each: name, provider name, model string, and the marks
  `in_catalog` and `last_error_code/at` (read-only facts). Real:
  `GET /api/settings/models`.
- **Create/edit:** name, provider, model string, context_window,
  max_output_tokens, temperature (0–2), request_timeout. **Output profile**
  selector (decision 2, new backend) sits here or in Aufgaben — placement is a
  Stitch/owner call.
- **Default handover:** exactly one default; `is_default: true` moves it (409 on
  a lost race).
- **Connection test** (`POST /models/{id}/test`): running → ok (latency) / fail
  (named error). Design all three.
- **Delete:** non-default only; deleting the default is refused (409).
  Assignments cascade with a deleted model.

### Aufgaben (per-task model)
- The 4 assignable tasks: `writing.continuation`, `chat.ask`,
  `knowledge.extract-entities`, `knowledge.check-consistency`. Each: assign a
  model or clear (`profile_id: null` → back down the cascade). Real:
  `GET/PUT /api/settings/assignments`.
- **Effective view** (`GET /api/settings/tasks`): what actually answers —
  profile name + kind (`fake | openai-chat | anthropic`), including the honest
  "Fake — läuft ohne Konfiguration" floor. `settings.test` is audit-only,
  `assignable: false` — show it as not assignable, never a dropdown.
- 502 when a serving tier's key is gone (named), not a bare error.

### Projekt (KI-Regeln — decision 1, new backend)
- Novel selector (the instance's novels). Per novel, **editable**:
  - KI-Rolle (`archivar | coautor | lektor | sparring`)
  - Kanon-Strenge (1–5)
  - Autoren-Typologie (`plotter | pantser | plantser`)
  - Wortziel (positive int)
- Reads the bound values; writes via the new PATCH. Show the source honestly
  ("beim Setup gebunden" until changed). This section is the home the draft's
  Konsistenz-/Autonomie-Regler always wanted, now backed by real fields.
- **Not** in this section: model overrides per novel (decision 1 chose rules,
  not full SET-002 project model overrides).

### Omitted (decisions 3, 4) — no slots, reason rows in the gap doc
- Tastaturkürzel (SET-004 "later"), Backups & Revisionsspeicher,
  Editor-Typografie, Modell-Kontingent-Anzeige. None has a v2 API; they are
  argued out, not drawn disabled.

## Screen 2 — Prompt Override (own page, WP4)

Reached from the settings nav, but its own address with a **novel filter**.
Real API: `/api/prompts`.

### List
- Exactly the **4 keys**, each with `bundled_summary` and the override marks
  `override_global` / `override_novel`, and `novel_scopable`. No invented
  modules, no 8-feature grid.
- Novel filter scopes the list; `chat.ask` is **global-only** (no novel chip).

### Editor (per key)
- **Two scope chips:** Global / Dieser Roman (novel chip only when
  `novel_scopable`). Empty novel scope shows **"erbt: <global state>"** and an
  explicit create-from-effective action — saving never silently forks a scope.
- **Variable legend** from the API (`variables: name + example`), click to
  insert. Bundled source visible (`bundled_content`); effective source
  (`effective_content`) distinguishable.
- Jinja template editor (monospace). Machine markers (`PURPOSE:`, `SOURCE:`)
  are kernel-fed variables, not prose the user must keep — the contract check
  enforces them.
- **Save** (`PUT`) → fresh detail; **422 refusal named**: `syntax`,
  `undefined-variable`, `include-cycle`, `contract`, `novel-scope`,
  `unknown-novel`. Design the refusal state with reason + detail.
- **Reset per scope** (`DELETE`, idempotent) with confirmation; the other tier
  is untouched.
- **Diff** (`GET /{key}/diff`): bundled vs override, side-by-side, client-side.

### Preview & Live-Test (decision 6, new backend — PROMPT-003)
- **Provider-free preview:** a panel showing the fully resolved prompt with
  variable provenance + validation diagnostics. No model call, no provider
  secret. Clearly labelled as an understanding tool, not a quality result.
- **Live test:** gated — only active when a provider is configured; explicit
  token/privacy warning before the first run; SSE streaming result; cancel +
  retry; rate-limited (429 state); result shown in a preview, never written to
  the manuscript, never stored as history. Visually separate from the preview.

### Omitted (decisions 7, 8)
- Prompt history / compare-restore / update badges (WP4 non-goal).
- File-override layer and bundled/file/db source indicators (Phase B). The
  cascade shown is exactly Roman → Global → Bundled.

## States, i18n, dark (both screens)

- Every read surface: empty, loading, error (the named refusals above), success.
- Every write: idle, submitting, refused (named), saved.
- Dark variant on the Midnight Ink token ladder; light is authoritative.
- Chrome in DE/EN/FR (rule 5, three catalogs, du-tone in German). Prompt
  **content** is user content, not localized.
- No invented numbers anywhere: quota, latency, token counts, percentages only
  where the API returns them; otherwise neutral `—`.

## What is left to Stitch / the owner

- Visual layout, section grouping, component shapes — Stitch designs, not this
  brief.
- Where the output-profile selector lives (Modelle vs Aufgaben).
- Whether the Projekt section is a nav section or a novel-scoped sub-view.
- The exact preview/live-test panel geometry.

## Round outcome (2026-11-15)

Generated fresh via MCP (`generate_screen_from_text`, Literary Modernism light,
Desktop), content-checked, owner checkpoint passed after one correction round
(`edit_screens` on the API-visible prompt screen removed the English shell,
invented tech badges and non-demo novel names). Both screens are archived under
`docs/design/stitch/screens/shell/` (stable slugs, WebP q82) and the README table
is updated; the drifted drafts remain in git history.

Stitch screen records (project `15314899202287259920`):

- Settings: `screens/6cfa7c40e0864e92944617c103a9056d`
- Prompt Override (corrected, authoritative): `screens/23eb6983e288473c972c7b1f551562e8`
  (supersedes the first draft `screens/b7d0b4c044954ad9b709b2ea35dee7ee`)

Follow-up round (2026-11-15, owner choice): dark (Midnight Ink) variants and
state-reference sheets generated and archived. The dark settings first came out
stacked (8742 px); a correction round (`edit_screens`) restored the light
section-nav layout (2048 px). Dark prompts was layout-faithful from the start.

Additional Stitch screen records:

- Settings dark (corrected, authoritative): `screens/a7f0407c77434e5ba3cf5314197a9e8b`
  (supersedes the stacked first draft `screens/c242280da11f44e5b24e0d9a45546481`)
- Prompt Override dark: `screens/dc397046a3274fff89efa0f1010b1af0`
- Settings states reference: `screens/4b4dcd20f3d14e42ac89aaec99673d25`
- Prompt Override states reference: `screens/ed837650d4364e09b757699c8dc879d1`

The port and the three backend builds are scoped into the wave's plan
(writing-plans) before any port wires a control to them; the designs show the
real target surfaces.