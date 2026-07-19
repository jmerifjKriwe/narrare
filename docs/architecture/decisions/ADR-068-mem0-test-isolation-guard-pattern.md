# ADR-068 — mem0 Test-Isolation Guard Pattern: Accept the API-Key Tension

> **Status:** ✅ Accepted
> **Date:** 2026-07-18
> **Deciders:** Architecture Specialist (PR #126 follow-up design)
> **Supersedes:** —
> **Related:** ADR-033 (mem0 OSS architecture), CR-06 mem0-loop design note,
> CR-AUFG-03-10 (consistency-feedback singleton — pattern established),
> PR #126 / commit `3ee3f048` (event-loop regression fix that surfaced this
> pattern), ADR-064 (mem0 scope boundary), RULE-08/11/20,
> `architectural-discipline.md` §7 (verify reality, not claims).

---

## Context

mem0 is installed in the test environment, and `tests/conftest.py:32-33`
unconditionally sets dummy `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` for the
entire test process:

```python
os.environ["ANTHROPIC_API_KEY"] = "sk-test-dummy-anthropic-key"
os.environ["OPENAI_API_KEY"]    = "sk-test-dummy-openai-key"
```

The accompanying comment ("only needed because pydantic-ai validates API
keys at import time") is slightly imprecise: the keys are needed because
pydantic-ai's providers fetch them at **construction time**
(`packages/core/narrare_core/llm/_providers/anthropic.py:55`,
`openai.py:57`) — and model construction is widespread in tests (every
`FakeModelRegistry`, every `TestModel`-based agent test, etc.).
`models.ALLOW_MODEL_REQUESTS = False` (set on `conftest.py:43`) blocks
runtime API calls, so the keys are present but never used for real
network I/O. Removing the keys would break a large fraction of the unit
suite; narrowing them to specific tests (Option D below) is impractical.

**The tension:** `narrare_core.memory.availability.detect_provider_from_env()`
uses the **same signal** (presence of `OPENAI_API_KEY` /
`ANTHROPIC_API_KEY`) to decide "credentials available". Every
mem0-backed singleton therefore believes credentials are present in the
test environment and proceeds past the availability gate to
`create_memory_client_sync()`, which instantiates a real
`mem0.AsyncMemory` backed by local Qdrant + sqlite.

These real clients leak across pytest-asyncio event loops, surfacing at
teardown as `RuntimeError: Task got Future attached to a different loop`
plus unclosed-file-handle `ResourceWarning`s — the proximate cause of
the PR #126 regression in `test_session_stop_and_recovery.py`.

PR #126 fixed the immediate regression by extending the
`_no_real_mem0_clients` autouse fixture to cover the new
`_feedback_memory_deps` singleton. Three follow-ups were surfaced during
that fix and are resolved by this ADR:

1. **`get_session_memory_instance`** in `apps/api/narrare/writing/
   _session_memory_deps.py` has the **same latent bug** PR #126 just fixed for
   `_feedback_memory_deps` (function-body imports instead of
   module-level imports → unpatchable by the guard).
2. **`_prewarm_composer` session/function scope mismatch** — the
   integration `_prewarm_composer` (session-scoped) runs *before* the
   function-scoped `_no_real_mem0_clients` guard, so the preference
   singleton creates a real client once per integration session before
   any guard can prevent it.
3. **The API-key tension itself** (this ADR's main subject) — recurring,
   will resurface every time a new mem0-backed singleton is added.

---

## Decision Drivers

- **RULE-20 (no half-implementations).** Test isolation must be
  complete; "mostly isolated" is regressable debt.
- **architectural-discipline §7 (verify reality, not claims).** The
  conftest comment was slightly imprecise about *why* the keys are
  needed; the ADR records the verified reality (construction-time fetch,
  not strict import-time validation).
- **RULE-08 (mem0 confined to `core/memory/`).** The fix must not spread
  mem0 awareness into the test layer beyond the existing singleton
  module-level seam.
- **RULE-11 (no silent failures).** A leak that manifests as a
  cross-event-loop `RuntimeError` at teardown is a silent failure in the
  sense that the test passes while resources leak.
- **Minimise production-code surface for test-only concerns.** Tests
  should not introduce new production config knobs or branches.
- **Sustainability.** The decision must hold when a 4th mem0-backed
  singleton is added.

---

## Options Considered

### Option A — Accept the tension; codify the module-level guard pattern as the architectural invariant  ✅ CHOSEN

Production code stays unchanged. The test-isolation invariant is
enforced at the test boundary via the autouse `_no_real_mem0_clients`
fixture (unit + integration conftests), which patches each singleton's
**module-level** re-imported `is_mem0_available` reference so the
singleton short-circuits before reaching `create_memory_client_sync()`.

The pattern has three mandatory components, all pinned by regression
tests:

1. **Singleton imports `is_mem0_available` + `detect_provider_from_env`
   at MODULE LEVEL** (not inside the function body) so the re-imported
   reference exists as a patchable module attribute.
2. **`_no_real_mem0_clients` fixture lists every mem0-backed singleton**
   and patches its module-level `is_mem0_available` reference.
3. **A per-singleton regression test** (mirroring
   `tests/unit/api/kb/test_consistency_feedback_singleton_isolation.py`)
   spies on `create_memory_client_sync` and asserts the singleton does
   NOT reach it under the guard; plus a `test_module_level_imports_present`
   that pins the import-location invariant.

**Pros:**
- Production code unchanged; no new config surface.
- Uses the architecturally-correct seam (the singleton's module-level
  import) — `is_mem0_available()` was *designed* to be test-patchable
  for exactly this reason (see `availability.py` docstring).
- Each singleton's isolation is independently verifiable via its own
  regression test (defence in depth).
- Aligns with the CR-06 design note, which already identified
  `writing/_session_memory_deps.py::get_session_memory_instance()` as the
  canonical pattern.

**Cons:**
- Maintenance burden: a new mem0-backed singleton requires extending the
  guard in **both** conftests AND adding a regression test. Forgetting
  any one of these silently re-introduces the leak.
- The guard's scope must match the lifetime of any session-scoped
  fixture that triggers singleton creation (see follow-up #2).

### Option B — Gate mem0-client creation on `NARRARE_MEM0_ENABLED` (default "auto"; tests set "disabled")

Add a new env var `NARRARE_MEM0_ENABLED` with values `auto` (default;
production behaviour unchanged — auto-detect from credentials) /
`disabled` (short-circuit). `tests/conftest.py` sets it to `disabled`.

**Pros:**
- Eliminates the `_no_real_mem0_clients` fixture entirely — no patch
  list to maintain.
- Single source of truth for "is mem0 active in this process".

**Cons:**
- **Introduces a production config surface for a test-only concern.**
  Even with `auto` as the documented default, operators must understand
  a new knob. This violates "tests should not expand the production
  config schema".
- **Moves the coupling, doesn't remove it.** The coupling is
  fundamental: mem0's `detect_provider_from_env()` and pydantic-ai's
  provider constructors both key off the same env vars. Option B just
  adds a second signal layered on top — it does not eliminate the
  shared-signal root cause.
- **Fragments the gating logic.** Today `is_mem0_available()` is the
  single seam; Option B introduces a parallel `is_mem0_enabled()` that
  every singleton must also check. More branches = more places to get
  wrong.
- The Backend specialist's triage reaction ("forbidden — bypasses
  production behaviour") stands unless rebutted by an ADR; this ADR
  does not find that rebuttal compelling enough to override the
  "no test-only prod config" principle.

### Option C — Refactor singletons to be FastAPI-DI-injectable; register `NullMemoryClient` in test DI

Replace module-level singleton state with `Depends()`-injectable
factories. In tests, override the dependency to return
`NullMemoryClient` (the integration conftest already does this for the
unrelated `get_memory_client` dep at line 266).

**Pros:**
- Cleanest separation; uses FastAPI's native DI override mechanism.

**Cons:**
- **Too invasive for the problem size.** Refactoring 3 singletons
  (`dependencies_prompts._get_preference_service_instance`,
  `_session_memory_deps.get_session_memory_instance`,
  `_feedback_memory_deps.get_consistency_feedback_memory_instance`)
  changes DI wiring, affects every caller, and risks regression — all
  for a test-isolation concern.
- **Does not address the prompt-composer prewarm path.** The
  `PromptComposer` is constructed via `@lru_cache` and calls
  `_get_preference_service_instance()` directly (not via `Depends()`),
  so the prewarm would still trigger singleton creation unless
  `get_composer()` itself is restructured.
- Current module-level singleton pattern does **not** violate RULE-04
  or RULE-06 — it is a deliberate design choice for long-lived mem0
  clients (see `_feedback_memory_deps.py` docstring).

### Option D — Narrow the dummy API keys to only the tests that need them

Set the keys via a session-scoped fixture or per-test `monkeypatch.setenv`
rather than unconditionally at conftest import.

**Pros:**
- Addresses the symptom directly — no keys, no mem0 client creation.

**Cons:**
- **Impractical.** Keys are needed at model-construction time, which
  happens in essentially every test that builds a `Model`, an `Agent`,
  or uses `FakeModelRegistry` / `TestModel`. Auditing every test file
  to determine which need keys is brittle and doesn't scale — a new
  test that constructs a model silently breaks without keys.
- **Does not actually eliminate the tension.** Any test that needs
  model construction still triggers `detect_provider_from_env()`, so
  the guard is still needed for those tests.

---

## Decision

**We choose Option A.** The mem0 test-isolation guard pattern (module-
level imports + autouse `_no_real_mem0_clients` fixture + per-singleton
regression test) is the architectural invariant. Production code is
unchanged. Three concrete commitments follow:

### Decision 1 — Module-level import requirement for mem0-backed singletons

Every mem0-backed singleton MUST import `is_mem0_available` and
`detect_provider_from_env` at **module level** (not inside the function
body) so the test guard can patch the re-imported reference. This is
already the pattern in `dependencies_prompts.py` and (post-PR #126)
`_feedback_memory_deps.py`. Follow-up #1 extends it to
`writing/_session_memory_deps.py`.

### Decision 2 — Guard scope must match the longest-lived fixture that triggers singleton creation

In `tests/integration/conftest.py`, the `_no_real_mem0_clients` guard
MUST be **session-scoped** (not function-scoped) so it runs before the
session-scoped `_prewarm_composer` fixture (which calls `get_composer()`
→ `_get_preference_service_instance()`). The unit-test guard stays
function-scoped (unit tests don't use session-scoped prewarm fixtures).
Follow-up #2 implements this.

The session-scoped guard uses `pytest.MonkeyPatch()` instantiated
directly (the `monkeypatch` fixture is function-scoped by design and
cannot be used at session scope).

### Decision 3 — Per-singleton regression test is mandatory

Every mem0-backed singleton MUST have a regression test mirroring
`tests/unit/api/kb/test_consistency_feedback_singleton_isolation.py`:
- `test_singleton_does_not_call_create_memory_client_sync` — spies on
  `create_memory_client_sync` and asserts the guard short-circuits.
- `test_module_level_imports_present` — asserts `hasattr(module,
  "is_mem0_available")` and `hasattr(module, "detect_provider_from_env")`,
  pinning Decision 1 against future refactors.

### Decision 4 — `tests/conftest.py` API-key setting stays as-is

The dummy API keys are needed for pydantic-ai provider construction
(widespread in tests). `ALLOW_MODEL_REQUESTS = False` blocks runtime
calls. Narrowing the keys (Option D) is impractical. The
slightly-imprecise conftest comment is updated to reflect the verified
reality (construction-time fetch, not strict import-time validation).

---

## Rationale

**Why Option A over B.** Option B's "production bypass" risk is real
even with a documented `auto` default: every operator must now
understand a knob that exists only because tests need it. The current
pattern keeps production code unchanged and uses the seam
(`is_mem0_available`) that was *designed* for this purpose. The
maintenance burden (extend the guard when adding a singleton) is
acceptable because (a) mem0-backed singletons are rare — three exist
today, added over months — and (b) the per-singleton regression test
makes omission a detectable failure, not a silent leak.

**Why Option A over C.** The current module-level singleton pattern is
a deliberate design choice (long-lived mem0 client, DI-compatible
construction — see `_feedback_memory_deps.py:48-66`). Refactoring it to
FastAPI-DI-injectable changes wiring across every caller for a
test-only benefit, and does not even fully solve the problem (the
`get_composer()` `@lru_cache` path would still need restructuring).

**Why Option A over D.** Option D is impractical: model construction
needs the keys and is widespread. It also does not eliminate the
guard requirement for the tests that *do* need keys.

**Tradeoff accepted (Option A's known cost):** when a 4th mem0-backed
singleton is added, the implementer MUST extend the guard in **both**
conftests AND add a regression test. Omission is detectable (the
regression test for the new singleton would be missing; the integration
test logs would show `*_initialized` events) but not CI-blocking by
default. Reviewers must check for it during PR review. (A meta-regression
test that scans for mem0-backed singletons and asserts each has a guard
entry is a future-hardening option, deferred — see Review Triggers.)

---

## Consequences

**Positive:**
- The mem0 test-isolation invariant is documented, machine-pinned by
  per-singleton regression tests, and applies uniformly to all current
  and future mem0-backed singletons.
- Production code is unchanged — no new config surface, no DI refactor.
- The pattern's three components (module-level imports + guard list +
  regression test) are each independently auditable.
- The session-vs-function scope rule (Decision 2) prevents the
  `_prewarm_composer` timing bug from recurring for any future
  session-scoped fixture that touches singleton state.

**Negative / Tradeoffs:**
- Maintenance burden: a new mem0-backed singleton requires touching
  `tests/unit/conftest.py`, `tests/integration/conftest.py`, and adding
  a regression test file. Omission is a silent leak, not a hard CI
  failure (until the next event-loop regression surfaces).
- The guard list is duplicated across two conftests (unit + integration).
  Drift between them is possible if a contributor updates one but not
  the other. Mitigation: the per-singleton regression test is the
  canonical source of truth — if the unit guard misses a singleton,
  its regression test (run under the unit guard) fails.

**Constraints introduced:**
- **RULE-08 (mem0 confined to `core/memory/`).** The guard patches
  references in `apps/api/` modules, but does NOT import or touch
  `mem0` directly — it patches `is_mem0_available`, which is a
  `narrare_core.memory.availability` function. RULE-08 is preserved.
- **RULE-11 (no silent failures).** The guard converts a silent
  resource leak into an enforced test-isolation invariant.
- **RULE-20 (no half-implementations).** A new singleton without its
  guard entry + regression test is an incomplete implementation.

---

## RULE-XX Compliance

| Rule | Status | Notes |
|------|--------|-------|
| RULE-03 | ✅ | No new contract required — `SessionMemoryService` / `ConsistencyFeedbackService` / `PreferenceService` already typed. The regression test is the "contract" for the isolation invariant. |
| RULE-04 | ✅ | No file-size impact; guard additions are <10 lines each. |
| RULE-06 | ✅ | One responsibility per file preserved; guard lives in conftest, regression test lives in its own file. |
| RULE-08 | ✅ | mem0 still confined to `core/memory/`; the guard patches `narrare_core.memory.availability.is_mem0_available` re-imports, never touches `mem0` directly. |
| RULE-11 | ✅ | The guard prevents a silent resource leak (cross-event-loop `RuntimeError` at teardown). |
| RULE-20 | ✅ | Three components required per singleton (module-level imports + guard entry + regression test) — no half-implementation. |
| RULE-22 | ✅ | N/A — no cross-feature data flow. |
| RULE-23 | ✅ | No type suppressions introduced. |

---

## Implementation Notes

This ADR is a decision + documentation change; the implementation is
delegated to the Backend specialist (follow-up #1: production-code
import relocation + regression test) and Platform specialist (follow-up
#2: test-only guard scope change). No Core changes required.

### Follow-up #1 — `get_session_memory_instance` (Backend specialist)

**File:** `apps/api/narrare/writing/_session_memory_deps.py`

- Move the `availability` import block (currently inside the `try:`) to
  module level, mirroring `_feedback_memory_deps.py:32-35`:

  ```python
  from narrare_core.memory.availability import (
      detect_provider_from_env,
      is_mem0_available,
  )
  ```

- Inside the `try:`, keep only the lazy runtime imports (`get_settings`,
  `NullMemoryClient`, `create_memory_client_sync`,
  `SessionMemoryService`) — these MUST stay lazy to avoid circular
  imports and to keep the singleton cheap until first call.
- Update the function docstring to note the module-level-import
  rationale (matching the `_feedback_memory_deps.py` docstring).

**File:** `tests/unit/conftest.py`

- Add a third `monkeypatch.setattr` for
  `"narrare.writing._session_memory_deps.is_mem0_available"`.

**File:** `tests/integration/conftest.py`

- Add the same `monkeypatch.setattr` line for
  `"narrare.writing._session_memory_deps.is_mem0_available"`.

**File (NEW):** `tests/unit/api/writing/test_session_memory_singleton_isolation.py`

- Mirror `tests/unit/api/kb/test_consistency_feedback_singleton_isolation.py`
  structure exactly: autouse reset fixture for
  `_session_memory_instance` / `_session_memory_init_tried`;
  `TestNoRealMem0InSessionMemorySingleton` class with
  `test_singleton_does_not_call_create_memory_client_sync` and
  `test_module_level_imports_present`.

### Follow-up #2 — Session-scope the integration guard (Platform specialist)

**File:** `tests/integration/conftest.py`

- Convert `_no_real_mem0_clients` from function-scoped `@pytest.fixture(autouse=True)`
  to session-scoped, using `pytest.MonkeyPatch()` instantiated directly
  (the `monkeypatch` fixture is function-scoped and cannot be used at
  session scope):

  ```python
  @pytest.fixture(autouse=True, scope="session")
  def _no_real_mem0_clients() -> Any:
      mp = pytest.MonkeyPatch()
      mp.setattr("narrare._app.dependencies_prompts.is_mem0_available", lambda: False)
      mp.setattr("narrare.kb._feedback_memory_deps.is_mem0_available", lambda: False)
      mp.setattr("narrare.writing._session_memory_deps.is_mem0_available", lambda: False)
      yield
      mp.undo()
  ```

- Add `_no_real_mem0_clients` as an explicit parameter to
  `_prewarm_composer` to guarantee ordering (autouse session fixtures
  do not have deterministic order without an explicit dependency):

  ```python
  @pytest.fixture(scope="session", autouse=True)
  def _prewarm_composer(_no_real_mem0_clients: None) -> None:
      get_composer()
  ```

- Keep `tests/unit/conftest.py` function-scoped — unit tests do not use
  session-scoped prewarm fixtures, so the function scope is correct and
  the `monkeypatch` fixture remains the right tool.

- Optional hardening (recommended): add
  `tests/integration/test_no_mem0_clients_in_session.py` that uses
  `caplog` to assert none of `preference_service_initialized` /
  `session_memory_initialized` / `consistency_feedback_initialized`
  appear during a minimal integration test run.

### Follow-up #3 — Conftest comment precision (Backend or Platform specialist)

**File:** `tests/conftest.py:29-33`

- Update the comment to reflect the verified reality (construction-time
  fetch, not strict import-time validation):

  ```python
  # Set dummy API keys for LLM providers. pydantic-ai providers fetch
  # the key from env at model-construction time (see
  # packages/core/narrare_core/llm/_providers/{anthropic,openai}.py),
  # which happens in most tests (FakeModelRegistry, TestModel, etc.).
  # models.ALLOW_MODEL_REQUESTS = False (below) blocks runtime API calls,
  # so the keys are present but never used for real network I/O.
  # See ADR-068 for why this makes mem0 test-isolation guards necessary.
  os.environ["ANTHROPIC_API_KEY"] = "sk-test-dummy-anthropic-key"
  os.environ["OPENAI_API_KEY"]    = "sk-test-dummy-openai-key"
  ```

---

## ADR Implementation Completeness Gate (Gate-12)

Opened with this ADR. Closes when:

- [ ] Follow-up #1 shipped (writing singleton module-level imports +
      guard extension + regression test).
- [ ] Follow-up #2 shipped (integration guard session-scoped +
      `_prewarm_composer` explicit dependency).
- [ ] Follow-up #3 shipped (conftest comment precision).
- [ ] All three regression tests (consistency-feedback, preference,
      session-memory) green under both unit and integration suites.
- [ ] Integration suite log-grep confirms no `*_initialized` events from
      mem0 singletons.

This ADR is `✅ Accepted` (decisions in effect); it is **not**
`✅ Implemented` until the Phase-D enforcement ships.

---

## Review Trigger

- [ ] When a 4th mem0-backed singleton is added → re-evaluate whether
      the guard-list maintenance burden justifies Option B (env-var
      gate) or a meta-regression test that auto-detects unguarded
      singletons.
- [ ] When pydantic-ai changes its key-validation / key-fetch behaviour
      → re-evaluate whether the dummy keys are still needed globally
      (Option D may become feasible).
- [ ] When `is_mem0_available()` or `detect_provider_from_env()` are
      refactored → verify the module-level-import invariant still
      holds for all three singletons.
- [ ] If a 2nd session-scoped fixture that triggers singleton creation
      is added to integration tests → verify it also depends on
      `_no_real_mem0_clients`.
