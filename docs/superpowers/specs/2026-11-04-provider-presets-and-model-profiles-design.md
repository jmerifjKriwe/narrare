# LLM providers, model profiles and presets — design

**Date:** 2026-11-04 · **Status:** draft for approval
**Repo:** `/home/kiesow/projects/narrare` · **Area:** settings, kernel/llm

## Intent

Settings should let a user pick a provider from nine presets, save their own
provider once and reuse it, hang as many models off it as they like, and give
each task the provider and model it deserves. The same model may be served by
several providers at different prices or context windows; the product must not
pretend those are one thing.

Two measured defects motivated the shape and are fixed by it:

- **Discovery asks the wrong URL.** "Modelle entdecken" calls
  `{base_url}/models`. At OpenCode the chat base is `…/inference/openai/v1`
  (whose `/models` answers 404) while the model list lives at
  `…/inference/v1/models` (200); at OpenCode Go the pair is `…/go/openai/v1` and
  `…/go/v1/models`.
- **Prices resolve against the wrong vendor.** `effective_info` matches a bare
  model id across the whole snapshot: `glm-5.3-flash` finds
  `302ai/glm-5.3-flash` (0.075 / 0.25) rather than `opencode-go/glm-5.3-flash`
  (0.15 / 0.50), and the audit under-reports by half. A flat-fee plan
  (`zai-coding-plan`, prices 0/0) is unreachable at all. Giving the provider the
  vendor key fixes this at the root.

## Goals

1. **Providers are rows**: name, API shape (`kind`), base URL, models URL,
   vendor key, API key. Nine presets fill the creation form; a custom provider
   is saved and appears in the same list.
2. **Models hang off a provider**: model id, context window, output limit,
   temperature, timeout, one default. Several models on one provider share its
   endpoint and key; a rotated key is edited once.
3. **Tasks choose a model profile** — provider and model in one row — so
   `writing.continuation` can run on OpenCode Go / GLM 5.3 Flash while
   `knowledge.check-consistency` runs on OpenRouter / Claude.
4. **The same model on two providers is two facts.** The catalog lookup asks
   `provider.vendor + "/" + model`, so price and context window follow the
   provider; the profile's own tunables still override the window.
5. **Discovery asks the provider's `models_url`** and sends the key only to the
   endpoint's own host — for both remote kinds, Anthropic included
   (`GET {base_url}/models` with `x-api-key` and `anthropic-version`, same
   `data[].id` reply).
6. **Claude speaks its native API**: a third `PROVIDER_KINDS` value `anthropic`
   and an adapter covering text stream, usage and `json_schema`. Its model
   picker is the `anthropic/*` catalog list, exactly like every other provider.

## Models come and go

Three sources answer different questions, and the design keeps them apart:

| Source | Answers | Ages |
|---|---|---|
| Vendored catalog | which ids exist, what they cost, their windows | with each snapshot |
| Live discovery (per provider, on demand) | what this provider serves **now** | at the moment it is fetched |
| The call itself | whether it still works | always current |

Behaviour:

- The model picker shows the provider's catalog models **and** the last live
  list, where one was fetched this visit. Two marks make the difference
  readable: *only in the catalog* (possibly retired) and *reported by the
  provider, no price known* (new, not in the snapshot).
- A saved model that is missing from a freshly fetched live list gets the mark
  *no longer offered*, once the list has been loaded — never a silent deletion.
- Nothing runs in the background: the snapshot is refreshed by the repository
  action (`python -m app.kernel.llm.data.refresh`), the live list by the user
  pressing a button. No network call happens on a page load or a request path.
- The picker names the catalog's date, so its age is visible. The snapshot
  carries its `snapshot_date` (sorted keys put it at the file's end — a
  first-bytes look reads "absent" wrongly); the loader returns it when present
  and stays silent when it is not. Regenerating the snapshot stays a repository
  action; a dated regeneration is its own change when wanted.
- A retired model fails loudly on its next call: the adapter classifies it, the
  audit records the reason as a code, and the surface names it (see *A model
  that is gone*). No silent fallback to another model — that would hide the
  breakage.
- Costs of past calls stay as recorded (`cost_usd` is written at call time). A
  model that left the snapshot only makes *future* costs NULL, never 0, and the
  row says *no price known*.

## A model that is gone — what the user sees

Today the user sees nothing useful. The stream ends with `event: error` +
`data: {}` (`ERROR_FRAME`), the editor announces *"Fortsetzung fehlgeschlagen"*,
and the provider's own words exist only in the audit row and the log. A retired
model therefore reads as a Narrare bug. That changes here:

- **Classified failures.** The adapter turns the two unambiguous provider
  answers into a typed error — HTTP 404/`not_found_error` for a model the
  provider no longer serves, and an auth failure — instead of letting a raw
  exception become a generic frame. Everything else stays unclassified, so we
  never invent a cause.
- **The frame carries a code.** `ERROR_FRAME` becomes
  `event: error\ndata: {"code": "model-not-found", "model": "…"}`, and the two
  pre-call endings get their own codes (`key-unavailable`, `prompt-refused`),
  which are just as mute today. Writing and chat keep sending one spelling.
- **The surface says what to do.** The editor and the chat panel localise the
  code: *"Der Anbieter bedient »GLM 5.3« nicht mehr. Wähle unter Einstellungen →
  Modelle ein anderes."* with the settings link. An unclassified failure names
  no cause — one neutral sentence (`errors.unknown`) answers for both surfaces.
- **Settings shows the state of every model**, from the cheapest available
  facts, and never deletes anything by itself:
  - *Preis unbekannt* — the catalog has no entry for the id.
  - *Nicht im aktuellen Angebot* (with the list's timestamp) — absent from a
    live list fetched in this session.
  - *Letzter Aufruf fehlgeschlagen: <reason>* — the newest audit row for that
    model ended in `error`; `LlmCall.error_code` carries the reason as a code so
    the UI localises it, `error` keeps the vendor text.
  - The same mark rides on the task row, so a dead assignment is visible where
    it was made.
- **Saving does not call the vendor.** A save is not a completion; making it
  fail because a provider is briefly down would be worse than the problem. The
  form warns from local facts only — *not in the list you just loaded — save
  anyway?*, *no catalog entry — price will be unknown* — and the explicit
  **Prüfen** button is the one action that makes a real call.

The rest of the surface's error wording is issue #582 (51 generic keys, 20 of
them guessing "is the local service running?", 3 printing raw server text).
This wave adds the three codes it needs and leaves that sweep alone.

## Non-goals

- A cross-provider model-equivalence table. Each provider spells the id the way
  its API expects (`glm-5.3-flash` at OpenCode, `z-ai/glm-5.3-flash` at
  OpenRouter); the catalog prices each in that vendor's terms. We do not unify
  them and do not claim they behave alike.
