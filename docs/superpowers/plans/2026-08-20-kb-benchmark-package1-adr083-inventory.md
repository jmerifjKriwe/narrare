# KB Benchmark Package 1 — ADR-083 + User-Capability Inventory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Author program ADR-083 and survey the user-facing KB capability surface (the benchmark's test surface) as verified inventory documents.

**Architecture:** Docs-only package — no production code changes. ADR-083 records the program decisions from the approved spec (boundary to ADR-032, manually-only carve-out, co-evolution, baseline-first, conditional MCP/A2A). The inventory surveys what a user can retrieve / have checked / automatically extract, from the user's perspective, with every claimed API path mechanically verified against router code and the frontend's own API client.

**Tech Stack:** Markdown docs; `rg` (ripgrep) for mechanical path verification; graphify MCP (`query_graph`) for structure questions; standard repo commit hooks as the gate.

**Spec:** `docs/superpowers/specs/2026-08-20-kb-benchmark-instrument-design.md` (commits `3bd75a45`, `c3d7b258`) — binding.

## Global Constraints

- Project language English — all artifacts in English.
- NO production code changes in this package. Created/modified files: `docs/architecture/decisions/*`, `benchmark/inventory/*`, `docs/_shared/CURRENT_STATE.md` only.
- Benchmark program is manually-only: never wire anything into CI, pre-commit, coverage or adoption gates. Normal repo commit hooks still apply to these commits (they are repo gates, not benchmark gates).
- No reuse of `evals/` evaluators/judges — not applicable to docs, but do not reference evals code as inventory evidence; the inventory's evidence is router code + frontend API client.
- Every inventory API path must be mechanically verified (exact router decorator exists; frontend client call exists) before it enters a table. Unverifiable paths are findings, not entries.
- Per-task file cap: ≤ 3 files changed per task (repo delegation rule).
- ADR numbering: ADR-083 is the next free number (ADR-082 is the highest existing).

---

### Task 1: ADR-083 — KB Infrastructure Benchmark Program

**Files:**
- Create: `docs/architecture/decisions/ADR-083-kb-infrastructure-benchmark-program.md`
- Modify: `docs/architecture/decisions/INDEX.md` (add one table row)

**Interfaces:**
- Consumes: spec §2 (decision list, verbatim below), spec §6 (runner + LLM config), spec §7 (candidate probes).
- Produces: `ADR-083` referenced by all later program plans and by `benchmark/inventory/README.md` (Task 2).

- [ ] **Step 1: Read format exemplars and the spec**

Read `docs/architecture/decisions/ADR-082-token-budget-governance.md` (recent, compact) and `docs/architecture/decisions/INDEX.md` (row format). Read the full spec `docs/superpowers/specs/2026-08-20-kb-benchmark-instrument-design.md`.

- [ ] **Step 2: Write the ADR**

Match the existing ADR structure (Status / Context / Decision / Options / Consequences / Review Trigger where used). Status: match the repo's convention for an accepted-but-not-yet-implemented decision (check how INDEX marks non-implemented accepted ADRs; if all are Implemented, use `Accepted` and state that implementation tracking lives in the program plans).

Content — decisions (binding, from spec §2, §6, §7):

1. **Boundary to ADR-032:** `evals/` = CI-integrated SSOT for AI runtime quality (agents, tailored evaluators). New `benchmark/` program area = manual infrastructure comparison on production functions. No import relationship in either direction.
2. **Manually-only carve-out:** benchmark runs are deliberate manual acts; no CI job, pre-commit hook, coverage or adoption gate may ever depend on the benchmark.
3. **Production-surface-only measurement:** benchmark drives the same REST/SSE endpoints the UI drives (token auth); no internal test hooks; no reuse of evals evaluators/judges; LLM judges only if unavoidable, declared in the run manifest.
4. **Co-evolution, not consumption:** the benchmark is not a Narrare-as-dependency consumer; candidate-driven seams in Narrare happen in this repo via the normal architecture process with own ADRs, only when a candidate has earned integration.
5. **MCP/A2A conditional:** not needed for the baseline (deterministic HTTP runner); referenced against Q-001/Q-002 (ADAPTER-001/002); decided only when a concrete case requires it.
6. **Baseline-first:** baseline = current implementation; no candidate registry, no pre-selection; probes are demand-driven user decisions after baseline analysis.
7. **Candidate probe protocol:** standalone setup, native methods mandatory, documented result mapping (native output → reference format), install/teardown documentation enabling residue-free uninstall; feeding modes reference-import vs. self-extraction.
8. **Runner-local LLM config:** gitignored config inside `benchmark/` (real credentials; committed template with placeholders); provisioning via the normal user path (Setup Wizard → setup/settings endpoints; code anchor `apps/api/narrare/setup/provider_schemas.py`) — exact endpoints verified in the runner slice; run manifest records an LLM-config fingerprint, never the secret.
9. **Ownership one-liner:** KB-touching changes must check whether benchmark corpus or capability-inventory assumptions need updating.

