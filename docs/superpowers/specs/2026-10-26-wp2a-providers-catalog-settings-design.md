# WP2a — Providers, Catalog, Keychain, Settings Route Design

**Date:** 2026-10-26 · **Status:** approved by the product owner, 2026-10-27
**Authority:** Fahrplan `docs/superpowers/plans/2026-10-25-v2-foundation.md` §5 (WP2);
architecture spec `2026-10-21-narrare-v2-architecture-design.md`; frontend spec
`2026-10-22-frontend-design.md`. WP2 splits into **WP2a + WP2b** (decided 2026-10-26);
this design covers WP2a. Where this document and §5/§8.1 differ, this document wins
(and the Fahrplan gets overwritten when WP2a closes).

## Intent

One provider selection per user and per task, instead of one process-wide environment
choice. Today `NARRE_LLM_PROVIDER` picks a single entry at process start
(`get_provider()`, `provider_facts()` read the environment), every user of a process
shares it, and the audit cannot name which configuration a call used. WP2a gives every
user their own `ProviderProfile` rows (`fake` or `openai-chat`), a per-task
`TaskAssignment`, a vendored `models.dev` catalog that prices every call, encrypted API
keys, and the `/settings` route the profiles live in. `LlmCall` gains `profile_id` and
a real `cost_usd`.

## Goals

- **Data model** (kernel-owned, `app/kernel/llm/models.py` beside `LlmCall`, `UserOwned`
  base, scoped repository access):
  - `ProviderProfile`: `id, user_id, name, kind, base_url, model, api_key,
    api_key_hint, is_default, context_window?, max_output_tokens?, temperature?,
    request_timeout?, created_at, updated_at`. `kind` is `fake | openai-chat` (a
    string with a closed vocabulary in code, like `ENTITY_TYPES`). Exactly one
    `is_default` per user — the first profile becomes the default automatically,
    setting a new default unsets the old in the same transaction, and "profiles
    exist with no default" is not a legal state. `api_key` holds ciphertext in the
    Fernet tier and stays empty in the keyring tier (the plaintext lives in the OS
    keychain); `api_key_hint` holds the last four characters for masked reads
    without a keychain round-trip — a hint, not a secret. No `chars_per_token`
    column (D8).
  - `TaskAssignment`: `id, user_id, task_key, profile_id, created_at, updated_at`,
    `unique (user_id, task_key)`.
  - `LlmCall.profile_id`: nullable, **no FK on purpose** — a log row outlives its
    profile, the same reasoning as `novel_id` (§3.4).
