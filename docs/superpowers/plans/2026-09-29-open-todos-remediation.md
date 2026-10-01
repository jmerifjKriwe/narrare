# Open-Todos Remediation & Verification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the stale open-todos list from CURRENT_STATE 2026-09-29 — five of six items are already implemented in commits `7a1b75c6..ebd1bb26` on branch `bold-yak` (unpushed, unreviewed, docs stale); this plan produces hard verification evidence for them, closes the one remaining code gap (httpx cross-catch guard AST rewrite), runs the review gate, truth-fixes CURRENT_STATE, and opens a PR.

**Architecture:** Verification-first remediation. No production-code changes except an ephemeral, byte-identically-restored mutation proof. The single durable code change is test-only: rewriting the httpx guard's Rule 1 (cross-catch detection) and its SDK-module classifier from regex heuristics to Python `ast`, closing the `import httpx as hx` blind spot and the docstring false-positive class. Rule 2 (http_client injection) stays a documented same-file regex heuristic.

**Tech Stack:** Python 3.14, pytest (unit; integration against real Postgres `postgres_test:5433` via Alembic-only schema), stdlib `ast`, FastAPI/SQLAlchemy app under `apps/api`.

## Global Constraints

- Project language: English (code, comments, tests, commit messages, docs).
- No real LLM calls in tests; ADR-030 fakes at domain boundaries.
- Integration tests: schema only via real Alembic migrations (RULE-14); test DB must be up before integration suites.
- Git writes (add/commit/push/PR) ONLY via NarrarePlatformSpecialist; implementer subagents never commit. `git commit --no-verify` / `-n` is FORBIDDEN.
- RULE-23: no unjustified type suppressions; RULE-11: logged graceful degradation, no silent failure.
- Package cap per delegation: ≤3 files changed / ≤250 new LOC.
- CI is billing-rot (GitHub payment, PO action pending); local gates are the evidence of record.
- Working tree must be clean (zero net changes) after Task 2; branch tip before this plan: `ebd1bb26`.

---

### Task 1: Preflight (coordinator-run)

**Files:** none.

- [ ] **Step 1: Identify the pytest runner** — inspect `justfile` targets and virtualenv (`.venv/bin/pytest` or `uv run pytest`).
- [ ] **Step 2: Verify test DB reachability** — resolve the integration DB host/port from `tests/integration/conftest.py` and probe it (e.g. `pg_isready`). If down: start the compose test DB. BLOCKED-report to the user if it cannot be brought up.
- [ ] **Step 3: Record BASE** — `git rev-parse HEAD` (expected `ebd1bb26`), tree clean (`git status --short` empty).

### Task 2: Verification evidence package (report-only, zero net file changes)

**Files:**
- Ephemeral edit: `apps/api/narrare/consistency/deps.py` (mutation proof; restored byte-identically)
- Report: `<sdd-workspace>/task-2-report.md`

**Interfaces:** none. Produces evidence for the final review and the CURRENT_STATE entry (Task 5).

- [ ] **Step 1: Consistency unit suites** — Run:
  `pytest tests/unit/api/consistency/ tests/unit/core/agents/test_consistency_deps_relationships.py tests/unit/core/prompts/test_analysis_prompts.py -q`
  Expected: all pass, 0 failures.
- [ ] **Step 2: FIND-001 mutation proof** — Using the edit tool (no git restore): remove the exact line `        relationship_repo=relationship_repo,` from the `ConsistencyCheckerService(...)` construction in `apps/api/narrare/consistency/deps.py` (≈ line 135). Run `pytest tests/unit/api/consistency/test_deps_relationship_wiring.py -q` — Expected: **FAIL** (this proves the pin bites). Re-add the identical line via edit tool. Run again — Expected: PASS. Prove zero residue: `git diff --stat` empty, `git status --short` empty.
- [ ] **Step 3: Consistency integration suites** — Run:
  `pytest tests/integration/kb/test_router_consistency.py tests/integration/kb/test_kb_consistency_lazy_resolution.py -q`
  Expected: all pass.
- [ ] **Step 4: summary + chat suites** — Run:
  `pytest tests/integration/writing/test_summary_api.py tests/integration/chat/ -q`
  and `pytest tests/unit/api/writing/test_summary_router.py tests/unit/api/writing/test_summary_ownership.py -q`
  Expected: all pass.
