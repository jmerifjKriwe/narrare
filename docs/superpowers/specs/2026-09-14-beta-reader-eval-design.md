# Beta-Reader Mini-Eval — Instrument Design

> **Status:** Proposed (2026-09-14) — awaiting PO approval
> **Repo anchor:** `9472fae2`
> **Deciders:** PO (rulings below), Architecture Agent (draft)
> **PO rulings baked in (binding, not re-litigated):**
> 1. Option B — own mini-eval instrument OUTSIDE the KB benchmark (ADR-083 scope).
> 2. Genre pinning via corpus manifest `genre: "Literary Fiction"` — single source.
> 3. EN templates are the settled convention; no localization work.
> 4. No LLM-judge in v1.
> **Related:** ADR-083 (KB benchmark program boundary), ADR-082 (token budgets),
> ADR-086 (ModelRegistry.prepare / model resolution), ADR-035 (agent output
> validators), ADR-032 (pydantic-evals SSOT — boundary discussed in §3),
> spec 2026-08-20-kb-benchmark-instrument-design (sibling instrument),
> commits `ee40bc65` + `9f4c7519` (the prompt changes under test).

---

## 1. Goal & Non-Goals

**Goal.** A repeatable, cost-bounded, manually-triggered instrument that answers:
*"Do beta_reader / beta_reader_deepdive prompt changes preserve or improve the
quality of the analysis on real chapter-scale prose?"* — with two scoring layers:

- **Layer 1 (automatic):** deterministic Output-Format contract checks on the
  real chain's structured output (enums, count bounds, score ranges,
  excerpt grounding).
- **Layer 2 (qualitative):** per-run artifact set (system prompt, user prompt,
  response, summary) plus a rendered **rating template** the PO fills against a
  fixed rubric. The PO rating is the ground truth; there is no machine judge.

**Non-Goals.**