- **Keychain module** (`app/kernel/secrets.py`): OS keyring first — the plaintext
  key lives there and the DB column stays empty; Fernet under `NARRE_SECRET_KEY`
  when no keychain is available — the ciphertext lives in `api_key`; **neither →
  storing an `api_key` fails with a named error** ("no keychain and NARRE_SECRET_KEY
  is not set"). No auto-generated key file — no silent third tier. A key lost with
  its keychain (restored DB, cleared keychain) makes the call fail with a named
  error naming the profile; the masked list keeps showing the hint. Fake profiles
  store no key. The module reads one env knob (`NARRE_KEYRING=off`) so tests force a
  tier: the E2E stack runs the Fernet tier, the keyring tier is unit-tested with an
  in-memory backend, and no test touches a developer's real keychain.
- **Masked keys:** list/read return a mask (`sk-…abcd`, last four); create returns the
  full key exactly once; update with an empty key field keeps the stored one; keys
  never appear in logs, in `LlmCall`, or in tracebacks.
- **Catalog:** `app/kernel/llm/catalog.py` + `data/models.json`, a vendored
  `models.dev` snapshot with `snapshot_date`. `ModelInfo`: `context_window`,
  `max_output_tokens`, input/output price per Mtok, `supports_json_schema`,
  `supports_tools`, `supports_vision`. Lookup: exact id → provider prefix → normalized
  match → profile override → the UI asks. Refresh is a manual
  `python -m app.kernel.llm.data.refresh` (network there and only there; no recipe, no
  gate). Attribution lands in `THIRD-PARTY-NOTICES.md`.
- **Cost truth table** (unit-tested as a function; the E2E proves the wiring):
  priced model on a remote endpoint → computed at write time; unknown model on a
  remote endpoint → `NULL`, never `0`; any model on a local endpoint (loopback/private
  `base_url`) → `0.0`; `fake` kind → `0.0`. §12's "cost present for a priced model"
  reads as *non-NULL*: on the local vendor server a priced model yields `0.0`, which is
  present; the `NULL` tier is proven in unit tests with a remote `base_url`, because
  every E2E endpoint is local by construction.
- **Resolution** (kernel): `resolve_provider(session, user_id, task_key)` → exact task
  → capability prefix → user default → environment (`NARRE_LLM_*`, semantics
  unchanged) → fake. It returns a **`ResolvedProvider`**: the `TextProvider` plus the
  facts the caller needs — `profile_id`, `kind`, `model`, `context_window`,
  `max_output_tokens`, `temperature` (the audit consumes the same structure; WP2b's
  allocator reads it too). The known task keys are a kernel constant beside the
  resolver (`writing.continuation`, `chat.ask`, `knowledge.extract-entities`,
  `knowledge.check-consistency`, `settings.test`); unknown keys are allowed
  (forward-compatible).
- **Audit rewiring:** the resolved `(kind, model, profile_id)` flow into
  `record_call`/`audited_stream`; `provider_facts()`'s global environment read is
  deleted. A fake profile's `model` is free text — ignored for answering, carried
  through to the audit — which is what makes the two-profile E2E assertion possible.
- **Adapter:** `openai-chat` moves onto the `openai` SDK (async client,
  `base_url`/`api_key` from the profile, `stream_options.include_usage`,
  **`max_retries=0`** so a 401 raises exactly once, as today). The hand-rolled httpx
  SSE parser is deleted. `NARRE_LLM_PROVIDER=openai-compatible` stays accepted as an
  alias naming the same adapter; audit rows record `openai-chat`.
- **Settings HTTP surface** (settings capability): profile CRUD, masked keys, set
  default, task assignments, `POST /profiles/{id}/test` (one cheap completion — it
  writes one `LlmCall` row, `task_key: settings.test`; one row per provider call is
  the audit's identity), `GET /profiles/{id}/models` (model discovery against the
  profile's endpoint). A half-configured profile is refused at create/update with
  422 and named fields — `openai-chat` needs a `model`, and an `api_key` when the
  `base_url` is remote (broken config never reaches a model call; the WP4
  save-time-validation philosophy). `configuration_problems()` and the startup
  validation stay the environment tier's.
- **Live fields:** `request_timeout` (SDK timeout), `temperature` and
  `max_output_tokens` (request fields) work in WP2a; `context_window` is stored for
  the catalog and WP2b's allocator. Precedence when a capability sets a field
  itself: capability > profile > absent. The settings form exposes the columns.
- **`/settings` route:** settings grows `web/`; `capability.yaml` becomes
  `path: /settings` (still `nav: false`); `just generate`. Sections: **Sprache** (the
  existing locale surface) and **Provider** (list, form, assignments, test,
  discovery). The top bar **gains a gear control** linking to `/settings` (there is
  none today); the TopBar locale select stays as the quick switch. The frontend
  spec's settings paragraph is overwritten when WP2a closes.

## Non-goals

- WP2b in full: the context allocator and continuation assembly (own design doc).
- Native adapters (`anthropic-messages`, `google-generateContent`) — one file each
  when a user needs one; `litellm` stays rejected (trigger: a third native protocol).
- Embedding-provider profiles (env-based; §5.8), per-request overrides beyond task
  keys, hosted auth, usage dashboards (`LlmCall` stays machine-read).
- The prompts section of settings (WP4's content, WP5's coherence).

## Anti-goals

No plaintext or logged keys anywhere. No per-vendor branching: a kind is one catalog
entry plus one adapter file. No silent encryption tier below keyring and
`NARRE_SECRET_KEY`. No capability importing a capability (settings serves HTTP over
kernel-owned models; resolution lives in the kernel). No new rules, registries or
gates; no migration tool (`just db-reset` — no profiles exist to lose).

## Constraints

House rules as always: one capability one folder, generated routes (`just generate`),
`user_id` on every user-owned row, scoped repository base, en/de/fr catalogs in the
same commit (missing key = build error, German du-form), conventional commits with a
real `User-visible:` line, E2E on real UI + real API + real Postgres with the fake only
at the LLM/embeddings boundary, `assert_accessible` on every page, `just check` before
commits, `just verify` before the WP closes.

## Approaches (build decomposition)

1. **Big-bang** — the whole §5.7 E2E red, then everything green. Rejected: a red test
   spanning models, keychain, catalog, adapter and UI names no cause; the largest
   review diff in the project.
2. **Frontend-first** — `/settings` against a mocked API, backend later. Rejected:
   masked-key semantics, the resolution cascade and the default guard *define* the
   UI's states, not the reverse; the mock would invent them.
3. **Five tasks, house pattern** (as WP0-B/C, WP1) — **chosen**:
   - **T1** Models + keychain + repositories (incl. `LlmCall.profile_id`), db-reset;
     keychain unit tests including the named refusal and the mask round-trip.
   - **T2** Catalog: vendored snapshot, lookup cascade, the cost truth table wired
     into `record_call`; unit tests (priced/unknown/local/fake).
   - **T3** Resolution + audit rewiring: `resolve_provider` cascade, `get_provider`
     per request, audit carries the resolved facts; all four task keys keep working;
     the environment tier is behaviour-identical.
   - **T4** Adapter onto the `openai` SDK + the settings HTTP surface (CRUD, masked
     keys, assignments, test, discovery) against the vendor server.
   - **T5** `/settings` web/ + gear link + full §5.7 E2E + axe + Fahrplan overwrite.

## Decisions (2026-10-26, product owner)

- **D1 — Split:** WP2 becomes WP2a then WP2b; WP2b builds on merged WP2a. Reviews
  stay sharp at WP1 scale instead of one double-wide review.
- **D2 — `/settings` pulled forward** from WP5 into WP2a. WP5 shrinks to the prompts
  section, the palette and coherence. Overrides §8.1; recorded in the Fahrplan when
  WP2a closes.
- **D3 — Keychain cascade:** keyring → `NARRE_SECRET_KEY` (Fernet) → named refusal
  when a key would be stored. No auto-generated key file.
- **D4 — Cost truth table** as in Goals; "local endpoints cost 0" does not override a
  computed price on remote endpoints, and the `NULL` tier is unit-proven (see Goals).
- **D5 — Adapter on the `openai` SDK** per Fahrplan §2, with `max_retries=0`
  preserving today's raise-once error semantics.
- **D6 — Per-request resolution;** the environment tier keeps `NARRE_LLM_*` semantics
  unchanged, so a fresh clone and a headless CI run keep working with zero setup.
- **D7 — Delete guard and default semantics:** the default profile cannot be
  deleted — including while it is the only one, in which case the error names the way
  out (create a second, make it default, delete). The first profile created becomes
  the default automatically; "profiles exist with no default" is not a legal state.
  A non-default profile's assignments cascade with it and affected tasks fall back
  down the cascade.
- **D8 — `chars_per_token` is a kernel constant** (in WP2b's `context.py`, default
  3.5), not a profile column. Fahrplan §5.4's "on the profile" is overwritten: the
  column is deferred with the trigger "a user asks, or mixed-language corpora
  misestimate".

## Left to the builder

- Mask format details (last four, `…`), form field order, i18n key naming.
- The settings router's exact request/response schemas within the masked-key rules.
- Vendor-server coverage for `test`/`models` in `app/kernel/testing` (extend as
  needed).
- Where `is_default` exclusivity is enforced (service layer in one transaction).
- Test and E2E file layout per the house pattern.

## Done criterion

§5.7 E2E on the real stack: create two fake profiles through the `/settings` UI, set
one default, assign `writing.continuation` to the other, run a continuation, assert on
`LlmCall` that the alt profile's `profile_id` and `model` were used; test connection
and model discovery against the real vendor server; masked-key round-trip (list masks,
update with an empty key keeps the stored one, create returns the full key once);
delete guard on the default profile; cost column non-NULL on the vendor server
(0.0, local); the `settings.test` call appears in `LlmCall`. The gear reaches
`/settings`; the locale quick-select still works; `assert_accessible` on every page;
all new surfaces in en/de/fr. The E2E runs the Fernet keychain tier (`NARRE_SECRET_KEY`
set, keyring off). `just verify` green.

## Carry-forward

The WP2a implementation plan reserves an explicit carry-forward section for the WP1
final-review findings; they are binding constraints on implementation, not design
input, and the plan is finalized only once that review has landed. If any finding is
architectural, this design reopens before implementation starts.