- [ ] **Step 5: Remap `-O` safety** — Run both:
  `pytest tests/unit/core/planning/test_remap_degrade.py -q` and `python -O -m pytest tests/unit/core/planning/test_remap_degrade.py -q`
  Expected: both pass (the original defect was an assert that vanishes under `-O`).
- [ ] **Step 6: Chat single-fetch + WS title suites** — Run:
  `pytest tests/unit/api/chat/test_chat_kb_single_fetch.py tests/unit/api/kb/test_kb_context_provider.py tests/unit/api/writing/test_ws_turn_title_supply.py -q`
  Expected: all pass.
- [ ] **Step 7: Report** — Write per command: exact command, exit code, pass/fail counts, duration; for Step 2 also the RED assertion text and the clean-tree proof. Return only: status (DONE / BLOCKED), one-line summary per step, concerns.

### Task 3: httpx cross-catch guard — AST rewrite (TDD, test-only)

**Files:**
- Modify: `tests/unit/scripts/test_httpx_cross_catch_guard.py` (single file; no production code)
- Report: `<sdd-workspace>/task-3-report.md`

**Interfaces:**
- Keeps: `_find_cross_catch_violations(root: Path) -> list[str]` (finding format `cross-catch: <relpath>:<lineno>`), `_find_sdk_modules(root, scan_roots=...) -> set[Path]`, Rule 2 helpers (`_module_violations`, `_HTTP_CLIENT_ARG_RE`, `_BARE_HTTPX_CLIENT_CONSTRUCTION_RE`, `_find_http_client_violations`) unchanged.
- Consumes: stdlib `ast` only (no new dependencies).

- [ ] **Step 1: Write the failing tests first** — add these three tests:

```python
def test_rule1_detects_module_alias_cross_catch(tmp_path: Path) -> None:
    """``import httpx as hx`` + ``except hx.HTTPError:`` must be flagged (AST binding)."""
    module = tmp_path / "packages/core/fake_sdk_alias_module.py"
    module.parent.mkdir(parents=True)
    module.write_text(
        "import openai\nimport httpx as hx\n\n\ndef call() -> None:\n    try:\n        pass\n"
        "    except hx.HTTPError:\n        pass\n",
        encoding="utf-8",
    )
    assert _find_cross_catch_violations(tmp_path) == [
        "cross-catch: packages/core/fake_sdk_alias_module.py:8"
    ]


def test_rule1_detects_module_alias_tuple_catch(tmp_path: Path) -> None:
    """``except (hx.HTTPError, ValueError):`` after a module-alias import must be flagged."""
    module = tmp_path / "packages/core/fake_sdk_alias_tuple.py"
    module.parent.mkdir(parents=True)
    module.write_text(
        "import openai\nimport httpx as hx\n\n\ndef call() -> None:\n"
        "    try:\n        pass\n    except (hx.HTTPError, ValueError):\n        pass\n",
        encoding="utf-8",
    )
    assert _find_cross_catch_violations(tmp_path) == [
        "cross-catch: packages/core/fake_sdk_alias_tuple.py:7"
    ]


def test_rule1_ignores_docstring_only_sdk_mention(tmp_path: Path) -> None:
    """A docstring mention of ``import openai`` is not a real SDK import.

    Own-REST style module (real ``from httpx import`` + catch is legal there):
    the SDK-module classifier must consider real imports only, not prose.
    """
    module = tmp_path / "packages/core/fake_docstring_mention.py"
    module.parent.mkdir(parents=True)
    module.write_text(
        '"""Docs say: import openai somewhere else."""\n'
        "from httpx import HTTPError\n\n\n"
        "def call() -> None:\n    try:\n        pass\n    except HTTPError:\n        pass\n",
        encoding="utf-8",
    )
    assert _find_cross_catch_violations(tmp_path) == []
```

