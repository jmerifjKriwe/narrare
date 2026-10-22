# E2E Spec: Analysis (`test_analysis.py` + `_streams`/`_voice` splits) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the ANALYSIS spec batch of the Phase-B E2E program — `test_analysis.py` (ANAL-001 beta reader incl. the N13 min-words boundary, ANAL-002 sentiment, ANAL-003 readability incl. the N12 honest-skip, ANAL-004 POV incl. the B07 fixed-behavior pin), `test_analysis_streams.py` (ANAL-005 coreference, ANAL-008 character voices incl. the N11 roster pin, and the CONS-001/ADR-044 stream content assertions promised by the KB wave), and `test_analysis_voice.py` (ANAL-007 author voice, ANAL-009 voice drift, voice check, author drift) — with six just-in-time fix slices landing first (PO fixes-first pattern): the **N12 readability KB-context supply** (the AI sentence phase has NEVER run — verified red in-tree this session), the **N13 word-count 422 mapping**, the **E03 spaCy-absent graceful degradation (503 machine-readable)**, the **N11 roster-gated speaker attribution** in two Backend slices, and the **M05-class i18n-first error rendering** for the seven analysis panels this wave specs.

**Architecture:** Three-layer delivery, same shape as the ai-writing and KB waves: (1) fix slices — five Backend (N12 mirrors the landed B07 POV `kb_context_provider` pattern in `ReadabilityService` + `get_readability_service`; N13 re-bases the two word-count errors on the core `ValidationError` so the existing app-level NarrareError handler answers 422 machine-readable; E03 wraps the bare `import spacy` into `NLPProviderError` plus a dedicated 503 handler; N11 adds a pure-core roster filter + wiring into the three voice services, split into two tasks for the 3-file cap) and one Frontend (M05: render `tStudio(error.i18nKey)` instead of the hardcoded-German `error.userMessage` in exactly the seven analysis panels this wave drives through error paths — ChatPanel, DialogueCoachPanel and kb/ConsistencyCheckPanel stay the M05 wave's, per the KB-wave closing note); (2) catalog growth: `pov` happy+error (JSON capability — the B07-fixed panel's deterministic content); (3) the specs in three files (RULE-04 ≤ 400 lines each) plus one new helper module `helpers/analysis_world.py`. Mocking follows the established two-layer split: REAL backend under TestModel for the tolerance-loose surfaces the audit verified working (readability, POV, author voice, author drift, voice drift, voice check, sentiment-when-models-present) and the landed browser-layer catalog for the validator-strict surfaces (beta reader, coreference, character voices, consistency stream) plus the POV panel-content leg; every gate that was FIXED gets a green pin against the real path — no xfail anywhere in this batch.

**Tech Stack:** Python 3.14 · pytest + pytest-playwright (sync API, marker `e2e`) · FastAPI/SQLAlchemy async (error mapping, KB wiring) · React 19 + Vitest (M05 panel slice) · pydantic-ai TestModel (factory layer) · page.route() browser-layer catalog.

