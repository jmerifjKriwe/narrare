# KB Infrastructure Benchmark — Instrument Design

- **Date:** 2026-08-20
- **Status:** Approved design — implementation planning follows (`writing-plans`)
- **Program:** KB Infrastructure Benchmark (program ADR to be authored as **ADR-083**, the first implementation task)
- **Scope:** The measuring *instrument* — capability inventory, test corpus, runner, scoring, run artifacts, and the candidate-probe protocol. The candidates themselves are out of scope.

---

## 1. Goal & Thesis

The claim under test: **"PostgreSQL + pgvector is the right knowledge-base architecture for Narrare."** This claim shaped the KB stack but has never been validated. This program builds the instrument that makes the claim falsifiable — before any alternative technology is even looked at.

Operating principle: **measure exclusively through the normal, implemented functions.** The benchmark drives the production surface (the same REST/SSE endpoints the UI drives). No customized helper functions, no reuse of `evals/` evaluators or judges, no internal test hooks. A measurement that encodes Narrare's own assumptions would compare assumptions, not systems.

Operation is **manually only**: a benchmark run is a deliberate manual act by the user. No CI job, no pre-commit hook, no coverage/adoption gate will ever depend on the benchmark. LLM cost is therefore bounded by explicit human decision, never by automation.

## 2. Program Frame — ADR-083

ADR-083 ("KB Infrastructure Benchmark Program") is authored as the first implementation task (Architecture layer). It decides:

- **Boundary to ADR-032:** `evals/` is the CI-integrated SSOT for AI *runtime quality* (agents, prompts, tailored evaluators). The new `benchmark/` program area is the *manual infrastructure comparison* running on production functions. No import relationship in either direction.
- **Manually-only carve-out:** documented explicitly, so the benchmark can never silently fall into a gate and then be "aligned" to it.
- **Co-evolution, not consumption:** the benchmark is not a Narrare-as-dependency consumer. If testing a candidate ultimately requires a seam in Narrare (e.g. an extractable KB-backend interface), that change happens *in this repo* through the normal architecture process with its own ADR — and only when a candidate has earned integration (see §7).
- **MCP/A2A is conditional:** referenced against Q-001/Q-002 (ADAPTER-001/002, "Planned, Not Implemented"), deliberately *not* decided here. The baseline needs neither (§6).
- **Baseline-first:** the baseline is the current implementation, full stop. No candidate registry, no pre-selection. Which tools get probed, and when, is a user decision after baseline analysis.
- **Ownership one-liner:** KB-touching changes must check whether benchmark corpus or inventory assumptions need updating.

## 3. User-Capability Inventory (first implementation package)

Before anything can be measured, the test surface must be known — from the **user's perspective**, not the code's. The inventory answers three questions:

1. What can a user **retrieve** from the KB?
2. What can a user **have checked** (consistency, contradictions, timeline, …)?
3. What can a user **automatically extract** into the KB?

Each inventory entry records:

| Field | Meaning |
|---|---|
| Capability | User-visible ability, one sentence |
| Direction | **in** (text → KB: extraction, endorse/reject, merge) · **out** (KB → use: search, graph view, wiki, context injection) · **check** (KB ↔ text: consistency, contradiction detection, timeline checks, series drift) |
| API path(s) | The exact route(s) the UI drives, incl. auth requirements |
| Output artifact | What the operation produces (KB entry, report, SSE stream, …) |
| LLM-backed? | Whether the capability executes server-side LLM calls (determines the LLM-config dependency, §6) |
| Benchmarkable? | Is the output mechanically scorable against the reference? |

Findings rule: capabilities that exist only as frontend orchestration (no direct API path) are a **documented finding** — verdict "not benchmarkable as-is" or "backend must expose this", never a silent decision.

The inventory implicitly defines the yardstick for later candidates: a candidate is measured against exactly these capabilities, with adapted tests using its native operations (§7).

Prototype scenario (from design discussion): a character extracted from chapter N is endorsed into the KB (**in**); a consistency check then validates that character against chapter M's prose — did the height silently change from 1.65 m to 1.80 m? (**check**). The check's report is scored against the injected error truth.

## 4. Test Corpus

