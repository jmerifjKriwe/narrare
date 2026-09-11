# KB Benchmark Package 3 — Runner + Scoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The benchmark runner: a deterministic Python program that spins up its own Narrare stack (docker compose), provisions LLM config via the normal setup path, ingests the corpus (clean + variants, incremental and import modes), drives ALL 26 inventoried capabilities via the production REST/SSE API, scores against the reference and error registries, and writes the standardized run artifacts — then tears the stack down residue-free.

**Architecture:** `benchmark/` becomes a registered Python scan-root (evals/ precedent). Deterministic orchestration only — no LLM in the measurement path beyond what the driven capabilities themselves do server-side. Capability drivers are grouped by invocation shape (REST-JSON / SSE / long-running); scorers are grouped by evidence shape (KB-content vs detection-report vs retrieval). Every score must be mechanically traceable to reference ids or registry error ids. Tests live in `benchmark/tests/` with manual invocation — never in the CI test tree (ADR-083 manually-only carve-out).

**Tech Stack:** Python 3.14 (repo toolchain: uv, pyright strict, ruff, English), httpx (sync client OK for orchestration; SSE via httpx streaming), docker compose CLI (subprocess, never docker SDK), PyYAML (already a dep? verify; else vendored stdlib-only parsing is NOT acceptable — declare pyyaml if missing), pytest (manual scope).

**Spec:** `docs/superpowers/specs/2026-08-20-kb-benchmark-instrument-design.md` §5 (measurement), §6 (runner + LLM config), §8.4. **PO decisions:** F1=B (self-managed stack), F2=A (all 26 capabilities in v1). **Binding riders (from ledger memos):** variant injection MUST scope anchors by the registry's chapter field, never corpus-wide grep (L09 lesson); X07/L06 disjoint-anchor pattern is expected in ch-12.

## Global Constraints

- Manually-only (ADR-083): benchmark code NEVER enters CI jobs, pre-commit gates for the repo, coverage baselines, or adoption checks. Benchmark tests run via `uv run pytest benchmark/tests/` (manual) — root pytest config must NOT pick them up; a guard test in the repo test tree asserts benchmark/ is absent from CI testpaths.
- Production-surface-only: the runner speaks HTTP(S) to the API exactly as the UI does; no internal imports of narrare code beyond shared type definitions if unavoidable (prefer: no imports at all — the runner knows only JSON shapes). Importing narrare_core into benchmark/ is FORBIDDEN (co-evolution boundary: the runner must survive KB-internal refactors).
- English throughout (code, comments, tests, artifacts). German appears only in corpus data flowing through.
- Repo Python standards: pyright strict clean, ruff clean, one responsibility per file, RULE-04 size limits apply (they are pre-commit hooks — they DO run on benchmark/ files).
- No secrets in git: benchmark/config.local.yaml is gitignored (template with placeholders committed; Gitleaks guards).
- Per-task caps: ≤3 files / ≤250 new LOC per delegation.
- Determinism: no wall-clock or randomness in scoring; LLM-backed capability outputs are RECORDED per run (their variability is the object of measurement, not noise to hide); seeds/nondeterminism settings wherever the API offers them.
- Stack hygiene: every run ends with teardown (containers, volumes, networks) unless `--keep-stack` is passed; teardown verified by name-prefix listing returning empty.

---

### Task 1: API-surface investigation + area registration

**Files:**
- Create: `benchmark/docs/api-surface.md`
- Modify: `pyproject.toml` (workspace/script registration as needed), `scripts/check_architecture.py` scan-root registration ONLY if the checker requires explicit listing for benchmark/ (investigate how evals/ is registered; follow exactly), `benchmark/pyproject.toml` OR root-declared package per workspace convention (follow evals/ precedent exactly), Create `benchmark/__init__.py`, `benchmark/tests/__init__.py` + one placeholder test, `benchmark/tests/test_guard.py` (asserts root pytest testpaths exclude benchmark), Modify root `pyproject.toml`/pytest config so CI testpaths exclude benchmark/ explicitly if not already implicit.

**Interfaces:**
- Produces: the VERIFIED API map (auth register/login/token refresh; setup wizard steps incl. LLM provider provisioning endpoints with request shapes from `apps/api/narrare/setup/provider_schemas.py`; novel/chapter creation + publish; extraction trigger + candidates + endorse/reject; the ingest-into-KB flows per inventory CAP-IN-*; check-capability endpoints per CAP-CHK-*; retrieval endpoints per CAP-OUT-*; SSE event shapes) — every later task consumes this document; requests verified against routers (method-pinned) and, where feasible, by starting a dev server manually ONCE and recording real exchanges (optional but recommended; document how).

