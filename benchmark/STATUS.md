# KB Benchmark Program — Status

Standing document: where the program stands, what the numbers say, what is open.
How to run things lives in the runbook [`README.md`](README.md) §2–§6; governance and
scope in [ADR-083](../docs/architecture/decisions/ADR-083-kb-infrastructure-benchmark-program.md).

The program measures how well Narrare's Knowledge-Base capabilities actually work end
to end: each run spins up a throwaway production stack, ingests the German benchmark
corpus through the real REST/SSE surface exactly as the UI would, and scores the result
against a hand-built reference corpus. Its second job is finding product defects —
findings must change the product through the normal process, never the instrument
(ADR-083 D3).

## 1. Where we stand (2026-09-08)

Best baseline: run `2026-09-08-clean-incremental-2` (commit `27747444`) — entity
coverage **81.8%**, fact coverage **76.0%**, fact precision **56.1%**, relation
coverage **55.6%**, all best-ever. Resolution (CAP-IN-10) is **vacuous-clean**: no
duplicate arose, so detection precision/recall are 1.0 by construction
(`expected_pair_count: 0`, `suggested_count: 0`); detection and the distractor gate
are armed and will produce real scores the moment run variance produces a duplicate
pair.

## 2. Metric trajectory (clean incremental runs only)

All values read from each run's `results.json` / `overview.md`
(`benchmark/runs/<id>/` — gitignored, local artifacts).

| run | entity | fact cov | fact prec | relation | notes |
|---|---|---|---|---|---|
| `2026-09-06-clean-incremental-2` | 45.5% | 4.0% | 100%* | 0% | first full 12-chapter run, pre-fixes; 63 spurious entities |
| `2026-09-06-clean-incremental-4` | 69.7% | 54.7% | 14.6% | 33.3% | scoring fixes: KB relationship name enrichment, canonical predicates, merge-not-clobber, salience |
| `2026-09-07-clean-incremental-1` | 72.7% | 61.3% | 37.0% | 51.9% | apply data-loss fix landed; 56/56 KB entries present post-ingest, 0 lost |
| `2026-09-07-clean-incremental-2` | 72.7% | 65.3% | 51.0% | 29.6% | extraction prompt v1.8.0 + fact-match validity (temporal fact keys, semantic value matching) |
| `2026-09-07-clean-incremental-3` | 78.8% | 61.3% | 58.7% | 22.2% | prompt v1.9.2 + gender-aware relation matching; relation edges entity-blocked by the "Anna" duplicate |
| `2026-09-08-clean-incremental-2` | 81.8% | 76.0% | 56.1% | 55.6% | ADR-085 resolution layer + falsy-zero position fix; current best |

\* Vacuous: only 3 facts were found (3 correct, 0 wrong) — precision over an
almost-empty match set means nothing.

## 3. Measurement caveats

- **LLM run-to-run variance is large; compare trends, not single runs.** Relation
  coverage swung 22.2% → 55.6% between `2026-09-07-clean-incremental-3` and the
  `2026-09-08` runs with extraction prompts and relation scoring unchanged. In the
  two `2026-09-08` runs — differing only by the position fix — fact coverage moved
  62.7% → 76.0% and fact precision 74.5% → 56.1%. Treat single-run scores as
  ±10–20pp noisy. Model: `glm-5.3-flash` via the zai endpoint (identical config
  fingerprint across all runs).
- **Fact precision band 51–75%** across the four recent runs (51.0 / 56.1 / 58.7 /
  74.5). It is the least stable headline metric; do not read single-run movements as
  regressions without a repeat run.
- **Resolution metrics are vacuous-clean when extraction produces no duplicate** —
  the expected good-pipeline case. They bite when variance strikes: in
  `2026-09-07-clean-incremental-3` a bare "Anna" entry coexisted with the matched
  "Anna Meyer" (the designed distractor, "Anna Meier", is a different person by
  corpus design) and entity-blocked 6 direction-fixable relation edges — the run's
  relation coverage 22.2% is the measured damage. That run predates CAP-IN-10, so
  the resolver did not score it; CAP-IN-10 exists to score exactly such runs.

## 4. Product bugs the benchmark found (all fixed)

- **Relationship apply dead-path** — source/target endpoints never resolved; repair
  in `2e92c905`.
- **Silent batch data loss via poisoned session** — one duplicate-edge
  `IntegrityError` poisoned the session; the whole batch rolled back while the
  response still reported success. Benchmark run 5 proved it: 33 of 64 created
  entities vanished server-side. Fix: relationship idempotency +
  savepoint-per-item + in-batch resolution, `89348508`.
- **Settings get-or-create races** under concurrent setup — race-safe upserts,
  `b030e8ec`.
- **Falsy-zero position collapse** in chapters/volumes `max_position`
  (`scalar_one_or_none() or -1`): position 0 is falsy, so ALL API-created chapters
  collapsed to position 0, breaking ordering and downstream range logic —
  `27747444`.
- **Per-request cache lifetime in resolution endpoints** — the cache was constructed
  per request and could never hit across requests; module-level singleton —
  `d8029a4a`.

## 5. Open / deferred

- **`light` + `complex` variant runs** — deferred while clean-baseline fundamentals
  were being fixed; both error registries are ready
  (`benchmark/corpus/variants/{light,complex}/`), the runner supports `--variant`.
  This is the NEXT natural step (detection metrics are all-zero until a variant
  runs).
- **Open product findings** (deferred, from the ADR-085 SDD reviews):
  - `apps/api/narrare/kb/_consistency_deps.py:91` — the consistency DI factory builds
    a per-request `InMemorySessionCache()`; same defect class as the fixed
    resolution-cache bug, so the consistency cache can never hit cross-request
    (parked slice).
  - `get_shortest_path` BFS traverses deprecated nodes as intermediate hops (the
    adjacency map is not deprecation-filtered; only display naming is).
  - Cross-writer note-absence: the endorse flow refreshes caches with a note-less
    payload, which analyze then cache-hits — REVIEW suggestions served with notes as
    `None`.
  - 11 legacy `type: ignore`s in `tests/unit/api/volumes/test_volume_repository.py`.
  - Extraction prompt v1.9.x wording dedup (object-fact sentence is redundant).
- **Auto-merge policy: v1 ships none** — the engine only reports the
  `auto_merge_eligible` band (`auto_band_ok` in the artifacts). Activation is gated
  by the ADR-085 Review Trigger: recalibrate the spec §4 constants and decide the
  policy after enough CAP-IN-10 evidence, as its own ADR amendment.
- **Provenance backfill for pre-ADR-085 entries: none** — entries without
  provenance score with unknown-signal degradation, accepted by design (design spec
  OQ-3).

## 6. How to continue (quick start)

- Run (full procedure, prerequisites, config: README §2–§3):

  ```sh
  uv run python -m benchmark run --variant clean --mode incremental \
    --capabilities CAP-IN-01,CAP-IN-10,CAP-OUT-03
  ```

  Observed wall-clock for 2–3-capability incremental runs: 24–61 min. A slow
  extraction call can fail the run with a ReadTimeout — just retry.
- Compare: artifacts land in `benchmark/runs/<id>/` — `overview.md` (human summary)
  and `results.json` (scores; carries a `resolution` section when CAP-IN-10 is
  driven), plus `answers.jsonl`, `events.jsonl`, `manifest.json`. Failed runs write
  `failure.json` before teardown.
- Current extraction prompt: **v1.9.2**
  (`packages/core/narrare_core/prompts/_bundled/kb/en/extract/system.md`,
  frontmatter `prompt_version`).