Reference the spec as the detailed instrument design; reference superseded approaches (spec §10) briefly in a Design-History/Alternatives note (knowledge-contract doc + anchor checker; adapter-seam-first; separate repo — each with the one-line rejection reason).

- [ ] **Step 3: Add INDEX row**

In `docs/architecture/decisions/INDEX.md`, add the row matching the table format exactly:

```markdown
| [ADR-083](ADR-083-kb-infrastructure-benchmark-program.md) | KB Infrastructure Benchmark Program | <status> | 2026-08-20 | `benchmark/`, KB capabilities, evaluation governance |
```

- [ ] **Step 4: Verify and commit**

Run `rg -n "ADR-083" docs/architecture/decisions/INDEX.md docs/architecture/decisions/ADR-083-kb-infrastructure-benchmark-program.md` — expect matches in both files. Stage exactly these two files, commit:

```bash
git add docs/architecture/decisions/ADR-083-kb-infrastructure-benchmark-program.md docs/architecture/decisions/INDEX.md
git commit -m "docs(adr): add ADR-083 KB infrastructure benchmark program"
```

Commit hooks must pass (Frontmatter/SSOT/doc-drift hooks validate ADR indexing). On hook failure: report verbatim, stop.

---

### Task 2: Inventory format + direction `in` (text → KB)

**Files:**
- Create: `benchmark/inventory/README.md`
- Create: `benchmark/inventory/01-in.md`

**Interfaces:**
- Consumes: ADR-083 (Task 1) for the program reference.
- Produces: the inventory table format (verbatim below) — Tasks 3 and 4 reuse it unchanged; `benchmark/inventory/` area that Task 5 synthesizes.

- [ ] **Step 1: Write `README.md` (method + format + status)**

Contents (binding for all inventory files):

- Purpose: user-perspective test surface of the KB, per spec §3; the benchmark measures exactly these capabilities; implicit yardstick for later candidates.
- Method: API paths are sourced from the frontend's own API clients (`packages/web/lib/api/*.ts`) and cross-verified against backend routers (`apps/api/narrare/*/router*.py` decorators). LLM-backed = the service behind the route invokes an agent/LLM (check service imports of `narrare_core.agents`). Output artifact = the response/stream the user actually receives.
- Entry format (used verbatim in `01-in.md`, `02-out.md`, `03-check.md`):

```markdown
### CAP-IN-NN: <capability name, user perspective, one sentence>

| Field | Value |
|---|---|
| Direction | in |
| API path(s) | `<METHOD> /api/v1/<path>` (router: `apps/api/narrare/<domain>/router*.py`; client: `packages/web/lib/api/<file>.ts`) |
| Output artifact | <what the operation produces: KB entry, report, SSE stream, …> |
| LLM-backed | yes / no / partial (<one-line reason, e.g. service uses ExtractionAgent>) |
| Benchmarkable | yes / partially / no (<one-line reason: is the output mechanically scorable against a reference?>) |
| Notes | <optional: preconditions, caveats, findings> |
```

- Findings rule (from spec §3): capabilities that exist only as frontend orchestration (no direct API path) are recorded as findings in the file's trailing `## Findings` section — verdict `not benchmarkable as-is` or `backend must expose this`, never silently dropped.
- Status section: which files exist, survey date, coverage counts.

- [ ] **Step 2: Survey `in` capabilities and write `01-in.md`**