- [ ] Investigate (graphify + router reads): auth flow (registration? login? token type/lifetime), setup steps 1–5 endpoint sequence for provider config, per-capability endpoints for all 26 CAP entries (pull from benchmark/inventory/*.md — they already carry method-pinned paths), SSE event name/shape conventions, error-shape convention.
- [ ] Write `benchmark/docs/api-surface.md`: per endpoint — method, path, auth, request schema, response schema, SSE events, notes (idempotency, limits). Mark anything unverifiable as OPEN with the blocking question.
- [ ] Register the area (follow evals/ precedent exactly for pyproject/scan roots); placeholder package + guard test; verify `uv run pytest benchmark/tests/` runs the guard green locally; verify root `uv run pytest tests/` collection does NOT include benchmark.
- [ ] Commit: `feat(benchmark): register runner area + verified API surface map`.

### Task 2: Config + stack manager

**Files:**
- Create: `benchmark/config.py` (dataclass config loader: benchmark/config.local.yaml + template validation), `benchmark/stack.py` (compose orchestration), `benchmark/tests/test_config.py`, `benchmark/tests/test_stack.py` (unit-test the command construction + name-prefix filtering with a fake subprocess runner; NO docker needed in tests), `.gitignore` entry (modify root .gitignore), Create `benchmark/config.template.yaml`.

- [ ] config: fields — stack (project_name prefix, port range), api (base_url override, timeout), auth (benchmark user credentials), llm (provider, api_key, model settings per setup schema), run (variants, modes, keep_stack flag). Template with placeholders; loader validates + fails with precise messages; never logs secrets (redaction helper).
- [ ] stack manager: `up()` (compose -p <prefix> up -d with the repo compose file + API service; wait-for-health polling the API /health or equivalent — verify real endpoint in Task 1 map; timeout + clear error), `teardown(verify=True)` (down -v --remove-orphans; then ls by prefix → empty assertion), `is_up()`. Subprocess invocation with captured output, loggable on failure. Port collision handling: dynamic free-port selection for the API port, injected via compose env override.
- [ ] Tests: command construction, teardown verification logic, redaction, config validation errors. All unit-level with fakes.
- [ ] Commit: `feat(benchmark): config + self-managed compose stack`.

### Task 3: API client (auth + REST + SSE)

**Files:**
- Create: `benchmark/client.py` (httpx-based), `benchmark/sse.py` (SSE line parser + event accumulation), `benchmark/tests/test_client.py`, `benchmark/tests/test_sse.py` (parser tests against recorded event bytes; client tests against a local aiohttp/httpx mock transport — no network).

- [ ] client: register (if the flow requires) + login → token; auto-refresh on 401 once; typed thin wrappers ONLY for generic request/stream; endpoint-specific helpers live in drivers (Task 7+), not here.
- [ ] SSE: parse `event:`/`data:` frames per the Task 1 map; accumulate JSON payloads; expose async iterator or list-collector; handle [DONE]/close conventions verified from real streams in the map.
- [ ] Commit: `feat(benchmark): API client with auth + SSE parsing`.

### Task 4: Provisioning (user + LLM config via setup path)

**Files:**
- Create: `benchmark/provision.py`, `benchmark/tests/test_provision.py`.

- [ ] Idempotent provisioning: ensure benchmark user exists (register or login-implies-exists per Task 1 findings), walk setup wizard to the provider step, PUT/POST the LLM provider config from benchmark config (provider, key, model) using the EXACT normal-user path (spec §6: anchor `setup/provider_schemas.py`); verify success response; no env-var plane unless Task 1 proves the user path impossible (then: document deviation in api-surface.md + spec amendment proposal — do NOT silently switch).
- [ ] Test: fake client asserting the endpoint sequence + payload shape.
- [ ] Commit: `feat(benchmark): idempotent user + LLM provisioning via setup path`.

### Task 5: Corpus materializer

**Files:**
- Create: `benchmark/corpus.py`, `benchmark/tests/test_corpus.py`.

- [ ] Load corpus.yaml + reference YAMLs + variant registries (pyyaml). Materialize chapters into memory (or tmp dir): clean = chapter files as-is; variant = per-error find/replace applied ONLY within the error's own chapter (binding rider: scope by registry chapter field; never corpus-wide), with pre-flight validation (anchor exactly-once in that chapter — re-run the G2 gate at runtime; failure = hard error, corpus/registries drifted) and post-flight sanity (replacement absent from clean pre-apply). Expose: chapters(variant) → list[(stem, text)], reference() → typed views, errors(variant) → list with class/chapter/ground_truth_ref.
- [ ] Tests: variant application incl. the L09 multi-chapter-recurrence case (apply only in ch-08), X07/L06 same-paragraph disjoint case, drift detection error paths.
- [ ] Commit: `feat(benchmark): corpus + variant materialization with drift gates`.

### Task 6: Ingest drivers (build path)

**Files:**
- Create: `benchmark/ingest.py`, `benchmark/tests/test_ingest.py`.

- [ ] Incremental mode: for each chapter in order — create chapter (or novel+chapter for the first), set text, publish/trigger per Task 1 map, run extraction (CAP-IN-01 flow), capture candidates, endorse per strategy (v1 strategy: endorse-all-with-confidence-threshold? NO — v1: endorse ALL candidates; record every decision; the strategy is part of the measured pipeline, keep it deterministic and documented), proceed. Import mode: the bulk path per map (if none exists, import = incremental without per-chapter waits — document).
- [ ] Progress + failure capture: every step's raw request/response logged into the run's raw-events sink (for artifacts).
- [ ] Tests: orchestration against fake client (call sequence, ordering, candidate recording).
- [ ] Commit: `feat(benchmark): incremental + import ingest drivers`.

### Task 7: Capability driver framework + registry

**Files:**
- Create: `benchmark/drivers/__init__.py`, `benchmark/drivers/base.py` (shape contracts: REST/SSE/poll), `benchmark/capabilities.py` (inventory→driver mapping table: all 26 CAP ids with driver ref + invocation spec + output schema pointer), `benchmark/tests/test_capabilities.py`.

- [ ] base: driver protocol — `invoke(ctx) -> CapabilityResult(raw, parsed, timing)`; SSE drivers collect events to terminal state; polling drivers poll until done/timeout. ctx carries client + corpus + novel/chapter ids.
- [ ] capabilities table: for each of the 26 inventory entries — id, direction, endpoint spec (from api-surface.md), driver class, output parser ref. Unmounted/unusable entries (the 2 unmounted routers, no-client cases): present but marked `unavailable_reason` → invoked as `SKIPPED(unavailable)` and reported as such (honest reporting beats silent omission; the artifact lists them).
- [ ] Tests: registry completeness (26 entries, ids match inventory files exactly — parse benchmark/inventory/*.md to assert).
- [ ] Commit: `feat(benchmark): capability driver framework + 26-entry registry`.

### Tasks 8–10: Drivers per direction (in / out / check)

**Files per task:** `benchmark/drivers/in_direction.py` + test / `out_direction.py` + test / `check_direction.py` + test (one task per direction; each ≤3 files).

- [ ] in (Task 8): extraction-candidates fetch, assist-session, improve-analyze/apply, scope toggle/promote, timeline extract+confirm, wiki generation trigger, character-voice (CAP-IN-09), etc. per table — each driver invokes per its inventory API path(s) and parses outputs into typed records.
- [ ] out (Task 9): browse/list, entity detail, relationships/graph data, wiki read, timeline read, suggestions, templates — parse into typed records; where output is prose (wiki summaries) record raw for artifact, mark scorable surface.
- [ ] check (Task 10): staged consistency run (mounted router only), series drift (needs series setup? — the check capabilities requiring a SERIES: v1 drives them on the single novel where possible; if a capability structurally requires entities the corpus cannot provide, `SKIPPED(structural)` with reason — record in artifacts; do not fabricate setup), duration checks, voice checks.
- [ ] Commits: `feat(benchmark): in/out/check capability drivers`.

### Task 11: Scoring — KB build quality

**Files:**
- Create: `benchmark/scoring/build_quality.py`, `benchmark/scoring/__init__.py`, `benchmark/tests/test_build_quality.py`.

- [ ] After ingest: fetch KB state via out-direction endpoints (entity list + details + relationships). Match against reference (by name + predicate set): coverage per entity/fact/relation (expected-found), precision (found-correct), with per-item lists (found/missing/spurious) carrying reference ids (F/R/E/PF/OF) for traceability. Interval-aware fact matching (value + valid_from/valid_to tolerance: month precision). Output: typed BuildQualityScore.
- [ ] Tests: synthetic KB vs synthetic reference — coverage/precision math, interval matching, id traceability.
- [ ] Commit: `feat(benchmark): KB build-quality scoring vs reference`.

### Task 12: Scoring — detection (TP/FP/FN per error class × capability)

**Files:**
- Create: `benchmark/scoring/detection.py`, `benchmark/tests/test_detection.py`.

- [ ] For each variant run: the check-capability outputs (parsed reports from drivers) are matched against the error registry: an injected error counts as detected (TP) only if the report names/locates it within tolerance (matching rules per report shape — citation of chapter + statement proximity; document rules in module docstring); unflagged injected error = FN; a contradiction/finding reported that maps to NO injected error = FP (matching against clean-corpus truths to avoid counting pre-existing honest findings; the clean run establishes the FP baseline — spec §5's detection quality needs the clean-run comparison). Per class × capability matrix → precision/recall/F1 where set-valued.
- [ ] Tests: report-to-error matching rules incl. near-miss citations; FP baseline subtraction logic.
- [ ] Commit: `feat(benchmark): detection scoring with clean-run FP baseline`.

### Task 13: Scoring — retrieval + partial mappings

**Files:**
- Create: `benchmark/scoring/retrieval.py`, `benchmark/tests/test_retrieval.py`.

- [ ] Entity lookup / state-at-time / relationship queries derived FROM the reference (query generation: for N sample facts, ask the out-endpoints; expected answer = reference value). Mark `partially`-benchmarkable capabilities per inventory verdicts: score what is mechanically comparable, record the rest as recorded-not-scored. Skipped-structural/unavailable capabilities aggregate into the artifact's coverage table.
- [ ] Tests: query generation determinism, answer matching.
- [ ] Commit: `feat(benchmark): retrieval + partial-capability scoring`.

### Task 14: Artifacts (results JSON + Markdown overview + manifest)

**Files:**
- Create: `benchmark/artifacts.py`, `benchmark/tests/test_artifacts.py`.

- [ ] results.json: per capability × per class scores + itemized lists (traceable ids); answers.jsonl: per driven capability raw parsed outputs; manifest: timestamp, git commit, corpus version, variant, mode, config fingerprint (LLM provider/model/config-hash, NEVER the key), stack: compose file hash + image digests + api version endpoint payload; run id (`YYYY-MM-DD-<variant>-<mode>-<n>`); overview.md: the human "aussagekräftige Übersicht" — per-direction tables, error-class matrix, FP baseline note, skipped table with reasons.
- [ ] Tests: artifact shape, secret redaction (no key anywhere), manifest completeness.
- [ ] Commit: `feat(benchmark): run artifacts — results, answers, manifest, overview`.

### Task 15: CLI + end-to-end wiring

**Files:**
- Create: `benchmark/__main__.py`, `benchmark/runner.py`, `benchmark/tests/test_runner.py`.

- [ ] CLI: `uv run python -m benchmark run --variant light --mode incremental [--keep-stack] [--capabilities CAP-IN-01,...]`; subcommands `stack up|down|status` for debugging. runner.py: orchestrate stack → provision → materialize → ingest → drive capabilities → score → artifacts → teardown (always, also on failure — try/finally). Fail-fast with clear errors; partial-failure runs still write artifacts with the failure recorded.
- [ ] Tests: wiring with all collaborators faked (sequence, teardown-always, flag plumbing).
- [ ] Commit: `feat(benchmark): CLI + end-to-end orchestration`.

### Task 16: README runbook + dry-run rehearsal

**Files:**
- Create: `benchmark/README.md` (runbook: prerequisites (docker, config.local.yaml from template), commands, artifact locations, troubleshooting incl. port/health issues, manual test invocation), Modify `benchmark/docs/api-surface.md` if rehearsal corrected anything.
- [ ] Rehearsal: with a REAL local docker stack and a REDACTED/dummy LLM config (or the PO's real key if provided), execute one smoke run on `--variant clean --mode incremental --capabilities CAP-IN-01,CAP-OUT-03` (subset); fix what breaks (root-cause); document actual run output in the README (redacted). If no Docker/key available in session: mark rehearsal as PO-step with exact instructions; do not fake results.
- [ ] Commit: `docs(benchmark): runner runbook + rehearsal notes`.

### Task 17: Final review + CURRENT_STATE

- [ ] Whole-branch review (reviewer, most capable): plan coverage, 26-capability completeness vs inventory, artifact honesty, CI-isolation guard intact, no narrare imports, no secrets.
- [ ] CURRENT_STATE entry; memory update; ledger close.

---

## Plan Self-Review (executed)

- Spec coverage: §5 measurement (Tasks 11–13), §6 runner/LLM-config/determinism/artifacts (Tasks 2–4, 14–15), §8.4, F1=B (Task 2), F2=A (Task 7 + 8–10 + 13 partial mappings + skipped-reporting). Riders honored: chapter-scoped anchor application (Task 5 + test), X07/L06 case (Task 5 test).
- Placeholder scan: endpoint specifics deliberately deferred to Task 1's verified map (investigation IS the task, outputs committed); no TBDs in logic.
- Type consistency: CapabilityResult/BuildQualityScore/DetectionReport named in Tasks 7/11/12 and consumed in 13–15; capabilities table is the single id source (asserted against inventory files).
- Risks documented: series-dependent check capabilities (structural-skip path), missing bulk-import endpoint (fallback documented), LLM nondeterminism (recorded not hidden), CI isolation (guard test).