- **Novel:** constructed specifically for this purpose (not an existing work), so that ground truth is known per fact. Order of magnitude ~8–12 chapters; the exact size is tuned during corpus authoring. Language: **German** (matches the primary writing context; extraction prompts support de).
- **Reference KB (ground truth):** the expected entities, facts, and relations — each anchored to its source chapter, including temporal courses (residences, professions, ages over time). Machine-readable format is defined in the corpus slice; it is the scoring reference for every run.
- **Variants:**
  - **Clean** — fully consistent; baseline quality measurement.
  - **Light errors** — attribute-value deviations (wrong age, wrong height), timeline mismatches (dates that cannot fit the established course).
  - **Complex errors** — semantically difficult cases: implicit temporal statements, contradictions that require interpretation rather than literal comparison.
  Each injected error is recorded in the ground truth with its class and location, so detection can be scored exactly.
- **Ingest modes:**
  - **Incremental** — chapter for chapter, exactly as the KB grows in live operation (publish → extract → endorse per chapter).
  - **Full import** — the complete material at once.
- Corpus authoring is its own implementation slice (the authoring effort proper, incl. AI-assisted drafting with human verification against the recorded truth).

## 5. Measurement & Scoring

Per run, against the identical corpus and reference:

- **KB build quality** (in-capabilities): coverage and precision of the built KB vs. the reference — "were all expected contents present, and was what's there correct?" Measured per entity/fact/relation, per ingest mode.
- **Detection quality** (check-capabilities): per error class and per capability, scored as TP/FP/FN against the injected error truth → precision/recall/F1 where the output is set-valued. This yields the per-capability success rate ("Erfolgsquote je Funktion").
- **Retrieval quality** (out-capabilities): scorable wherever the output is mechanically comparable to the reference (e.g. entity lookup, state-at-time queries); free-text outputs are scored mechanically wherever possible.
- **LLM judges only if unavoidable** — for genuinely free-form outputs — and then explicitly declared in the run manifest (model + version), keeping the measurement honest about where model judgment enters.
- **Run artifacts (the comparability):** every run — baseline or candidate — produces the same artifact shape:
  - `results` (structured JSON: per-capability, per-error-class scores),
  - a rendered Markdown overview (the human-readable "aussagekräftige Übersicht": which errors were found, KB quality, expected-content coverage, per-function success rates),
  - a run manifest (git commit, Narrare version, corpus variant + version, ingest mode, config incl. an LLM-config fingerprint — provider/model/config hash, never the secret itself, §6; timestamps; for candidate runs additionally tool/version and the result mapping, §7).

## 6. Runner

A **deterministic Python HTTP/SSE client** that drives exactly the production endpoints the UI drives, authenticating like a real client (token auth). No Playwright, no UI automation — the frontend is itself only an API client, so driving the API *is* "as if it happened directly in Narrare".

The AI agent is deliberately **not in the measurement path**: the measured capabilities (extraction, consistency, …) do their LLM work server-side inside Narrare; the runner only orchestrates HTTP calls and scores. An agent in the loop would add non-determinism and cost without measurement quality. The agent's roles are authorship (corpus, reference, error variants, candidate test adaptations) and candidate ops (§7).

Mode flags: corpus variant × ingest mode. Location: `benchmark/` top-level program area (concrete layout is a planning decision).

### Runner Configuration & LLM Backend Config

Several benchmarked capabilities are LLM-backed server-side; the backend needs a valid LLM provider configuration before any run. Consequences:

- The benchmark keeps its own **local config file inside `benchmark/`, gitignored**, holding real credentials: target API base URL, benchmark-user auth token, LLM provider settings (provider, API key, model(s)). A committed template with placeholders documents the format; secrets never enter git (also guarded by the Gitleaks hook).
- **How this config lands in the backend is verified in the runner slice.** Expected candidate (consistent with the production-surface principle, and consistent with the code survey: `apps/api/narrare/setup/provider_schemas.py` — Setup Wizard Steps 4–5): provisioning through the **normal user configuration path** (Setup Wizard → setup/settings endpoints), so the benchmarked instance is configured exactly like a real user's instance. The operator env-var plane (`CoreSettings`, ADR-071) is acceptable only if it proves to be the (only) production path for these values.
- Provisioning is an idempotent runner setup step executed before runs; the run manifest records the LLM-config fingerprint (§5), never the secret.