Seed list to verify and survey (extend with anything discovered — this list is a floor, not a ceiling):

- KB-007 extraction: chapter → extraction candidates → endorse/reject (confirm endpoint)
- KB-002 assist: KB assist session flow (suggest → review → apply)
- KB-003 improve: analyze + apply on an existing entry
- KB-009 merge/dedup: KBMergeAgent flow (`POST /novels/{novel_id}/kb/merge`)
- SERIES-001 canon/overlay: scope toggle, join preview → apply, promote/demote
- PLAN-004 timeline: extraction SSE + confirm
- WIKI-001: wiki (precomputed context) generation triggers

For each: locate the route(s) (`rg -n "@router\.(get|post|patch|put|delete)\(" apps/api/narrare/kb/ apps/api/narrare/series/ apps/api/narrare/planning/`), the client call (`rg -n "kb|series|planning|wiki" packages/web/lib/api/ --glob "*.ts" -l` then inspect), the service's agent usage, and the output artifact. One entry per capability, numbered `CAP-IN-01…`.

- [ ] **Step 3: Mechanical verification**

For every API path listed in `01-in.md`, verify the router decorator exists:

```bash
rg -n "@router\.(get|post|patch|put|delete)\(" apps/api/narrare/ | rg "<path fragment>"
```

Expect one match per listed path. Any path without a match → move to `## Findings` with the failure, do not leave it as an entry.

- [ ] **Step 4: Commit**

```bash
git add benchmark/inventory/README.md benchmark/inventory/01-in.md
git commit -m "docs(benchmark): capability inventory — format and in-direction survey"
```

---

### Task 3: Direction `out` (KB → use)

**Files:**
- Create: `benchmark/inventory/02-out.md`

**Interfaces:**
- Consumes: entry format from `benchmark/inventory/README.md` (Task 2) — verbatim, unchanged.
- Produces: `02-out.md` entries `CAP-OUT-NN` for Task 5 synthesis.

- [ ] **Step 1: Survey `out` capabilities**

Seed list (floor, not ceiling):

- KB browsing / worldbuilding 3-column view data endpoints
- Entity lookup / detail (incl. metadata, relationships for KnowledgeGraphView)
- Semantic / embedding search (INFRA-004 — determine whether a user-facing search endpoint exists; if retrieval is only internal (proactive context pipeline), that is a finding)
- Wiki overview + chapter summary panels (WIKI-001 read side)
- Timeline read/visualization (PLAN-004 GET)
- Proactive context (KB-005 — likely internal pipeline; if no user-facing query path, finding: `not benchmarkable as-is` / `backend must expose this`)

Method and verification identical to Task 2 Steps 2–3 (`rg` router-decorator check per listed path; findings for unverifiable/frontend-only).

- [ ] **Step 2: Commit**

```bash
git add benchmark/inventory/02-out.md
git commit -m "docs(benchmark): capability inventory — out-direction survey"
```

---

### Task 4: Direction `check` (KB ↔ text)

**Files:**
- Create: `benchmark/inventory/03-check.md`

**Interfaces:**
- Consumes: entry format from `benchmark/inventory/README.md` (Task 2) — verbatim, unchanged.
- Produces: `03-check.md` entries `CAP-CHK-NN` for Task 5 synthesis.

- [ ] **Step 1: Survey `check` capabilities**

Seed list (floor, not ceiling):

- CONS-001 consistency checker: run + rule-based pre-check + suggested actions
- ADR-044 staged consistency: extraction-stage and contradiction-stage outputs; `ContradictionPromotionPolicy`
- SERIES-004 drift: canon-contradiction check (KB-based) and series voice drift (classify honestly: prose/voice-profile based, KB-adjacent — the `Benchmarkable` verdict must say what the comparison base actually is)
- PLAN-004 duration impossibility checks + LLM timeline consistency
- Prototype from spec §3: character extracted at chapter N checked against chapter M prose (height 1.65 → 1.80 m) — record which existing capability(ies) realize this scenario, or record as finding if none does end-to-end

Method and verification identical to Task 2 Steps 2–3.

- [ ] **Step 2: Commit**

```bash
git add benchmark/inventory/03-check.md
git commit -m "docs(benchmark): capability inventory — check-direction survey"
```