- [ ] **Step 2: Run them red** — `pytest tests/unit/scripts/test_httpx_cross_catch_guard.py -q` — Expected: the two `detects_*` tests FAIL (regex misses module aliases), `ignores_docstring_only` FAILS (regex over-flags). Capture output.
- [ ] **Step 3: Implement AST-based Rule 1 + SDK classifier** —
  - SDK detection: parse each candidate file with `ast.parse` (skip files that raise `SyntaxError`); real imports of roots `openai`, `anthropic`, `pydantic_ai` via `ast.Import` (incl. `as`-aliases and dotted names) and `ast.ImportFrom`. Docstring/comment mentions no longer count.
  - httpx bindings per module, two sets: module aliases (`import httpx` → `httpx`, `import httpx as hx` → `hx`) and from-import aliases (`from httpx import X [as Y]` → `Y`; ignore `*`). `httpx2` never matches because the module name differs.
  - Catch detection: walk `ast.Try.handlers`; flag a handler when its `type` expression is (a) `ast.Attribute` whose value is `ast.Name` in the module-alias set, or (b) `ast.Name` in the from-import alias set, or (c) an `ast.Tuple` containing either. Report `handler.lineno`.
  - Keep `_find_sdk_modules` signature/contract (the pairing pin test uses it). Delete now-unused regex helpers for Rule 1 only; keep Rule 2 regex path untouched.
  - Update the module docstring: Rule 1 is AST-based (alias-form coverage, no prose false-positives); Rule 2 remains the documented same-file regex heuristic.
- [ ] **Step 4: Run the full guard suite green** — `pytest tests/unit/scripts/test_httpx_cross_catch_guard.py -q` — Expected: ALL pass, including every pre-existing mutation test and the real-tree clean baselines (`test_rule1_clean_baseline`, `test_rule2_clean_baseline`, `test_own_rest_modules_are_not_sdk_modules`, `test_sole_http_client_site_uses_httpx2`).
- [ ] **Step 5: Adjacent regression check** — `pytest tests/unit/scripts/ -q` green.
- [ ] **Step 6: Self-review + report** — diff self-review (no stray debug code, docstring truthful, English throughout); write report with red/green evidence; return status + concerns. Do NOT commit (Platform commits after review).

### Task 4: Final whole-branch review (reviewer, edit: deny)

**Files:** none (review-only).

- [ ] **Step 1: Generate review package** for `c40810eb..HEAD` (merge base = program-completion commit) via `scripts/review-package`.
- [ ] **Step 2: Dispatch NarrareReviewerSpecialist** with the package path + binding constraints (this plan's Global Constraints; verification evidence from Task 2's report; ADR-086 lazy-resolution conventions: gate-before-resolution, 422-before-400, fakes at registry/agent seams).
- [ ] **Step 3: Handle findings** — Critical/Important → one fix dispatch (implementer) + scoped re-review; Minor → ledger with ruling. Load-bearing/unresolvable → STOP and report to the user.

### Task 5: CURRENT_STATE truth-fix (docs)

**Files:**
- Modify: `docs/_shared/CURRENT_STATE.md` (new top entry only)
- Commit via Platform: `docs(state): close 2026-09-29 open points with verification evidence`

- [ ] **Step 1: Write the new top entry (English)** — remediation wave `7a1b75c6..HEAD`: FIND-001 wiring restored + mutation-proven pin; summary+chat integration suites (+ 404 error-shape refinement); remap `-O`-safe None-degrade + pin; chat single-fetch KB bundle + partitioned `kb_other`; integration-conftest `sys.executable` PATH fix; WS title/genre supply; httpx guard Rule 1 now AST-based. Verification: Task 2 targeted-suite evidence + Task 4 review verdict. **Remaining open:** Dependabot triage (1 critical/1 high/2 moderate), CI billing-rot (PO action), httpx guard Rule 2 same-file limitation (documented), migration round-trip CI-fresh proof outstanding.
- [ ] **Step 2: Verify doc gate** — no other docs reference the now-closed items as open (grep `FIND-001|ohne Integration-Suites|AST-Lücke` outside history entries).

### Task 6: Push + PR (platform)

**Files:** none (git/gh only, via NarrarePlatformSpecialist).

- [ ] **Step 1: Commit Task 3's change** — `test(guard): ast-based httpx cross-catch detection` (hooks must run; never `--no-verify`).
- [ ] **Step 2: Push `bold-yak`** to origin.
- [ ] **Step 3: Open PR against `main`** — body: purpose, evidence summary (suite counts, mutation proof, review verdict), note that CI is billing-rot so local gates are the evidence of record.