## 7. Candidate Probes (after baseline analysis; demand-driven)

- **Trigger:** the user's decision after analyzing baseline results. No registry, no schedule. (mem0, graph databases, SQLite-with-extension, local memory systems — all examples of what *could* be probed, not a list.)
- **Standalone first:** a candidate is set up *detached from Narrare*. The AI agent installs it and documents exactly: tool, version, how and where installed, configuration — such that the setup is **repeatable** and **uninstalls residue-free** (a setup/teardown protocol per candidate: after teardown, containers/volumes/networks/packages/ports are verifiably gone).
- **Feeding modes:**
  1. **Reference-import** — novel + reference KB are ingested into the candidate. Measures storage and retrieval quality with defined input.
  2. **Self-extraction** — novel only; the candidate builds its KB with its own native extraction methods. Measures extraction quality.
  Combined with the in/check/out capability directions (§3), this forms the comparison grid against the baseline's twin measurements.
- **Native methods are mandatory:** the adapted tests drive the tool's own operations (CLI, API, query language — whatever it has). No unified adapter protocol, no bending the tool into a foreign interface; otherwise we would measure the bending, not the tool.
- **Documented result mapping:** each candidate run records how native outputs map onto the reference format (which native call, which transformation, which version). The mapping is part of the run artifact, so comparisons stay auditable months later.
- **Narrare integration only if earned:** if and only if a probe shows promise does integration into Narrare get considered — then via the normal architecture process (seam + own ADR, §2 co-evolution). Never before.

## 8. Sequence

1. This spec (instrument design).
2. **ADR-083 + capability inventory** (Architecture-led; inventory = first empirical deliverable).
3. **Corpus authoring** (novel, reference KB, error variants).
4. **Runner + scoring** for the current implementation.
5. **Baseline runs** producing standardized overviews — the baseline runs *are* the survey of the current implementation.
6. **User analysis of baseline results** — the decision point.
7. **Ad-hoc candidate probes**, each with its own mini-plan (install doc, adapted tests, feeding mode(s), result mapping, teardown).

## 9. Non-Goals

- No CI / pre-commit / coverage / adoption integration — ever (§1).
- No candidate selection, registry, or capability matrix now; candidates are demand-driven (§7).
- No MCP/A2A implementation in this program phase; conditional on Q-001/Q-002 when a concrete case requires it.
- No unified adapter protocol for candidates.
- No reuse of `evals/` evaluators or judges in either direction.
- No Narrare production-code changes, except findings surfaced by the inventory — each going through the normal change process.

## 10. Design History (superseded approaches — honest record)

- **Knowledge-Contract sub-project** (8-area semantic survey document, capability-declaration matrix, candidate registry incl. mem0/opencode-mem classification, plus a mechanical anchor checker `scripts/check_knowledge_contract.py`): **superseded** during design review. Reason: it pre-structured exactly what the empirical baseline runs should determine; a doc-first survey would have measured beliefs about the KB before measuring the KB. The user-capability inventory (§3) replaces the survey for the test surface; the baseline runs (§8.5) replace it for the semantics. The anchor-checker idea was retired with its subject — inventory API paths are verified empirically by the runner (a missing route fails the run loudly).
- **Adapter-seam-first architecture** (benchmark runner behind an MCP/A2A agent interface): **replaced** by the deterministic HTTP runner on production paths (§6); MCP/A2A demoted to a conditional enabler.
- **Separate-repo option** (`narrare-evaluation/`): **rejected** — the benchmark co-evolves with Narrare (§2); a pinned external dependency could not feed architecture changes back.

## 11. Open Points (explicitly undecided)

- MCP/A2A necessity and shape — Q-001/Q-002; decided when a concrete candidate case requires it.
- Which candidates are probed, and when — user decision after baseline analysis.
- Exact corpus size, chapter count, and reference-format details — corpus slice (§8.3).
- Concrete `benchmark/` directory layout — planning decision of the runner slice.
- Exact mechanism and endpoints for provisioning the benchmark's LLM config into the backend (expected: normal setup/settings path, §6) and the concrete gitignored config file format — runner slice.