**Inputs:**
- Spec: `docs/superpowers/specs/2026-10-11-e2e-full-suite-design.md` — §5 row `test_analysis.py` (features ANAL-001..005/007/008/009; gates B07 E03 N11 N12 N13; scope "per-analyzer happy path via mocks; beta-reader min-words boundary; readability honest-skip pin; voice family panels"), §3 mock layers, §6 interleaving ("fixes zuerst"), §7 runtime budget, §8 E03 ("without `--extra nlp` the endpoint must answer 503/422 machine-readable, not 500"), §10 catalog ratchet + skipif discipline.
- Audit: `docs/superpowers/reports/2026-10-11-e2e-ui-audit.md` — B07 (fixed in the blocker wave — pin the fixed behavior), E03, N11 (garbage-token speakers + heatmap list fallback), N12, N13, M05-class German fallbacks (analysis panels), E04 (TestModel insufficient for coreference/character-voices → catalog), "Verified WORKING" list (readability, author voice, author drift, check voice, chat-class SSE).
- Landed assets: `tests/e2e/foundation.py` (`stable_user`/`module_stable_user`/`stable_novel`, `make_authed_request`, `NovelContext`), `tests/e2e/helpers/` (`editor_ai`, `kb_world` incl. `seed_kb_entity`/`open_worldbuilding`/`track_posts`/`capture_json_response`, `llm_mocks.mock_llm`, `probes`, `novel_factory`), `tests/e2e/mocks/catalog_analysis.py` (`beta_reader` happy, `coreference_stream` happy+error, `character_voice_stream` happy+error, `consistency_stream` happy+error, `consistency_check`), `scripts/run_e2e.sh` (incl. `NARRARE_RATE_LIMIT_WS=100`, `NARRARE_RATE_LIMIT_ANALYSIS=100`), the :3001 live-stack recipe (testing-standards § E2E).
- Prior plans (same discipline): `docs/superpowers/plans/2026-10-12-e2e-blocker-fixes.md` (B07 fix = the POV kb-supply this wave's N12 fix mirrors), `2026-10-12-e2e-suite-foundation.md`, `2026-10-13-e2e-spec-ai-writing.md` (M06 honest-error precedent), `2026-10-15-e2e-spec-kb.md`.

## Decisions log

- **D-2026-10-18-1 — N12 verified REAL and FIXED in-plan (Backend, Task 1).** In-tree probe this session (real `PromptComposer(PromptRegistry())`, `mode="readability"`, bare context): `PromptVariableError: Missing required prompt variable 'kb_characters' in analysis/en/readability`. The readability template requires the four `kb_*` slots (`packages/core/narrare_core/prompts/_bundled/analysis/en/readability/system.md` lines 53–56 — same slots as pov/coreference), but `ReadabilityService` composes with NO `extra` and has no `kb_context_provider` (constructor verified: chapter_repo, novel_repo, model_registry, model_resolution, composer, invocation_pipeline, run_limit_resolver). The pipeline fallback in `compose_analysis_invocation_prompt` also raises (`AnalysisError`), and `_analyze_chapter`'s `except Exception: graceful degradation` swallows it — so the AI sentence phase has NEVER executed and the UI honestly renders its metrics with the dishonest "No problematic sentences detected!" claim (audit N12). Fix: exactly the landed B07 POV shape — `kb_context_provider: KBContextProviderProtocol | None = None` param, `KBContextBundle.empty(...)` degradation when `None`, `extra=kb_vars` on the compose call (`pov_service.py:169-193` is the reference implementation), wired in `get_readability_service` mirroring `get_pov_service`'s `KBContextProvider(kb_repo=…, relationship_repo=…)` (`dependencies.py:177-180`). The graceful-degradation `except` STAYS — it is the designed RULE-11 seam for genuine agent failures — and gets its own regression pin (agent failure → 200 + deterministic metrics + empty `sentence_analyses`). The "2-line compose-extra" framing from the blocker wave undercounts the wiring (the service lacks the provider entirely); the honest fix is provider + wiring + extra, still one small task.
- **D-2026-10-18-2 — N13 fixed as a domain-error re-base (Backend, Task 2), no handler changes.** Root cause (verified in-tree): `InsufficientWordCountError`/`ExcessiveWordCountError` inherit `AnalysisError(Exception)` — plain exceptions with no app-level handler, so the beta-reader business rule escapes as a generic 500 with only an `unhandled_exception` log (`_app/main.py:215`). The app already maps the CORE `ValidationError` (a `NarrareError`) to HTTP 422 `{"detail", "code"}` (`main.py:104-105,118-121`) — the M06 `EMPTY_DRAFT` precedent. Fix: re-base the two word-count errors on `narrare_core.shared.errors.ValidationError` with explicit codes `WORD_COUNT_BELOW_MINIMUM` / `WORD_COUNT_ABOVE_MAXIMUM` (~10 LOC in `analysis/errors.py`). No `except AnalysisError` clause anywhere catches these two today (grep-verified; the service raises them straight through; the existing `pytest.raises(InsufficientWordCountError)` unit tests keep passing — class identity unchanged). The rest of the `AnalysisError` hierarchy stays `Exception`-based (changing all of it would be a broad behavioral change beyond the audit finding). FE i18n mapping for the 422 body is deliberately NOT in this slice — the panel already renders an error state; a dedicated `betaReader.tooShort` key is M05-wave polish (documented follow-on).
- **D-2026-10-18-3 — E03: graceful degradation FIXED (Backend, Task 3); E2E pins the happy path skipif-guarded; degradation pinned at integration level.** Two defects verified in-tree: (a) `SpacyNLPProvider._get_model` does a bare `import spacy` (`provider_spacy.py:107`) — with the package absent this raises `ModuleNotFoundError`, which is NOT a `NarrareError`, so it escapes the domain handler entirely → raw 500 (the audit's exact repro); (b) even the wrapped path (`OSError` on missing model) yields `NLPProviderError` → generic `NarrareError` mapping → HTTP 400, not the spec §8 "503/422 machine-readable" (this machine's venv: spacy 3.8.13 installed, all three `_MODEL_MAP` models MISSING — so today the local answer is 400, the audit env's was 500; both are wrong per §8). Fix: wrap the import → `NLPProviderError` with install instructions; register a dedicated `NLPProviderError` handler → **503** `{"detail", "code": "NLP_NOT_CONFIGURED"}` (503 over 422: the capability is not configured in this deployment — the request is valid, retrying unchanged cannot succeed; mirrors the `ExportFormatUnavailableError` 503 precedent, `main.py:166`). **E2E stance:** CI's `test-e2e` job installs `--extra nlp` AND the three models (`uv sync … --extra nlp` + the W3-2 model cache, `.github/workflows/ci.yml:1538-1585`), so the nightly suite runs sentiment fully; a bare local venv does not (verified: `en_core_web_md` missing). The sentiment happy-path spec therefore carries `pytest.mark.skipif(not sentiment_models_available(), reason=…)` per spec §10 (documented rationale: run `just install-nlp-models`; the recipe note lands in Task 11), and the 503 degradation contract is pinned deterministically at integration level (dependency-override raising `NLPProviderError` — runs in every environment). Installing the models into the runner's venv from the plan was rejected: it mutates the developer environment and hides the exact degradation the gate exists to pin.
- **D-2026-10-18-4 — N11 root cause verified; roster-gated attribution (Backend, Tasks 4–5).** Why garbage "characters" (In, Order, About, Ahead)? `DialogueParser._action_beat_speaker` attributes a quote to the LAST capitalized token in the preceding clause at MEDIUM confidence, and `_NON_NAMES` (`dialogue_parser.py:105-181`) is a finite pronoun/article/weekday list — ordinary sentence-initial words pass as "names". Why do they reach the UI as characters? Nothing downstream checks speaker names against the novel's KB — the only SSOT for who IS a character: `collect_speakers` unions raw parser speakers into the drift character set (each garbage name surfacing as a `no_stored_profile` card — also why the drift "heatmap" degenerates into a garbage list), and character-voice/check profile every metrics key. Core-only tightening (extending `_NON_NAMES`) is whack-a-mole with no honest terminating condition — rejected. Fix: a pure-core helper `restrict_speakers_to_roster(utterances, roster)` (+ name-set form) in `dialogue_parser.py` that demotes any attribution whose speaker is not in the KB roster to `speaker=None` / `CONFIDENCE_LOW` — exactly ADR-055 Decision 3's designed degradation (unattributed quotes are left for the agent, rendered `?` in the agent prompt). Roster semantics: **empty roster → no-op** (a KB-less novel has no SSOT to gate against; current behavior preserved — honest degradation, no regression); non-empty roster → case-insensitive membership. Data-safety check: `persist_voice_analysis` only writes to EXISTING character entries (returns `None` otherwise — verified `character_voice_kb_writer.py:90-92`), so garbage never polluted the KB; the defect is UI-facing only. Split into Task 4 (core helper + `character_roster.py` + character-voice wiring — 3 product files) and Task 5 (voice drift + voice check + their dependency factories — 4 product files, ~24 LOC; cap deviation flagged in OPEN QUESTION 2) so each task stays reviewable and the cap deviation is confined to one task.
- **D-2026-10-18-5 — M05-class slice scoped to THIS wave's seven analysis panels (Frontend, Task 6); the rest stays M05-wave.** Root cause (verified): `AI_ERROR_MESSAGE_MAP`'s `userMessage` is by construction the hardcoded German `.de` string, and seven analysis panels render `error?.userMessage` directly — `CoreferencePanel.tsx:142`, `VoiceCheckPanel.tsx:138`, `VoiceDriftPanel.tsx:152`, `CharacterVoicePanel.tsx:139`, `AuthorVoicePanel.tsx:164`, `AuthorVoiceDriftPanel.tsx:154`, `ConsistencyPanel.tsx:121` (analysis-side) — so the EN UI shows German on every stream-death/error path this wave's specs drive (audit M05 class; the catalog error variants would otherwise force the specs to pin German text — dishonest). Fix = the landed M06 `GenerationPanel` precedent: render `tStudio(error.i18nKey ?? "aiActions.errorDefault")` (the panels' `t` is namespace `analysis`; `aiActions.*` lives in `studio.json`, hence a second `useTranslations("studio")` hook — `ConsistencyPanel` already has `tStudio`). Deliberately NOT in this slice: `ChatPanel`, `DialogueCoachPanel` (German-first `userMessage ?? t(…)`), `kb/ConsistencyCheckPanel`, settings/learning panels — the M05 wave's `test_settings_auth.py` slice per the coverage matrix and the KB-wave closing note; the systemic mapper cleanup (dropping `userMessage` entirely) also stays M05-wave. Task 6 carries 7 product files × ~2 LOC — over the 3-file cap, flagged in OPEN QUESTION 1 (recommendation: fold, per the D-5 one-task-one-session precedent; if declined, split 3+3+1 mechanically).
- **D-2026-10-18-6 — One plan, not two; spec files split per RULE-04.** The gates interleave with the specs (fixes zuerst: N12→readability spec, N13→beta-reader boundary, N11→voice pins, M05→error-path pins, E03→sentiment stance), so splitting fix-wave from spec-wave would strand gated specs from their gates (spec §6). Honest sizing needs three spec files: `test_analysis.py` (JSON analyzers: beta reader, sentiment, readability, POV), `test_analysis_streams.py` (SSE: coreference, character voices, consistency stream), `test_analysis_voice.py` (voice family panels: author voice, author drift, voice drift, voice check) — the same RULE-04 split the ai-writing wave made for its single §5 row.
- **D-2026-10-18-7 — Per-surface mock strategy (spec §3, audit E04).** REAL backend under TestModel (factory layer) for: readability (deterministic metrics; the AI phase now composes — Task 1 — and `readability_types.py` carries no output validators, unlike beta reader), POV (B07 fixed; the pin is "200 + result shape", not content), author voice / author drift / voice check / voice drift (audit "Verified WORKING" under TestModel; drift's deterministic prefix — progress + no_profile events — is fully assertable, the agent-dependent classification is asserted structurally). Browser-layer catalog (validator-strict, E04): `beta_reader` happy (landed), `coreference_stream` happy+error (landed), `character_voice_stream` happy+error (landed), `consistency_stream` happy+error (landed — the KB wave's promised ADR-044 stream content assertions land in Task 9), plus NEW `pov` happy+error (Task 7) so the POV panel leg has deterministic content independent of TestModel's output shape. The N11 pins run on the REAL streams (the garbage filtering happens in the deterministic prefix — the `progress` event text "Profiling 1 character(s)" is emitted BEFORE any agent call, so the pin is immune to TestModel strictness). Voice-drift full-result chain: character-voice cannot seed stored profiles under TestModel (stream death precedes persistence), so the drift spec seeds `speech.voice_analysis` directly through the KB PATCH API (`KBEntryUpdate.metadata` — verified in-tree) — the same real-API seeding discipline as the KB wave's D-8.
- **D-2026-10-18-8 — Runtime budget ≤ 7 min added (PROPOSAL — PO confirmation requested, D-9 precedent).** Per-file guidance on `E2E_FRONTEND_MODE=dev`: `test_analysis.py` ≤ 2.5 min (four analyzers, one module user + wizard novel), `test_analysis_streams.py` ≤ 2.5 min (three SSE surfaces), `test_analysis_voice.py` ≤ 2 min (four panels sharing one module novel + profile seeding); each test ≤ 90 s; the runner's `--timeout=300` stays the hard stop. Task 11 records measured actuals. Given the two prior batches measured 53 s and ~2.5 min against 6 and 11 min budgets, 7 min is comfortably safe; the PO confirms (or trims) with the plan review.

## Global Constraints

- **Project language is English** — code, comments, tests, commit messages, docs (exception: `packages/i18n` message files).
- **`docs/_shared/CONSTRAINTS.md` is the constitution** — load it before starting. Most relevant here: RULE-02/02a (prompts only via PromptComposer — Task 1 fixes a governed-route variable-supply gap, it does not add prompts), RULE-04 (test files and helpers ≤ 400 lines; hence the three-file spec split), RULE-06 (one responsibility per file), RULE-08 (`provider_spacy.py` is the ONLY place `import spacy` is permitted — Task 3 edits inside it), RULE-10 (tests mandatory), RULE-11 (no silent failures — Task 1 keeps the logged degradation seam and adds the red test proving the compose now succeeds; N11 demotions are the designed ADR-055 handoff, logged), RULE-16 (i18n keys en/de/fr parity in the same commit — Task 6 adds NO keys: `aiActions.*` already ships in all three locales), RULE-17 (FE types mirror BE schemas — no wire changes in this batch), RULE-23 (no naked `# type: ignore`).
- **Regression-first:** every fix task writes the failing test FIRST, runs it, and records the red-phase output (command + observed failure) in the task report. A fix without red evidence is not done.
- **Task cap:** ≤ 3 product-implementation files and ≤ 250 new product LOC per task. Spec/helper/test files are the deliverable of Tasks 7–10 and are **exempt** per the PO ruling on suite slices. Tasks 1–5 are product fixes and count normally; Task 5 carries 4 product files (~24 LOC) and Task 6 carries 7 product files (~15 LOC) — both flagged for the PO's fold ruling (OPEN QUESTION 1 and 2); every other task stays within caps.
- **Layer tags** (first line of each task) route via the coordinator: `Backend` → NarrareBackendSpecialist, `Frontend` → NarrareFrontendSpecialist, `Platform` → NarrarePlatformSpecialist, `Docs` → NarrareDocsSpecialist. "Fixes zuerst": product fixes (Tasks 1–6) land BEFORE the specs that depend on them; execution order is 1 → 11, Docs last.
- **No product changes inside spec tasks.** If a spec task finds a NEW product defect (beyond Tasks 1–6's ruled fixes), it writes the red pin (`xfail(strict=True)` documentation form per spec §5), stops, and routes the fix to the coordinator — never patches product code in a Platform task.
- **Conventional commits** (`fix(analysis): …`, `fix(core): …`, `fix(web): …`, `test(e2e): …`, `docs(testing): …`). **`git commit --no-verify` is FORBIDDEN.** Implementing sessions commit; pushes/tags go through NarrarePlatformSpecialist.
- **No real LLM calls, ever** (spec §3): factory layer (`NARRARE_E2E_TEST=1` → TestModel) for everything not intercepted; browser-layer catalog ONLY where deterministic content is asserted (`beta_reader`, `coreference_stream`, `character_voice_stream`, `consistency_stream`, new `pov`). Sentiment is NOT an LLM surface (ADR-021 deterministic) — it runs REAL, gated on model presence (D-3).
- **Test commands:**
  - Python unit: `uv run --all-packages pytest tests/unit/api/analysis tests/unit/core/analysis tests/unit/core/nlp -v -p no:randomly` (Task 1 also runs `tests/unit/api/kb/test_consistency_analyzer.py`-style real-composer checks inside its own new file).
  - Python integration (fix tasks): `uv run --all-packages pytest tests/integration/analysis -v -p no:randomly` (requires `just dev-services`, postgres_test on :5433).
  - Web unit: `pnpm --filter narrare-web exec vitest run components/studio/analysis`; Web typecheck: `pnpm --filter narrare-web run type-check`.
  - Catalog/unit: `uv run --all-packages pytest tests/unit/test_e2e_mock_catalog.py -v -p no:randomly`.
  - Full E2E (CI-faithful): `just e2e`; subsets: `E2E_PYTEST_ARGS="tests/e2e/test_analysis.py" just e2e` etc.
- **Live-stack verification (manual spot-check, fix tasks):** the :3001 recipe from `docs/development/testing-standards.md` § E2E: API on :8000 with `ENVIRONMENT=test NARRARE_E2E_TEST=1 SECRET_KEY=test-secret-key-not-for-production AUTH_JWT_SECRET=test-secret-key-not-for-production NARRARE_CSRF_TRUSTED_ORIGINS='["http://localhost:3001"]'` against `narrare_test` on :5433; web via `pnpm dev --port 3001` with `AUTH_JWT_SECRET` exported (E01). For sentiment happy-path spot-checks only: `just install-nlp-models` first (Task 3/11 notes).
- **Runtime budget (spec §7):** full-suite target stays **≤ 25 min**. This batch's proposal: **≤ 7 min added** on `E2E_FRONTEND_MODE=dev` (D-8, PO confirmation requested); Task 11 records measured actuals in `docs/development/e2e-coverage.md`.
- **Markers:** every test carries `@pytest.mark.e2e` (the runner selects `-m e2e`). **No new custom markers** (spec §7 default: single suite). The sentiment happy-path specs carry the spec §10-sanctioned `skipif` with documented rationale (D-3).
- **Catalog contract (spec §10):** new entries = fixture constant + `RouteSpec` + module `validate()` case + unit-test extension, in the same commit. The new `pov` entries are a JSON capability shipping happy+error (the POV panel spec asserts the panel's error branch via the error variant).
- Line numbers quoted from source may be stale — each task re-verifies by semantic location before editing.

## Gate → Task map (fixes first — PO ruling "fixes zuerst")

| Task | Layer | Gate | Deliverable |
|------|-------|------|-------------|
| 1 | Backend | N12 (D-1) | `ReadabilityService` kb-supply (B07 POV pattern) + real-composer red test + graceful-skip pin |
| 2 | Backend | N13 (D-2) | Word-count errors re-based on core `ValidationError` → 422 machine-readable |
| 3 | Backend | E03 (D-3) | `import spacy` wrapped → `NLPProviderError`; dedicated 503 `NLP_NOT_CONFIGURED` handler |
| 4 | Backend | N11 (D-4, half 1) | Core `restrict_speakers_to_roster` + `character_roster.py` + character-voice wiring |
| 5 | Backend | N11 (D-4, half 2) | Voice-drift + voice-check roster wiring (+ dependency factories) — 4-file fold flagged |
| 6 | Frontend | M05-class (D-5) | i18n-first error rendering in the 7 analysis panels — 7-file fold flagged |
| 7 | Platform | catalog prep | `pov` happy+error catalog entries (validated against `POVResult`) |
| 8 | Platform | B07 E03 N12 N13 pins | `helpers/analysis_world.py` + `test_analysis.py` — beta reader (+boundary), sentiment, readability, POV |
| 9 | Platform | N11 pin (streams), CONS-001 | `test_analysis_streams.py` — coreference, character voices, consistency stream content |
| 10 | Platform | N11 pin (panels), ANAL-007/009 | `test_analysis_voice.py` — author voice, author drift, voice drift, voice check |
| 11 | Docs | spec §9 | `e2e-coverage.md` statuses + budget actuals + sentiment-models note in testing-standards |

---

### Task 1: Readability KB-context supply (N12, Backend)

**Layer:** Backend · **Gate:** N12 (audit: "Readability: LLM sentence analysis silently skipped → UI claims 'No problematic sentences detected!'"). Fix lands BEFORE the readability spec (Task 8). Root cause verified red in-tree this session (D-1): `PromptVariableError: Missing required prompt variable 'kb_characters' in analysis/en/readability`.

**Files:**
- Modify: `apps/api/narrare/analysis/services/readability_service.py` (constructor + `_analyze_chapter` compose call)
- Modify: `apps/api/narrare/analysis/dependencies.py:70-123` (`get_readability_service` wiring)
- Test: `tests/unit/api/analysis/test_readability_kb_supply.py` (create)

**Interfaces:**
- Produces: `ReadabilityService(..., kb_context_provider: KBContextProviderProtocol | None = None)` — additive, default `None` (all existing constructions keep working; `None` degrades to empty kb slots, which now COMPOSE successfully — the pre-fix behavior of never composing is the bug). The readability AI phase runs whenever the routing cascade resolves; the graceful-degradation `except` stays for genuine agent failures.
- Consumes: `KBContextProvider` from `narrare.kb._context_provider` + `KBContextBundle`/`RenderOptions` (the exact `pov_service.py:169-193` shape), `StaticModelResolution` (test), real `PromptComposer(PromptRegistry())`.

**Root cause (2× why):**
- Why does the UI claim "No problematic sentences detected!" for text that has plenty? The AI sentence phase never ran: the readability template requires `{{kb_characters}}`…`{{kb_relationships}}` (lines 53–56 of the bundled template) but the service composes with no `extra`, so both the pipeline compose and its direct fallback raise, and `_analyze_chapter`'s `except Exception` swallows the failure into metrics-only output.
- Why was it never caught? The graceful-degradation seam is legitimate and unit-tested with FakeComposer/agent failures; the REAL composer path was never exercised — the same "real composition path unexercised" family as the KB wave's D-1 CONS-001 hazard and the blocker wave's B07.

**Alternatives considered:**
1. Mirror the landed B07 POV kb-supply (chosen) — identical bug family, identical fix shape (`kb_context_provider` + `extra=kb_vars`); the governed template stays untouched; ~25 LOC + wiring.
2. Declare the four kb slots `optional_variables` for the readability route — renders them permanently empty (the pov fix's rejected alternative, blocker-plan line 390): the prompt loses KB context it was designed to carry, and it papers over the service-side supply gap for every future ANALYSE mode. Rejected.
3. Ship a readability template variant without kb slots — forks the governed prompt surface for a service-side bug; rejected (RULE-02 governance).

- [ ] **Step 1: Write the failing test**

Create `tests/unit/api/analysis/test_readability_kb_supply.py`:

```python
"""N12 regression: the readability AI phase must actually RUN.

Audit N12: the readability template requires the four ``kb_*`` slots, but
``ReadabilityService`` composed with no ``extra`` — ``composer.build``
raised ``PromptVariableError: Missing required prompt variable
'kb_characters' in analysis/en/readability`` on EVERY call (verified
in-tree 2026-10-18), the service's graceful-degradation ``except``
swallowed it, and the UI claimed "No problematic sentences detected!".
The fix mirrors the landed B07 POV kb-supply (kb_context_provider +
extra=kb_vars); ``kb_context_provider=None`` degrades to EMPTY slots,
which compose successfully.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest
from unittest.mock import MagicMock

from narrare._app.dependencies_services import StaticModelResolution
from narrare.analysis.services.readability_service import ReadabilityService
from narrare_core.llm.model_routing import ResolvedModel, ResolvedModelConfig
from narrare_core.prompts.composer import PromptComposer
from narrare_core.prompts.registry import PromptRegistry

_CHAPTER_TEXT = (
    "Elara waited by the gate. The bells rang twice, and she counted "
    "them the way her mother had taught her, waiting for the third."
)


class _FakeChapterRepo:
    def __init__(self, content: str) -> None:
        self._content = content

    async def get_by_id(self, chapter_id, novel_id):
        return SimpleNamespace(id=chapter_id, novel_id=novel_id, content=self._content)


class _FakeNovelRepo:
    async def get_by_id(self, novel_id, user_id):
        return SimpleNamespace(id=novel_id, writing_language="en", title="Gate")


class _FakePrepared:
    model = object()
    model_settings = None
    usage_limits = None


class _FakeRegistry:
    def __init__(self) -> None:
        self.prepare_calls = 0

    async def prepare(self, *args, **kwargs):
        self.prepare_calls += 1
        return _FakePrepared()


def _build_service(monkeypatch, agent_run) -> tuple[ReadabilityService, list]:
    """ReadabilityService on the REAL composer with a stubbed ReadabilityAgent.

    ``_prepare_agent`` imports ``ReadabilityAgent`` at call time from
    ``narrare_core.agents.readability_agent``, so monkeypatching the module
    attribute intercepts construction. Returns (service, agent_instances).
    """
    import narrare_core.agents.readability_agent as ra_module

    instances: list = []

    class _FakeAgent:
        def __init__(self, *, model, system_prompt=None):
            instances.append(self)
            self.system_prompt = system_prompt

        async def run(self, **kwargs):
            return await agent_run(**kwargs)

    monkeypatch.setattr(ra_module, "ReadabilityAgent", _FakeAgent)

    registry = _FakeRegistry()
    service = ReadabilityService(
        chapter_repo=_FakeChapterRepo(_CHAPTER_TEXT),
        novel_repo=_FakeNovelRepo(),
        model_registry=cast("ModelRegistry", registry),  # type: ignore[name-defined]
        model_resolution=StaticModelResolution(
            ResolvedModel(config=cast("ResolvedModelConfig", MagicMock(spec=ResolvedModelConfig)))
        ),
        composer=PromptComposer(PromptRegistry()),
    )
    return service, instances


class TestReadabilityKBSupply:
    @pytest.mark.asyncio
    async def test_ai_phase_composes_and_runs_the_agent(self, monkeypatch) -> None:
        """RED pre-fix: the compose fails before the agent is ever built."""

        async def agent_run(**kwargs):
            return SimpleNamespace(sentence_analyses=[], overall_assessment="ok")

        service, instances = _build_service(monkeypatch, agent_run)

        results = await service.analyze(
            novel_id=uuid4(), chapter_ids=[uuid4()], user_id=uuid4(), language="en"
        )

        assert len(results) == 1
        assert results[0].metrics.flesch_reading_ease is not None
        # The N12 pin: the AI phase was REACHED (compose succeeded).
        assert len(instances) == 1
        assert instances[0].system_prompt  # the governed template rendered

    @pytest.mark.asyncio
    async def test_agent_failure_degrades_to_deterministic_metrics(self, monkeypatch) -> None:
        """The RULE-11 seam stays: agent failure → 200-shape, metrics only."""

        async def agent_run(**kwargs):
            raise RuntimeError("agent down (E04-class failure)")

        service, instances = _build_service(monkeypatch, agent_run)

        results = await service.analyze(
            novel_id=uuid4(), chapter_ids=[uuid4()], user_id=uuid4(), language="en"
        )

        assert len(instances) == 1  # the agent was reached, then failed
        assert len(results) == 1
        assert results[0].metrics.sentence_count >= 1
        assert results[0].sentence_analyses == []
```

Calibration: if `merge_agent_result` (in `analysis/services/_readability_helpers.py`) requires a typed `ReadabilityAgentOutput` rather than the duck-typed `SimpleNamespace`, construct the real output model in `agent_run` (read the helper first and mirror its attribute access; the assertion target is the agent being REACHED, not the merge).

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run --all-packages pytest tests/unit/api/analysis/test_readability_kb_supply.py -v -p no:randomly`
Expected: FAIL — `test_ai_phase_composes_and_runs_the_agent`: `assert len(instances) == 1` fails with 0 (the compose raised `PromptVariableError` → `AnalysisError` → swallowed; no agent built). `test_agent_failure_degrades…` also fails with `instances == 0` pre-fix. Record both outputs.

- [ ] **Step 3: Implement the kb-supply (B07 POV pattern)**

In `apps/api/narrare/analysis/services/readability_service.py`:

1. Extend the `TYPE_CHECKING` imports with `from narrare.kb.context_contracts import KBContextProviderProtocol`.
2. Add the constructor parameter (after `composer`) and store it:

```python
        kb_context_provider: KBContextProviderProtocol | None = None,
```

```python
        self._kb_context_provider = kb_context_provider
```

3. In `_analyze_chapter`, between the content check and the compose call, add (mirroring `pov_service.py:169-181`):

```python
                # KB-context variables for the readability template's
                # {{kb_*}} slots (audit N12): canonical provider (ADR-067),
                # the same SSOT supply the POV fix (audit B07) uses. ``None``
                # provider degrades to empty slots (RULE-11); without this
                # supply the compose ALWAYS failed and the AI phase was
                # silently skipped (the "No problematic sentences detected!"
                # dishonesty).
                from narrare_core.context._render_options import RenderOptions

                if self._kb_context_provider is None:
                    from narrare.kb.context_contracts import KBContextBundle

                    kb_bundle = KBContextBundle.empty(
                        RenderOptions(annotate_provenance=True)
                    )
                else:
                    kb_bundle = await self._kb_context_provider.fetch_context(
                        novel_id,
                        entity_types=["character", "location", "faction"],
                        options=RenderOptions(annotate_provenance=True),
                    )
                kb_vars = kb_bundle.to_prompt_variables()
```

4. Pass the variables to the compose call: add `extra=kb_vars,` to the `compose_analysis_invocation_prompt(...)` invocation (after `mode="readability",`).

In `apps/api/narrare/analysis/dependencies.py`, `get_readability_service` (lines ~70-123): mirror the POV wiring — add to the local imports (`narrare.kb._context_provider.KBContextProvider`, `narrare.kb.relationship_repository.RelationshipRepository`, `narrare.kb.repository.KBRepository`), construct before the return:

```python
    # Canonical KB-context provider (ADR-067) — the same supply get_pov_service
    # wires (audit B07); readability's template carries the same kb_* slots
    # (audit N12).
    kb_context_provider = KBContextProvider(
        kb_repo=KBRepository(session),
        relationship_repo=RelationshipRepository(session),
    )
```

and pass `kb_context_provider=kb_context_provider,` in the `ReadabilityService(...)` construction.

- [ ] **Step 4: Run the tests to verify green**

Run: `uv run --all-packages pytest tests/unit/api/analysis/test_readability_kb_supply.py tests/unit/api/analysis -v -p no:randomly && uv run --all-packages pytest tests/integration/analysis/test_readability_api.py -v -p no:randomly`
Expected: ALL PASS (existing readability tests are FakeComposer/service-override based and unaffected; the integration route tests pin the response shape, which is unchanged).

- [ ] **Step 5: Live-stack spot-check (:3001 recipe)**

With the stack running: create a novel + one text chapter via the UI, then from the editor open the Readability panel and run it. Expected: the panel renders metric cards AND the AI sentence section (post-fix the agent runs under TestModel; with no problematic sentences synthesized the section may legitimately be empty — the wire proof is the log: `grep readability_agent_failed` must show NO `PromptVariableError`/composition failure for the run, and the API response's `sentence_analyses` key must be present). Cross-check with:

```bash
curl -s -X POST "http://localhost:8000/api/v1/analysis/readability?novel_id=<novel_id>" \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"chapter_ids": ["<chapter_id>"], "language": "en"}' | python3 -m json.tool | head -30
```

Expected: 200, `metrics` populated, and the API log free of `readability_agent_failed … PromptVariableError`. Record the exchange.

- [ ] **Step 6: Commit**

```bash
git add apps/api/narrare/analysis/services/readability_service.py apps/api/narrare/analysis/dependencies.py tests/unit/api/analysis/test_readability_kb_supply.py
git commit -m "fix(analysis): supply the kb_* prompt slots to the readability composer (N12 — the AI phase never ran)"
```

---

### Task 2: Word-count business rules → 422 machine-readable (N13, Backend)

**Layer:** Backend · **Gate:** N13 (audit: "Beta Reader min-1000-words business rule returned as generic 500"). Fix lands BEFORE the beta-reader boundary spec (Task 8).

**Files:**
- Modify: `apps/api/narrare/analysis/errors.py` (re-base two error classes)
- Test: `tests/unit/api/analysis/test_word_count_error_contract.py` (create)
- Test: `tests/integration/analysis/test_analysis_api.py` (append one class)

**Interfaces:**
- Produces: `InsufficientWordCountError` / `ExcessiveWordCountError` as `narrare_core.shared.errors.ValidationError` subclasses with `code="WORD_COUNT_BELOW_MINIMUM"` / `"WORD_COUNT_ABOVE_MAXIMUM"` → the existing app-level NarrareError handler answers **422** `{"detail": str, "code": …}` (main.py:104-121 — no handler changes). Task 8's E2E pins exactly `422` + `WORD_COUNT_BELOW_MINIMUM` on the real route.
- Consumes: nothing new (`validate_word_count` in `analysis/validation.py` raises these unchanged).

**Root cause (2× why):**
- Why does the min-words rule 500? The two word-count errors inherit `AnalysisError(Exception)`; no app-level exception handler knows that hierarchy, so Starlette's generic handler answers 500 with only an `unhandled_exception` log.
- Why were they not `NarrareError`s? The analysis error module predates the app-level domain-handler convention (`NarrareError` + status mapping); the M06 slice established the 422-with-`code` pattern for exactly this class of business rule (`EMPTY_DRAFT`).

**Alternatives considered:**
1. Re-base on core `ValidationError` with explicit codes (chosen) — reuses the existing 422 mapping (`main.py:104-105`), zero handler changes, machine-readable `code`, M06 precedent; ~10 LOC.
2. Dedicated `InsufficientWordCountError` handler — duplicates the ValidationError mapping for one error pair; more registration code for the same wire. Rejected.
3. Re-base ALL of `AnalysisError` on `NarrareError` — flips compose/agent failures from 500 to 400 everywhere in one wave; a broad behavioral change beyond the audit finding. Rejected (kept as an M05-wave candidate note).

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/api/analysis/test_word_count_error_contract.py`:

```python
"""N13 contract: word-count business rules are 422 domain errors.

The beta-reader min/max word-count rules previously escaped as generic
500s (plain ``Exception`` subclasses with no handler). As core
``ValidationError`` subclasses they ride the existing app-level mapping
to HTTP 422 ``{"detail", "code"}`` (audit N13, M06 EMPTY_DRAFT precedent).
"""

from __future__ import annotations

from narrare.analysis.errors import ExcessiveWordCountError, InsufficientWordCountError
from narrare.analysis.validation import validate_word_count
from narrare_core.shared.errors import ValidationError


def test_insufficient_word_count_is_a_422_domain_error() -> None:
    exc = InsufficientWordCountError(
        "Chapter is too short for meaningful analysis (412 words, minimum 1000)."
    )
    assert isinstance(exc, ValidationError)  # → app handler maps to 422
    assert exc.code == "WORD_COUNT_BELOW_MINIMUM"


def test_excessive_word_count_is_a_422_domain_error() -> None:
    exc = ExcessiveWordCountError("Selected chapters exceed the analysis limit.")
    assert isinstance(exc, ValidationError)
    assert exc.code == "WORD_COUNT_ABOVE_MAXIMUM"


def test_validate_word_count_raises_the_typed_error_below_minimum() -> None:
    try:
        validate_word_count(412)
    except InsufficientWordCountError as exc:
        assert "412" in str(exc)
        assert exc.code == "WORD_COUNT_BELOW_MINIMUM"
    else:
        raise AssertionError("validate_word_count(412) must raise")
```

Append to `tests/integration/analysis/test_analysis_api.py` (reusing the file's existing `client` / `auth_headers` fixtures and the `get_beta_reader_service` import; the stub raises through the REAL route so the app-level handler mapping is what's under test):

```python
class TestBetaReaderWordCountContract:
    """N13: the min-words business rule must answer 422 machine-readable."""

    async def test_below_minimum_answers_422_with_code(
        self, client: AsyncClient, auth_headers: dict[str, str], monkeypatch
    ) -> None:
        from narrare.analysis.errors import InsufficientWordCountError

        async def _raise(**kwargs):
            raise InsufficientWordCountError(
                "Chapter is too short for meaningful analysis "
                "(412 words, minimum 1000)."
            )

        service = MagicMock(spec=BetaReaderService)
        service.analyze = AsyncMock(side_effect=_raise)
        app_dependency = get_beta_reader_service
        client.app.dependency_overrides[app_dependency] = lambda: service
        try:
            resp = await client.post(
                "/api/v1/analysis/beta-reader",
                params={"novel_id": str(uuid4())},
                json={"chapter_ids": [str(uuid4())]},
                headers=auth_headers,
            )
        finally:
            client.app.dependency_overrides.pop(app_dependency, None)

        assert resp.status_code == 422, resp.text[:300]
        body = resp.json()
        assert body["code"] == "WORD_COUNT_BELOW_MINIMUM"
        assert "1000" in body["detail"]
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run --all-packages pytest tests/unit/api/analysis/test_word_count_error_contract.py tests/integration/analysis/test_analysis_api.py -v -p no:randomly`
Expected: FAIL — unit: `assert isinstance(exc, ValidationError)` is False (base is plain `AnalysisError`) and `exc.code is None`; integration: `assert 500 == 422` (the audit repro). Record both outputs.

- [ ] **Step 3: Implement the re-base**

In `apps/api/narrare/analysis/errors.py`, add the import and change the two bases:

```python
from narrare_core.shared.errors import ValidationError
```

```python
class InsufficientWordCountError(ValidationError):
    """Chapter is too short for meaningful analysis (< 1000 words).

    N13: re-based on the core ``ValidationError`` so the app-level domain
    handler answers 422 machine-readable instead of a generic 500 (the
    beta-reader min-words business rule; M06 ``EMPTY_DRAFT`` precedent).
    """

    def __init__(self, message: str) -> None:
        super().__init__(message, code="WORD_COUNT_BELOW_MINIMUM")


class ExcessiveWordCountError(ValidationError):
    """Chapter(s) exceed token limit for analysis (> 10000 words)."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="WORD_COUNT_ABOVE_MAXIMUM")
```

(`AnalysisError`, `ChapterNotFoundError`, `CacheRetrievalError` keep their current bases — D-2.)

- [ ] **Step 4: Run the tests to verify green**

Run: `uv run --all-packages pytest tests/unit/api/analysis tests/integration/analysis -v -p no:randomly`
Expected: ALL PASS (the pre-existing `pytest.raises(InsufficientWordCountError)` pins in `test_beta_reader_deepdive.py` are class-identity compatible).

- [ ] **Step 5: Live-stack spot-check (:3001 recipe)**

Create a novel + one SHORT chapter (~60 words) via the UI/API, then:

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST "http://localhost:8000/api/v1/analysis/beta-reader?novel_id=<novel_id>" \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"chapter_ids": ["<chapter_id>"]}'
```

Expected: `422` (pre-fix `500`), and the body carries `"code": "WORD_COUNT_BELOW_MINIMUM"`. Record both.

- [ ] **Step 6: Commit**

```bash
git add apps/api/narrare/analysis/errors.py tests/unit/api/analysis/test_word_count_error_contract.py tests/integration/analysis/test_analysis_api.py
git commit -m "fix(analysis): answer the beta-reader word-count rules as 422 machine-readable (N13)"
```

---

### Task 3: spaCy-absent graceful degradation — 503 NLP_NOT_CONFIGURED (E03, Backend)

**Layer:** Backend · **Gate:** E03 (audit: "Sentiment 500 `No module named 'spacy'` — product should degrade gracefully (503/422 machine-readable)"); spec §8. Fix lands BEFORE the sentiment spec (Task 8).

**Files:**
- Modify: `packages/core/narrare_core/nlp/provider_spacy.py:94-148` (`_get_model` import wrap)
- Modify: `apps/api/narrare/_app/main.py` (dedicated handler after the BudgetExceededError handler, ~line 212)
- Test: `tests/unit/core/nlp/test_provider_spacy_absent.py` (create)
- Test: `tests/integration/analysis/test_sentiment_degradation.py` (create)

**Interfaces:**
- Produces: `SpacyNLPProvider._get_model` raises `NLPProviderError` (never `ModuleNotFoundError`) when the spaCy package is absent; the app answers any `NLPProviderError` with **503** `{"detail": str, "code": "NLP_NOT_CONFIGURED"}`. Task 8's spec relies on: models present → real deterministic 200; models absent → 503 with that code (integration-pinned here, D-3).
- Consumes: `NLPProviderError` (`narrare_core.shared.errors:302`, already a `NarrareError`), the InvalidMonthError/BudgetExceededError handler-registration precedents.

**Root cause (2× why):**
- Why did the audit see a raw 500? `import spacy` sits bare at the top of `_get_model` — with the package absent it raises `ModuleNotFoundError`, which is not a `NarrareError`, so it bypasses the domain handler entirely (unhandled → 500).
- Why is even the wrapped path wrong? The model-missing (`OSError`) path already raises `NLPProviderError`, but the generic `NarrareError` mapping answers 400 — while spec §8 and the audit call for a machine-readable **503** ("NLP not configured"): the request is valid, the capability is absent in this deployment (verified live this session: this venv has spacy 3.8.13 but none of `_MODEL_MAP`'s `en_core_web_md`/`de_core_news_md`/`fr_core_web_md`).

**Alternatives considered:**
1. Wrap import + dedicated 503 handler (chosen) — machine-readable on both absence layers; 503 mirrors the `ExportFormatUnavailableError` precedent (capability-not-configured ≠ request problem).
2. Wrap import only (keep 400) — machine-readable but semantically wrong per spec §8, and clients cannot distinguish "fix your request" from "install the NLP extra". Rejected.
3. `is_available()` pre-check in the sentiment service → local 422 — moves the contract into one service and leaves dialogue/other NLP consumers inconsistent; the provider is the single seam (RULE-08). Rejected.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/core/nlp/test_provider_spacy_absent.py`:

```python
"""E03: absent spaCy package degrades machine-readable, never a raw 500.

``sys.modules['spacy'] = None`` makes ``import spacy`` raise ImportError
in-process, simulating the audit env that ran without ``--extra nlp``.
"""

from __future__ import annotations

import sys

import pytest

from narrare_core.nlp.provider_spacy import SpacyNLPProvider
from narrare_core.shared.errors import NLPProviderError


def test_missing_spacy_module_raises_nlp_provider_error(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "spacy", None)

    with pytest.raises(NLPProviderError) as excinfo:
        SpacyNLPProvider()._get_model("en")  # noqa: SLF001 — seam under test

    assert "not installed" in str(excinfo.value)


def test_nlp_provider_error_is_machine_readable() -> None:
    exc = NLPProviderError("spaCy model 'en_core_web_md' is not installed.")
    assert isinstance(exc.code, str | type(None))
```

Create `tests/integration/analysis/test_sentiment_degradation.py`:

```python
"""E03: POST /analysis/sentiment answers 503 NLP_NOT_CONFIGURED (spec §8).

Pinned via dependency override (deterministic in every environment — the
real provider's absence cannot be staged in-process in CI, which installs
the models).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from narrare.analysis.dependencies import get_sentiment_service
from narrare_core.shared.errors import NLPProviderError

if TYPE_CHECKING:
    from fastapi import FastAPI
    from httpx import AsyncClient


class TestSentimentNlpDegradation:
    @pytest.mark.asyncio
    async def test_nlp_provider_error_answers_503_with_code(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        service = MagicMock()
        service.analyze_chapters = AsyncMock(side_effect=NLPProviderError("NLP not configured."))

        async def _override():
            return service

        client.app.dependency_overrides[get_sentiment_service] = _override
        try:
            resp = await client.post(
                "/api/v1/analysis/sentiment",
                params={"novel_id": str(uuid4())},
                json={"chapter_ids": [str(uuid4())]},
                headers=auth_headers,
            )
        finally:
            client.app.dependency_overrides.pop(get_sentiment_service, None)

        assert resp.status_code == 503, resp.text[:300]
        assert resp.json()["code"] == "NLP_NOT_CONFIGURED"
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run --all-packages pytest tests/unit/core/nlp/test_provider_spacy_absent.py tests/integration/analysis/test_sentiment_degradation.py -v -p no:randomly`
Expected: FAIL — unit: `ModuleNotFoundError` raised instead of `NLPProviderError`; integration: `assert 400 == 503` (generic NarrareError mapping). Record both outputs.

- [ ] **Step 3: Implement the wrap + handler**

In `packages/core/narrare_core/nlp/provider_spacy.py`, `_get_model` (replace the bare import at line ~107):

```python
        try:
            import spacy  # pyright: ignore[reportMissingImports] -- optional dependency
        except ImportError as exc:
            # E03 (spec §8): absent package degrades machine-readable —
            # a raw ModuleNotFoundError escaped as HTTP 500 (audit E03).
            raise NLPProviderError(
                "The spaCy NLP package is not installed in this deployment. "
                "Install with: uv sync --all-packages --group dev --extra nlp "
                "(plus `just install-nlp-models` for the language models)."
            ) from exc
```

In `apps/api/narrare/_app/main.py`, after the BudgetExceededError handler (~line 212), add:

```python
    # --- NLP-not-configured handler (audit E03 / spec §8) ---
    # NLPProviderError IS a NarrareError; without this registration the
    # generic mapping answers 400 (and a pre-wrap absent package escaped as
    # a raw 500). 503: the capability is not configured in this deployment —
    # the request is valid, retrying unchanged cannot succeed (same
    # semantics as ExportFormatUnavailableError).
    from narrare_core.shared.errors import NLPProviderError

    @app.exception_handler(NLPProviderError)
    async def _nlp_provider_error_handler(  # pyright: ignore[reportUnusedFunction]
        _: Request, exc: NLPProviderError
    ) -> JSONResponse:
        logger.warning("nlp_provider_unavailable", detail=str(exc))
        return JSONResponse(
            status_code=503,
            content={"detail": str(exc), "code": "NLP_NOT_CONFIGURED"},
        )
```

- [ ] **Step 4: Run the tests to verify green**

Run: `uv run --all-packages pytest tests/unit/core/nlp tests/integration/analysis -v -p no:randomly`
Expected: ALL PASS (existing provider tests exercise present-package paths; the model-missing OSError path is unchanged).

- [ ] **Step 5: Live-stack spot-check (:3001 recipe, models NOT installed)**

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST "http://localhost:8000/api/v1/analysis/sentiment?novel_id=<novel_id>" \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"chapter_ids": ["<chapter_id>"]}'
```

Expected: `503` with `"code": "NLP_NOT_CONFIGURED"` (this venv lacks the models — the exact honest degradation). Then optionally `just install-nlp-models`, re-run: `200` with a `SentimentOverview` list. Record both.

- [ ] **Step 6: Commit**

```bash
git add packages/core/narrare_core/nlp/provider_spacy.py apps/api/narrare/_app/main.py tests/unit/core/nlp/test_provider_spacy_absent.py tests/integration/analysis/test_sentiment_degradation.py
git commit -m "fix(core): degrade absent spaCy as 503 NLP_NOT_CONFIGURED (E03, spec §8)"
```

---

### Task 4: Roster-gated speaker attribution — core helper + character voice (N11 half 1, Backend)

**Layer:** Backend · **Gate:** N11 (audit: "Voice Drift/Check Voice extract garbage 'characters' (In, Order, About, Ahead, …)"). Fix lands BEFORE the voice specs (Tasks 9–10).

**Files:**
- Modify: `packages/core/narrare_core/analysis/dialogue_parser.py` (append the roster helpers)
- Create: `apps/api/narrare/analysis/character_roster.py` (KB roster read, one responsibility — RULE-06)
- Modify: `apps/api/narrare/analysis/character_voice_service.py:189-194` (roster filter before metrics)
- Test: `tests/unit/core/analysis/test_dialogue_parser_roster.py` (create)
- Test: `tests/unit/api/analysis/test_character_voice_roster.py` (create; extend the harness conventions of `_character_voice_test_helpers.py`)

**Interfaces:**
- Produces (core, pure): `restrict_speakers_to_roster(utterances: list[AttributedUtterance], roster: set[str]) -> list[AttributedUtterance` — empty roster → the input unchanged (no SSOT to gate against); otherwise any utterance whose `speaker.casefold()` is not in `{r.casefold() for r in roster}` comes back as a NEW `AttributedUtterance` with `speaker=None`, `confidence=CONFIDENCE_LOW` (inputs are never mutated). Plus `filter_speaker_names(names: set[str], roster: set[str]) -> set[str]` (same semantics on plain name sets — Task 5's drift seam).
- Produces (api): `async def known_character_names(kb_repo, novel_id: UUID) -> set[str]` in `character_roster.py`, backed by `narrare.kb.worldbuilding_entity_assembly.list_entities(kb_repo, novel_id, ["character"])` (the established name-source helper — same one the wiki and consistency services use).
- Consumes: `AttributedUtterance` / `CONFIDENCE_LOW` from `narrare_core.analysis.voice_types` / `dialogue_parser`, `KBRepositoryProtocol.list_entries` (via `list_entities`).

**Root cause (2× why):** see D-4 — the action-beat heuristic accepts any capitalized token not in the finite `_NON_NAMES` list (why garbage appears), and no downstream consumer cross-checks speaker names against the KB, the only SSOT for who is a character (why garbage reaches the UI).

**Alternatives considered:**
1. Roster gate at the service seam via a pure core helper (chosen) — the parser stays prose-only pure; the KB (API side) supplies the roster; ADR-055 Decision 3 defines the None-demotion as the designed handoff to the agent.
2. Extend `_NON_NAMES` — no terminating condition (every common word is a candidate); rejected as whack-a-mole.
3. Require the speaker name to appear ≥2 times in the text — penalizes minor legitimate characters and still admits repeated garbage ("In order" is frequent prose); rejected.
4. KB-gate inside `DialogueParser.parse` — would push KB access into a pure core model (RULE-07 layering); rejected.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/core/analysis/test_dialogue_parser_roster.py`:

```python
"""N11: roster-gated speaker attribution.

The action-beat heuristic attributes quotes to the last capitalized token
of the preceding clause — sentence-initial prose words ("In order to…")
become MEDIUM-confidence "speakers". The roster gate demotes any speaker
not in the novel's KB character roster to None (ADR-055 Decision 3: the
agent resolves unattributed quotes inline). Empty roster → no-op (no SSOT
to gate against — KB-less novels keep the parser's hint behavior).
"""

from __future__ import annotations

from narrare_core.analysis.dialogue_parser import (
    CONFIDENCE_LOW,
    CONFIDENCE_MEDIUM,
    DialogueParser,
    filter_speaker_names,
    restrict_speakers_to_roster,
)

# Deterministic N11 repro: "Elara" is the only roster character; the
# sentence-initial words before quotes attract garbage attributions.
_N11_TEXT = (
    'Elara pressed her palm against the gate. "Open it," she said.\n\n'
    "In order to be ready, she counted the bells. \"Two strikes. The gate, then.\"\n\n"
    'About an hour later, the guard sighed. "Nobody crosses after dark."'
)


class TestRestrictSpeakersToRoster:
    def test_garbage_action_beat_names_are_demoted(self) -> None:
        utterances = DialogueParser().parse(_N11_TEXT)
        speakers = {u.speaker for u in utterances if u.speaker}
        # The audit's garbage class is present pre-fix (In/Order/About…).
        assert speakers - {"Elara"}, f"repro stale: got {speakers}"

        gated = restrict_speakers_to_roster(utterances, {"Elara"})

        assert {u.speaker for u in gated if u.speaker} == {"Elara"}
        demoted = [u for u in gated if u.speaker is None]
        assert demoted, "garbage attributions must survive as None (agent handoff)"
        assert all(u.confidence == CONFIDENCE_LOW for u in demoted)

    def test_matching_is_case_insensitive(self) -> None:
        utterances = DialogueParser().parse('Elara said, "We leave at dawn."')
        gated = restrict_speakers_to_roster(utterances, {"elara thornwind"})
        assert gated[0].speaker == "Elara" or gated[0].speaker == "Elara Thornwind"

    def test_empty_roster_is_a_no_op(self) -> None:
        utterances = DialogueParser().parse(_N11_TEXT)
        gated = restrict_speakers_to_roster(utterances, set())
        assert [(u.speaker, u.confidence) for u in gated] == [
            (u.speaker, u.confidence) for u in utterances
        ]

    def test_inputs_are_not_mutated(self) -> None:
        utterances = DialogueParser().parse(_N11_TEXT)
        before = [(u.speaker, u.confidence) for u in utterances]
        restrict_speakers_to_roster(utterances, {"Elara"})
        assert [(u.speaker, u.confidence) for u in utterances] == before


class TestFilterSpeakerNames:
    def test_name_sets_are_filtered_case_insensitively(self) -> None:
        assert filter_speaker_names({"Elara", "Order", "About"}, {"elara"}) == {"Elara"}

    def test_empty_roster_keeps_names(self) -> None:
        assert filter_speaker_names({"Elara", "Order"}, set()) == {"Elara", "Order"}
```

Create `tests/unit/api/analysis/test_character_voice_roster.py`:

```python
"""N11 service seam: character-voice profiles only ROSTER characters.

The service reads the KB character roster and gates parser attributions
before metrics — the progress event must say "Profiling 1 character(s)"
for the N11 repro chapter, not 1 + garbage.
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from narrare.analysis.character_roster import known_character_names

_ROSTER_TEXT = (
    'Elara pressed her palm against the gate. "Open it," she said.\n\n'
    "In order to be ready, she counted the bells. \"Two strikes. The gate, then.\""
)


class FakeKBRepo:
    def __init__(self, names: list[str]) -> None:
        self._entries = [
            SimpleNamespace(id=uuid4(), name=n, entity_type="character") for n in names
        ]

    async def list_entries(self, novel_id, entity_type=None, tags=None, page=1, page_size=50):
        return list(self._entries), len(self._entries)


async def test_known_character_names_reads_the_kb_roster() -> None:
    roster = await known_character_names(FakeKBRepo(["Elara", "Gatekeeper"]), uuid4())
    assert roster == {"Elara", "Gatekeeper"}


async def test_known_character_names_empty_for_empty_kb() -> None:
    assert await known_character_names(FakeKBRepo([]), uuid4()) == set()
```

Calibration for the service-level pin: read `tests/unit/api/analysis/_character_voice_test_helpers.py` first and add one test that constructs `CharacterVoiceService` with the REAL `DialogueParser` (its `_make_dialogue_parser` is overridable), a `FakeKBRepo(["Elara"])`, a novel whose single chapter carries `_ROSTER_TEXT`, and a stubbed `run_character_voice_agent` (monkeypatch `narrare.analysis.character_voice_agent_runner.run_character_voice_agent` to record `character_names` and return a minimal valid `CharacterVoiceOutput`); assert the stub received `character_names == ["Elara"]`. If constructing the full service in that harness exceeds ~40 lines, pin the seam composition instead: `metrics = analyzer.analyze(restrict_speakers_to_roster(parser.parse(text), roster))` → `set(metrics) == {"Elara"}` — and note the E2E leg (Task 9) carries the end-to-end pin on the real stream.

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run --all-packages pytest tests/unit/core/analysis/test_dialogue_parser_roster.py tests/unit/api/analysis/test_character_voice_roster.py -v -p no:randomly`
Expected: FAIL — `ImportError: cannot import name 'restrict_speakers_to_roster'` / `No module named 'narrare.analysis.character_roster'` (the "function not defined" red). Record the output.

- [ ] **Step 3: Implement**

In `packages/core/narrare_core/analysis/dialogue_parser.py`, append after the `DialogueParser` class:

```python
# ---------------------------------------------------------------------------
# Roster-gated attribution (audit N11)
# ---------------------------------------------------------------------------


def restrict_speakers_to_roster(
    utterances: list[AttributedUtterance],
    roster: set[str],
) -> list[AttributedUtterance]:
    """Demote attributions whose speaker is not in the KB character roster.

    The action-beat heuristic accepts any capitalized token that is not in
    the finite ``_NON_NAMES`` list, so sentence-initial prose words ("In
    order to…") become MEDIUM-confidence "speakers" (audit N11: garbage
    characters in voice drift / check voice / character voices). The KB
    roster is the SSOT for who IS a character; a demoted utterance keeps
    its text/position with ``speaker=None`` at ``CONFIDENCE_LOW`` — the
    ADR-055 Decision 3 handoff: the agent resolves unattributed quotes
    inline (rendered ``?`` in the agent prompt).

    Empty *roster* → the input list unchanged (a KB-less novel has no SSOT
    to gate against; the parser's hint behavior stands). Inputs are never
    mutated — new utterances are returned for demotions.
    """
    if not roster:
        return utterances
    roster_cf = {name.casefold() for name in roster}
    gated: list[AttributedUtterance] = []
    for utt in utterances:
        if utt.speaker is not None and utt.speaker.casefold() not in roster_cf:
            gated.append(
                AttributedUtterance(
                    text=utt.text,
                    speaker=None,
                    confidence=CONFIDENCE_LOW,
                    start=utt.start,
                    end=utt.end,
                )
            )
        else:
            gated.append(utt)
    return gated


def filter_speaker_names(names: set[str], roster: set[str]) -> set[str]:
    """Name-set form of :func:`restrict_speakers_to_roster` (drift seam)."""
    if not roster:
        return set(names)
    roster_cf = {name.casefold() for name in roster}
    return {name for name in names if name.casefold() in roster_cf}
```

Create `apps/api/narrare/analysis/character_roster.py`:

```python
"""KB character-roster reads for the voice services (audit N11).

One responsibility (RULE-06): turn the novel's KB character entries into
the name set that gates parser speaker attributions. Reuses
``worldbuilding_entity_assembly.list_entities`` — the same name-source
helper the wiki and consistency services use (no second roster SSOT).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.kb.repository import KBRepositoryProtocol


async def known_character_names(kb_repo: KBRepositoryProtocol, novel_id: UUID) -> set[str]:
    """All character-entry names for *novel_id* (empty set for an empty KB).

    The empty set is meaningful: callers treat it as "no roster to gate
    against" and keep the parser's raw attributions (RULE-11 degradation).
    """
    from narrare.kb.worldbuilding_entity_assembly import list_entities

    entries = await list_entities(kb_repo, novel_id, ["character"])
    return {entry.name for entry in entries}
```

(Check `worldbuilding_entity_assembly.list_entities`'s third parameter name/type — it is `entity_types: list[str] | None` — and the `KBRepositoryProtocol` import path; adjust the TYPE_CHECKING import to the protocol module the repo actually exposes, `narrare.kb.contracts` or `narrare.kb.repository`.)

In `apps/api/narrare/analysis/character_voice_service.py`, `analyze` (lines ~189-194), after `utterances = parser.parse(chapter_text)`:

```python
        # N11: gate parser attributions against the KB character roster —
        # sentence-initial prose words otherwise become garbage "characters"
        # (action-beat heuristic). Demoted quotes stay in the agent prompt
        # as "?"-tagged dialogue (ADR-055 Decision 3).
        from narrare.analysis.character_roster import known_character_names
        from narrare_core.analysis.dialogue_parser import restrict_speakers_to_roster

        roster = await known_character_names(self._kb_repo, novel_id)
        utterances = restrict_speakers_to_roster(utterances, roster)
        metrics = analyzer.analyze(utterances)
```

(replacing the bare `metrics = analyzer.analyze(utterances)` line; everything downstream — `character_names`, the agent call, persistence — now sees roster-only names).

- [ ] **Step 4: Run the tests to verify green**

Run: `uv run --all-packages pytest tests/unit/core/analysis tests/unit/api/analysis -v -p no:randomly`
Expected: ALL PASS (existing character-voice tests use synthetic attributions; if any seeded fixture relied on a non-KB speaker name, update the fixture to add the name to its fake KB repo — record any such adjustment).

- [ ] **Step 5: Live-stack spot-check (:3001 recipe)**

Novel with a KB character "Elara" (World & Characters → Create new) + a chapter containing `_N11_TEXT` → editor → "Character Voices" → run. Expected: the progress line reads "Profiling 1 character(s)." and no cards named "Order"/"About"/"In" appear (the stream may end in a TestModel error event — E04, documented; the deterministic prefix is the pin). Record the observed event sequence.

- [ ] **Step 6: Commit**

```bash
git add packages/core/narrare_core/analysis/dialogue_parser.py apps/api/narrare/analysis/character_roster.py apps/api/narrare/analysis/character_voice_service.py tests/unit/core/analysis/test_dialogue_parser_roster.py tests/unit/api/analysis/test_character_voice_roster.py
git commit -m "fix(analysis): gate voice attributions against the KB character roster (N11, half 1)"
```

---

### Task 5: Roster-gated speaker attribution — voice drift + voice check (N11 half 2, Backend)

**Layer:** Backend · **Gate:** N11 (drift unions raw parser speakers into the character set — the garbage `no_stored_profile` cards; check profiles every metrics key). **Carries 4 product files (~24 LOC) — the ≤3-file cap needs the PO fold ruling (OPEN QUESTION 2).** Fix lands BEFORE the voice specs (Task 10).

**Files:**
- Modify: `apps/api/narrare/analysis/voice_drift_service.py:208-218` (`all_speakers` gate)
- Modify: `apps/api/narrare/analysis/voice_check_service.py:136-141` (utterance gate before metrics)
- Modify: `apps/api/narrare/analysis/dependencies_voice_drift.py` (roster provider wiring)
- Modify: `apps/api/narrare/analysis/dependencies_voice_check.py` (roster provider wiring)
- Test: `tests/unit/api/analysis/test_voice_drift_roster.py` (create; reuse `_voice_drift_test_helpers.py`)
- Test: `tests/unit/api/analysis/test_voice_check_roster.py` (create; reuse `_voice_check_test_helpers.py`)

**Interfaces:**
- Produces: both services accept `roster_provider: Callable[[UUID], Awaitable[set[str]]] | None = None` (keyword-only, default `None` = no gating — backwards compatible for every existing construction); `CharacterVoiceDriftService.run_stream` computes `all_speakers = filter_speaker_names(collect_speakers(chapters, parser), await self._roster_provider(novel_id))` when a provider is wired and returns a non-empty roster; `CharacterVoiceCheckerService.check` runs `utterances = restrict_speakers_to_roster(utterances, roster)` before `analyzer.analyze`.
- Consumes: Task 4's `filter_speaker_names` / `restrict_speakers_to_roster` / `known_character_names`; both dependency factories already construct `KBRepository(session)` for the profile consumer (verified: `dependencies_voice_drift.py:99`, `dependencies_voice_check.py` same shape).

**Root cause (2× why):** D-4; the drift-specific amplifier is `all_names = sorted(set(profiles_by_name) | all_speakers)` (`voice_drift_service.py:218`) — every garbage speaker becomes a surfaced "character" with a `no_stored_profile` card, which is also why the audit saw the heatmap degenerate to a garbage list (heatmaps exist only for profiled characters).

**Alternatives considered:**
1. `roster_provider` param wired from the existing dependency factories (chosen) — keeps the services repo-free beyond one callable; the factories already own the KB repo construction.
2. Pass `kb_repo` directly into the services — widens each service's dependency surface for one read; the provider callable matches the existing `consumer_provider` idiom in both constructors. Rejected.
3. Derive the roster from `assemble_for_checking` profiles — profiles exist only for ANALYZED characters; unprofiled-but-real KB characters must still be surfaced as `no_stored_profile` (designed behavior), so the profile set is not the roster. Rejected.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/api/analysis/test_voice_drift_roster.py` (mirror the construction harness in `_voice_drift_test_helpers.py`; the drift seam is testable at the `collect_speakers` + `filter_speaker_names` composition level):

```python
"""N11 drift seam: raw parser speakers are roster-gated before the union.

``CharacterVoiceDriftService`` unions profile names with parser speakers
(``set(profiles_by_name) | all_speakers``); ungated, garbage action-beat
"speakers" surface as no_stored_profile cards (audit N11). Pinned at the
exact composition the service performs.
"""

from __future__ import annotations

from narrare_core.analysis.dialogue_parser import DialogueParser, filter_speaker_names

_N11_TEXT = (
    "In order to be ready, she counted the bells. \"Two strikes. The gate, then.\"\n\n"
    'Elara said, "Then I make an exception."'
)


def test_drift_character_union_is_roster_gated() -> None:
    parser = DialogueParser()
    raw_speakers = {
        u.speaker for u in parser.parse(_N11_TEXT) if u.speaker
    }
    assert raw_speakers - {"Elara"}, f"repro stale: {raw_speakers}"

    roster = {"Elara"}
    all_speakers = filter_speaker_names(raw_speakers, roster)
    all_names = sorted(set({"Elara": object()}) | all_speakers)  # profiles | speakers

    assert all_names == ["Elara"]


def test_empty_roster_preserves_the_union() -> None:
    parser = DialogueParser()
    raw_speakers = {u.speaker for u in parser.parse(_N11_TEXT) if u.speaker}
    assert filter_speaker_names(raw_speakers, set()) == raw_speakers
```

Plus one service-level test in the same file: construct `CharacterVoiceDriftService` per the existing helpers with `roster_provider` returning `{"Elara"}`, a fake consumer returning NO stored profiles, and one chapter carrying `_N11_TEXT`; collect the `run_stream` events; assert every `no_profile` event's character name is `"Elara"` and no garbage name appears in any event (the agent is never reached with zero checkable characters — the stream ends after the no_profile events, keeping the test TestModel-free). RED pre-fix: garbage names appear in `no_profile` events.

Create `tests/unit/api/analysis/test_voice_check_roster.py` (mirror `_voice_check_test_helpers.py`): service with `roster_provider` → `{"Elara"}`, chapter with `_N11_TEXT`, consumer with a stored "Elara" profile, stubbed checker agent runner; assert the checker received only "Elara" as checkable. RED pre-fix: garbage names in `checkable`/progress text.

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run --all-packages pytest tests/unit/api/analysis/test_voice_drift_roster.py tests/unit/api/analysis/test_voice_check_roster.py -v -p no:randomly`
Expected: FAIL — `TypeError: … unexpected keyword argument 'roster_provider'` for the service-level tests (the seam tests fail on the garbage-name assertions once the constructor accepts the param mid-implementation; treat the constructor error as the gate red). Record the output.

- [ ] **Step 3: Implement**

In `voice_drift_service.py`: add `roster_provider: VoiceProfileConsumerProvider | None = None` style keyword param — concretely `roster_provider: Callable[[UUID], Awaitable[set[str]]] | None = None` (extend the module's existing `Callable`/`Awaitable` TYPE_CHECKING imports), store `self._roster_provider`; in `run_stream`, after `all_speakers = collect_speakers(chapters, parser)` (line ~211):

```python
        # N11: gate raw parser speakers against the KB character roster
        # before the union — garbage action-beat "speakers" otherwise
        # surface as no_stored_profile cards (audit N11).
        if self._roster_provider is not None:
            roster = await self._roster_provider(novel_id)
            if roster:
                from narrare_core.analysis.dialogue_parser import filter_speaker_names

                all_speakers = filter_speaker_names(all_speakers, roster)
```

In `voice_check_service.py`: same constructor param; in `check`, after `utterances = parser.parse(chapter.content or "")` (line ~139):

```python
        if self._roster_provider is not None:
            roster = await self._roster_provider(chapter.novel_id)
            if roster:
                from narrare_core.analysis.dialogue_parser import restrict_speakers_to_roster

                utterances = restrict_speakers_to_roster(utterances, roster)
        current_metrics = analyzer.analyze(utterances)
```

In `dependencies_voice_drift.py` and `dependencies_voice_check.py` (both already build `kb_repo = KBRepository(session)` for the consumer): add

```python
    from narrare.analysis.character_roster import known_character_names

    async def roster_provider(novel_id: UUID) -> set[str]:
        return await known_character_names(kb_repo, novel_id)
```

and pass `roster_provider=roster_provider,` to the service construction in each factory.

- [ ] **Step 4: Run the tests to verify green**

Run: `uv run --all-packages pytest tests/unit/api/analysis -v -p no:randomly && uv run --all-packages pytest tests/integration/analysis/test_analysis_api.py tests/integration/analysis/test_character_voice_api.py -v -p no:randomly`
Expected: ALL PASS (integration factories run through the new wiring; default `None` keeps unit constructions stable).

- [ ] **Step 5: Live-stack spot-check (:3001 recipe)**

Novel with KB "Elara" + `_N11_TEXT` chapter → editor → "Voice Drift" → run: the overview lists exactly Elara (as a no-profile card — no stored profile yet), zero garbage cards. Then "Check Voice": progress names only Elara (or the no-dialogue skip if the roster gate removed everything checkable). Record both observations.

- [ ] **Step 6: Commit**

```bash
git add apps/api/narrare/analysis/voice_drift_service.py apps/api/narrare/analysis/voice_check_service.py apps/api/narrare/analysis/dependencies_voice_drift.py apps/api/narrare/analysis/dependencies_voice_check.py tests/unit/api/analysis/test_voice_drift_roster.py tests/unit/api/analysis/test_voice_check_roster.py
git commit -m "fix(analysis): roster-gate voice drift + voice check speaker sets (N11, half 2)"
```

---

### Task 6: i18n-first error rendering in the analysis panels (M05-class, Frontend)

**Layer:** Frontend · **Gate:** M05 class (audit: "`lib/api/ai-error-mapping.ts` maps 4xx/5xx/stream-death to hardcoded German … rendered in the English UI"), scoped to THIS wave's seven analysis panels (D-5). **Carries 7 product files × ~2 LOC — the ≤3-file cap needs the PO fold ruling (OPEN QUESTION 1).** Lands BEFORE the specs that pin English error copy (Tasks 9–10).

**Files:**
- Modify: `packages/web/components/studio/analysis/CoreferencePanel.tsx:142`
- Modify: `packages/web/components/studio/analysis/VoiceCheckPanel.tsx:138`
- Modify: `packages/web/components/studio/analysis/VoiceDriftPanel.tsx:152`
- Modify: `packages/web/components/studio/analysis/CharacterVoicePanel.tsx:139`
- Modify: `packages/web/components/studio/analysis/AuthorVoicePanel.tsx:164`
- Modify: `packages/web/components/studio/analysis/AuthorVoiceDriftPanel.tsx:154`
- Modify: `packages/web/components/studio/analysis/ConsistencyPanel.tsx:121`
- Test: the seven sibling `.test.tsx` files (one error-render assertion update each)

**Interfaces:**
- Produces: every error state in these panels renders `tStudio(error.i18nKey ?? "aiActions.errorDefault")` — the localized copy — instead of `error?.userMessage` (which is by construction the German fallback string from `AI_ERROR_MESSAGE_MAP`; `aiActions.*` keys ship in en/de/fr, verified). Tasks 9–10's specs pin the ENGLISH `errorConnection` copy ("Connection lost. Check your internet connection.") on the catalog error variants.
- Consumes: `useTranslations("studio")` (a second hook instance next to each panel's existing `useTranslations("analysis")` — `ConsistencyPanel` already has `tStudio`); the existing `AIErrorResponse.i18nKey` contract.

**Root cause (2× why):**
- Why does the EN UI show German? The mapper's `userMessage` field is defined as the map's `.de` string (`ai-error-mapping.ts:26-67` — "i18n key → default DE message"; every construction site sets `userMessage: AI_ERROR_MESSAGE_MAP[key].de`), and these panels print `userMessage` directly.
- Why was `i18nKey` not used? The panels predate the M06 ruling that panels must render `t(error.i18nKey)`; the GenerationPanel fix (ai-writing wave Task 2) established the pattern but only touched its own panel. The `aiActions.*` keys exist with full en/de/fr parity — nothing but the render line is missing.

**Alternatives considered:**
1. Per-panel i18n-first rendering (chosen — the landed M06 precedent) — no mapper change, no new keys, seven one-line edits + tests.
2. Drop `userMessage` from `AIErrorResponse` mapper-wide — the honest systemic fix, but it touches every consumer across chat/settings/learning/kb at once: that is the M05 wave's slice (documented follow-on; this task is the analysis-panel down-payment that unblocks honest E2E pins).
3. Translate `userMessage` at runtime by locale lookup — duplicates what `t(i18nKey)` already does. Rejected.

- [ ] **Step 1: Write the failing tests**

In each of the seven sibling test files, update (or add) the error-path test to assert the i18n key renders. The tests' `next-intl` mock returns keys directly (setupTests.ts), so the assertion is the key string. Shape (shown for `CoreferencePanel.test.tsx`; the other six mirror it with their own harness names):

```tsx
  it("renders the localized error key, not the German userMessage (M05)", () => {
    setState({
      result: null,
      error: {
        kind: "stream",
        i18nKey: "aiActions.errorConnection",
        userMessage: "Verbindung verloren. Prüfe deine Internetverbindung.",
        retryable: true,
        cause: new Error("stream death"),
      },
      isLoading: false,
      isStreaming: false,
      isComplete: false,
      isError: true,
    });

    render(<CoreferencePanel {...defaultProps} />);

    expect(screen.getByText("aiActions.errorConnection")).toBeDefined();
    expect(screen.queryByText("Verbindung verloren. Prüfe deine Internetverbindung.")).toBeNull();
  });
```

Calibration: each file already stages its hook mock via a `setState`-style helper and an error fixture carrying BOTH fields (`networkError(message)` builders at e.g. `CoreferencePanel.test.tsx:93-101`); reuse them and only change the assertions if a German-copy assertion already exists. `ConsistencyPanel`'s existing line is `error?.userMessage || t("error")` — its test asserts the analysis-namespace `error` fallback; the new assertion targets `tStudio(error.i18nKey ?? …)`.

- [ ] **Step 2: Run them to verify they fail**

Run: `pnpm --filter narrare-web exec vitest run components/studio/analysis`
Expected: FAIL — each new test finds the German `userMessage` rendered (`queryByText("Verbindung verloren…")` non-null). Record the counts.

- [ ] **Step 3: Implement the seven render-line changes**

For the six panels rendering `{error?.userMessage}` (`CoreferencePanel.tsx:142`, `VoiceCheckPanel.tsx:138`, `VoiceDriftPanel.tsx:152`, `CharacterVoicePanel.tsx:139`, `AuthorVoicePanel.tsx:164`, `AuthorVoiceDriftPanel.tsx:154`):

1. Add the studio hook beside the existing one: `const tStudio = useTranslations("studio");`
2. Replace the error copy line:

```tsx
                <p className="text-sm text-muted-foreground mb-4">
                  {error ? tStudio(error.i18nKey ?? "aiActions.errorDefault") : null}
                </p>
```

(keep each panel's own className/ordering; only the expression changes).

For `ConsistencyPanel.tsx:121` (`tStudio` already exists):

```tsx
  const errorMessage = error ? tStudio(error.i18nKey ?? "aiActions.errorDefault") : t("error");
```

- [ ] **Step 4: Run the tests to verify green**

Run: `pnpm --filter narrare-web exec vitest run components/studio/analysis && pnpm --filter narrare-web run type-check`
Expected: ALL PASS (the pre-existing error tests that asserted the raw `userMessage` string were updated in Step 1; no other behavior changes).

- [ ] **Step 5: Live-stack spot-check (:3001 recipe)**

Kill the API process (or block `**/api/v1/analysis/**` in devtools), open the Coreference panel in the EN UI, trigger a run: the error line reads "Connection lost. Check your internet connection." — NOT "Verbindung verloren…". Record the screenshot/text.

- [ ] **Step 6: Commit**

```bash
git add packages/web/components/studio/analysis/CoreferencePanel.tsx packages/web/components/studio/analysis/VoiceCheckPanel.tsx packages/web/components/studio/analysis/VoiceDriftPanel.tsx packages/web/components/studio/analysis/CharacterVoicePanel.tsx packages/web/components/studio/analysis/AuthorVoicePanel.tsx packages/web/components/studio/analysis/AuthorVoiceDriftPanel.tsx packages/web/components/studio/analysis/ConsistencyPanel.tsx packages/web/components/studio/analysis/CoreferencePanel.test.tsx packages/web/components/studio/analysis/VoiceCheckPanel.test.tsx packages/web/components/studio/analysis/VoiceDriftPanel.test.tsx packages/web/components/studio/analysis/CharacterVoicePanel.test.tsx packages/web/components/studio/analysis/AuthorVoicePanel.test.tsx packages/web/components/studio/analysis/AuthorVoiceDriftPanel.test.tsx packages/web/components/studio/analysis/ConsistencyPanel.test.tsx
git commit -m "fix(web): render localized aiActions error keys in the analysis panels (M05 class)"
```

---

### Task 7: Catalog growth — `pov` happy + error (Platform)

**Layer:** Platform · **Gate:** catalog prep for Task 8 (spec §10 ratchet).

**Files:**
- Modify: `tests/e2e/mocks/catalog_analysis.py` (fixtures + SPECS + `validate()`)
- Modify: `tests/unit/test_e2e_mock_catalog.py` (extend)

**Interfaces:**
- Produces: `mock_llm(page, "pov")` (happy) and `mock_llm(page, "pov", fixture="error")` — JSON `RouteSpec`s on `**/api/v1/analysis/pov*` (method POST, `application/json`). The happy body is a `POVResult`; the error body is a 500 `{"detail": "e2e-mock: pov agent failed"}` (the panel's error branch maps 5xx → `aiActions.errorConnection`).
- Consumes: `POVResult` from `narrare_core.analysis.types` (validate), the module's existing fixture conventions.

- [ ] **Step 1: Add the fixtures + specs + validation**

In `tests/e2e/mocks/catalog_analysis.py`, after `CONSISTENCY_ERROR_SSE`:

```python
# Mirrors POVResult (narrare_core.analysis.types — field names verified
# in-tree 2026-10-18: POVScene.scene_index/start_position/end_position/
# pov_character/confidence; POVIssue.type/location/text/explanation/
# suggestion/severity; POVIssueType values are snake_case strings).
_POV_RESULT = {
    "scenes": [
        {
            "scene_index": 0,
            "start_position": 0,
            "end_position": 220,
            "pov_character": "Elara",
            "confidence": 0.93,
        }
    ],
    "issues": [
        {
            "type": "head_hop",
            "location": "chapter 1, paragraph 4",
            "text": "The gatekeeper doubted her story.",
            "explanation": "Mid-scene slip into the gatekeeper's interiority.",
            "suggestion": "Keep the gatekeeper externally observed.",
            "severity": "warning",
        }
    ],
    "pov_distribution": {"first_person": 1},
    "switch_count": 0,
    "analysis_type": "single_pov",
}

POV_HAPPY = json.dumps(_POV_RESULT)
POV_ERROR = json.dumps({"detail": "e2e-mock: pov agent failed"})
```

Extend `SPECS`:

```python
    RouteSpec(
        capability="pov",
        variant="happy",
        pattern="**/api/v1/analysis/pov*",
        method="POST",
        body=POV_HAPPY,
    ),
    RouteSpec(
        capability="pov",
        variant="error",
        pattern="**/api/v1/analysis/pov*",
        method="POST",
        status=500,
        body=POV_ERROR,
    ),
```

Extend `validate()`:

```python
    from narrare_core.analysis.types import POVResult

    POVResult.model_validate_json(POV_HAPPY)
```

Calibration: the nested field names above were verified against `narrare_core.analysis.types` this session (`POVScene.scene_index/start_position/end_position/pov_character/confidence`; `POVIssue.type/location/text/explanation/suggestion/severity`; `POVIssueType` values snake_case) — `model_validate` in `validate()` remains the ratchet. Extend `tests/unit/test_e2e_mock_catalog.py` with a `pov` happy+error case mirroring the existing entries.

- [ ] **Step 2: Run the catalog ratchet**

Run: `uv run --all-packages pytest tests/unit/test_e2e_mock_catalog.py -v -p no:randomly`
Expected: PASS (the ratchet proves the fixture validates against the real model).

- [ ] **Step 3: Commit**

```bash
git add tests/e2e/mocks/catalog_analysis.py tests/unit/test_e2e_mock_catalog.py
git commit -m "test(e2e): catalog pov happy+error entries (ANAL-004 panel legs)"
```

---

### Task 8: `helpers/analysis_world.py` + `test_analysis.py` — beta reader, sentiment, readability, POV (Platform)

**Layer:** Platform · **Gates:** B07 pin (fixed in the blocker wave — pin green), E03 (stance per D-3), N12 pin (fixed in Task 1), N13 pin (fixed in Task 2).

**Files:**
- Create: `tests/e2e/helpers/analysis_world.py`
- Create: `tests/e2e/test_analysis.py`

**Interfaces:**
- Produces (helper): `open_analysis_panel(page, panel)` (toolbar trigger click + right-panel wait; labels verified from `packages/i18n/messages/en/analysis.json` this session), `sentiment_models_available() -> bool` (spec §10 skipif guard), `N11_DIALOGUE_CHAPTER` / `SHORT_CHAPTER` / `RICH_CHAPTER` prose constants, `seed_voice_profile(authed_request, novel_id, character_entry_id, voice_analysis)` (KB PATCH, used by Task 10).
- Consumes: `editor_ai.prepare_ai_chapter`, `kb_world.seed_kb_entity`, `foundation.make_authed_request`, `mock_llm`, `novel_factory.complete_wizard`.

- [ ] **Step 1: Create the helper module**

Create `tests/e2e/helpers/analysis_world.py`:

```python
"""Analysis-surface prep for the analysis E2E specs (spec §4 helpers).

Owns the recurring analysis concerns so the three spec files assert
instead of navigating: toolbar panel entry, N11 repro prose, sentiment
model-presence guard (spec §10 skipif), and voice-profile seeding via
the KB PATCH API (character-voice cannot seed profiles under TestModel —
E04 stream death precedes persistence — so drift/check specs seed the
``speech.voice_analysis`` block directly, the KB wave's D-8 discipline).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.e2e.helpers.editor_ai import prepare_ai_chapter

if TYPE_CHECKING:
    from collections.abc import Callable

    import requests
    from playwright.sync_api import Page

_UI_WAIT_MS: int = 15_000

# Toolbar trigger labels — packages/i18n/messages/en/analysis.json
# (verified 2026-10-18; re-calibrate if the labels drift).
ANALYSIS_TRIGGERS: dict[str, str] = {
    "beta_reader": "Beta Reader",
    "sentiment": "Sentiment",
    "consistency": "Consistency",
    "readability": "Readability",
    "pov": "POV",
    "coreference": "Coreference",
    "character_voice": "Character Voices",
    "voice_check": "Check Voice",
    "voice_drift": "Voice Drift",
    "author_voice": "Author Voice",
    "author_voice_drift": "Author Drift",
}


def open_analysis_panel(page: Page, panel: str) -> None:
    """Open an analysis right-panel from its toolbar trigger button."""
    page.get_by_role("button", name=ANALYSIS_TRIGGERS[panel], exact=True).click()
    page.get_by_test_id("editor-right-panel").wait_for(state="visible", timeout=_UI_WAIT_MS)


def sentiment_models_available() -> bool:
    """True when the spaCy EN model the provider maps to is installed.

    CI's test-e2e installs the models (W3-2 cache); a bare local venv does
    not — the guard keeps the deterministic happy-path specs honest in
    both (spec §10; E03 degradation is integration-pinned in Task 3).
    """
    try:
        import spacy

        return bool(spacy.util.is_package("en_core_web_md"))
    except Exception:  # noqa: BLE001 — absence IS the signal
        return False


# N11 repro: sentence-initial capitalized words directly before quotes —
# the action-beat heuristic's garbage attractors. "Elara" is the only
# roster character in every spec that seeds a KB entry by that name.
N11_DIALOGUE_CHAPTER = (
    'Elara pressed her palm against the gate. "Open it," she said.\n\n'
    'In order to be ready, she counted the bells. "Two strikes. The gate, then."\n\n'
    'About an hour later, the guard sighed. "Nobody crosses after dark."\n\n'
    'Ahead of her, torchlight guttered. Elara said, "Then I make an exception."'
)

# ~60 words: below the beta-reader 1000-word minimum (N13 boundary).
SHORT_CHAPTER = (
    "Elara waited by the gate. The bells rang twice, and she counted "
    "them the way her mother had taught her, waiting for the third "
    "before she stepped into the dark."
)

# Multi-sentence emotional prose for the deterministic sentiment run.
RICH_CHAPTER = (
    "Elara was furious when the gate stayed shut. She screamed at the "
    "guard, joyful for a moment when the lock clicked, then terrified "
    "of the dark road beyond. \"Open it,\" she said, calm again. The "
    "guard laughed. She wept, quietly, and waited for the third bell."
)


def seed_voice_profile(
    authed_request: Callable[..., requests.Response],
    novel_id: str,
    entry_id: str,
    voice_analysis: dict,
) -> dict:
    """Write ``speech.voice_analysis`` onto a KB character via PATCH.

    The drift/check pipelines read stored profiles through the ADR-050
    consumer; this seeds one deterministically (the shape mirrors the
    catalog's validated ``voice_analysis`` block).
    """
    resp = authed_request(
        "PATCH",
        f"/api/v1/novels/{novel_id}/kb/entries/{entry_id}",
        json={"metadata": {"speech": {"voice_analysis": voice_analysis}}},
    )
    assert resp.status_code == 200, f"{resp.status_code} {resp.text[:300]}"
    return resp.json()


__all__ = [
    "ANALYSIS_TRIGGERS",
    "N11_DIALOGUE_CHAPTER",
    "RICH_CHAPTER",
    "SHORT_CHAPTER",
    "open_analysis_panel",
    "seed_voice_profile",
    "sentiment_models_available",
]
```

(`prepare_ai_chapter` is re-exported for the spec files' convenience import; drop the import if lint objects and import from `editor_ai` directly in the specs.)

- [ ] **Step 2: Write the spec**

Calibration BEFORE writing (record in the task report): (a) on the live stack (:3001 recipe), confirm the BetaReader panel's tab labels + a feedback card's title text (`analysis.json` `betaReader.*`), the Readability metric-card labels (`readability.fleschScore` etc.), the Sentiment results header, and the POV distribution bar — adjust the text assertions if the rendered EN strings differ; (b) confirm each panel's run affordance (BetaReaderPanel auto-runs on mount; the others expose an Analyze/Run button — read the panel components for the exact accessible names and tighten the regexes); (c) the fixtures mirror `test_kb_management.py`'s `kb_novel` + `authed_request` pair exactly — `prepare_ai_chapter` takes the module's `authed_request`, never the raw `api_request`.

Create `tests/e2e/test_analysis.py`:

```python
"""Analysis E2E specs — ANAL-001 beta reader, ANAL-002 sentiment,
ANAL-003 readability, ANAL-004 POV (spec §5 row ``test_analysis.py``).

Real backend under TestModel for readability/POV/sentiment (ADR-021
deterministic or tolerance-loose); the browser-layer catalog for the
validator-strict beta reader (E04). Pins: B07 (POV kb-supply — FIXED in
the blocker wave; pinned green), E03 (sentiment model-presence stance,
D-3), N12 (readability AI phase runs — fixed in-wave), N13 (min-words
422 machine-readable — fixed in-wave).

Runtime budget: ≤ 2.5 min (spec §7 / D-8). Markers: e2e.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest

from tests.e2e.config import BASE_URL
from tests.e2e.foundation import NovelContext, make_authed_request
from tests.e2e.helpers import mock_llm
from tests.e2e.helpers.analysis_world import (
    N11_DIALOGUE_CHAPTER,
    RICH_CHAPTER,
    SHORT_CHAPTER,
    open_analysis_panel,
    sentiment_models_available,
)
from tests.e2e.helpers.editor_ai import prepare_ai_chapter
from tests.e2e.helpers.novel_factory import complete_wizard

if TYPE_CHECKING:
    from collections.abc import Callable

    import requests as http_requests


@pytest.fixture(scope="module")
def analysis_novel(module_stable_user) -> NovelContext:
    novel = complete_wizard(module_stable_user.page, BASE_URL)
    return NovelContext(
        page=module_stable_user.page,
        novel_id=novel["novel_id"],
        email=module_stable_user.email,
        password=module_stable_user.password,
        access_token=module_stable_user.access_token,
    )


@pytest.fixture
def authed_request(
    api_request: Callable[..., http_requests.Response],
    analysis_novel: NovelContext,
) -> Callable[..., http_requests.Response]:
    return make_authed_request(api_request, analysis_novel)


@pytest.mark.e2e
class TestBetaReader:
    def test_happy_path_renders_mocked_feedback(self, analysis_novel, authed_request) -> None:
        page = analysis_novel.page
        prepare_ai_chapter(
            page, authed_request, analysis_novel.novel_id,
            title="Beta Chapter", content=N11_DIALOGUE_CHAPTER,
        )
        mock_llm(page, "beta_reader")
        open_analysis_panel(page, "beta_reader")

        # The panel auto-runs on the active chapter (catalog-mocked).
        page.get_by_text("Elara's motivation is concrete").first.wait_for(
            state="visible", timeout=20_000
        )
        assert page.get_by_text("A focused opening scene with one clear objective.").first.is_visible()

    def test_below_minimum_words_answers_422_machine_readable(
        self, analysis_novel, authed_request
    ) -> None:
        """N13 pin (fixed in-wave): the business rule is honest on the wire.

        NO catalog mock installed — the REAL backend must validate.
        """
        page = analysis_novel.page
        prepare_ai_chapter(
            page, authed_request, analysis_novel.novel_id,
            title="Too Short", content=SHORT_CHAPTER,
        )
        open_analysis_panel(page, "beta_reader")

        with page.expect_response(lambda r: "/api/v1/analysis/beta-reader" in r.url) as caught:
            page.get_by_role("button", name=re.compile("Analyze|Refresh|Run")).first.click()
        resp = caught.value
        assert resp.status == 422
        body = resp.json()
        assert body["code"] == "WORD_COUNT_BELOW_MINIMUM"


@pytest.mark.e2e
class TestSentiment:
    @pytest.mark.skipif(
        not sentiment_models_available(),
        reason="spaCy en_core_web_md not installed — run `just install-nlp-models`; "
        "CI test-e2e installs the models (E03 stance, D-3; degradation is "
        "integration-pinned in the fix task)",
    )
    def test_deterministic_scores_render(self, analysis_novel, authed_request) -> None:
        page = analysis_novel.page
        prepare_ai_chapter(
            page, authed_request, analysis_novel.novel_id,
            title="Mood Chapter", content=RICH_CHAPTER,
        )
        open_analysis_panel(page, "sentiment")

        with page.expect_response(lambda r: "/api/v1/analysis/sentiment" in r.url) as caught:
            page.get_by_role("button", name=re.compile("Analyze|Run")).first.click()
        resp = caught.value
        assert resp.status == 200
        overview = resp.json()[0]
        assert overview["sentence_count"] >= 1
        assert "average_vad" in overview
        # Data-quality warning is part of the deterministic contract
        # (< 500 words → warning; ADR-021).
        assert any("500" in w for w in overview.get("warnings", []))
        page.get_by_text(re.compile("Sentences|sentences")).first.wait_for(
            state="visible", timeout=15_000
        )


@pytest.mark.e2e
class TestReadability:
    def test_metrics_and_ai_phase_on_the_real_path(self, analysis_novel, authed_request) -> None:
        """N12 pin (fixed in-wave): 200 + metrics + the AI phase RAN."""
        page = analysis_novel.page
        prepare_ai_chapter(
            page, authed_request, analysis_novel.novel_id,
            title="Readability Chapter", content=RICH_CHAPTER,
        )
        open_analysis_panel(page, "readability")

        with page.expect_response(lambda r: "/api/v1/analysis/readability" in r.url) as caught:
            page.get_by_role("button", name=re.compile("Analyze|Run")).first.click()
        resp = caught.value
        assert resp.status == 200
        result = resp.json()[0]
        assert isinstance(result["metrics"]["flesch_reading_ease"], (int, float))
        # The AI phase now composes (Task 1). Under TestModel the agent
        # output is schema-generated: assert the KEY is present; the
        # count may be 0 only if TestModel synthesizes an empty list —
        # record the observed value in the report and, if 0, keep the
        # key-presence assertion + note (honest pin, no hard-fail on a
        # TestModel artifact).
        assert "sentence_analyses" in result
        page.get_by_text(re.compile("Flesch|Reading Ease")).first.wait_for(
            state="visible", timeout=15_000
        )


@pytest.mark.e2e
class TestPOV:
    def test_real_path_answers_200_b07_fixed(self, analysis_novel, authed_request) -> None:
        """B07 pin: the kb-supply fix holds — 200 POVResult, no 500."""
        page = analysis_novel.page
        prepare_ai_chapter(
            page, authed_request, analysis_novel.novel_id,
            title="POV Chapter", content=N11_DIALOGUE_CHAPTER,
        )
        open_analysis_panel(page, "pov")

        with page.expect_response(lambda r: "/api/v1/analysis/pov" in r.url) as caught:
            page.get_by_role("button", name=re.compile("Analyze|Run")).first.click()
        resp = caught.value
        assert resp.status == 200, f"B07 regression: {resp.status} {resp.text[:200]}"
        result = resp.json()
        assert "pov_distribution" in result and "scenes" in result

    def test_panel_renders_deterministic_content(self, analysis_novel, authed_request) -> None:
        """Panel-content leg via the catalog (independent of TestModel)."""
        page = analysis_novel.page
        prepare_ai_chapter(
            page, authed_request, analysis_novel.novel_id,
            title="POV Content", content=N11_DIALOGUE_CHAPTER,
        )
        mock_llm(page, "pov")
        open_analysis_panel(page, "pov")

        page.get_by_text("Elara").first.wait_for(state="visible", timeout=20_000)
```

If a panel does not auto-run and exposes no "Analyze"-named button, read the panel component for its run affordance's accessible name and calibrate the regex (record it) — the auto-trigger convention differs per panel (BetaReaderPanel auto-runs on mount; POVPanel may require the run button; the run-button regexes are intentionally loose and MUST be tightened to the calibrated names before merge).

- [ ] **Step 3: Run the spec**

Run: `E2E_PYTEST_ARGS="tests/e2e/test_analysis.py" just e2e`
Expected: ALL PASS (locally the sentiment spec SKIPS with the documented reason when models are absent — that skip is the D-3 stance; the other three classes pass). Tasks 1 and 2 must be merged first (N12/N13 pins are green pins of the fixed behavior).

- [ ] **Step 4: Commit**

```bash
git add tests/e2e/helpers/analysis_world.py tests/e2e/test_analysis.py
git commit -m "test(e2e): analysis specs — beta reader boundary (N13), sentiment (E03 stance), readability (N12), POV (B07 pin)"
```

---

### Task 9: `test_analysis_streams.py` — coreference, character voices, consistency stream (Platform)

**Layer:** Platform · **Gates:** N11 stream pin (fixed in Task 4), E04 catalog surfaces, the KB wave's promised CONS-001/ADR-044 stream content assertions, M05-fixed English error copy (Task 6).

**Files:**
- Create: `tests/e2e/test_analysis_streams.py`

**Interfaces:**
- Consumes: catalog `coreference_stream` / `character_voice_stream` / `consistency_stream` happy+error (landed), `analysis_world.open_analysis_panel` / `N11_DIALOGUE_CHAPTER` / `seed_kb_entity`, `make_authed_request`, Task 6's English error copy.

- [ ] **Step 1: Write the spec**

Create `tests/e2e/test_analysis_streams.py`:

```python
"""Analysis SSE specs — ANAL-005 coreference, ANAL-008 character voices,
and the CONS-001/ADR-044 consistency-stream content assertions the KB wave
deferred here.

Catalog (browser layer) for the validator-strict surfaces (E04:
coreference + character voices stream-die under TestModel; consistency
content is asserted deterministically), plus one REAL character-voice leg
whose deterministic PREFIX (the progress event) pins the N11 roster fix.

Runtime budget: ≤ 2.5 min (D-8). Markers: e2e.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest

from tests.e2e.config import BASE_URL
from tests.e2e.foundation import NovelContext, make_authed_request
from tests.e2e.helpers import mock_llm
from tests.e2e.helpers.analysis_world import (
    N11_DIALOGUE_CHAPTER,
    open_analysis_panel,
)
from tests.e2e.helpers.editor_ai import prepare_ai_chapter
from tests.e2e.helpers.kb_world import seed_kb_entity
from tests.e2e.helpers.novel_factory import complete_wizard

if TYPE_CHECKING:
    from collections.abc import Callable

    import requests as http_requests


@pytest.fixture(scope="module")
def streams_novel(module_stable_user) -> NovelContext:
    novel = complete_wizard(module_stable_user.page, BASE_URL)
    return NovelContext(
        page=module_stable_user.page,
        novel_id=novel["novel_id"],
        email=module_stable_user.email,
        password=module_stable_user.password,
        access_token=module_stable_user.access_token,
    )


@pytest.fixture
def authed_request(
    api_request: Callable[..., http_requests.Response],
    streams_novel: NovelContext,
) -> Callable[..., http_requests.Response]:
    return make_authed_request(api_request, streams_novel)


@pytest.mark.e2e
class TestCoreference:
    def test_happy_path_renders_resolutions(self, streams_novel, authed_request) -> None:
        page = streams_novel.page
        prepare_ai_chapter(
            page, authed_request, streams_novel.novel_id,
            title="Coref Chapter", content=N11_DIALOGUE_CHAPTER,
        )
        mock_llm(page, "coreference_stream")
        open_analysis_panel(page, "coreference")

        page.get_by_text("92").first.wait_for(state="visible", timeout=20_000)
        assert page.get_by_text("Pronoun use is unambiguous").first.is_visible()

    def test_stream_error_renders_english_not_german(self, streams_novel, authed_request) -> None:
        """M05-class pin (fixed in Task 6): localized error copy."""
        page = streams_novel.page
        prepare_ai_chapter(
            page, authed_request, streams_novel.novel_id,
            title="Coref Error", content=N11_DIALOGUE_CHAPTER,
        )
        mock_llm(page, "coreference_stream", fixture="error")
        open_analysis_panel(page, "coreference")

        page.get_by_text("Connection lost. Check your internet connection.").first.wait_for(
            state="visible", timeout=20_000
        )
        assert page.get_by_text("Verbindung verloren").count() == 0


@pytest.mark.e2e
class TestCharacterVoices:
    def test_happy_path_renders_character_card(self, streams_novel, authed_request) -> None:
        page = streams_novel.page
        prepare_ai_chapter(
            page, authed_request, streams_novel.novel_id,
            title="Voices Chapter", content=N11_DIALOGUE_CHAPTER,
        )
        mock_llm(page, "character_voice_stream")
        open_analysis_panel(page, "character_voice")

        page.get_by_text("Clipped countdown speech unlike the gatekeeper's formality.").first.wait_for(
            state="visible", timeout=20_000
        )

    def test_real_stream_profiles_only_roster_characters(
        self, streams_novel, authed_request
    ) -> None:
        """N11 pin on the REAL stream: the deterministic prefix is honest.

        The progress event ("Profiling N character(s)") is emitted BEFORE
        any agent call, so this pin is immune to TestModel strictness
        (E04). The chapter's garbage attractors must NOT become profiles;
        the agent phase may legitimately die under TestModel afterwards —
        that tail is the documented E04 limitation, not a failure.
        """
        page = streams_novel.page
        seed_kb_entity(authed_request, streams_novel.novel_id, name="Elara")
        prepare_ai_chapter(
            page, authed_request, streams_novel.novel_id,
            title="N11 Chapter", content=N11_DIALOGUE_CHAPTER,
        )
        open_analysis_panel(page, "character_voice")

        progress = page.get_by_text(re.compile(r"Profiling \d+ character"))
        progress.first.wait_for(state="visible", timeout=30_000)
        assert "Profiling 1 character" in progress.first.inner_text()
        # No garbage profile cards — the roster gate held.
        for garbage in ("Order", "About", "Ahead"):
            assert page.get_by_text(re.compile(rf"^{garbage}$")).count() == 0


@pytest.mark.e2e
class TestConsistencyStream:
    def test_stage_sequence_and_result_content(self, streams_novel, authed_request) -> None:
        """CONS-001/ADR-044 content assertions (KB wave follow-through)."""
        page = streams_novel.page
        prepare_ai_chapter(
            page, authed_request, streams_novel.novel_id,
            title="Consistency Chapter", content=N11_DIALOGUE_CHAPTER,
        )
        mock_llm(page, "consistency_stream")
        open_analysis_panel(page, "consistency")

        # Stage vocabulary mirrors consistency_orchestrator.py:
        # extracting_facts → checking_consistency → result.
        page.get_by_text(re.compile("Extracting facts", re.IGNORECASE)).first.wait_for(
            state="visible", timeout=20_000
        )
        page.get_by_text("Consistent").first.wait_for(state="visible", timeout=20_000)

    def test_stream_error_renders_english_not_german(self, streams_novel, authed_request) -> None:
        page = streams_novel.page
        prepare_ai_chapter(
            page, authed_request, streams_novel.novel_id,
            title="Consistency Error", content=N11_DIALOGUE_CHAPTER,
        )
        mock_llm(page, "consistency_stream", fixture="error")
        open_analysis_panel(page, "consistency")

        page.get_by_text("Connection lost. Check your internet connection.").first.wait_for(
            state="visible", timeout=20_000
        )
```

Calibration (live stack first, recorded in the report): the ConsistencyPanel's stage/progress rendering (`consistency.*` keys in `analysis.json` — the panel may render a spinner + stage text or only the result; if the stage text is not rendered verbatim, assert the result content ("Consistent" / issue count 0) and the request wire via `page.expect_response` instead — the ADR-044 CONTENT assertion then rides the captured SSE body's first `data:` lines). The character-voice garbage-card assertion assumes cards render the bare name; verify against `CharacterVoiceResultCard` and tighten the regex if the name renders with suffixes.

- [ ] **Step 2: Run the spec**

Run: `E2E_PYTEST_ARGS="tests/e2e/test_analysis_streams.py" just e2e`
Expected: ALL PASS (Tasks 4 and 6 merged first — the N11 + English-error pins are green pins of the fixed behavior).

- [ ] **Step 3: Commit**

```bash
git add tests/e2e/test_analysis_streams.py
git commit -m "test(e2e): analysis stream specs — coreference + character voices (E04 catalog, N11 pin) + consistency stream content"
```

---

### Task 10: `test_analysis_voice.py` — author voice, author drift, voice drift, voice check (Platform)

**Layer:** Platform · **Gates:** ANAL-007/009, N11 panel pins (fixed in Tasks 4–5), audit "Verified WORKING" surfaces (author voice, author drift, check voice) get happy-path pins.

**Files:**
- Create: `tests/e2e/test_analysis_voice.py`

**Interfaces:**
- Consumes: `analysis_world.open_analysis_panel` / `N11_DIALOGUE_CHAPTER` / `seed_voice_profile` / a validated `voice_analysis` block (mirror the catalog's `_CHARACTER_VOICE_RESULT["voice_analysis"]` — validated against the real model by the catalog ratchet), `seed_kb_entity`, `make_authed_request`. All four runs are REAL under TestModel (D-7).

- [ ] **Step 1: Write the spec**

Create `tests/e2e/test_analysis_voice.py`:

```python
"""Voice-family specs — ANAL-007 author voice, ANAL-009 voice drift,
voice check (WRITE-010 surface), author voice drift (ANAL-009 Phase 2B).

All four run the REAL backend under TestModel (audit "Verified WORKING":
author voice, author drift, check voice; drift's deterministic prefix).
Stored profiles are seeded via the KB PATCH API (character-voice cannot
seed them under TestModel — E04; D-7 discipline).

Runtime budget: ≤ 2 min (D-8). Markers: e2e.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

import pytest

from tests.e2e.config import BASE_URL
from tests.e2e.foundation import NovelContext, make_authed_request
from tests.e2e.helpers.analysis_world import (
    N11_DIALOGUE_CHAPTER,
    open_analysis_panel,
    seed_voice_profile,
)
from tests.e2e.helpers.editor_ai import prepare_ai_chapter
from tests.e2e.helpers.kb_world import seed_kb_entity
from tests.e2e.helpers.novel_factory import complete_wizard

if TYPE_CHECKING:
    from collections.abc import Callable

    import requests as http_requests

# Validated voice_analysis block (mirrors the catalog fixture, which the
# §10 ratchet validates against the real VoiceAnalysis model).
_VOICE_ANALYSIS = {
    "formality": 0.3,
    "vocabulary_level": "moderate",
    "sentence_profile": "varied",
    "emotional_range": "expressive",
    "cultural_regional_markers": "harbour-town idioms",
    "voice_examples": ["Two strikes. The gate, then."],
    "voice_metrics": {
        "avg_sentence_length": 11.2,
        "sentence_length_std": 4.1,
        "type_token_ratio": 0.62,
        "avg_syllables_per_word": 1.4,
        "contraction_rate": 0.21,
        "verbal_tic_frequency": {"Two strikes": 0.08},
        "punctuation_profile": {"ellipsis": 0.02},
    },
}


@pytest.fixture(scope="module")
def voice_novel(module_stable_user) -> NovelContext:
    novel = complete_wizard(module_stable_user.page, BASE_URL)
    return NovelContext(
        page=module_stable_user.page,
        novel_id=novel["novel_id"],
        email=module_stable_user.email,
        password=module_stable_user.password,
        access_token=module_stable_user.access_token,
    )


@pytest.fixture
def authed_request(
    api_request: Callable[..., http_requests.Response],
    voice_novel: NovelContext,
) -> Callable[..., http_requests.Response]:
    return make_authed_request(api_request, voice_novel)


@pytest.mark.e2e
class TestAuthorVoice:
    def test_profile_generates_and_renders(self, voice_novel, authed_request) -> None:
        page = voice_novel.page
        prepare_ai_chapter(
            page, authed_request, voice_novel.novel_id,
            title="Author Voice Chapter", content=N11_DIALOGUE_CHAPTER,
        )
        open_analysis_panel(page, "author_voice")

        with page.expect_response(lambda r: "/analysis/author-voice" in r.url) as caught:
            page.get_by_role("button", name=re.compile("Analyze|Create|Run")).first.click()
        assert caught.value.status == 200
        page.get_by_text(re.compile("profile|Profile")).first.wait_for(
            state="visible", timeout=30_000
        )


@pytest.mark.e2e
class TestAuthorVoiceDrift:
    def test_narrator_trend_renders(self, voice_novel, authed_request) -> None:
        page = voice_novel.page
        prepare_ai_chapter(
            page, authed_request, voice_novel.novel_id,
            title="Drift Chapter", content=N11_DIALOGUE_CHAPTER,
        )
        open_analysis_panel(page, "author_voice_drift")

        with page.expect_response(lambda r: "/analysis/author-voice-drift" in r.url) as caught:
            page.get_by_role("button", name=re.compile("Analyze|Run|Check")).first.click()
        assert caught.value.status == 200
        page.get_by_text(re.compile("Ch1|chapter", re.IGNORECASE)).first.wait_for(
            state="visible", timeout=30_000
        )


@pytest.mark.e2e
class TestVoiceDrift:
    def test_roster_only_characters_in_events(self, voice_novel, authed_request) -> None:
        """N11 panel pin: KB character + stored profile → drift result;
        garbage speakers never enter the character set (fixed in-wave)."""
        page = voice_novel.page
        entry = seed_kb_entity(authed_request, voice_novel.novel_id, name="Elara")
        seed_voice_profile(authed_request, voice_novel.novel_id, entry["id"], _VOICE_ANALYSIS)
        prepare_ai_chapter(
            page, authed_request, voice_novel.novel_id,
            title="Voice Drift Chapter", content=N11_DIALOGUE_CHAPTER,
        )
        open_analysis_panel(page, "voice_drift")

        # API probe (deterministic prefix): progress names 1 character.
        with page.expect_response(lambda r: "/analysis/voice-drift" in r.url) as caught:
            page.get_by_role("button", name=re.compile("Analyze|Run")).first.click()
        assert caught.value.status == 200
        body = caught.value.text()
        assert "Elara" in body
        for garbage in ("Order", "About", "Ahead"):
            assert garbage not in body, f"N11 regression: {garbage} leaked into the stream"

        # Panel leg: the overview row for Elara renders (heatmaps exist
        # only for profiled characters — the audit's list-fallback note).
        page.get_by_text("Elara").first.wait_for(state="visible", timeout=30_000)


@pytest.mark.e2e
class TestVoiceCheck:
    def test_check_matches_seeded_profile(self, voice_novel, authed_request) -> None:
        page = voice_novel.page
        entry = seed_kb_entity(authed_request, voice_novel.novel_id, name="Elara")
        seed_voice_profile(authed_request, voice_novel.novel_id, entry["id"], _VOICE_ANALYSIS)
        prepare_ai_chapter(
            page, authed_request, voice_novel.novel_id,
            title="Check Chapter", content=N11_DIALOGUE_CHAPTER,
        )
        open_analysis_panel(page, "voice_check")

        with page.expect_response(lambda r: "/analysis/voice-check" in r.url) as caught:
            page.get_by_role("button", name=re.compile("Check|Analyze|Run")).first.click()
        assert caught.value.status == 200
        page.get_by_text("Elara").first.wait_for(state="visible", timeout=30_000)
```

Calibration (live stack first): each panel's run-button accessible name (`authorVoice.*` / `authorVoiceDrift.*` / `voiceDrift.*` / `voiceCheck.*` keys in `analysis.json`), the AuthorVoicePanel's chapter-selection preconditions (it consumes `chapters` — it may require selecting chapters in-panel before the run button enables; mirror the panel component), and whether `author-voice` is SSE (assert on the response status + a result card testid instead of a JSON body if so — `AuthorVoiceStreamEvent` is SSE; use `expect_response` for the status and pin content via the panel's rendered summary). The drift/check `expect_response(...).value.text()` reads the completed SSE body after the stream ends (terminal `done` event) — verified pattern; if Playwright returns partial body on long streams, switch to an `authed_request` POST probe with `resp.text` for the body assertions (probe-by-default).

- [ ] **Step 2: Run the spec**

Run: `E2E_PYTEST_ARGS="tests/e2e/test_analysis_voice.py" just e2e`
Expected: ALL PASS (Tasks 4–5 merged first — the N11 pins are green pins of the fixed behavior; author voice/drift ride the audit-verified TestModel paths).

- [ ] **Step 3: Commit**

```bash
git add tests/e2e/test_analysis_voice.py
git commit -m "test(e2e): voice family specs — author voice/drift real pins, voice drift + check with N11 roster pins"
```

---

### Task 11: Coverage matrix, budget actuals, sentiment-models note (Docs)

**Layer:** Docs · **Gate:** spec §9.

**Files:**
- Modify: `docs/development/e2e-coverage.md`
- Modify: `docs/development/testing-standards.md` (§ End-to-End (E2E) — runner note)

**Interfaces:** none (documentation).

- [ ] **Step 1: Update the coverage matrix + runner note**

In `docs/development/e2e-coverage.md`: mark the `test_analysis.py` row done, delivered as three files (`test_analysis.py`, `test_analysis_streams.py`, `test_analysis_voice.py` — RULE-04 split), with per-gate status: B07 pinned green (blocker-wave fix holds), E03 fixed in-wave (503 `NLP_NOT_CONFIGURED`; happy path skipif-guarded on model presence — CI installs the models), N11 fixed in-wave (roster-gated attribution; real-stream + panel pins), N12 fixed in-wave (readability AI phase composes; graceful-skip seam pinned), N13 fixed in-wave (422 `WORD_COUNT_BELOW_MINIMUM`). Honest-gap notes: the beta-reader deep-dive (Phase 2) is not E2E-covered (a catalog-mocked Phase 1 yields a fake `cache_key` — a real Phase 1 is E04-blocked; document as follow-on), the drift/check agent-classification tails are structural pins only (TestModel strictness, E04), and `userMessage`-based German fallbacks OUTSIDE the seven analysis panels remain the M05 wave's slice. Record measured per-file runtimes against the ≤ 7 min batch budget (D-8) and the ≤ 25 min suite target.

In `docs/development/testing-standards.md` § End-to-End (E2E), under "Runner", add one bullet: sentiment (ANAL-002) runs the REAL deterministic pipeline and requires the spaCy language models — `just install-nlp-models` (CI's test-e2e installs them; without them the sentiment specs skip with the documented reason and the API answers 503 `NLP_NOT_CONFIGURED` — E03).

- [ ] **Step 2: Commit**

```bash
git add docs/development/e2e-coverage.md docs/development/testing-standards.md
git commit -m "docs(testing): e2e coverage — analysis wave statuses, budget actuals, sentiment models note"
```

---

## Self-Review

**1. Spec coverage (§5 row `test_analysis.py`):** features — ANAL-001 (Task 8 beta reader happy + boundary), ANAL-002 (Task 8 sentiment, D-3 stance), ANAL-003 (Task 8 readability + N12 pin), ANAL-004 (Task 8 POV real + catalog legs, B07 pin), ANAL-005 (Task 9 coreference), ANAL-007 (Task 10 author voice), ANAL-008 (Task 9 character voices + N11 pin), ANAL-009 (Task 10 voice drift; author-drift Phase 2B included as the audit's working surface). Gates — B07 pinned green (Task 8), E03 fixed + stance (Tasks 3/8/11), N11 fixed + pinned on stream AND panels (Tasks 4/5/9/10), N12 fixed + pinned (Tasks 1/8), N13 fixed + pinned (Tasks 2/8). Scope line — "per-analyzer happy path via mocks" (catalog where E04-strict, real otherwise), "beta-reader min-words boundary" (Task 8), "readability honest-skip pin" (Task 1's degradation test + Task 8's key-presence assertion), "voice family panels" (Task 10). CONS-001 stream content assertions (KB-wave follow-through) in Task 9. No gaps.

**2. Placeholder scan:** every step carries complete code or an exact-edit instruction; the calibration notes name the files to read and the exact labels/selectors to confirm on the live stack before merge (the run-button regexes are explicitly flagged for tightening). No TBD/TODO/"add appropriate handling" anywhere; every type/function referenced is defined in its producing task (`restrict_speakers_to_roster`/`filter_speaker_names` T4→T5, `known_character_names` T4→T5, `open_analysis_panel`/`seed_voice_profile`/`sentiment_models_available` T8→T9/T10, `pov` catalog T7→T8).

**3. Type consistency:** wire shapes verified against source this session — routes (`/analysis/beta-reader`, `/analysis/sentiment`, `/analysis/readability`, `/analysis/pov`, `/analysis/coreference/{chapter_id}`, `/analysis/character-voice/{novel_id}`, `/analysis/voice-check/{chapter_id}`, `/analysis/voice-drift/{novel_id}`, `/analysis/author-voice/{novel_id}`, `/analysis/author-voice-drift/{novel_id}`, `/consistency/check/stream`), request bodies (`BetaReaderRequest.chapter_ids: list[str]`, `SentimentRequest.chapter_ids/language/detect_arc`), response models (`BetaReaderResponse`, `list[SentimentOverview]` incl. `warnings`, `list[ReadabilityResult]` with `metrics.flesch_reading_ease`/`sentence_analyses`, `POVResult` with `pov_distribution`/`scenes`), error contracts (`ValidationError`→422 `{"detail","code"}` via `main.py:104-121`; `NLPProviderError` handler added in Task 3), fixture names (`stable_user`/`module_stable_user`/`make_authed_request`/`NovelContext`, `seed_kb_entity`, `prepare_ai_chapter(page, api_request, novel_id, *, title, content)`), catalog API (`mock_llm(page, capability, *, fixture)`), KB PATCH (`KBEntryUpdate.metadata`). The N12 red claim was verified by live compose probe (PromptVariableError, exact message recorded); N13's 500-escape and E03's two failure layers verified against `main.py`/`provider_spacy.py`/`errors.py` in-tree; N11's repro prose validated against the parser's actual patterns (`_action_beat_speaker` + `_NON_NAMES`, garbage set In/Order/About/Ahead).

**4. Sustainability (3-month):** every fix is at a named seam with a regression test (compose path, error-class contract, handler mapping, roster gate); no new dependencies; no prompt-surface changes; the M05 slice is the established per-panel pattern the M05 wave will finish. The spec files are ≤ 400 lines each by construction (three-way split). Follow-ons recorded: beta-reader deep-dive E2E, `userMessage` mapper cleanup (M05 wave), `AnalysisError`→`NarrareError` re-base decision, FE i18n key for the 422 word-count body.

## Follow-on note

Next waves per spec §5 (suggested order): `test_import_export.py`, then `test_stats_budget.py`, `test_volumes_scenes.py`, `test_series_scratchpad.py`, `test_settings_auth.py` (the M05 wave — it inherits this wave's seven-panel down-payment plus ChatPanel, DialogueCoachPanel, kb/ConsistencyCheckPanel, and the systemic `userMessage` mapper cleanup), `test_onboarding.py`. Candidates surfaced by this wave for the PO backlog: beta-reader Phase 2 deep-dive E2E coverage (blocked on an E04-real Phase 1), an FE i18n key rendering the 422 `WORD_COUNT_BELOW_MINIMUM` body in the beta-reader panel (M05-wave polish), the `AnalysisError`→`NarrareError` wholesale re-base decision (D-2 alternative 3), and the drift agent-classification content pins once a validator-loose fixture strategy exists for `CharacterVoiceDriftAgent`.