- No CI integration, no gate, no coverage/adoption entanglement (manual-only,
  mirroring ADR-083 Decision 2's philosophy for cost-bound instruments).
- No KB-capability scoring — beta_reader emits feedback text, not
  machine-scorable KB structures (ADR-083 capability registry: 27 entries,
  zero beta_reader; empirically confirmed).
- No API-stack E2E — the stack benchmark already owns production-surface
  measurement; this instrument measures the changed surface (templates +
  user-channel builder + model behavior), which is fully exercised core-chain.
- No localization (PO ruling 3), no LLM-judge (ruling 4), no multi-mode
  generalization in v1 (beta_reader + beta_reader_deepdive only; structure may
  host further analysis modes later — demand-driven).

## 2. Root Cause (why this instrument, ≥2× why)

**Symptom.** The header-governance program changed beta_reader/deepdive prompts
more than any other templates (`ee40bc65` surgery + `9f4c7519` family) with no
measurement vehicle for output quality.

**Why #1 — why can't existing vehicles measure it?**
(a) The KB benchmark is scoped to machine-scorable KB capabilities
(ADR-083); beta_reader's feedback text has no scorer. (b) `scripts/probes/
analysis_probes.py` proves pipeline *mechanics* (`evidence_recorded` on fixture
sentences with a stub `ComposedPrompt`) — it never asserts output quality and
never runs chapter-scale prose. (c) The render smoke proved the *compose path*
(`build_budgeted_prompt` + `AnalysisContextAssembler`), not model behavior.

**Why #2 — why isn't "tests green" enough?** The contract tests validate the
template's variables and the validators' mechanics with deterministic fakes;
the property at risk — *whether the real model, reading the real composed
prompt over a real chapter, produces well-calibrated, genre-appropriate,
actionable feedback* — is observable only by running the real chain and
reading the output. Hence: dedicated instrument, real chain, PO judgment.

## 3. Decision D1 — Home: `scripts/evals/` (new directory)

Three candidates evaluated (the two offered plus the existing third the
boundary discussion obliges us to consider):

| Option | Verdict | Reason |
|---|---|---|
| `benchmark/evals/` | **Rejected** | ADR-083 Decision 1 charters `benchmark/` as *manual infrastructure comparison* on KB capabilities. Homing a prompt-quality eval inside the program area invites registry/scope creep (next contributor "just adds" it to the capability inventory) and breaches the charter from the inside. The corpus argument justifies *reading benchmark assets*, not homing the instrument. |
| `evals/` (ADR-032 SSOT) | **Rejected** | Textually the mandate fits ("CI-integrated SSOT for AI runtime quality — agents, prompts"), but the harness is machine-scored suites: smoke/runtime modes, dataset/evaluator shapes, JSON reports + drift checker. The PO-rubric workflow (read full prompts/responses per run dir, fill `rating.md`, compare run trees before/after) does not fit those shapes without distorting both instruments. ADR-083 Decision 3's judge-reuse prohibition also signals deliberate instrument separation. |
| `scripts/evals/` | **Chosen** | Sibling of `scripts/probes/` — the established home for manual, human-triggered, real-chain drivers. Precedent: `scripts/probes/ai_assist_probes.py` imports `narrare.*` services directly; workspace members are `.pth`-installed (verified: `narrare`, `narrare_core` resolvable); pyright `extraPaths` includes `scripts` (pyproject:79); pytest `testpaths=["tests"]` keeps the instrument out of CI by construction. |

**Boundary rules (binding for implementation):**

- Allowed imports: stdlib, `narrare_core.*`, `narrare.analysis.*` (apps/api
  analysis modules — same direction as probes; never reverse).
- **Forbidden imports:** anything from `benchmark/` or `evals/` — corpus and
  config are consumed as *files via paths*, never as code. Zero code coupling
  to either SSOT area; asset reads only.
- Data dependencies (read-only): `benchmark/corpus/corpus.yaml`,
  `benchmark/corpus/clean/chapters/*.md`, `benchmark/config.local.yaml`
  (`llm` section only).

## 4. Decision D2 — Invocation: the real chain, no API stack

**Scope v1:** corpus chapters × {`beta_reader` (Phase 1), `beta_reader_deepdive`
(Phase 2)}, driven through the exact production composition + agent + model
path, with only the *data source* swapped (files instead of DB rows) and the
API transport removed. "Minimal-but-real": everything the prompt change
touches is real; everything it doesn't touch (router, auth, ownership gates,
cache, DB) is absent.

**Chain per case (source-anchored, faithful to `beta_reader_service.py`):**

1. **Corpus source** (own loader — `parse_chapter` semantics replicated, no
   benchmark import): manifest keys `name/version/language/genre/chapters`;
   chapter text from `clean/chapters/<stem>.md`; title = first `# ` line;
   `word_count = len(text.split())`.
2. **Deps** — `BetaReaderDeps(chapter_text, chapter_titles, word_count,
   genre=<manifest genre>, language=<manifest language>, kb_characters="",
   kb_locations="", previous_chapter_summaries=[], focus_categories=None)`.
   *Fidelity gaps vs production (documented in `manifest.known_gaps`):* no KB
   envelopes, no previous-chapter summaries (production gets both via the
   DB-backed ContextAssembler). v1 measures template + model behavior on
   chapter text alone; KB-channel effects are out of scope (open point §11).
3. **System prompt** — `PromptComposer(registry=PromptRegistry()).build(
   LLMIntent.BETA_READ, PromptContext(language=<manifest language>,
   mode="beta_reader" | "beta_reader_deepdive", project_title=""))`. This is
   *identical* to the service's own Mode-1 fallback composition
   (`_invocation_compose.py:123` — the production path when the invocation
   pipeline is absent). German manifest language → registry template fallback
   de→EN (settled convention, PO ruling 3); `writing_language` resolves to the
   manifest language, so feedback language matches the chapter — exactly the
   shipped product behavior.
4. **User prompt (Phase 1)** — `narrare.analysis.beta_reader_prompt.
   build_budgeted_prompt(deps, AnalysisContextAssembler())` — the real
   user-channel builder the render smoke proved. Budget: the assembler's
   documented default (32k, ADR-082 Decision 5) instead of the service's
   model-window-aware cascade — immaterial at single-chapter scale (chapters
   ≈ 2–4k words ≪ budget); recorded as a known gap.
5. **Model** — read `benchmark/config.local.yaml` `llm` section →
   `ResolvedModelConfig(provider_name, model_id, temperature=<CLI, default
   0.0>, max_tokens=4096, streams=False)`; then the service's `_prepare_model`
   replica: `DefaultRunLimitResolver().resolve(...)` → `ModelRegistry().
   prepare(config, intent=BETA_READ, usage_limits=..., api_key=...,
   base_url=None)` (ADR-086 prepared triple). `api_key` lives in-process only.
   *v1 restriction:* `zai_endpoint` must be `general` (`base_url=None`);
   `coding` → hard CLI error (open point §11).
6. **Phase 1 run** — `BetaReaderAgent(model=prepared.model,
   system_prompt=composed.system)` + `run_phase1(...)` from
   `beta_reader_agent_run.py` (real error wrapping, RULE-11), with
   `model_settings = {**prepared.model_settings, "temperature": t}`.
7. **Phase 2 run** — deep-dive deps assembled in-memory exactly as
   `deep_dive_deps()` does with the cache replaced by the live Phase-1 result
   (`phase1_strengths_summary` / `phase1_feedback_summary` from result titles
   — same content the cached path yields); composer mode
   `beta_reader_deepdive`; `run_phase2(...)` (builds its user prompt via
   `build_deepdive_prompt(deps)` internally — the artifact records the same
   string by calling that pure builder once for capture).

**Determinism:** temperature pinned via CLI (default `0.0`, merged into
prepared model settings, recorded in the manifest). No seed claim — provider
variance is acknowledged; before/after comparison therefore reads artifact
*suites* and rubric verdicts, not single-number equality. One run per
chapter×mode; variance probing = manual re-run into a fresh run dir.

**Why not against the stack:** the changed surface is fully exercised
core-chain (template + builder + model). The stack adds postgres/auth/SSE cost
while measuring nothing that changed; production-surface measurement is the
benchmark program's job, explicitly out of scope here (ADR-083 boundary).
Probe-style core-chain driving is sanctioned precedent
(`evals/tasks/dialogue_coach_runtime.py` does precisely this: PromptComposer +
ModelRegistry + real agent, no stack).

**Cost model:** default = 1 chapter × 2 phases = **2 LLM calls**. `--all` =
12 × 2 = 24 calls, explicit opt-in (the flag is the deliberate act — printed
call estimate precedes execution). `--dry-run` = compose + artifacts, **0
calls** (free prompt-regression capture).

## 5. Decision D3 — Scoring

### Layer 1 — automatic contract checks (deterministic, per chapter×mode)

Runs on the **post-validator output** (what the user would receive — ADR-035
validators silently drop empty items before we see the result; a count
violation therefore means a *shipped* contract breach, which is the correct
measurement).

Phase 1 (`beta_reader`):

| Check | Rule | Additive? |
|---|---|---|
| L1-P1-enum-category | every strengths/feedback/questions `category` ∈ {plot, character, prose, pacing, experience} | partly — validator enforces feedback only; strengths/questions additive |
| L1-P1-enum-severity | feedback `severity` ∈ {critical, moderate, minor} | yes — enforced nowhere today |
| L1-P1-count-strengths | 3 ≤ len(strengths) ≤ 7 | yes — prompt "Quality Rules" contract |
| L1-P1-count-feedback | 5 ≤ len(feedback) ≤ 12 | yes |
| L1-P1-count-questions | 2 ≤ len(questions) ≤ 5 | yes |
| L1-P1-nonempty | title/description non-empty on all items | post-filter emptiness = regression signal |
| L1-P1-scores | six overall scores ∈ [1, 10] | model-enforced; recorded for artifact completeness |
| L1-P1-grounding *(soft)* | fraction of non-null `text_excerpt` values found verbatim (whitespace-normalized) in `chapter_text` | new — mechanical false-positive proxy |

Phase 2 (`beta_reader_deepdive`): L1-P2-enum-category, L1-P2-enum-severity,
L1-P2-count-feedback (**5–10**), L1-P2-count-suggestions (**3–6**),
L1-P2-nonempty (suggestions + item fields), L1-P2-score (category_score
∈ [1, 10]), L1-P2-grounding *(soft)*.

**Semantics:** violations are *measurements*, not crashes. A run with 13
feedback items completes, writes full artifacts, and lists the violation —
that violation IS the regression signal the PO needs in context. Exit codes:
`0` run completed (violations may exist); `1` harness failure
(compose/invocation/artifact error — RULE-11, never silent); `2` CLI misuse.
Soft checks are reported, never fail anything. No gate consumes these numbers
(manual instrument).

### Layer 2 — PO rating template (ground truth)

Each run renders `rating.md`: per chapter×mode block + overall block. Rubric
dimensions (1–5 each + one free-text evidence line each):

1. **Genre calibration** — does the feedback prioritize per the manifest genre
   ("Literary Fiction": prose quality, interiority, thematic resonance,
   contemplative pacing — the template's own genre contract)?
2. **Severity discipline** — are critical/moderate/minor applied with the
   template's definitions, or inflated/deflated?
3. **False-positive impression** — do flagged issues hold up against the
   chapter (cross-reads the automatic grounding fractions)?
4. **Craft-actionability** — are suggestions concretely implementable (the
   template's "immediately" standard)?

Plus: overall verdict field per chapter×mode ∈ {regression, improvement,
parity, inconclusive} and a "compared against run `<id>`" field for
before/after use. The template is rendered fresh per run; the PO edits it in
place.

**No LLM-judge in v1 — argument (PO ruling 4):**

1. **Infinite regress.** A judge prompt is itself an instrument that must be
   validated against ground truth; validating the judge requires a judge of
   the judge. The only regress-stopper is a human authority — so the human
   authority should rate directly in v1.
2. **Single-author tool.** The PO is the consumer whose judgment the feature
   exists to serve; no proxy outperforms the ground-truth consumer here.
3. **Precedent.** ADR-083 Decision 3: LLM judges "only if unavoidable" — not
   unavoidable here; `evals/` judges exist but are optional/disabled, and
   cross-program judge reuse is explicitly prohibited. A fresh judge would
   add an unvalidated dependency to an instrument whose purpose is validity.

## 6. Decision D4 — Artifacts

**Root:** `scripts/evals/runs/beta-reader/` (mirrors the `benchmark/runs/`
precedent of run output inside the instrument's own area; gitignored —
`.gitignore` entry lands in Slice 1).

**Run id:** `YYYY-MM-DD-<git-short>-<n>` — `n` = next free counter in the
runs root (deterministic, no timestamps in the id; collision → loud mkdir
failure without `exist_ok`, benchmark `artifacts.py` semantics).

**Tree per run:**

```
<run_id>/
├── manifest.json                     # NO secrets (see below)
├── <stem>__beta_reader/
│   ├── system_prompt.txt             # composed, verbatim
│   ├── user_prompt.txt               # build_budgeted_prompt output
│   ├── response.json                 # Phase1Output model dump (post-validator)
│   └── layer1.json                   # check results incl. soft fractions
├── <stem>__beta_reader_deepdive/     # same 4 files (user = build_deepdive_prompt)
├── summary.md                        # per chapter×mode table: counts, violations,
│                                     # severity distribution, grounding, totals
└── rating.md                         # PO rubric template (§5)
```

`manifest.json`: run_id, created_at, git_commit, corpus {name, version,
language, genre, chapters}, prompt_versions {beta_reader, beta_reader_deepdive}
(template frontmatter `prompt_version` of the composed templates), model
{provider, model_id, temperature, max_tokens} — **never `api_key`** —,
config_fingerprint (sha256 over the redacted `llm` section), cli args,
call_count, known_gaps (§4 fidelity list).

**Atomicity:** all content is rendered in memory *before* any file is created
(a render/validation failure leaves the runs root untouched); each file writes
through tmp + `os.replace`. Semantics replicated from `benchmark/artifacts.py`
— deliberately *not* imported (§3 boundary).

**Secret hygiene:** the api key exists only in-process; artifacts carry
provider/model ids + fingerprint hash. Belt-and-braces: a secret-pattern sweep
(provid key shapes, `Bearer …`) over every rendered artifact before write —
any hit aborts the run before the first file lands.

**Before/after (regression) convention:** run the instrument on the old and
new revisions (bundled templates are package assets → use a worktree or branch
checkout; no runtime override mechanism in v1), then `--diff RUN_A RUN_B`
renders `diff_report.md`: per chapter×mode — prompt byte deltas, Layer-1
violation table A|B, count/severity/score deltas, artifact pointers for
side-by-side reading. Pure local JSON/markdown munging — zero LLM calls. The
PO fills both `rating.md`s and records the verdict pair.

## 7. Decision D5 — Corpus manifest genre (single source)

`benchmark/corpus/corpus.yaml` gains one top-level key:

```yaml
genre: "Literary Fiction"
```

**Tolerance (verified):** `benchmark/corpus_loader.py` reads named keys via
`config.get(...)` only — unknown top-level keys are ignored. The KB benchmark
is unaffected; no benchmark code changes.

**Ownership:** the eval owns its manifest reader (pydantic model:
`name/version/language/genre (non-empty str, required)/chapters (non-empty
list)`). Missing/empty genre → hard CLI error. The benchmark loader stays
genre-agnostic (its runs don't consume genre). No cross-instrument corpus
schema governance exists today; adding one is explicitly out of scope (open
point §11).

## 8. Decision D6 — CLI shape & cost guard

```
python scripts/evals/beta_reader_eval.py \
    [--chapter ch-01] [--all] \
    [--phases both|phase1] \
    [--category plot] \
    [--temperature 0.0] \
    [--dry-run] \
    [--out scripts/evals/runs/beta-reader] \
    [--diff RUN_A RUN_B]
```

- Defaults: chapter `ch-01`, both phases, deepdive category `plot`,
  temperature `0.0`. Default run = 2 LLM calls.
- `--all` opts into the full corpus (12 × 2 = 24 calls; estimate printed
  before execution).
- `--dry-run` composes and writes prompts + manifest with **zero** LLM calls —
  the free capture mode for prompt-only regressions.
- Direct script invocation with the probes' sys.path bootstrap — no `just`
  recipe in v1 (probes have none either; the usage banner in the module
  docstring documents invocation, probes style). A `just` recipe is backlog
  if the instrument becomes routine.
- Never pytest-driven: the global test guard blocks real LLM calls — the
  instrument's unit tests use TestModel/fixtures only; real runs are manual
  CLI acts.

## 9. Slices (≤3 substantive files each; contracts first per RULE-03)

**Slice 1 — Corpus source & manifest genre.**
Files: `benchmark/corpus/corpus.yaml` (+1 line), `scripts/evals/__init__.py`,
`scripts/evals/corpus_source.py` (pydantic contract models `EvalCorpusManifest`
/ `EvalChapter` + `load_eval_corpus(root)`), `tests/unit/scripts/
test_eval_corpus_source.py` (valid manifest; missing/empty genre → error;
title/word_count derivation; default corpus root).
Gate: benchmark corpus-loader unit tests stay green (tolerance proof);
`check_architecture.py` green.

**Slice 2 — Invocation runner + Layer-1 scorer.**
Files: `scripts/evals/beta_reader_runner.py` (deps construction, system-prompt
composition, `_prepare_model` replica, phase-1/2 execution; injectable
agent/model seams for TestModel), `scripts/evals/beta_reader_scoring.py`
(`Layer1Report` contract model + `check_phase1` / `check_phase2`), tests:
`test_beta_reader_scoring.py` (synthetic outputs: clean pass, each violation
class, grounding normalization), `test_beta_reader_runner.py` (TestModel agent;
deps faithfulness asserts; dry-run path).
Gate: unit tests green; zero `# type: ignore` (RULE-23).

**Slice 3 — Artifacts, CLI, rating template, diff.**
Files: `scripts/evals/beta_reader_artifacts.py` (in-memory render → atomic
writes; manifest; `summary.md`; `rating.md` template; secret sweep),
`scripts/evals/beta_reader_eval.py` (argparse wiring, all flags incl.
`--diff`), `.gitignore` (+`scripts/evals/runs/`), tests:
`test_beta_reader_artifacts.py` (no partial tree on render error; sweep blocks
a planted key; id collision fails loudly), `test_beta_reader_eval_cli.py`
(parse-level + dry-run end-to-end with TestModel seam).
Gate: full `just verify` green; manual PO-approved smoke: `--dry-run`, then
one real chapter against `config.local.yaml`.

## 10. RULE-XX Validation (constraint check)

- **RULE-01b** — no LLM client imports in the eval; models come exclusively
  from `ModelRegistry` (prepare path). ✔
- **RULE-02/02a/02b** — the eval builds zero prompt strings; system prompts
  via `PromptComposer`, user prompts via the real builders
  (`build_budgeted_prompt` / `build_deepdive_prompt`). ✔
- **RULE-03** — typed contracts (pydantic models) land in Slice 1/2 before CLI
  wiring in Slice 3. ✔
- **RULE-04** — one responsibility per module: corpus_source / runner /
  scoring / artifacts / cli. ✔
- **RULE-06** — N/A (no router). ✔
- **RULE-11** — harness failures raise/log (exit 1), never silently swallowed;
  Layer-1 violations are reported, not hidden. ✔
- **RULE-23** — zero type-ignore suppressions in new files. ✔
- **Sustainability (3-month):** instrument survives as long as the
  header-governance program runs; module structure hosts further analysis
  modes without structural change, while v1 scope stays beta_reader-only
  (scope discipline). Boundary stays one-way (`scripts/evals/` → core/api
  imports; benchmark/evals consumed as assets only). ✔

## 11. Open Points (explicitly undecided)

1. `zai_endpoint=coding` unsupported in v1 (hard error); support = pass the
   coding URL as `base_url` — backlog.
2. KB-channel fidelity (kb envelopes, previous-chapter summaries): out of
   scope v1, recorded per-run in `manifest.known_gaps`; revisit if
   header-governance findings implicate the context channels.
3. Model-window-aware budget assembler (ADR-082 cascade) replaced by the
   32k default — immaterial at chapter scale; revisit for multi-chapter
   analysis cases.
4. `prompt_version` extraction: read template frontmatter if
   `ComposedPrompt` does not expose it; bundled templates are authoritative
   in the eval (no DB overrides).
5. Cross-instrument corpus-manifest schema governance (one validator for
   benchmark + eval readers) — deferred; two readers with overlapping field
   checks accepted for now (eval reader is the genre owner).
6. Variance probing (N runs per case) — manual re-runs in v1; batching only
   on demonstrated need.

## 12. Design History (rejected alternatives — honest record)

- **(A) Extend `analysis_probes.py`** — rejected (PO): probes assert pipeline
  mechanics (`evidence_recorded`, fixture sentences, stub prompt); they cannot
  express chapter-scale output quality without becoming a different instrument
  inside a CI-facing evidence tool.
- **(C) No vehicle** — rejected (PO): the largest prompt delta in the program
  would ship unmeasured.
- **LLM-judge layer** — rejected for v1 (§5; PO ruling 4).
- **`benchmark/evals/` home** — rejected (§3, ADR-083 charter).
- **`evals/` (ADR-032) home** — rejected (§3, harness/shape mismatch).
- **API-stack-driven eval** — rejected (§4): measures an unchanged surface at
  stack cost; production-surface measurement belongs to the benchmark program.