- The Responses API, tools, vision, prompt caching, thinking or effort levels.
- Embedding providers (follow-up #416), subscription login/OAuth, a provider
  registry consulted at request time, refreshing the snapshot from the network,
  background availability probes, and a cross-provider model-equivalence table.

## Anti-goals

- A bare model id resolving against one global index. That is the measured
  mispricing, and it cannot be repaired by "better" defaults — only by the
  provider stating its vendor.
- A custom provider that is only a form the user retypes per model.
- Claude through Anthropic's OpenAI compatibility layer: it accepts
  `response_format` only as `json_schema` with `strict: true`, which Narrare
  does not send, so entity extraction and consistency checks would 400 — and it
  would look like a Narrare bug.

## Constraints read from the repo

- `docs/_shared/CONSTRAINTS.md`: a new vendor on the OpenAI shape is data, not
  code; a new API shape is an adapter plus one kind value; no registry without
  the owner's approval; user-visible text in en/de/fr; the only permitted fake
  is the provider at its boundary.
- **ADR-102 is recut.** It says "a provider is a profile row". C splits that
  into a provider (endpoint, key, vendor) and a model profile (model, tunables,
  assignment target). The owner approved this on 2026-11-04; the design record
  for the cut is this document, and the build session adds a dated amendment
  note to ADR-102 pointing here.
- `app/kernel/db`: the schema has a real history (`app/kernel/db/migrations`,
  `just db-revision "<message>"`, `prepare_database` on startup with an
  automatic dump). This change ships a revision: it creates `llm_providers`,
  **backfills one provider per existing profile row** (no dedupe — an existing
  profile keeps its own endpoint row, so nothing is lost and nothing is
  guessed), points each profile at it, and drops the columns that moved.
  Kept scope: it is data already in a user's database, so the revision is not
  a drop-and-recreate.

## Facts measured on 2026-11-04

| Provider | Chat base | Models list | Kind |
|---|---|---|---|
| OpenAI | `https://api.openai.com/v1` | `/models` 401 (exists) | openai-chat |
| Claude | `https://api.anthropic.com/v1` | needs `x-api-key`, not Bearer | **anthropic** |
| Grok (xAI) | `https://api.x.ai/v1` | 401 (exists) | openai-chat |
| Gemini | `https://generativelanguage.googleapis.com/v1beta/openai/` | documented, 404 without key | openai-chat |
| OpenRouter | `https://openrouter.ai/api/v1` | 200 | openai-chat |
| OpenCode | `https://opencode.ai/inference/openai/v1` | `…/inference/v1/models` 200 | openai-chat |
| OpenCode Go | `https://opencode.ai/inference/go/openai/v1` | `…/go/v1/models` 200 | openai-chat |
| Z.ai | `https://api.z.ai/api/paas/v4` | 401 without key | openai-chat |
| Z.ai Coding Plan | `https://api.z.ai/api/coding/paas/v4` | 401 without key | openai-chat |

Catalog prefixes exist for all nine (`openai`, `anthropic`, `xai`, `google`,
`openrouter`, `opencode`, `opencode-go`, `zai`, `zai-coding-plan`), and the same
model id carries different entries per vendor — `glm-5.3-flash` is 1 000 000
tokens at `opencode` and 1 048 576 at `openrouter/z-ai`, and 302ai sells it at
half OpenCode's price. That is the user's point, confirmed in the snapshot.

Other facts that shaped the decision:

- LiteLLM, the reference for multi-provider libraries, never routes Claude
  through the compatibility layer: `/v1/messages`, `max_tokens` defaulted to
  4096, native `output_format` plus the `structured-outputs-2025-11-13` beta
  header on current models, `cache_control`/`thinking` natively. Vercel AI SDK,
  Pydantic AI and LangChain do the same in their own adapters.
- z.ai restricts the Coding Plan to a published list of tools; Narrare is not
  on it. The preset exists because the owner asked for both variants, and it
  carries that limitation as a note in the UI.
- OpenCode Go asks clients to send `x-opencode-session` and a product user
  agent. Narrare sends neither; calls work, prompt caching is not optimised.

## Approaches considered

**A — presets as form filler only.** Nine templates, everything else stays a
flat profile. Does not give a saved custom provider, so it fails the owner's
requirement.

**B — saved provider templates, key per model.** A second table holds name,
URL and model list; the key stays on each profile. Smaller, but the same key is
stored (and rotated) once per model.

**C — providers and models as two levels (chosen).** The provider owns the
endpoint, the API shape, the key and the vendor key; models hang off it. One key
per endpoint, one URL edit for all its models, and the vendor key makes pricing
follow the provider. Cost: a re-cut of ADR-102 and a second level in the UI.

**D — Claude via the compatibility layer.** Rejected in favour of the native
adapter (see Anti-goals).

## Decision

Ship C plus the native Claude adapter. Two tables, one adapter, a preset table,
a providers/models split in the settings surface, i18n, tests, an extended E2E.

## The shape

### Tables — `app/kernel/llm/models.py`

- `LLMProvider` (`llm_providers`): `id`, `user_id`, `name`, `kind` (a
  `PROVIDER_KINDS` value), `base_url`, `models_url`, `vendor`, `api_key`,
  `api_key_hint`, `created_at`, `updated_at`.
  `PROVIDER_KINDS = ("fake", "openai-chat", "anthropic")` — `fake` stays a kind
  so the boundary's fake provider stays a provider row chosen by configuration,
  as the constraint requires; the settings form never offers it.
- `ProviderProfile` (`provider_profiles`, now the model level): `id`, `user_id`,
  `provider_id` (FK, cascade), `name`, `model`, `context_window`,
  `max_output_tokens`, `temperature`, `request_timeout`, `is_default`.
  The partial unique index keeping one default per user moves here unchanged.
- `TaskAssignment` unchanged: `task_key → profile_id`.
- `LlmCall` gains `error_code: str | None` — the classified reason, so the
  settings surface can localise *why* a call failed without parsing vendor
  prose. `error` keeps the raw text.
- Deleting a provider with models is refused (409 naming them) rather than
  cascading assignments away; the user removes the models first.

### Kernel — `app/kernel/llm/`

- `presets.py` (new): frozen `ProviderPreset(id, label, kind, base_url,
  models_url, vendor, model, note_key)`, `PRESETS` (nine) and `preset(id)`.
  Labels are vendor proper nouns; the one prose sentence (z.ai's restriction) is
  an i18n key.
- `catalog.py`: `vendor_models(vendor)` (bare ids, sorted) for the picker;
  `effective_info(model_id, *, vendor, ...)` tries `f"{vendor}/{model_id}"`
  first, then today's exact/bare/folded tiers.
- `resolution.py`: the cascade resolves task → assignment → model profile →
  provider, and builds the adapter from the provider's endpoint and kind plus
  the profile's model and tunables. `_merged` takes the provider's vendor.
  `ANTHROPIC_DEFAULT_BASE_URL = "https://api.anthropic.com/v1"` is the anthropic
  branch's default; the settings gate applies the same rules to `openai-chat`
  and `anthropic` (model required, key required for a remote host, https only).
  The audit's `profile_id` keeps naming the model profile; `provider_kind`,
  `model` and `base_url` are unchanged in shape.
- `anthropic_messages.py` (new): the adapter, same interface as
  `OpenAIChatProvider.stream`.
- `contract.py` gains the typed failures both adapters raise —
  `ModelNotFoundError(model)` from a 404/`not_found_error`, `ProviderAuthError`
  from a rejected key — and `streaming.py`'s `ERROR_FRAME` becomes
  `event: error` with a `{"code": …, "model"?: …}` payload. Writing and chat map
  the exception to the code; an unclassified exception keeps the generic frame
  with `{"code": "unknown"}` so the client never has to parse prose.
- `repositories.py` (renamed from `profiles.py`): the provider repository beside
  the model and assignment ones; the model repository gains `for_provider` and
  `count_for_provider`.

Wire mapping for Claude:

- `POST {base_url}/messages`, headers `x-api-key`, `anthropic-version:
  2023-06-01`, `stream: true`; `response_schema` adds
  `anthropic-beta: structured-outputs-2025-11-13`.
- `system` messages hoisted into the top-level `system` field, joined with a
  newline; user turns verbatim.
- `max_tokens = request.max_tokens or 4096` (the API requires it); `temperature`
  only when configured.
- `response_schema` → `output_format: {"type": "json_schema", "schema": …}`.
- Events: `message_start` → input tokens; `content_block_delta` with
  `text_delta` → `Delta`; `message_delta` → output tokens; `message_stop` → one
  `DONE`. An `error` event or a non-2xx response raises and yields no `DONE`.

### Settings — `app/capabilities/settings/`

- `router.py`:
  - `GET/POST /api/settings/providers`, `PATCH/DELETE /api/settings/providers/{id}`.
    The connection probe lives on the model row
    (`POST /api/settings/models/{id}/test`), audited as `settings.test`, because
    a provider has no single model to call.
  - `GET /api/settings/providers/{id}/models` — discovery against the
    provider's `models_url` (absent: `{base_url}/models`). Direct `httpx` GET,
    `data[].id` parsed; **the key travels only when `models_url`'s host equals
    `base_url`'s host**, so a list on another host is asked anonymously.
    Headers follow the kind: `Authorization: Bearer` for `openai-chat`,
    `x-api-key` plus `anthropic-version: 2023-06-01` for `anthropic`. Both
    reply `{data: [{id}]}`.
  - `GET /api/settings/presets` — the nine presets with their catalog model ids
    and the snapshot's date (`[{id, label, kind, base_url, models_url, vendor,
    model, note_key, models, snapshot_date}]`), about 30 KB once per settings
    visit, so the form needs no second call.
  - `/api/settings/models` — CRUD for model profiles (today's `/profiles`,
    renamed: the name now means what it says).
  - `/api/settings/assignments`, `/api/settings/tasks` unchanged.
- `schemas.py`: provider create/update/read (key write-only, mask read),
  model create/update/read, `kind` create-only as today.
- `providers_service.py` / `models_service.py` (renamed from
  `profiles_service.py`): the provider and model services; the gate (model
  required, remote key required, https), masked keys, the default flip in one
  transaction.

### Web — `app/capabilities/settings/web/`

Three sections on `/settings/provider`, or a tab each:

- **Anbieter**: the saved providers with preset-filled creation (preset select,
  then name, kind, base URL, models URL, key), masked key, edit, discovery,
  delete refused while models exist. `vendor` is set by the preset and not a
  field.
- **Modelle**: provider select, model input with a `<datalist>` that merges the
  provider's catalog models with the live list when one was fetched (free text
  allowed), name, tunables, default badge, test. The two marks and the
  catalog's date sit beside the list (see *Models come and go*).
- **Aufgaben**: the assignment select, now labelled with model names that carry
  their provider ("OpenCode Go · GLM 5.3 Flash").
- Choosing a preset resets the provider form and clears the key field. i18n keys
  for the three headings, the preset select, the z.ai note, the empty states, in
  en, de and fr.

## Verification

- Kernel: preset table well-formed (unique ids, every vendor a catalog prefix,
  https URLs); `vendor_models`; **the same model id under two vendors resolves
  to two different fact sheets** (`opencode` vs `openrouter` for
  `glm-5.3-flash` differ in context window; a 302ai-free id differs in price);
  the catalog exposes its `snapshot_date` when the file carries one and stays
  silent when it does not; the adapter against a local Messages stand-in in
  `app/kernel/testing/vendor.py` (ordered `Delta`s, one `Usage`, one `DONE`,
  refusal raises without `DONE`, `system` hoisting, `max_tokens` default,
  `output_format` shape and beta header, `message_stop`); a 404 and a
  `not_found_error` become `ModelNotFoundError`, a 401 becomes
  `ProviderAuthError`, anything else stays unclassified, and each writes its
  `error_code` on the audit row.
- Settings: provider and model CRUD persist; a provider delete with models is a
  409; the gate refuses a remote provider without a key and an http endpoint;
  discovery hits `models_url` first, withholds the key across hosts, and sends
  the kind's headers (`Bearer` against a stand-in whose list lives on another
  path; `x-api-key` plus `anthropic-version` for Anthropic); the marks come out
  right (catalog-only, live-only, and a saved model absent from a fresh list);
  the presets endpoint returns nine entries with model lists.
- Web: a preset resets the provider form; the datalist carries the provider's
  models; free text survives; the assignment select shows provider-qualified
  names; the three marks render from the three facts (catalog, live list, last
  audit row); the editor and the chat panel turn `model-not-found` into the
  actionable sentence and keep the generic text for `unknown`.
- E2E: on the real stack, create a provider from a preset, add two models from
  its catalog list, assign one task to each, see both rows and both effective
  kinds; no vendor is called.
- Gates: `just check`, `just test-file <path>` in the loop, `just verify`, the
  settings capability's E2E.

## Risks

- ADR-102 recut: reversing it later means merging two tables again. Mitigation:
  the model row keeps the name and the assignment target, so the cascade and the
  audit barely move.
- The snapshot ages: a model added after it is only reachable by typing its id,
  or by pressing discovery; a retired one keeps working until its next call. The
  date beside the picker is the honest signal, and the regeneration is a
  repository action, not a background job.
- Anthropic's `output_format` is beta and model-gated; an older model answers
  400 and the failure names itself. The picker offers current models.
- Preset URLs rot; they are suggestions, every field is editable, and no
  resolution path reads them.
- z.ai's Coding Plan restriction is a terms question; the note is the honest
  place for it.
- OpenCode Go answers without `x-opencode-session`; caching is unoptimised.

## My calls (check these while reading)

1. `models_url` and `vendor` belong to the provider, not the model — one
   endpoint, one spelling of its catalogue, one price key.
2. The probe moves to the model row: a provider has no single model to call.
   Discovery stays on the provider.
3. `fake` remains a provider kind for the boundary/E2E; the form never offers
   it.
4. Two tables, no compatibility shim: the old `/api/settings/profiles` route is
   renamed to `/models` (no external clients; tests and E2E move with it).
5. Preset selection is create-only for providers; `kind` is not editable after
   creation, as today.
6. Same model, different providers: two profiles, no deduplication, no
   equivalence claim. The catalog decides the facts per vendor.
7. Nothing polls a vendor: the snapshot is refreshed by its script, the live
   list by a button. Staleness is shown, not hidden, and a retired model fails
   loudly instead of falling back to a neighbour.
8. Saving a model never calls the vendor; only **Prüfen** does. The save-time
   warning reads local facts (catalog, this session's live list).
9. A dead model is marked, never removed automatically; removing it stays the
   user's act, and its past audit rows keep their costs.

## Builder check — questions and resolutions

A fresh builder read the earlier (single-table) draft against the code and
raised six questions. Their answers survive the re-cut:

1. **How do presets reach the form?** One read (`GET /api/settings/presets`)
   carrying the table with model ids; a TypeScript copy would be a second,
   unread source.
2. **How does discovery issue its request?** Direct `httpx` GET of
   `models_url`, `data[].id`, key only on the endpoint's host, headers by kind —
   `Bearer` for `openai-chat`, `x-api-key` plus `anthropic-version` for
   `anthropic`.
3. **Default base URL and gate.** A dedicated Anthropic default, and the same
   gate for both remote kinds.
4. **Preset select while editing?** Create only. (Now: while creating a
   provider.)
5. **What happens to fields the preset does not name?** The selection resets the
   form and clears the key field.
6. **Is `models_url` editable?** Yes, on the provider; empty means
   `{base_url}/models`.
