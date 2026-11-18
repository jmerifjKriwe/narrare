# Frontend Rebuild — W5 (Knowledge) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The knowledge capability's four surfaces — the workspace dock (making W4's #866–#869 placeholders real), the lore graph with entity/relation CRUD, the dossiers (real fields, invented fields as honest gaps), and the sources archive (documents + semantic search) — all on the complete existing backend, split into small PRs.

**Architecture:** The knowledge capability's web folder is rebuilt from scratch. The dock is a dockRoute under the W4 workspace's dock registry; the graph, dossiers and sources are addressable routes under the capability's own path. Everything rides the existing API (`/api/knowledge/*`: documents, search, extraction→suggestions, consistency→findings, entities CRUD+merge, relations CRUD). No new backend.

**Tech Stack:** unchanged.

**Spec:** `docs/superpowers/specs/2026-11-13-frontend-rebuild-design.md`. Drafts (read-first authority): the harmonized `lore-graph-2`, `dossiers-2`, `sources-archive-2` (owner-approved, content-verified against real fields) + the existing `knowledge-ai-dock` for the dock.

## Owner decisions binding this wave (2026-11-19)

- Scope: Dock + Graph + Dossiers + Sources (all four families).
- Invented dossier fields (Want/Need/Lie, status taxonomy, counts, export) are honest disabled placeholders with gap rows — never filled with fake content.
- Atlas and entity-genesis chat are later waves (Atlas needs a geography model decision; Genesis belongs to the chat wave).
- The dock's entity-chip family (#866–#869) rides this wave: the placeholders retire.

## Global Constraints

- No deferred findings, any severity (owner rule since W2). Small PRs (owner rule since W4).
- Stitch alone designs; the harmonized drafts are the authority; deviations through named-gap rounds; honest values only (no invented numbers).
- Rule 5: en/de/fr catalogs, sorted, same keys, du-tone. Rule 2: the knowledge E2E suite ships this wave. Rule 1: no cross-capability imports; the dock composes through the generated dock registry.
- Models rev. 6: implementer/UI `qwencloud/qwen4-max-preview`, reviewer `zai-coding-plan/glm-5.3`.
- Conventional commits: `feat(knowledge)` with real `User-visible:` lines; hidden types for infra.

## Review Focus

1. **Dock truth** — every dock face reads the real API (findings list, consistency trigger, entity chips from the row, extraction suggestions); no mock number.
2. **Graph determinism** — same entities/relations → same layout (seeded/pure physics or deterministic fallback); CRUD dialogs honest.
3. **Honest gaps** — every invented field renders as a clearly-disabled area with its gap-row note; no fake content sneaks in.
4. **i18n whole** — knowledge catalogs NEW; parity across three; du-tone.
5. **E2E real** — extraction with the fake provider → suggestion accept → entity in graph → dock chip; consistency → finding → acknowledge.

---

### PR A — Dock (makes #866–#869 real)

**Task 1: Dock scaffolding + findings**
- The dockRoute under the workspace's dock registry (the generated table's composition point); the findings face: list, acknowledge, dismiss (real API); the consistency trigger with its async-job honest busy. Pinned by vitest + E2E leg.

**Task 2: Entity chips + extraction suggestions**
- The entity-chip face from the row's entities; the extraction trigger + suggestion accept/discard flow (async, honest busy, accept creates the entity). The #866/#867 placeholders retire (in-code interims removed, issues close from commits).

### PR B — Lore graph + dossiers

**Task 3: Graph page (the harmonized `lore-graph-2` draft)**
- Route + the force-graph (nodes=entities typed by the real type set, edges=relations with notes); deterministic layout (seeded positions or a pure deterministic pass); zoom/pan; node click → dossier panel (inline, the real fields); edge click → note popover; type filter + name search (client-side over the loaded graph). i18n. Vitest: determinism, filter, selection, du-tone.

**Task 4: Entity/relation CRUD + merge dialogs**
- Create/edit entity (name/type/description), create/edit/delete relation (type + note), merge (the existing endpoint); confirm/destructive states per the quick-menu discipline; focus contracts.

**Task 5: Dossiers page (the harmonized `dossiers-2` draft)**
- Route + the dossier grid (type-filtered, searchable) + the dossier detail (real fields: name/type/description/relations); the invented fields as honest disabled areas with gap-doc rows + child issues. The dossier-detail IS the entity's expanded view (no second data model).

### PR C — Sources + E2E + wave close

**Task 6: Sources page (the harmonized `sources-archive-2` draft)**
- Route + document upload/list/delete + semantic search results (document title + chunk excerpt); footnote/fact-check as honest disabled areas with gap rows.

**Task 7: Knowledge E2E suite + gap ledger**
- The fake-provider flow: seed a novel → upload a document → extraction → suggestion appears → accept → entity in graph + dock chip → consistency → finding → acknowledge. de-DE; per-suite DB; two workers max.
- The wave's gap ledger (`2026-11-19-knowledge.md`): every honest placeholder with its trigger; the dock's retired placeholders' issues close; W4's dock rows in the shelf/workspace ledgers resolve.

**Task 8: Wave gate + PR**
- `just verify` all green; whole-branch review; merge after owner.
