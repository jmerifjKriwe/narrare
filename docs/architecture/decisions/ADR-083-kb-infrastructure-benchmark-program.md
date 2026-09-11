# ADR-083 — KB Infrastructure Benchmark Program

> **Status:** ✅ Accepted (2026-08-20) — implementation not in this ADR; delivery is
> tracked in the program plans (see Implementation Notes), starting with
> `docs/superpowers/plans/2026-08-20-kb-benchmark-package1-adr083-inventory.md`
> **Date:** 2026-08-20
> **Deciders:** PO (program design approved 2026-08-20), Architecture Agent (draft)
> **Detailed instrument design:**
> `docs/superpowers/specs/2026-08-20-kb-benchmark-instrument-design.md`
> (approved 2026-08-20; this ADR is its binding program-decision record —
> decisions below mirror the spec's §2/§6/§7 and are authoritative)
> **Related:** ADR-032 (pydantic-evals SSOT — boundary drawn in Decision 1),
> Q-001/Q-002 (ADAPTER-001/002 — MCP/A2A conditionality, Decision 5),
> ADR-071 (CoreSettings — operator env-var plane referenced by the LLM-config
> provisioning expectation)

---

## Context

The claim under test: **"PostgreSQL + pgvector is the right knowledge-base
architecture for Narrare."** This claim shaped the KB stack but has never been
validated. The KB Infrastructure Benchmark program builds the measuring
*instrument* — user-capability inventory, test corpus, runner, scoring, run
artifacts, and a candidate-probe protocol — that makes the claim falsifiable,
**before** any alternative technology is even looked at.

Two operating principles shape every decision below:

- **Measure exclusively through the normal, implemented functions.** The
  benchmark drives the production surface (the same REST/SSE endpoints the UI
  drives). A measurement that encodes Narrare's own assumptions would compare
  assumptions, not systems.
- **Manual operation only.** A benchmark run is a deliberate manual act by the
  user; LLM cost is bounded by explicit human decision, never by automation.

This ADR is the program's decision record. It decides the program frame;
instrument details (corpus format, scoring formulas, directory layout) are
specified in the instrument-design spec and its successor implementation plans.

---

## Decision Drivers

- **Falsifiability first** — the architecture claim must be testable before any
  candidate comparison can be meaningful.
- **Honest measurement** — no adapted helper functions, no test hooks, no reuse
  of `evals/` machinery; the benchmark must not encode Narrare's assumptions.
- **Bounded, deliberate cost** — LLM-backed capabilities run on every
  measurement; only a human may decide to spend.
- **Clear boundary to ADR-032** — `evals/` already has a mandate; the program
  must not blur it.
- **Co-evolution** — benchmark findings must be able to change Narrare's
  architecture through the normal in-repo process.

---

## Options Considered (Design History — superseded approaches)

Recorded honestly from the design review (spec §10); each rejected for cause:

- **Knowledge-Contract sub-project** (8-area semantic survey document,
  capability-declaration matrix, candidate registry, plus a mechanical anchor
  checker `scripts/check_knowledge_contract.py`): **superseded** — it
  pre-structured exactly what the empirical baseline runs should determine; a
  doc-first survey would have measured beliefs about the KB before measuring
  the KB. The user-capability inventory replaces it for the test surface; the
  baseline runs replace it for the semantics.
- **Adapter-seam-first architecture** (benchmark runner behind an MCP/A2A
  agent interface): **replaced** — by the deterministic HTTP runner on
  production paths; MCP/A2A demoted to a conditional enabler (Decision 5).
- **Separate repo** (`narrare-evaluation/`): **rejected** — the benchmark
  co-evolves with Narrare (Decision 4); a pinned external dependency could not
  feed architecture changes back.

---

## Decision

1. **Boundary to ADR-032:** `evals/` = CI-integrated SSOT for AI *runtime
   quality* (agents, prompts, tailored evaluators). The new `benchmark/`
   program area = *manual infrastructure comparison* on production functions.
   No import relationship in either direction.

2. **Manually-only carve-out:** benchmark runs are deliberate manual acts; no
   CI job, pre-commit hook, coverage or adoption gate may ever depend on the
   benchmark. Documented explicitly so the benchmark can never silently fall
   into a gate and then be "aligned" to it.

3. **Production-surface-only measurement:** the benchmark drives the same
   REST/SSE endpoints the UI drives (token auth); no internal test hooks; no
   reuse of `evals/` evaluators or judges in either direction; LLM judges only
   if unavoidable — for genuinely free-form outputs — and then declared in the
   run manifest (model + version).

4. **Co-evolution, not consumption:** the benchmark is not a
   Narrare-as-dependency consumer. Candidate-driven seams in Narrare (e.g. an
   extractable KB-backend interface) happen *in this repo* via the normal
   architecture process with their own ADRs — only when a candidate has earned
   integration (Decision 6/7).

5. **MCP/A2A conditional:** not needed for the baseline (deterministic HTTP
   runner, spec §6); referenced against Q-001/Q-002 (ADAPTER-001/002,
   "Planned, Not Implemented"); decided only when a concrete case requires it.

6. **Baseline-first:** the baseline is the current implementation, full stop.
   No candidate registry, no pre-selection, no capability matrix authored now.
   Which tools get probed, and when, are demand-driven user decisions after
   baseline analysis.

7. **Candidate probe protocol:** standalone setup (detached from Narrare),
   native methods mandatory (no unified adapter protocol — otherwise we would
   measure the bending, not the tool), documented result mapping
   (native output → reference format, part of the run artifact), and
   install/teardown documentation enabling residue-free uninstall. Feeding
   modes: **reference-import** (novel + reference KB ingested) vs.
   **self-extraction** (novel only; the candidate builds its KB with its own
   native extraction methods).

8. **Runner-local LLM config:** gitignored config file inside `benchmark/`
   holding real credentials (target API base URL, benchmark-user auth token,
   LLM provider settings); a committed template with placeholders documents
   the format; secrets never enter git. Provisioning goes through the
   **normal user configuration path** (Setup Wizard → setup/settings
   endpoints; code anchor `apps/api/narrare/setup/provider_schemas.py`) so the
   benchmarked instance is configured exactly like a real user's instance —
   exact endpoints verified in the runner slice. The run manifest records an
   LLM-config fingerprint (provider/model/config hash), never the secret.

9. **Ownership one-liner:** KB-touching changes must check whether benchmark
   corpus or capability-inventory assumptions need updating.

---

## Rationale

The program exists to falsify, not to confirm. Every decision above removes a
path by which the instrument could lie: measuring through production functions
(3) prevents assumption-encoding; the manual carve-out (2) prevents the
benchmark from being optimized toward a gate; baseline-first (6) prevents
premature candidate framing from biasing what gets measured; native candidate
methods (7) prevent measuring an adapter instead of a tool; co-evolution (4)
keeps the feedback loop inside the repo where architecture change actually
happens. The ADR-032 boundary (1) keeps runtime-quality evaluation (CI, prompts,
agents) strictly separate from infrastructure comparison (manual, production
surface) — different questions, different instruments, no shared machinery.

---

## Consequences

**Positive:**

- The KB architecture claim becomes empirically testable; baseline runs
  produce the first honest survey of the current implementation.
- Candidate probes become repeatable, auditable (result mappings in run
  artifacts), and reversible (residue-free teardown) — no evaluation residue
  accumulates in the repo or the machine.
- The `evals/` mandate stays clean; no gate anywhere depends on benchmark
  results, so the benchmark can never drift into CI cost or flakiness.

**Negative / Trade-offs:**

- Manual operation means no continuous regression signal from the benchmark —
  accepted deliberately (cost bounding, Decision 2).
- Production-surface-only measurement caps the benchmark at what the API
  exposes; capabilities that exist only as frontend orchestration surface as
  inventory findings ("not benchmarkable as-is"), not as measurements.
- LLM-backed capabilities make runs non-deterministic and non-free; comparability
  rests on identical corpus + reference + manifest discipline, not on
  bit-reproducibility.

**Constraints introduced / touched:**

- KB-touching changes carry the Decision-9 check (corpus / inventory
  assumptions) — an ownership rule, enforced by review discipline.
- No CONSTRAINTS.md RULE-XX change: the program adds no production code and no
  dependency; if the runner slice proposes one (e.g. an HTTP client library),
  that decision belongs to the runner slice under RULE-08, not here.

---

## Implementation Notes

- **Program sequence** (spec §8): (1) instrument spec — done; (2) this ADR +
  user-capability inventory (first empirical deliverable, in/out/check
  directions, API paths, LLM-backed flag, benchmarkable verdict);
  (3) corpus authoring (German test novel, machine-readable reference KB,
  clean/light/complex error variants, incremental + full-import ingest modes);
  (4) runner + scoring for the current implementation; (5) baseline runs;
  (6) user analysis — the decision point; (7) ad-hoc candidate probes, each
  with its own mini-plan.
- **Implementation tracking** lives in the program plans, not in this ADR.
  Package 1:
  `docs/superpowers/plans/2026-08-20-kb-benchmark-package1-adr083-inventory.md`
  (ADR-083 + capability inventory). Corpus and runner/scoring plans follow.
- **Deliberately undecided** (spec §11): MCP/A2A shape (Q-001/Q-002); which
  candidates, when; exact corpus size and reference format; concrete
  `benchmark/` layout; exact provisioning endpoints and gitignored config
  format (runner slice).
- The AI agent is never in the measurement path: it authors (corpus,
  reference, error variants, candidate test adaptations) and operates
  candidates, but the runner only orchestrates HTTP calls and scores.

**ADR Implementation Completeness Gate:** this ADR records program decisions
only — there is no code to wire. Its "implemented" state is reached when the
program artifacts it governs (inventory, corpus, runner, scoring) exist and
their plans reference this ADR; per-slice completeness is tracked in those
plans.

---

## Review Trigger

- [ ] When **baseline analysis completes** (program sequence step 6) — the
      user's candidate decisions then define the first probes; revisit nothing
      here, but each integration-worthy candidate requires its own ADR
      (Decision 4).
- [ ] When **Q-001/Q-002 (ADAPTER-001/002)** are decided — re-check Decision 5's
      conditionality against the actual adapter outcome.
- [ ] When a **KB capability changes shape** (new, removed, or re-routed API
      surface) — Decision 9 check: benchmark corpus and capability-inventory
      assumptions must be updated in the same change or explicitly waived.
      *Check record (2026-09-07, ADR-085 P4/D5):* the unmounted KB-009 merge
      router (`kb/router_merge.py`, `POST /novels/{novel_id}/kb/merge`) was
      deleted; the capability is superseded by the entity-resolution surface
      (`/kb/resolution/*`). The capability-inventory update (CAP-IN-10) lands
      with the benchmark integration slice.
- [ ] When any **gate ever proposes to consume benchmark results** — hard
      conflict with Decision 2; requires superseding this ADR, not amending it.
