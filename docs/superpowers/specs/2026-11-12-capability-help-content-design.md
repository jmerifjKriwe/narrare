# Capability Help Content — Integration Design

**Date:** 2026-11-12
**Status:** approved
**Scope:** how end-user help content is stored, discovered, and registered per capability — the foundation that must be established now (7 capabilities) before it gets costly (x capabilities). UI rendering is explicitly out of scope (being reworked separately).

## Intent

Narrare has no end-user documentation beyond `install.md` and the generated capability index. The only latent help corpus is the v1-era `ui_help_long` text in 104 feature notes — stale, mixed-language, referencing deleted v1 code paths. v2 has 7 real capabilities with real code and no help surface at all.

This design establishes the **container and discovery mechanism** for help content, so that:
- a capability can ship help "by existing" (drop files, regenerate, done),
- the same source feeds both in-app help and a future external docs site,
- the foundation scales from 7 to x capabilities without registry edits or governance friction.

It deliberately does **not** migrate v1 help text, build the UI renderer, or set up CI/publishing. Those are separate efforts that build on this container.

## Goals

- Help content lives **co-located with the capability** it describes (anti-drift).
- Discovery is **automatic**: a capability that ships help appears in the registry without editing any central file.
- **Multilingual by construction** (en/de/fr), with a graceful fallback and visible coverage gaps.
- **Optional**: no capability is forced to ship help; no new required field or artifact (governance §8 untouched).
- **Single source** for in-app help and a future external docs site.
- Scales: adding a capability, a topic, or a language is a file operation, not a code edit.

## Non-goals

- Migrating v1 `ui_help_long` text (content task, separate).
- The in-app rendering surface (`?` button, help panel, markdown renderer) — UI is being reworked; this design only fixes the data contract.
- An external docs site, custom domain, or GitHub Pages publishing.
- CI gates, link checking, or required checks.
- Backend serving of help (frontend bundle only, for now).
- Search over help content.

## Anti-goals (what would make this a failure even if it technically works)

- A help system that requires editing a central registry when a capability adds help.
- Help text that drifts from the code it describes because it lives elsewhere.
- A mandatory help artifact that blocks capabilities without content (§8 violation).
- A second, parallel content store duplicating i18n or feature notes.

## Constraints (from CONSTRAINTS.md / spec §8)

- One capability is one folder under `app/capabilities/<name>/`.
- A field exists in `capability.yaml` only while ≥2 generated views read it.
- User-visible text in every catalog the app carries (en, de, fr).
- Adding a sixth rule, registry, check script, hook, required field, or mandatory document is forbidden by default (NEEDS-APPROVAL). Help must therefore be **optional** and **additive**, not a new obligation.

## Chosen approach: per-capability help files + generated registry (Approach B)

**Rejected alternatives:**
- *Approach A (help as `help.*` keys in i18n catalogs):* reuses the pipeline but mixes UI labels with long-form prose; flat key-value is awkward for markdown; no "by existing" discovery or per-surface ownership.
- *Approach C (central `help/<locale>/<topic>.md`):* breaks "one capability is one folder"; help drifts from code; ownership unclear.

**Approach B** wins because it mirrors the existing optional-export → generated-registry pattern (Docks, Commands, Settings Pages), respects the folder rule, and provides one source for both in-app and external consumers.

## Directory layout

```
app/capabilities/<name>/web/
  help/                          # optional; absence = no help for this capability
    en/
      <topic-slug>.md
    de/                          # optional locale
      <topic-slug>.md
    fr/                          # optional locale
      <topic-slug>.md
```

- **Source language is `en`** (matches `SOURCE_LOCALE` in `generate_capabilities.py`). Every help topic must have an `en` file; `de`/`fr` are optional.
- A topic exists in a locale iff `<locale>/<slug>.md` exists. There is no "empty stub" — absence means "not yet translated," which the coverage report surfaces.
- Topic slug is lowercase, hyphenated, stable (it becomes part of the topic id). Renaming a slug is a breaking change for any external link; prefer stability.

## Topic file format

Each file is Markdown with YAML frontmatter:

```markdown
---
topic: editor
title: The Writing Editor
surfaces: [editor, chapter-rail]
order: 10
---

## The Writing Editor

Narrare's editor is built around one principle: your writing comes first.

...
```

### Frontmatter fields

| Field | Required | Meaning |
|---|---|---|
| `topic` | yes | Slug; must match the filename stem. Redundant by design (self-documenting, and a mismatch is a build error). |
| `title` | yes | Human-readable title in *this* locale (not an i18n key — help is per-locale prose, not UI label). |
| `surfaces` | yes (may be `[]`) | List of surface identifiers this topic applies to. The UI queries "help for surface X"; the registry returns topics whose `surfaces` contains X. An empty list means the topic is reachable only by direct topic id (e.g. linked from another topic). |
| `order` | no | Sort key within a surface's topic list. Default: filename sort. |

### Body

Free Markdown. The renderer (UI, out of scope) and the external site both consume it. Markdown flavor should match what the future renderer supports; for now, standard CommonMark + the same constructs used in feature notes (headings, bold, lists, code blocks). Avoid haben-style custom hint syntax unless the renderer supports it.

## Topic identity

- **Canonical id:** `<capability-id>.<topic-slug>` (e.g. `writing.editor`, `writing.focus-mode`).
- The UI never hardcodes topic ids. It requests help by **surface** (`helpFor('editor')`), and the registry resolves to the list of topics whose `surfaces` contains that surface, sorted by `order`.
- Direct topic links (from one topic to another, or from the external site) use the canonical id.

## Discovery & registry (the generator)

The generator (`scripts/generate_capabilities.py` and/or a companion) scans `app/capabilities/*/web/help/` and produces:

- **`web/lib/generated/help.ts`** — the frontend registry:
  - A `HelpTopic` type (`{ id, title, body, surfaces, locale, capability }`).
  - A `helpFor(surface, locale?)` resolver returning the sorted topic list, with fallback to `en` when the requested locale is missing.
  - Lazy loading: topic bodies are loaded on demand (dynamic import), not eagerly bundled. The registry exposes loaders; the UI calls them.
- (Phase 2) **Direct file consumption by the external site** — no generator needed; the site reads the `.md` files.

### Generator contract

- A capability **without** a `web/help/` directory simply has no entries. No error, no placeholder. (Optional by design.)
- A capability **with** `web/help/` must have at least one `en/` topic; otherwise build error ("help present but no source language").
- Every topic file's `topic` frontmatter must equal its filename stem; mismatch is a build error.
- `surfaces` entries are not validated against a closed enum (the UI owns surface identifiers). The generator only checks the field is a list of strings. This avoids coupling help discovery to UI internals.
- The generator must be idempotent and drift-checked (`just check-generated`), consistent with the other generated views.

### "By existing" scaling

- Capability #8 wants help: create `web/help/en/*.md`. Next `just generate` includes it. Zero edits to any registry or generator.
- New topic: new `.md` file. Regenerate.
- New locale: new `web/help/<code>/` directory mirroring slugs. Coverage report updates.
- This matches the Docks/Commands/Settings-Pages contract: "a new X appears by existing, with zero generator changes."

## Multilingual behavior

- **Source language `en` is required** for every topic (build error otherwise).
- **`de`/`fr` are optional.** When a topic is requested in a locale that lacks a file, the registry falls back to the `en` version and marks it as fallback (a flag on the resolved topic, e.g. `fallback: true`).
- The UI decides how to present fallback (e.g. a note "not yet available in your language"). That is a UI decision, out of scope here.
- **Coverage report:** the generator emits a (human-readable, committed or artifact) list of capabilities × topics × locales, showing which are present and which are missing. This makes translation gaps visible without blocking. Consistent with the project's advisory-check philosophy (CodeQL, Scorecard are advisory).

## Drift protection

1. **Co-location (primary):** help files live inside the capability folder, next to the code they describe. A PR touching `app/capabilities/<name>/web/` reviews the help in the same diff. This is the strongest available mechanism and costs nothing.
2. **Coverage report (secondary, advisory):** surfaces capabilities with UI but no help, and topics missing translations. Informational; does not block.
3. **No hard "every capability must have help" check.** Premature and would violate §8 (new obligation). Revisit if/when help coverage becomes a quality gate the project wants to enforce.

## Governance note

Help is an **optional, additive** artifact:
- No new field in `capability.yaml` (so no §8 trigger).
- No new required file or check.
- No change to `affected.py` classes (help files are content; whether they trigger tests is a separate, later decision — likely `INERT`-equivalent, like `docs/`).
- The generator extension is the only code change; it is additive (new output file, new scan) and does not alter existing generated views.

## Backend scope (Phase 1 = none)

Help is served from the frontend bundle. No `app/generated/help.py`, no API endpoint. Rationale: in-app help is a frontend concern; the app is offline-capable and local-first; adding a backend surface now would expand scope without need. If a future feature needs server-side help (search, API consumers, external site generation via backend), add it then — the per-capability file layout already supports it.

## Scaling story (7 → x)

| Action | What happens | Edits to central files |
|---|---|---|
| Add capability #8 with help | Create `web/help/en/*.md` | none (generator discovers) |
| Add a topic to an existing capability | Create `web/help/<locale>/<slug>.md` | none |
| Add a new locale | Create `web/help/<code>/` mirroring slugs | none (coverage report updates) |
| Translate an existing topic | Add `web/help/<code>/<slug>.md` | none |
| Remove help from a capability | Delete `web/help/` | none (registry omits it) |

No registry edit, no generator edit, no capability-facts change for any of these. This is the property the foundation must have, and it holds because discovery is directory-based and optional.

## Relationship to v1 content (explicitly out of scope here)

The 98 v1 `ui_help_long` texts are a **content source**, not part of this design. Migrating them is a separate project that depends on this container existing first. The migration effort (per capability, not per note) is roughly:
- Filter feature notes by v2 capability area + ported status + presence of `ui_help_long`.
- Verify each text against v2 behavior; strip v1 code paths and status claims.
- Normalize to one source language; translate or mark fallback.
- Place into `web/help/<locale>/<slug>.md`.

This design does not prescribe the migration; it only ensures the container is ready to receive it.

## Relationship to Phase 2 (external docs site)

The same `.md` files are the source for an external site (e.g. mkdocs/zensical). The site reads them directly — no transformation, no second copy. `install.md` and the generated capability index join them as site pages. The haben-style CI build (catch broken links on PRs) becomes meaningful only once this content exists; until then it is premature. This design does not implement Phase 2.

## What's left to the builder (implementation plan will detail)

- Exact generator implementation (scan logic, frontmatter parsing library, drift check integration).
- Lazy-loading mechanism (dynamic imports vs. fetch) — UI-team decision, but the registry must expose loaders, not eager bodies.
- Coverage report format and location (committed file vs. CI artifact).
- Surface identifier vocabulary (owned by UI; help just consumes strings).
- Markdown renderer choice for the UI (out of scope, but format must be compatible).

## Open questions (resolved)

1. **Markdown-with-frontmatter** chosen over JSON — better authoring for long-form prose; JSON reserved for UI labels (i18n).
2. **en required, de/fr optional + fallback + coverage report** chosen over mandatory all-three — matches advisory philosophy and avoids blocking on translation.
3. **Coverage report format** left to the implementation plan (committed file vs. CI artifact) — both are acceptable; the plan should pick one and justify.