---

### Task 5: Synthesis, findings register, CURRENT_STATE

**Files:**
- Create: `benchmark/inventory/04-findings.md`
- Modify: `docs/_shared/CURRENT_STATE.md` (one new entry at the top of `## Last Updated`)

**Interfaces:**
- Consumes: `01-in.md`, `02-out.md`, `03-check.md` (Tasks 2–4), README format.
- Produces: the synthesized capability counts + findings register that the corpus and runner plans build on; CURRENT_STATE entry.

- [ ] **Step 1: Write `04-findings.md`**

Sections (all derived from the three survey files — no new claims without verification):

- `## Capability counts` — table: direction × (total / benchmarkable yes / partially / no / LLM-backed).
- `## Findings register` — consolidated: every finding from the three files, each with: finding, affected capability ID(s), verdict (`not benchmarkable as-is` / `backend must expose this` / other), and impact on the benchmark (which measurement is blocked until resolved).
- `## LLM-config dependency` — list of capabilities with `LLM-backed: yes/partial`; note that these require the runner-local LLM config provisioning (spec §6, ADR-083 decision 8).
- `## Gaps for later slices` — explicitly out of this package: corpus reference format, runner, scoring (pointer to spec §8).

- [ ] **Step 2: Cross-check completeness**

```bash
rg -c "^### CAP-" benchmark/inventory/01-in.md benchmark/inventory/02-out.md benchmark/inventory/03-check.md
```

Counts must match the numbers in `04-findings.md`. Every `LLM-backed: yes` entry must appear in the dependency list. Mismatch → fix before commit.

- [ ] **Step 3: Add CURRENT_STATE entry**

Prepend one entry to `docs/_shared/CURRENT_STATE.md` under `## Last Updated` following the existing dense single-paragraph style:

```markdown
Date: 2026-08-20 (**KB Benchmark Package 1 — ADR-083 + User-Capability Inventory — implemented**; spec [2026-08-20-kb-benchmark-instrument-design.md](superpowers/specs/2026-08-20-kb-benchmark-instrument-design.md), commits <range>). Program ADR-083 records the KB infrastructure benchmark decisions (ADR-032 boundary — no evals reuse; manually-only carve-out; production-surface-only measurement via REST/SSE + token auth; co-evolution not consumption; MCP/A2A conditional on Q-001/Q-002; baseline-first, no candidate registry; standalone candidate probes with native methods + documented result mapping + install/teardown protocol; runner-local gitignored LLM config provisioned via the normal setup/settings path). `benchmark/inventory/` holds the user-perspective capability survey (in/out/check directions, API paths verified against routers + frontend clients, LLM-backed + benchmarkable verdicts, findings register in 04-findings.md). No production code changes. Next: corpus slice (test novel + ground truth + error variants), then runner + scoring, then baseline runs.)
```

Implementer fills `<range>` with the actual commit range; keeps the entry truthful to what shipped (adjust counts wording if findings changed the picture).

- [ ] **Step 4: Commit**

```bash
git add benchmark/inventory/04-findings.md docs/_shared/CURRENT_STATE.md
git commit -m "docs(benchmark): capability inventory synthesis + CURRENT_STATE entry"
```

---

## Plan Self-Review (executed)

- Spec coverage (package-1 scope): ADR-083 decisions §2 → Task 1 Step 2 items 1–9 ✓; LLM config §6 → Task 1 item 8 + Task 5 dependency list ✓; inventory fields §3 incl. `LLM-backed?` and findings rule → Task 2 format ✓; directions in/out/check → Tasks 2–4 ✓; synthesis + program handoff (CURRENT_STATE) → Task 5 ✓. Corpus/runner/scoring deliberately out — later plans per spec §8.
- Placeholder scan: `<status>`, `<capability name>`, `<METHOD> /api/v1/<path>` etc. are fill-in slots for survey results (the survey IS the task), not unspecified implementation — acceptable; no TBD/TODO.
- Type consistency: capability ID schemes `CAP-IN-NN` / `CAP-OUT-NN` / `CAP-CHK-NN` and file names used consistently across Tasks 2–5; entry format defined once (Task 2) and referenced verbatim.
