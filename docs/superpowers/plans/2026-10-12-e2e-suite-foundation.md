# E2E Suite Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the shared foundation of the full functional E2E suite (spec §3 mock catalog, §4 helpers package, §8 runner/env assertions, E01 smoke pin) so that eleven follow-on per-area spec plans can be written against stable primitives.

**Architecture:** A helpers package (`tests/e2e/helpers/`) consolidates the four recurring concerns — stable auth sessions (the class behind the current nightly failure), wizard/novel setup, AI mocking, and observation probes. A deterministic response catalog (`tests/e2e/mocks/catalog*.py`) intercepts validator-strict AI surfaces at the browser layer via `page.route()`, with every entry validated against the real pydantic schemas at session start (spec §10). The canonical runner gains a browser-presence preflight, a pytest-subset lever, and explicit E01 (AUTH_JWT_SECRET) guards; a fail-fast environment smoke spec pins the runtime behaviour.

**Tech Stack:** Python 3.14 · pytest + pytest-playwright (Playwright 1.61, sync API) · pydantic v2 (app schemas reused for fixture validation) · Bash (`scripts/run_e2e.sh`) · Markdown docs.

**Inputs:**
- Spec: `docs/superpowers/specs/2026-10-11-e2e-full-suite-design.md` (§3, §4, §8, §9, §10 are this plan's scope; §5 matrix = follow-on plans)
- Audit: `docs/superpowers/reports/2026-10-11-e2e-ui-audit.md` (E01, E02, E04, N06, N17 drive the foundation)
- Nightly run 38231495215 (pre-merge main): `tests/e2e/test_settings_persistence.py::test_settings_general_tab_renders[chromium]` FAILED — 30s wait on settings-tab nth(4) (5th tab) while only 4 rendered, mid-wait bounce to /login, `POST /auth/login` 401 "Invalid email or password"
- Existing suite: `tests/e2e/conftest.py`, `tests/e2e/test_helpers.py`, `tests/e2e/test_helpers_wizard.py`, `tests/e2e/http_session.py`, `tests/e2e/mocks/llm_responses.py`, `scripts/run_e2e.sh`

## Global Constraints

- **Project language is English** — code, comments, tests, commit messages, docs (exception: `packages/i18n` message files).
- **`docs/_shared/CONSTRAINTS.md` is the constitution** — load it before starting. Most relevant here: RULE-04 (modularize; one responsibility per file — the helpers package exists because of this), RULE-10 (tests mandatory — infra code for tests is still code), RULE-11 (no silent failures — every probe/validator fails with an actionable message), RULE-17 spirit (fixtures must mirror the real backend schemas — enforced by pydantic validation, not by hand), RULE-23 (no naked `# type: ignore`).
- **This plan changes NO product code.** Only test infra (`tests/e2e/`, `tests/unit/`), one script (`scripts/run_e2e.sh`), and docs. If a task discovers a product bug (expected in Task 9), it writes the red pin, stops, and routes the fix to the coordinator — never patches product code here.
- **Regression-first:** probes and session helpers must NOT mask regressions. No auto-healing sessions (a bounced login fails loudly with an actionable message), no retry-until-green inside assertions. The stable session is deterministic login state BEFORE the test body, not recovery during it.
- **No real LLM calls, ever** (spec §3): the suite runs under `NARRARE_E2E_TEST=1` (TestModel factory layer) + the browser-layer catalog for validator-strict surfaces; the smoke spec asserts the TestModel banner (`e2e_test_mode_active` in `logs/e2e-api.log`) and zero browser-side requests to provider hosts.
- **Task cap:** ≤ 3 implementation files and ≤ 250 new implementation LOC per task. In this plan the spec/helper files ARE the deliverable, so they are listed explicitly and do not count toward the caps; `scripts/run_e2e.sh` and `docs/` changes are implementation files and do count.
- **All registration goes through the UI** (PO ruling 2026-10-13): every user this plan's helpers/fixtures create — including `stable_user` — registers via the real `/register` form (fill form → `POST /auth/register` → auto-login), the audit-proven flow. No API-registration shortcut in new code; `login_via_api` only harvests tokens for an already-registered user. The pre-existing `register_unique_user` fixture (API path, consumed by today's spec files) predates this plan, stays untouched, and is not extended to new specs.
- **Conventional commits** (`test(e2e): …`, `chore(e2e): …`, `docs(testing): …`). **`git commit --no-verify` is FORBIDDEN.** Commits are made by the implementing session; pushes/tags go through NarrarePlatformSpecialist.
- **Layer tags** (first line of each task): `Platform` → NarrarePlatformSpecialist (test infra, runner, CI), `Docs` → NarrareDocsSpecialist. No Backend/Frontend/Core tasks exist in this plan by design.
- **Test commands:**
  - Unit (fast, no stack): `uv run --all-packages pytest tests/unit/test_e2e_probes.py tests/unit/test_e2e_mock_catalog.py tests/unit/test_e2e_llm_mocks.py -v -p no:randomly`
  - Full E2E (CI-faithful, starts+tears down the stack): `just e2e` — requires `docker compose -f docker-compose.dev.yml up -d postgres_test`
  - Targeted E2E (from Task 2 on): `E2E_PYTEST_ARGS="tests/e2e/<file>.py" just e2e`
- **Catalog contract (spec §10):** every catalog entry is validated against the real app pydantic model (or a structural SSE check where no envelope model exists) in a session-scoped conftest check AND in unit tests. UUID-typed fields get real UUIDs; enum-typed fields get real enum values.
- Line numbers quoted from the audit or source may be stale — each task re-verifies by semantic location in the current tree before editing.

## Capability → Task map

| Task | Layer | Deliverable |
|------|-------|-------------|
| 1 | Platform | `helpers/probes.py` — console/network capture + assertions, a11y dump |
| 2 | Platform | Runner hardening — browser-presence preflight, `E2E_PYTEST_ARGS`, E01 guards |
| 3 | Platform | `mocks/catalog.py` registry + `catalog_writing.py` (generation SSE, scene draft/refine) |
| 4 | Platform | `catalog_analysis.py` + `catalog_kb.py` (beta-reader, coreference, character-voice, consistency, extraction, improve, wiki) |
| 5 | Platform | `helpers/llm_mocks.py` — `mock_llm(page, capability, fixture=…)` |
| 6 | Platform | `helpers/audit_user.py` — register-through-UI + stable logged-in session (N06/nightly-failure class) |
| 7 | Platform | `helpers/novel_factory.py` — wizard completion (blank/demo/import) + volume/chapter API setup |
| 8 | Platform | conftest extension — catalog validation, env fail-fast checks, `stable_user`/`stable_novel` fixtures + environment smoke spec (E01 pin) |
| 9 | Platform | Nightly-failure triage — `test_settings_persistence.py` |
| 10 | Docs | `testing-standards.md` E2E section + `docs/development/e2e-coverage.md` skeleton |

---

### Task 1: Observation probes (`helpers/probes.py`)

**Layer:** Platform

**Files:**
- Create: `tests/e2e/helpers/__init__.py`
- Create: `tests/e2e/helpers/probes.py`
- Test: `tests/unit/test_e2e_probes.py` (new — unit tests of test-infra, precedent `tests/unit/test_e2e_http_session.py`)

**Interfaces:**
- Produces:
  - `PROVIDER_HOSTS: frozenset[str]` — LLM provider hostnames the browser must never call.
  - `capture_console(page: Page) -> ConsoleCapture` — attaches listeners; `ConsoleCapture.page_errors: list[str]`, `.console_errors: list[str]`, `.console_warnings: list[str]`, `.assert_no_page_errors(*, allow: tuple[str, ...] = ())`, `.assert_no_console_errors(*, allow: tuple[str, ...] = ())`.
  - `capture_network(page: Page) -> NetworkCapture` — attaches listeners; `NetworkCapture.api_failures: list[str]`, `.provider_calls: list[str]`, `.assert_no_provider_calls()`, `.assert_no_api_failures(*, allow_statuses: tuple[int, ...] = ())`.
  - `dump_a11y(page: Page, path: Path) -> Path` — writes the Playwright AXTree snapshot as JSON.
- `allow`/`allow_statuses` are substring/status filters for known-noisy cases; filtered entries stay recorded, they just don't fail the assertion.

- [ ] **Step 1: Write the failing unit tests**

Create `tests/unit/test_e2e_probes.py`:

```python
"""Unit tests for the E2E observation probes (tests/e2e/helpers/probes.py).

The probes are test-infra, but they carry assertions other specs rely on —
so they get the same regression discipline as product code. These tests run
WITHOUT a browser: a fake page records the listeners the probe attaches and
emits canned events through them.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tests.e2e.helpers.probes import (
    PROVIDER_HOSTS,
    capture_console,
    capture_network,
    dump_a11y,
)


class _FakeConsoleMessage:
    def __init__(self, type_: str, text: str) -> None:
        self.type = type_
        self.text = text


class _FakeRequest:
    def __init__(self, method: str, url: str) -> None:
        self.method = method
        self.url = url


class _FakeResponse:
    def __init__(self, request: _FakeRequest, url: str, status: int) -> None:
        self.request = request
        self.url = url
        self.status = status


class _FakePage:
    """Minimal Page stand-in: records .on() listeners, emits via .emit()."""

    def __init__(self) -> None:
        self.listeners: dict[str, list[Any]] = {}
        self.a11y_snapshot: dict[str, Any] | None = None

    def on(self, event: str, handler: Any) -> None:
        self.listeners.setdefault(event, []).append(handler)

    def emit(self, event: str, arg: Any) -> None:
        for handler in self.listeners.get(event, []):
            handler(arg)

    @property
    def accessibility(self) -> Any:
        page = self

        class _Accessibility:
            def snapshot(self, interesting_only: bool = True) -> Any:
                return page.a11y_snapshot

        return _Accessibility()


class TestConsoleCapture:
    def test_collects_page_and_console_errors_separately(self) -> None:
        page = _FakePage()
        capture = capture_console(page)  # type: ignore[arg-type]

        page.emit("pageerror", ValueError("boom"))
        page.emit("console", _FakeConsoleMessage("error", "api failed"))
        page.emit("console", _FakeConsoleMessage("warning", "deprecated"))

        assert capture.page_errors == ["boom"]
        assert capture.console_errors == ["api failed"]
        assert capture.console_warnings == ["deprecated"]

    def test_assert_no_page_errors_passes_with_allow_filter(self) -> None:
        page = _FakePage()
        capture = capture_console(page)  # type: ignore[arg-type]
        page.emit("pageerror", Exception("ResizeObserver loop limit exceeded"))

        capture.assert_no_page_errors(allow=("ResizeObserver",))  # not raised

        with pytest.raises(AssertionError, match="ResizeObserver"):
            capture.assert_no_page_errors()

    def test_assert_no_console_errors_empty_by_default(self) -> None:
        capture = capture_console(_FakePage())  # type: ignore[arg-type]
        capture.assert_no_console_errors()  # not raised


class TestNetworkCapture:
    def test_records_api_failures_with_status(self) -> None:
        page = _FakePage()
        capture = capture_network(page)  # type: ignore[arg-type]

        request = _FakeRequest("POST", "http://localhost:8000/api/v1/writing/generate")
        page.emit("response", _FakeResponse(request, request.url, 422))

        assert capture.api_failures == ["POST http://localhost:8000/api/v1/writing/generate → 422"]

    def test_ignores_successful_and_non_api_responses(self) -> None:
        page = _FakePage()
        capture = capture_network(page)  # type: ignore[arg-type]

        ok = _FakeRequest("GET", "http://localhost:8000/api/v1/novels")
        page.emit("response", _FakeResponse(ok, ok.url, 200))
        static = _FakeRequest("GET", "http://localhost:3000/_next/static/app.js")
        page.emit("response", _FakeResponse(static, static.url, 500))

        assert capture.api_failures == []

    def test_provider_calls_flagged_for_every_known_host(self) -> None:
        page = _FakePage()
        capture = capture_network(page)  # type: ignore[arg-type]

        for host in PROVIDER_HOSTS:
            page.emit("request", _FakeRequest("POST", f"https://{host}/v1/messages"))

        assert len(capture.provider_calls) == len(PROVIDER_HOSTS)
        with pytest.raises(AssertionError, match="real LLM provider"):
            capture.assert_no_provider_calls()

    def test_assert_no_api_failures_with_allowed_status(self) -> None:
        page = _FakePage()
        capture = capture_network(page)  # type: ignore[arg-type]

        request = _FakeRequest("GET", "http://localhost:8000/api/v1/health")
        page.emit("response", _FakeResponse(request, request.url, 503))

        capture.assert_no_api_failures(allow_statuses=(503,))  # not raised
        with pytest.raises(AssertionError, match="503"):
            capture.assert_no_api_failures()


class TestDumpA11y:
    def test_writes_snapshot_json(self, tmp_path: Path) -> None:
        page = _FakePage()
        page.a11y_snapshot = {"role": "WebArea", "children": [{"role": "heading"}]}

        out = dump_a11y(page, tmp_path / "a11y" / "login.json")  # type: ignore[arg-type]

        assert out.exists()
        assert json.loads(out.read_text(encoding="utf-8"))["role"] == "WebArea"
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run --all-packages pytest tests/unit/test_e2e_probes.py -v -p no:randomly`
Expected: FAIL — `ModuleNotFoundError: No module named 'tests.e2e.helpers'`. Record output.

- [ ] **Step 3: Implement the probes**

Create `tests/e2e/helpers/__init__.py`:

```python
"""Consolidated helper package for the E2E suite (spec §4).

One responsibility per module (RULE-04):
- probes       — console/network observation + a11y dumps
- llm_mocks    — mock_llm() installs catalog fixtures via page.route()
- audit_user   — registration-through-UI + stable logged-in sessions
- novel_factory— wizard completion + volume/chapter API setup
"""

from tests.e2e.helpers.probes import (
    PROVIDER_HOSTS,
    ConsoleCapture,
    NetworkCapture,
    capture_console,
    capture_network,
    dump_a11y,
)

__all__ = [
    "PROVIDER_HOSTS",
    "ConsoleCapture",
    "NetworkCapture",
    "capture_console",
    "capture_network",
    "dump_a11y",
]
```

Create `tests/e2e/helpers/probes.py`:

```python
"""Observation probes for E2E specs: console, network, accessibility.

Spec §4 (helpers package): probes.py owns every "what happened on the page
while the test ran" concern so specs assert instead of wiring listeners.

Scope note (spec §3): ``assert_no_provider_calls`` guards the BROWSER side —
the page's own requests must never reach an LLM provider host. The API side
is guaranteed by ``NARRARE_E2E_TEST=1`` (TestModel) and pinned by the
environment smoke spec via the ``e2e_test_mode_active`` startup banner.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from urllib.parse import urlparse

if TYPE_CHECKING:
    from pathlib import Path

    from playwright.sync_api import Page


#: LLM provider hosts the browser must never call (spec §3: no real LLM calls).
PROVIDER_HOSTS = frozenset(
    {
        "api.openai.com",
        "api.anthropic.com",
        "generativelanguage.googleapis.com",
        "api.groq.com",
        "openrouter.ai",
    }
)


@dataclass
class ConsoleCapture:
    """Collected console/page errors. Attach via :func:`capture_console`."""

    page_errors: list[str] = field(default_factory=list)
    console_errors: list[str] = field(default_factory=list)
    console_warnings: list[str] = field(default_factory=list)

    def assert_no_page_errors(self, *, allow: tuple[str, ...] = ()) -> None:
        """Fail on unfiltered page errors (RULE-11: loud, with the list)."""
        offending = [e for e in self.page_errors if not any(a in e for a in allow)]
        assert not offending, f"Page errors during test: {offending}"

    def assert_no_console_errors(self, *, allow: tuple[str, ...] = ()) -> None:
        """Fail on unfiltered console.error messages."""
        offending = [e for e in self.console_errors if not any(a in e for a in allow)]
        assert not offending, f"console.error during test: {offending}"


@dataclass
class NetworkCapture:
    """Collected API failures + provider leaks. Attach via :func:`capture_network`."""

    api_failures: list[str] = field(default_factory=list)
    provider_calls: list[str] = field(default_factory=list)

    def assert_no_provider_calls(self) -> None:
        """Fail on ANY browser-side LLM provider request (spec §3)."""
        assert not self.provider_calls, (
            "Browser made real LLM provider calls "
            f"(spec violation): {self.provider_calls}"
        )

    def assert_no_api_failures(self, *, allow_statuses: tuple[int, ...] = ()) -> None:
        """Fail on unfiltered >=400 API responses (recorded 'METHOD url → status')."""
        offending = [
            f
            for f in self.api_failures
            if int(f.rsplit("→ ", 1)[1]) not in allow_statuses
        ]
        assert not offending, f"API failures during test: {offending}"


def capture_console(page: Page) -> ConsoleCapture:
    """Attach console/pageerror listeners and return the collector."""
    capture = ConsoleCapture()
    page.on("pageerror", lambda err: capture.page_errors.append(str(err)))

    def _on_console(msg) -> None:  # noqa: ANN001 — Playwright ConsoleMessage
        if msg.type == "error":
            capture.console_errors.append(msg.text)
        elif msg.type == "warning":
            capture.console_warnings.append(msg.text)

    page.on("console", _on_console)
    return capture


def capture_network(page: Page) -> NetworkCapture:
    """Attach request/response listeners and return the collector."""
    capture = NetworkCapture()

    def _on_request(request) -> None:  # noqa: ANN001 — Playwright Request
        host = urlparse(request.url).hostname or ""
        if host in PROVIDER_HOSTS:
            capture.provider_calls.append(f"{request.method} {request.url}")

    def _on_response(response) -> None:  # noqa: ANN001 — Playwright Response
        if "/api/v1/" in response.url and response.status >= 400:
            capture.api_failures.append(
                f"{response.request.method} {response.url} → {response.status}"
            )

    page.on("request", _on_request)
    page.on("response", _on_response)
    return capture


def dump_a11y(page: Page, path: Path) -> Path:
    """Dump the Playwright AXTree snapshot to ``path`` as JSON; returns path."""
    snapshot = page.accessibility.snapshot(interesting_only=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    return path
```

- [ ] **Step 4: Run the tests to verify green**

Run: `uv run --all-packages pytest tests/unit/test_e2e_probes.py -v -p no:randomly`
Expected: ALL PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/e2e/helpers/__init__.py tests/e2e/helpers/probes.py tests/unit/test_e2e_probes.py
git commit -m "test(e2e): add observation probes (console/network/a11y) helper"
```

---

### Task 2: Runner hardening (browser preflight, subset lever, E01 guards)

**Layer:** Platform

**Files:**
- Modify: `scripts/run_e2e.sh` (env block ~line 85, preflight ~line 309-313, pytest invocation ~line 378-382)

**Interfaces:**
- Produces: `E2E_PYTEST_ARGS` env passthrough — `E2E_PYTEST_ARGS="tests/e2e/test_auth_flow.py" just e2e` runs a subset with the identical CI-faithful stack; default (`tests/e2e/`) is byte-for-byte today's invocation.
- Produces: `check_browser_present()` preflight — fails with remediation before any DB/service work when the pinned Playwright Chromium is missing or the cache drifted (audit: chromium-1243 cached vs pinned build).
- Produces: explicit `AUTH_JWT_SECRET` guard + comment (E01) — the export keeps its default but an empty override fails loudly.

**Root cause (2× why):**
- Why did the audit hit a browser-launch failure class? The Python `playwright` package (pinned 1.61.0 in `uv.lock`) expects one exact Chromium build under `~/.cache/ms-playwright/`; the machine had a different build cached. The runner checked Chromium's shared *libraries* (`check_browser_deps`) but never the *presence of the pinned binary*.
- Why was AUTH_JWT_SECRET implicit? `run_e2e.sh` exports it globally and both services inherit it — correct, but undocumented; the audit's standalone `pnpm dev` start (E01) showed the coupling is invisible until every navigation bounces to /login. The comment + guard + (Task 8) runtime pin make it a contract instead of an accident.

**Alternatives considered:**
1. Probe an actual headless launch for presence (chosen) — version-agnostic (no hardcoded build number that rots with each playwright bump); catches corrupt caches too; costs ~1-2s.
2. Check `~/.cache/ms-playwright/chromium-*` directory existence — needs the expected build number parsed out of the playwright package; brittle across versions.
3. No preflight, rely on pytest error — fails after DB migrate + service startup (wasted work, worse message).

- [ ] **Step 1: Add `check_browser_present` + call it**

In `scripts/run_e2e.sh`, directly below the `check_browser_deps()` function (before the `preflight_services` section), add:

```bash
# ---------------------------------------------------------------------------
# browser-presence preflight (audit risk: playwright cache drift)
# ---------------------------------------------------------------------------
check_browser_present() {
  # The Python playwright package (uv.lock) pins ONE exact Chromium build.
  # A stale/different cached build (audit: chromium-1243 cached vs the pinned
  # one) launches fine on libs but fails at binary resolve. Probe a real
  # headless launch — version-agnostic, catches corruption, ~1-2s.
  log "  browser presence: probing pinned Playwright Chromium launch"
  if ! ( cd "$REPO_ROOT" && uv run python - <<'PY'
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    browser.close()
PY
  ) >/dev/null 2>&1; then
    err "Playwright Chromium is missing or not launchable."
    cat >&2 <<'EOF'

   Install the exact build pinned by the Python playwright package:

     uv run playwright install chromium

   If a WRONG build lingers in the cache (audit saw chromium-1243 vs the
   pinned one), inspect and prune it first:

     ls ~/.cache/ms-playwright/
     uv run playwright install chromium --dry-run   # shows the expected build

   Then re-run:  just e2e
EOF
    return 1
  fi
  log "  browser present: pinned Chromium launches headless"
}
```

In the main flow, change the preflight block to (old lines `preflight_services` / `preflight_ports_free` / `check_browser_deps` stay, one line added):

```bash
preflight_services
preflight_ports_free
check_browser_deps
check_browser_present
```

- [ ] **Step 2: Guard + document AUTH_JWT_SECRET (E01)**

Replace the single line `export AUTH_JWT_SECRET=test-secret-key-not-for-production   # must match backend SECRET_KEY for JWT verify` with:

```bash
# E01 (2026-10-11 audit): the Next.js proxy (packages/web/proxy.ts) verifies
# the narrare_auth cookie with AUTH_JWT_SECRET ?? SECRET_KEY ?? dev-default.
# If the web process does NOT inherit this env (e.g. a standalone `pnpm dev`
# start), EVERY protected navigation bounces to /login. Both services below
# inherit this export; the guard fails loudly on an empty override, and
# tests/e2e/test_environment_smoke.py pins the runtime behaviour.
export AUTH_JWT_SECRET="${AUTH_JWT_SECRET:-test-secret-key-not-for-production}"   # must match backend SECRET_KEY for JWT verify
: "${AUTH_JWT_SECRET:?AUTH_JWT_SECRET must not be empty — proxy verify would bounce every navigation to /login (E01)}"
```

- [ ] **Step 3: Add the `E2E_PYTEST_ARGS` subset lever**

Replace the test invocation block (the log line, the `set +e`, and the pytest subshell) with:

```bash
# Subset lever for suite growth (spec §4): default is the full suite — the
# CI job's exact invocation. Override per run for triage or single-spec work:
#   E2E_PYTEST_ARGS="tests/e2e/test_settings_persistence.py" just e2e
E2E_PYTEST_ARGS="${E2E_PYTEST_ARGS:-tests/e2e/}"
log "Running E2E tests: pytest $E2E_PYTEST_ARGS -v -m e2e --timeout=300 --timeout-method=thread"
echo ""
# Temporarily disable `set -e` so pytest's exit code is captured, not swallowed.
set +e
# shellcheck disable=SC2086 — intentional word splitting: E2E_PYTEST_ARGS may carry multiple paths/options
( cd "$REPO_ROOT" && uv run pytest $E2E_PYTEST_ARGS -v -m e2e --timeout=300 --timeout-method=thread )
PYTEST_RC=$?
set -e
```

- [ ] **Step 4: Verify**

Run: `bash -n scripts/run_e2e.sh && shellcheck scripts/run_e2e.sh` (if shellcheck is unavailable, `bash -n` alone).
Expected: no syntax errors; shellcheck reports nothing new beyond the acknowledged SC2086 disable.
Then: `E2E_PYTEST_ARGS="tests/e2e/test_auth_flow.py" just e2e`
Expected: preflight logs `browser present: pinned Chromium launches headless`; the auth-flow spec file runs (subset) and passes; cleanup completes. Record the preflight log lines.

- [ ] **Step 5: Commit**

```bash
git add scripts/run_e2e.sh
git commit -m "chore(e2e): runner preflight for pinned browser, E01 guard, pytest subset lever"
```

---

### Task 3: Mock catalog core + writing surfaces

**Layer:** Platform

**Files:**
- Create: `tests/e2e/mocks/catalog.py` (registry + SSE structural check)
- Create: `tests/e2e/mocks/catalog_writing.py` (generation SSE happy/error, scene draft/refine)
- Test: `tests/unit/test_e2e_mock_catalog.py` (new)

**Interfaces:**
- Produces:
  - `RouteSpec` (frozen dataclass): `capability: str`, `variant: str` (`"happy" | "error"`), `pattern: str` (Playwright glob), `method: str`, `status: int = 200`, `content_type: str = "application/json"`, `body: str = ""`, `url_exclude: str | None = None`.
  - `CATALOG: list[RouteSpec]` — all entries from the `catalog_*` modules.
  - `entries_for(capability: str, variant: str) -> list[RouteSpec]`.
  - `assert_sse_body_wellformed(body: str) -> list[dict[str, object]]` — every `data:` line is JSON or `[DONE]`; terminal `[DONE]` required; returns parsed events.
  - `validate_catalog() -> None` — runs every module validator; raises with the failing capability/variant.
- Capabilities defined here: `generation_stream` (variants happy, error), `scene_draft` (happy), `scene_refine` (happy).
- Route decision (documented in the module): the generation **start** POST (`/writing/chapters/{id}/generate`) is NOT mocked — it creates a real request row so accept/reject keep working; only the stream GET is intercepted (that is where the validator-strict agent dies, audit E04).

- [ ] **Step 1: Write the failing unit tests**

Create `tests/unit/test_e2e_mock_catalog.py`:

```python
"""Unit tests for the E2E mock catalog (spec §3 + §10).

Every catalog entry must validate against the REAL app pydantic models —
this is the drift-ratchet the spec demands, runnable without a stack.
"""

from __future__ import annotations

import pytest

from tests.e2e.mocks.catalog import (
    CATALOG,
    assert_sse_body_wellformed,
    entries_for,
    validate_catalog,
)


class TestRegistry:
    def test_every_spec_has_body_pattern_and_capability(self) -> None:
        for spec in CATALOG:
            assert spec.body, f"{spec.capability}/{spec.variant}: empty body"
            assert spec.pattern.startswith("**/api/v1/"), spec.pattern
            assert spec.variant in {"happy", "error"}

    def test_entries_for_raises_on_unknown_capability(self) -> None:
        with pytest.raises(ValueError, match="Unknown capability"):
            entries_for("telepathy", "happy")

    def test_entries_for_raises_on_unknown_variant(self) -> None:
        with pytest.raises(ValueError, match="Unknown capability"):
            entries_for("generation_stream", "sad")


class TestSseWellformedness:
    def test_parses_events_and_requires_done_sentinel(self) -> None:
        body = 'data: {"text": "hi"}\n\ndata: [DONE]\n\n'
        events = assert_sse_body_wellformed(body)
        assert events == [{"text": "hi"}]

    def test_rejects_missing_done_sentinel(self) -> None:
        with pytest.raises(ValueError, match="missing terminal"):
            assert_sse_body_wellformed('data: {"text": "hi"}\n\n')

    def test_rejects_malformed_json_payload(self) -> None:
        with pytest.raises(ValueError):
            assert_sse_body_wellformed("data: {not json}\n\ndata: [DONE]\n\n")


class TestWritingEntries:
    def test_generation_stream_has_happy_and_error_variants(self) -> None:
        assert {s.variant for s in entries_for("generation_stream", "happy")} == {"happy"}
        assert {s.variant for s in entries_for("generation_stream", "error")} == {"error"}

    def test_generation_happy_stream_is_final_and_done_terminated(self) -> None:
        spec = entries_for("generation_stream", "happy")[0]
        assert spec.method == "GET"
        assert spec.content_type == "text/event-stream"
        events = assert_sse_body_wellformed(spec.body)
        assert events[0]["type"] == "context_meta"
        assert any(e.get("is_final") is True for e in events)

    def test_scene_fixtures_validate_against_real_models(self) -> None:
        validate_catalog()  # full ratchet; writing part asserted here by absence of raise
        happy = {s.capability: s for s in CATALOG if s.variant == "happy"}
        assert "scene_draft" in happy
        assert "scene_refine" in happy
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run --all-packages pytest tests/unit/test_e2e_mock_catalog.py -v -p no:randomly`
Expected: FAIL — `ModuleNotFoundError` / `ImportError` for `tests.e2e.mocks.catalog`. Record output.

- [ ] **Step 3: Implement the registry and writing catalog**

Create `tests/e2e/mocks/catalog.py`:

```python
"""Deterministic AI-response catalog for the E2E suite (spec §3, §10).

Browser-layer mocks: one valid response per validator-strict AI surface,
installed via ``page.route()`` by ``tests/e2e/helpers/llm_mocks.mock_llm``.
The factory layer (``NARRARE_E2E_TEST=1`` → pydantic_ai.TestModel) stays
active for everything NOT intercepted here (audit E04: TestModel is
insufficient exactly for these surfaces).

Contract (spec §10 — drift ratchet):
- JSON bodies validate against the REAL app pydantic model (module
  ``validate()`` functions below run in unit tests AND at session start
  from tests/e2e/conftest.py).
- SSE bodies are structurally checked (every ``data:`` line JSON-or-[DONE],
  terminal [DONE]) and event envelopes validate against their stream-event
  model where one exists.
- UUID-typed response fields carry REAL UUIDs (pydantic rejects fakes).

Route-handler interplay: handlers installed by mock_llm use
``route.fallback()`` on method mismatch or url_exclude hit, so they compose
with the auth-proxy route (``**/api/v1/**``) installed by session fixtures
regardless of registration order.
"""

from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass(frozen=True)
class RouteSpec:
    """One deterministic browser-layer response for an AI surface."""

    capability: str
    variant: str  # "happy" | "error"
    pattern: str  # Playwright glob matched against the full URL
    method: str  # "GET" | "POST"
    status: int = 200
    content_type: str = "application/json"
    body: str = ""
    url_exclude: str | None = None  # handler falls back when this is in the URL


def assert_sse_body_wellformed(body: str) -> list[dict[str, object]]:
    """Structural SSE check: JSON-or-[DONE] data lines + terminal [DONE]."""
    events: list[dict[str, object]] = []
    saw_done = False
    for raw_line in body.splitlines():
        if not raw_line.startswith("data: "):
            continue
        payload = raw_line[len("data: ") :]
        if payload == "[DONE]":
            saw_done = True
            continue
        events.append(json.loads(payload))
    if not saw_done:
        raise ValueError("SSE body missing terminal 'data: [DONE]'")
    return events


def entries_for(capability: str, variant: str) -> list[RouteSpec]:
    """All specs for one capability+variant; raises listing known names."""
    specs = [s for s in CATALOG if s.capability == capability and s.variant == variant]
    if not specs:
        known = sorted({f"{s.capability}/{s.variant}" for s in CATALOG})
        raise ValueError(
            f"Unknown capability/variant: {capability!r}/{variant!r}. Known: {known}"
        )
    return specs


def _concat_catalogs() -> list[RouteSpec]:
    from tests.e2e.mocks import catalog_analysis, catalog_kb, catalog_writing

    return [
        *catalog_writing.SPECS,
        *catalog_analysis.SPECS,
        *catalog_kb.SPECS,
    ]


def validate_catalog() -> None:
    """Run every module validator (spec §10 drift ratchet). Raises loudly."""
    from tests.e2e.mocks import catalog_analysis, catalog_kb, catalog_writing

    for module_name, validate in (
        ("catalog_writing", catalog_writing.validate),
        ("catalog_analysis", catalog_analysis.validate),
        ("catalog_kb", catalog_kb.validate),
    ):
        try:
            validate()
        except Exception as exc:  # noqa: BLE001 — re-raise with catalog context
            raise RuntimeError(f"Mock catalog validation failed in {module_name}: {exc}") from exc
    # SSE capabilities must ship an error variant (spec §3: failure-path
    # tests). Capabilities with no specs yet (stubs during catalog growth)
    # are skipped — the check arms itself as entries land.
    for capability in (
        "generation_stream",
        "coreference_stream",
        "character_voice_stream",
        "consistency_stream",
    ):
        variants = {s.variant for s in CATALOG if s.capability == capability}
        if not variants:
            continue
        assert {"happy", "error"} <= variants, (
            f"{capability}: SSE capabilities need happy+error variants, has {variants}"
        )


# Imported lazily above to avoid import cycles at module import time.
CATALOG: list[RouteSpec] = _concat_catalogs()
```

Create `tests/e2e/mocks/catalog_writing.py`:

```python
"""Writing-surface catalog entries: generation SSE + scene draft/refine.

Wire formats mirror the REAL endpoints (verified 2026-10-12):
- GET  /api/v1/writing/generation/{request_id}/stream — SSE:
  optional ``{"type": "context_meta", ...}`` first, then
  ``{"text": ...}`` chunks, final chunk carries ``is_final`` + ``usage``,
  terminated by ``data: [DONE]`` (apps/api/narrare/writing/router.py).
  The START POST is NOT mocked — the real backend creates the request row
  so accept/reject keep working; only the stream is deterministic.
- POST /api/v1/planning/scenes/{novel_id}/{chapter_id}/draft|refine — JSON
  (apps/api/narrare/planning/schemas_scenes.py).
"""

from __future__ import annotations

import json

from tests.e2e.mocks.catalog import RouteSpec, assert_sse_body_wellformed


def _sse(*events: str) -> str:
    return "".join(f"data: {event}\n\n" for event in events) + "data: [DONE]\n\n"


GENERATION_HAPPY_SSE = _sse(
    json.dumps({"type": "context_meta", "source": "e2e-mock", "word_count": 1420}),
    json.dumps({"text": "The harbour bell rang twice before dawn, "}),
    json.dumps({"text": "and Elara counted the strikes the way her mother had taught her."}),
    json.dumps(
        {
            "text": "Two strikes meant the tide gate would seal within the hour.",
            "is_final": True,
            "usage": {"prompt_tokens": 210, "completion_tokens": 48, "total_tokens": 258},
        }
    ),
)

GENERATION_ERROR_BODY = json.dumps({"detail": "e2e-mock: generation provider stream died"})

_SCENE_PROPOSAL = {
    "title": "Arrival at the Harbour Gate",
    "pov_character_ref": None,
    "location_ref": None,
    "present_characters": [],
    "purpose": "Establish Elara's deadline and the sealed gate.",
    "conflict": "The gatekeeper refuses passage without a writ.",
    "resolution": "Elara trades her mother's ring for a forged writ.",
    "beats": [
        "Elara arrives at dawn",
        "The gatekeeper bars the way",
        "The ring changes hands",
    ],
}

SCENE_DRAFT_HAPPY = json.dumps(
    {
        "proposals": [
            _SCENE_PROPOSAL,
            {
                "title": "The Forged Writ",
                "pov_character_ref": None,
                "location_ref": None,
                "present_characters": [],
                "purpose": "Show the cost of Elara's bargain.",
                "conflict": "The forgery names an authority the chapter never introduces.",
                "resolution": "Elara pockets the writ unanswered.",
                "beats": ["The gatekeeper studies the seal", "Elara lies about the seal's origin"],
            },
        ],
        "ai_unavailable": False,
    }
)

SCENE_REFINE_HAPPY = json.dumps({"proposal": _SCENE_PROPOSAL, "ai_unavailable": False})


SPECS: tuple[RouteSpec, ...] = (
    RouteSpec(
        capability="generation_stream",
        variant="happy",
        pattern="**/api/v1/writing/generation/*/stream",
        method="GET",
        content_type="text/event-stream",
        body=GENERATION_HAPPY_SSE,
    ),
    RouteSpec(
        capability="generation_stream",
        variant="error",
        pattern="**/api/v1/writing/generation/*/stream",
        method="GET",
        status=500,
        body=GENERATION_ERROR_BODY,
    ),
    RouteSpec(
        capability="scene_draft",
        variant="happy",
        pattern="**/api/v1/planning/scenes/*/*/draft",
        method="POST",
        body=SCENE_DRAFT_HAPPY,
    ),
    RouteSpec(
        capability="scene_refine",
        variant="happy",
        pattern="**/api/v1/planning/scenes/*/*/refine",
        method="POST",
        body=SCENE_REFINE_HAPPY,
    ),
)


def validate() -> None:
    """Spec §10 ratchet: scene JSONs validate against the real models; SSE is well-formed."""
    from narrare.planning.schemas_scenes import SceneDraftResponse, SceneRefineResponse

    SceneDraftResponse.model_validate_json(SCENE_DRAFT_HAPPY)
    SceneRefineResponse.model_validate_json(SCENE_REFINE_HAPPY)

    happy = SPECS[0]
    events = assert_sse_body_wellformed(happy.body)
    assert events[0]["type"] == "context_meta", "generation SSE must open with context_meta"
    assert any(e.get("is_final") is True for e in events), "missing is_final chunk"
```

Note: `catalog_analysis`/`catalog_kb` do not exist yet — `catalog.CATALOG` and `validate_catalog()` will raise `ModuleNotFoundError` until Task 4. That is expected; the Task 3 unit run scopes to the tests that pass (`TestSseWellformedness`, and `TestWritingEntries` partially). To keep the task green on its own, add the two modules as minimal stubs in this task's commit? **No** — instead create them as empty registries NOW (three lines each) and grow them in Task 4:

Create `tests/e2e/mocks/catalog_analysis.py`:

```python
"""Analysis-surface catalog entries (grown in the next task)."""

from __future__ import annotations

from tests.e2e.mocks.catalog import RouteSpec

SPECS: tuple[RouteSpec, ...] = ()


def validate() -> None:
    """Spec §10 ratchet — populated with the entries."""
```

Create `tests/e2e/mocks/catalog_kb.py`:

```python
"""KB/wiki-surface catalog entries (grown in the next task)."""

from __future__ import annotations

from tests.e2e.mocks.catalog import RouteSpec

SPECS: tuple[RouteSpec, ...] = ()


def validate() -> None:
    """Spec §10 ratchet — populated with the entries."""
```

(Task 4 replaces these stubs in full — they exist so `CATALOG` imports and this task commits green.)

- [ ] **Step 4: Run the tests to verify green**

Run: `uv run --all-packages pytest tests/unit/test_e2e_mock_catalog.py tests/unit/test_e2e_probes.py -v -p no:randomly`
Expected: ALL PASS (the SSE-capability error-variant assertion inside `validate_catalog` is satisfied by generation_stream; the other three capabilities are checked once Task 4 lands them — `TestWritingEntries.test_scene_fixtures_validate_against_real_models` calls `validate_catalog()` which currently sees only writing specs with error variants).

- [ ] **Step 5: Commit**

```bash
git add tests/e2e/mocks/catalog.py tests/e2e/mocks/catalog_writing.py tests/e2e/mocks/catalog_analysis.py tests/e2e/mocks/catalog_kb.py tests/unit/test_e2e_mock_catalog.py
git commit -m "test(e2e): mock catalog registry + writing-surface fixtures"
```

---

### Task 4: Mock catalog — analysis, KB, and wiki surfaces

**Layer:** Platform

**Files:**
- Modify: `tests/e2e/mocks/catalog_analysis.py` (replace stub)
- Modify: `tests/e2e/mocks/catalog_kb.py` (replace stub)
- Test: `tests/unit/test_e2e_mock_catalog.py` (extend)

**Interfaces:**
- Produces capabilities: `beta_reader` (happy; excludes `/deep-dive`), `coreference_stream` (happy, error), `character_voice_stream` (happy, error), `consistency_stream` (happy, error), `consistency_check` (happy JSON; excludes `/stream`), `kb_extraction` (happy; excludes `/extract/bulk`), `kb_improve` (happy; excludes `/improve/apply`), `wiki_refresh` (happy).
- Event envelopes validate against `narrare.analysis.schemas_coreference.CoreferenceStreamEvent`, `narrare.analysis.schemas_character_voice.CharacterVoiceStreamEvent`; result payloads against `narrare.consistency.schemas.ConsistencyResponse` + `narrare.consistency.stage_schemas.ConsistencyStageEvent`, `narrare.analysis.schemas.BetaReaderResponse`, `narrare_core.agents.extraction_types.ExtractionOutput`, `narrare.kb.improve_contracts.KBImproveAnalysisResponse`, `narrare.wiki.schemas.WikiRefreshResponse`.

- [ ] **Step 1: Write the failing unit tests (extend)**

Append to `tests/unit/test_e2e_mock_catalog.py`:

```python
class TestAnalysisEntries:
    def test_coreference_happy_envelope_validates_against_real_model(self) -> None:
        from narrare.analysis.schemas_coreference import CoreferenceStreamEvent

        spec = entries_for("coreference_stream", "happy")[0]
        events = assert_sse_body_wellformed(spec.body)
        for event in events:
            CoreferenceStreamEvent.model_validate(event)
        assert events[-1]["event"] == "done"

    def test_character_voice_happy_has_progress_result_done(self) -> None:
        from narrare.analysis.schemas_character_voice import CharacterVoiceStreamEvent

        spec = entries_for("character_voice_stream", "happy")[0]
        events = assert_sse_body_wellformed(spec.body)
        for event in events:
            CharacterVoiceStreamEvent.model_validate(event)
        kinds = [e["event"] for e in events]
        assert kinds[0] == "progress"
        assert kinds.count("result") >= 1
        assert kinds[-1] == "done"

    def test_beta_reader_fixture_validates_and_excludes_deep_dive(self) -> None:
        spec = entries_for("beta_reader", "happy")[0]
        assert spec.url_exclude == "/deep-dive"
        from narrare.analysis.schemas import BetaReaderResponse

        BetaReaderResponse.model_validate_json(spec.body)

    def test_consistency_result_validates_and_stream_excluded_from_check(self) -> None:
        json_spec = entries_for("consistency_check", "happy")[0]
        assert json_spec.url_exclude == "/stream"
        from narrare.consistency.schemas import ConsistencyResponse

        ConsistencyResponse.model_validate_json(json_spec.body)

        sse_spec = entries_for("consistency_stream", "happy")[0]
        events = assert_sse_body_wellformed(sse_spec.body)
        assert events[0]["type"] == "stage"
        assert events[-1]["type"] == "result"


class TestKbWikiEntries:
    def test_extraction_and_improve_exclude_sibling_routes(self) -> None:
        assert entries_for("kb_extraction", "happy")[0].url_exclude == "/extract/bulk"
        assert entries_for("kb_improve", "happy")[0].url_exclude == "/improve/apply"

    def test_full_catalog_validates(self) -> None:
        validate_catalog()
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run --all-packages pytest tests/unit/test_e2e_mock_catalog.py -v -p no:randomly`
Expected: FAIL — `entries_for("coreference_stream", …)` raises Unknown capability. Record output.

- [ ] **Step 3: Implement the two catalog modules**

Replace `tests/e2e/mocks/catalog_analysis.py` in full:

```python
"""Analysis-surface catalog entries (spec §3: validator-strict AI surfaces).

Wire formats mirror the REAL endpoints (verified 2026-10-12):
- POST /api/v1/analysis/beta-reader?novel_id=… — JSON BetaReaderResponse
  (deep-dive is a sibling route and explicitly excluded here).
- POST /api/v1/analysis/coreference/{chapter_id} — SSE envelope events
  ``{"event": "result"|"done"|"error", …}`` + [DONE].
- POST /api/v1/analysis/character-voice/{novel_id} — SSE envelope events
  ``progress`` / one ``result`` per character / ``done``.
- POST /api/v1/consistency/check/stream?novel_id=… — SSE events
  ``{"type": "stage", …}`` then ``{"type": "result", …}`` + [DONE];
  the non-stream POST /consistency/check answers JSON directly.
Severity/category enums are REAL values (FeedbackSeverity/FeedbackCategory).
"""

from __future__ import annotations

import json

from tests.e2e.mocks.catalog import RouteSpec, assert_sse_body_wellformed


def _sse(*events: str) -> str:
    return "".join(f"data: {event}\n\n" for event in events) + "data: [DONE]\n\n"


BETA_READER_HAPPY = json.dumps(
    {
        "novel_id": "e2e-mock-novel",
        "chapter_ids": ["e2e-mock-chapter"],
        "total_word_count": 1024,
        "strengths": [
            {
                "category": "character",
                "title": "Elara's motivation is concrete",
                "description": "The ring trade ties her goal to a visible cost.",
                "text_excerpt": "the way her mother had taught her",
            }
        ],
        "feedback": [
            {
                "category": "pacing",
                "severity": "minor",
                "location": "paragraph 3",
                "title": "Gatekeeper exchange rushes the turn",
                "description": "The refusal flips to acceptance within two lines.",
                "suggestion": "Let Elara's first offer fail before the ring appears.",
                "text_excerpt": None,
            }
        ],
        "questions": [
            {
                "category": "plot",
                "location": "paragraph 5",
                "question": "Who issued the sealed writ Elara forges?",
                "context": "The forgery implies an authority the chapter never names.",
            }
        ],
        "overall": {
            "summary": "A focused opening scene with one clear objective.",
            "reader_engagement": 7,
            "emotional_impact": 6,
            "pacing_score": 6,
            "prose_quality": 7,
            "plot_progression": 6,
            "character_development": 7,
        },
        "analyzed_at": "2026-10-12T00:00:00Z",
        "cache_key": "e2e-mock-cache-key",
    }
)

_COREFERENCE_RESULT = {
    "chapter_id": "00000000-0000-0000-0000-0000000000c1",
    "clarity_score": 92.0,
    "summary": "Pronoun use is unambiguous; one speaker chain stays clear.",
    "resolutions": [
        {
            "pronoun": "she",
            "position": 14,
            "referent": "Elara",
            "confidence": 0.96,
            "is_ambiguous": False,
        }
    ],
    "character_mentions": [
        {"character_name": "Elara", "mentions": [0, 14], "is_pov": True}
    ],
}

COREFERENCE_HAPPY_SSE = _sse(
    json.dumps({"event": "result", "result": _COREFERENCE_RESULT}),
    json.dumps({"event": "done", "is_final": True}),
)
COREFERENCE_ERROR_SSE = _sse(
    json.dumps(
        {"event": "error", "error": "e2e-mock: coreference agent failed", "is_final": True}
    ),
)

_CHARACTER_VOICE_RESULT = {
    "character_name": "Elara",
    "voice_analysis": {
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
    },
    "distinctiveness_notes": "Clipped countdown speech unlike the gatekeeper's formality.",
    "kb_entry_id": "00000000-0000-0000-0000-0000000000b1",
}

CHARACTER_VOICE_HAPPY_SSE = _sse(
    json.dumps({"event": "progress", "progress": "Found 1 speaking character"}),
    json.dumps({"event": "result", "result": _CHARACTER_VOICE_RESULT}),
    json.dumps({"event": "done", "is_final": True}),
)
CHARACTER_VOICE_ERROR_SSE = _sse(
    json.dumps(
        {
            "event": "error",
            "error": "e2e-mock: character-voice agent failed",
            "is_final": True,
        }
    ),
)

_CONSISTENCY_RESULT = {
    "novel_id": "00000000-0000-0000-0000-0000000000a1",
    "chapter_ids": ["00000000-0000-0000-0000-0000000000c1"],
    "check_types": ["timeline", "character"],
    "issues": [],
    "overall_assessment": "Consistent",
    "analyzed_at": "2026-10-12T00:00:00Z",
}

CONSISTENCY_HAPPY_SSE = _sse(
    json.dumps(
        {
            "type": "stage",
            "stage": "extracting_facts",
            "status": "start",
            "message": "Extracting facts",
        }
    ),
    json.dumps(
        {
            "type": "stage",
            "stage": "cross_checking",
            "status": "complete",
            "message": "Cross-checking facts",
        }
    ),
    json.dumps({"type": "result", **_CONSISTENCY_RESULT}),
)
CONSISTENCY_ERROR_SSE = _sse(
    json.dumps(
        {
            "type": "error",
            "error": "e2e-mock: consistency pipeline failed",
            "is_final": True,
        }
    ),
)

SPECS: tuple[RouteSpec, ...] = (
    RouteSpec(
        capability="beta_reader",
        variant="happy",
        pattern="**/api/v1/analysis/beta-reader*",
        method="POST",
        body=BETA_READER_HAPPY,
        url_exclude="/deep-dive",
    ),
    RouteSpec(
        capability="coreference_stream",
        variant="happy",
        pattern="**/api/v1/analysis/coreference/*",
        method="POST",
        content_type="text/event-stream",
        body=COREFERENCE_HAPPY_SSE,
    ),
    RouteSpec(
        capability="coreference_stream",
        variant="error",
        pattern="**/api/v1/analysis/coreference/*",
        method="POST",
        content_type="text/event-stream",
        body=COREFERENCE_ERROR_SSE,
    ),
    RouteSpec(
        capability="character_voice_stream",
        variant="happy",
        pattern="**/api/v1/analysis/character-voice/*",
        method="POST",
        content_type="text/event-stream",
        body=CHARACTER_VOICE_HAPPY_SSE,
    ),
    RouteSpec(
        capability="character_voice_stream",
        variant="error",
        pattern="**/api/v1/analysis/character-voice/*",
        method="POST",
        content_type="text/event-stream",
        body=CHARACTER_VOICE_ERROR_SSE,
    ),
    RouteSpec(
        capability="consistency_stream",
        variant="happy",
        pattern="**/api/v1/consistency/check/stream*",
        method="POST",
        content_type="text/event-stream",
        body=CONSISTENCY_HAPPY_SSE,
    ),
    RouteSpec(
        capability="consistency_stream",
        variant="error",
        pattern="**/api/v1/consistency/check/stream*",
        method="POST",
        content_type="text/event-stream",
        body=CONSISTENCY_ERROR_SSE,
    ),
    RouteSpec(
        capability="consistency_check",
        variant="happy",
        pattern="**/api/v1/consistency/check*",
        method="POST",
        body=json.dumps(_CONSISTENCY_RESULT),
        url_exclude="/stream",
    ),
)


def validate() -> None:
    """Spec §10 ratchet against the real app models."""
    from narrare.analysis.schemas import BetaReaderResponse
    from narrare.analysis.schemas_character_voice import CharacterVoiceStreamEvent
    from narrare.analysis.schemas_coreference import CoreferenceStreamEvent
    from narrare.consistency.schemas import ConsistencyResponse
    from narrare.consistency.stage_schemas import ConsistencyStageEvent

    BetaReaderResponse.model_validate_json(BETA_READER_HAPPY)
    ConsistencyResponse.model_validate_json(json.dumps(_CONSISTENCY_RESULT))

    for body in (COREFERENCE_HAPPY_SSE, COREFERENCE_ERROR_SSE):
        for event in assert_sse_body_wellformed(body):
            CoreferenceStreamEvent.model_validate(event)
    for body in (CHARACTER_VOICE_HAPPY_SSE, CHARACTER_VOICE_ERROR_SSE):
        for event in assert_sse_body_wellformed(body):
            CharacterVoiceStreamEvent.model_validate(event)

    for event in assert_sse_body_wellformed(CONSISTENCY_HAPPY_SSE):
        payload = {k: v for k, v in event.items() if k != "type"}
        if event["type"] == "stage":
            ConsistencyStageEvent.model_validate(payload)
        else:
            ConsistencyResponse.model_validate(payload)
```

Replace `tests/e2e/mocks/catalog_kb.py` in full:

```python
"""KB + wiki catalog entries (spec §3: validator-strict AI surfaces).

Wire formats mirror the REAL endpoints (verified 2026-10-12):
- POST /api/v1/novels/{id}/kb/extract/{chapter_id} — ExtractionOutput JSON
  (bulk extract lives at /kb/extract/bulk… and is excluded).
- POST /api/v1/novels/{id}/kb/entities/{entry_id}/improve —
  KBImproveAnalysisResponse JSON (…/improve/apply excluded).
- POST /api/v1/novels/{id}/wiki/summaries/{summary_id}/refresh —
  WikiRefreshResponse JSON (summary_id is UUID-typed: real UUID required).
"""

from __future__ import annotations

import json

from tests.e2e.mocks.catalog import RouteSpec


KB_EXTRACTION_HAPPY = json.dumps(
    {
        "results": [
            {
                "item_type": "new_entity",
                "entity_type": "character",
                "name": "Elara Thornwind",
                "confidence": 0.93,
                "source_text": "Elara counted the strikes the way her mother had taught her.",
                "proposed_content": {
                    "summary": "Counts bell strikes; keeps her mother's ring."
                },
            },
            {
                "item_type": "relationship",
                "name": "Elara → Gatekeeper",
                "confidence": 0.81,
                "source_text": "Elara trades her mother's ring for a forged writ.",
                "relationship_type": "bargains_with",
                "source_entity_name": "Elara Thornwind",
                "target_entity_name": "Gatekeeper",
            },
        ],
        "analysis_notes": "Two clear entities and one transactional relationship.",
    }
)

KB_IMPROVE_HAPPY = json.dumps(
    {
        "suggestions": [
            {
                "type": "expand",
                "target": "body",
                "description": "Anchor Elara's goal in the opening line.",
                "proposed_content": "Elara needs passage before the second bell seals the tide gate.",
                "related_entity_id": None,
                "related_entity_name": None,
                "confidence": 0.88,
                "reasoning": "The entry states urgency without a deadline.",
                "suggestion_id": 0,
            },
            {
                "type": "connect",
                "target": "Gatekeeper",
                "description": "Link the bargained ring to the Thornwind heirloom.",
                "proposed_content": None,
                "related_entity_id": "00000000-0000-0000-0000-0000000000b2",
                "related_entity_name": "Gatekeeper",
                "confidence": 0.74,
                "reasoning": "The ring trade creates a provenance edge.",
                "suggestion_id": 1,
            },
        ],
        "overall_assessment": "Solid scaffold; the entry needs one concrete goal.",
        "completeness_score": 0.62,
    }
)

WIKI_REFRESH_HAPPY = json.dumps(
    {
        "summary_id": "00000000-0000-0000-0000-0000000000d1",
        "status": "refreshed",
        "message": "Summary regenerated from 3 chapters.",
    }
)

SPECS: tuple[RouteSpec, ...] = (
    RouteSpec(
        capability="kb_extraction",
        variant="happy",
        pattern="**/api/v1/novels/*/kb/extract/*",
        method="POST",
        body=KB_EXTRACTION_HAPPY,
        url_exclude="/extract/bulk",
    ),
    RouteSpec(
        capability="kb_improve",
        variant="happy",
        pattern="**/api/v1/novels/*/kb/entities/*/improve*",
        method="POST",
        body=KB_IMPROVE_HAPPY,
        url_exclude="/improve/apply",
    ),
    RouteSpec(
        capability="wiki_refresh",
        variant="happy",
        pattern="**/api/v1/novels/*/wiki/summaries/*/refresh",
        method="POST",
        body=WIKI_REFRESH_HAPPY,
    ),
)


def validate() -> None:
    """Spec §10 ratchet against the real app/core models."""
    from narrare.kb.improve_contracts import KBImproveAnalysisResponse
    from narrare.wiki.schemas import WikiRefreshResponse
    from narrare_core.agents.extraction_types import ExtractionOutput

    ExtractionOutput.model_validate_json(KB_EXTRACTION_HAPPY)
    KBImproveAnalysisResponse.model_validate_json(KB_IMPROVE_HAPPY)
    WikiRefreshResponse.model_validate_json(WIKI_REFRESH_HAPPY)
```

- [ ] **Step 4: Run the tests to verify green**

Run: `uv run --all-packages pytest tests/unit/test_e2e_mock_catalog.py -v -p no:randomly`
Expected: ALL PASS, including `test_full_catalog_validates`.

- [ ] **Step 5: Commit**

```bash
git add tests/e2e/mocks/catalog_analysis.py tests/e2e/mocks/catalog_kb.py tests/unit/test_e2e_mock_catalog.py
git commit -m "test(e2e): catalog fixtures for analysis, KB, and wiki surfaces"
```

---

### Task 5: `mock_llm()` installer (`helpers/llm_mocks.py`)

**Layer:** Platform

**Files:**
- Create: `tests/e2e/helpers/llm_mocks.py`
- Modify: `tests/e2e/helpers/__init__.py` (re-export `mock_llm`)
- Test: `tests/unit/test_e2e_llm_mocks.py` (new)

**Interfaces:**
- Produces: `mock_llm(page: Page, capability: str, *, fixture: str = "happy") -> list[RouteSpec]` — installs one `page.route` handler per catalog spec of that capability+variant; raises `ValueError` listing known capability/variants for unknown names (fail-loud, RULE-11). Handlers `fulfill` on method match and no `url_exclude` hit, else `fallback()` — composing with the auth-proxy route regardless of registration order (Playwright routes are LIFO; fallback chains to the next matching handler).

- [ ] **Step 1: Write the failing unit tests**

Create `tests/unit/test_e2e_llm_mocks.py`:

```python
"""Unit tests for mock_llm() — catalog → page.route installation (no browser).

A fake page records route handlers; a fake route verifies dispatch:
method match + url_exclude respected + fallback otherwise.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from tests.e2e.helpers.llm_mocks import mock_llm
from tests.e2e.mocks.catalog import entries_for


class _FakeRoute:
    def __init__(self, method: str, url: str) -> None:
        self.request = SimpleNamespace(method=method, url=url)
        self.fulfilled: dict[str, Any] | None = None
        self.fell_back = False

    def fulfill(self, **kwargs: Any) -> None:
        self.fulfilled = kwargs

    def fallback(self) -> None:
        self.fell_back = True


class _FakePage:
    def __init__(self) -> None:
        self.routes: list[tuple[str, Any]] = []

    def route(self, pattern: str, handler: Any) -> None:
        self.routes.append((pattern, handler))


class TestMockLlm:
    def test_installs_one_handler_per_catalog_spec(self) -> None:
        page = _FakePage()
        specs = mock_llm(page, "kb_improve", fixture="happy")  # type: ignore[arg-type]

        assert len(page.routes) == len(specs) == 1
        assert page.routes[0][0] == specs[0].pattern

    def test_handler_fulfills_with_spec_body(self) -> None:
        page = _FakePage()
        specs = mock_llm(page, "beta_reader", fixture="happy")  # type: ignore[arg-type]
        handler = page.routes[0][1]
        spec = specs[0]

        route = _FakeRoute("POST", "http://localhost:3000/api/v1/analysis/beta-reader?novel_id=x")
        handler(route)

        assert route.fulfilled is not None
        assert route.fulfilled["status"] == spec.status
        assert route.fulfilled["body"] == spec.body
        assert route.fulfilled["content_type"] == spec.content_type

    def test_handler_falls_back_on_method_mismatch(self) -> None:
        page = _FakePage()
        mock_llm(page, "generation_stream", fixture="happy")  # type: ignore[arg-type]
        handler = page.routes[0][1]

        route = _FakeRoute("POST", "http://localhost:3000/api/v1/writing/generation/x/stream")
        handler(route)

        assert route.fell_back is True
        assert route.fulfilled is None

    def test_handler_falls_back_on_url_exclude(self) -> None:
        page = _FakePage()
        mock_llm(page, "beta_reader", fixture="happy")  # type: ignore[arg-type]
        handler = page.routes[0][1]

        route = _FakeRoute("POST", "http://localhost:3000/api/v1/analysis/beta-reader/deep-dive?novel_id=x")
        handler(route)

        assert route.fell_back is True

    def test_raises_for_unknown_capability(self) -> None:
        with pytest.raises(ValueError, match="Unknown capability/variant"):
            mock_llm(_FakePage(), "telepathy")  # type: ignore[arg-type]

    def test_every_happy_spec_body_matches_its_catalog_entry(self) -> None:
        # Cross-check: the handler really serves what the catalog validated.
        page = _FakePage()
        for spec in entries_for("consistency_check", "happy"):
            mock_llm(page, spec.capability, fixture=spec.variant)  # type: ignore[arg-type]
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run --all-packages pytest tests/unit/test_e2e_llm_mocks.py -v -p no:randomly`
Expected: FAIL — `ModuleNotFoundError` for `tests.e2e.helpers.llm_mocks`. Record output.

- [ ] **Step 3: Implement**

Create `tests/e2e/helpers/llm_mocks.py`:

```python
"""``mock_llm`` — install catalog fixtures on a page (spec §3).

Usage in specs::

    from tests.e2e.helpers import mock_llm

    mock_llm(page, "generation_stream")                    # happy variant
    mock_llm(page, "coreference_stream", fixture="error")  # failure path

Handlers fall back on method mismatch / url_exclude, so they compose with
the auth-proxy route (``**/api/v1/**``) regardless of registration order.
Call BEFORE the navigation that triggers the request (page.route contract).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.e2e.mocks.catalog import RouteSpec, entries_for

if TYPE_CHECKING:
    from playwright.sync_api import Page, Route


def mock_llm(page: Page, capability: str, *, fixture: str = "happy") -> list[RouteSpec]:
    """Install the catalog's route handlers for one capability+variant."""
    specs = entries_for(capability, fixture)
    for spec in specs:
        page.route(spec.pattern, _handler_for(spec))
    return specs


def _handler_for(spec: RouteSpec):  # noqa: ANN202 — Playwright handler closure
    def _handle(route: Route) -> None:
        request = route.request
        if request.method != spec.method or (
            spec.url_exclude and spec.url_exclude in request.url
        ):
            route.fallback()
            return
        route.fulfill(
            status=spec.status,
            content_type=spec.content_type,
            body=spec.body,
        )

    return _handle
```

Extend the `tests/e2e/helpers/__init__.py` import block and `__all__` with `mock_llm` (add `from tests.e2e.helpers.llm_mocks import mock_llm` and the `__all__` entry `"mock_llm"`).

- [ ] **Step 4: Run the tests to verify green**

Run: `uv run --all-packages pytest tests/unit/test_e2e_llm_mocks.py tests/unit/test_e2e_mock_catalog.py -v -p no:randomly`
Expected: ALL PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/e2e/helpers/llm_mocks.py tests/e2e/helpers/__init__.py tests/unit/test_e2e_llm_mocks.py
git commit -m "test(e2e): mock_llm installer for the AI response catalog"
```

---

### Task 6: Stable auth sessions (`helpers/audit_user.py`)

**Layer:** Platform

**Files:**
- Create: `tests/e2e/helpers/audit_user.py`
- Modify: `tests/e2e/helpers/__init__.py` (re-exports)

**Interfaces:**
- Produces:
  - `register_user_via_ui(page, base_url, *, email: str | None = None, password: str | None = None, display_name: str = "E2E Audit User") -> dict[str, str]` — the real first-run path AND the only registration path in the suite (PO ruling 2026-10-13): fills `#register-display-name` / `#register-email` / `#register-password`, submits, waits for the auto-login redirect off `/register`. `email=None` generates one unique address per call — the calling fixture's scope fixes the user identity (module-scoped fixture → one registration per spec module).
  - `login_via_api(api_session, api_url, email, password) -> dict[str, str]` — POST `/api/v1/auth/login` through the browser-mimic session (CSRF-safe Origin); returns `{access_token, refresh_token}`; raises with status+body on failure. Login ONLY — harvests tokens for an existing (UI-registered) user; never registers.
  - `attach_session(page, access_token) -> None` — `narrare_auth` cookie via init script + the auth-proxy route (delegates to the existing `tests.e2e.test_helpers._setup_auth_proxy`; no duplication). Safe to call after the first navigation: init scripts apply to every subsequent document, routes immediately.
  - `wait_logged_in(page, base_url, timeout: int = 15000) -> None` — navigates and fails with the actionable E01/N06 message if bounced to `/login`.
  - `build_stable_session(page, base_url, api_session, api_url, *, email: str | None = None, password: str = "E2eTest123!pass", display_name: str = "E2E Audit User") -> dict[str, str]` — `register_user_via_ui` (the mandated UI registration, deterministic unique email per fixture scope) + `login_via_api` token harvest + `attach_session` + `wait_logged_in`; returns `{email, password, display_name, access_token, refresh_token}`. The deterministic logged-in state BEFORE test bodies (the nightly-failure/N06 mitigation).
- Design rule (Global Constraints): stable session ≠ auto-healing. A mid-test bounce FAILS the spec loudly; nothing re-logs-in behind the test's back.
- Cost note (suite budget ≤ 25 min, PO 2026-10-13): UI registration adds a few seconds per user. `build_stable_session` runs once per FIXTURE scope — module-scoped user fixtures (Task 8's `module_stable_user`) amortize one registration across a spec module; function scope stays the isolation default.

**Root cause (2× why) — why a session helper is foundation:**
- Why did the nightly spec fail mid-body? The spec built its session by form-login inside `_complete_wizard_to_editor`, then overlaid `_setup_auth_proxy` — three timing-sensitive steps, each racing the app's memory-only access token (audit N06: every reload 401s until refresh; fast navigation can bounce to /login). The settings spec then navigated and clicked through tabs on that fragile base.
- Why does the foundation fix it? A stable session is established ONCE, deterministically (UI registration → one API token harvest → cookie → proxy route → explicit logged-in wait) before the test body — no form timing beyond the single mandated registration, no in-flight token loss. The class of "session died mid-test" becomes either impossible (deterministic state) or a LOUD product regression instead of a flake.

- [ ] **Step 1: Implement the helper**

Create `tests/e2e/helpers/audit_user.py`:

```python
"""Auth session helpers: register-through-UI + stable logged-in sessions.

Spec §4 (audit_user). Two concerns:
- ``register_user_via_ui`` — the REAL first-run path and the ONLY
  registration path in the suite (PO ruling 2026-10-13: fill form →
  POST /auth/register → auto-login — the audit-proven flow).
- ``build_stable_session`` — deterministic logged-in state BEFORE test
  bodies: UI registration (auto-login) → one API login to harvest the
  access token → narrare_auth cookie → auth-proxy route → explicit
  logged-in wait. Mitigates the N06/nightly class (memory-only access
  token; reload 401s until refresh; mid-test bounce to /login) by
  removing the race, not by hiding it: a bounce still FAILS the spec
  (regression-first — no auto-healing).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from tests.e2e.test_helpers import _setup_auth_proxy

if TYPE_CHECKING:
    import requests as http_requests

    from playwright.sync_api import Page


def register_user_via_ui(
    page: Page,
    base_url: str,
    *,
    email: str | None = None,
    password: str | None = None,
    display_name: str = "E2E Audit User",
) -> dict[str, str]:
    """Register through the real /register form and wait for auto-login.

    Returns ``{"email", "password", "display_name"}``. The app auto-logs-in
    after registration (verified working in the 2026-10-11 audit).
    """
    email = email or f"e2e-ui-{uuid.uuid4().hex[:8]}@example.com"
    password = password or "E2eTest123!pass"

    page.goto(f"{base_url}/register")
    page.locator("#register-display-name").wait_for(state="visible", timeout=10_000)
    page.fill("#register-display-name", display_name)
    page.fill("#register-email", email)
    page.fill("#register-password", password)
    page.click('button[type="submit"]')

    # Auto-login redirect: land anywhere that is NOT /register or /login.
    page.wait_for_url(
        lambda url: "/register" not in url and "/login" not in url,
        timeout=15_000,
    )
    return {"email": email, "password": password, "display_name": display_name}


def login_via_api(
    api_session: http_requests.Session,
    api_url: str,
    email: str,
    password: str,
) -> dict[str, str]:
    """Login via the API (browser-mimic Origin) → ``{access_token, refresh_token}``.

    Login ONLY: harvests tokens for an existing (UI-registered) user so the
    browser session can carry the narrare_auth cookie + proxy route. Never
    registers — ALL registration goes through the UI (PO ruling 2026-10-13).
    """
    resp = api_session.post(
        f"{api_url}/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 200, (
        f"API login failed for {email}: {resp.status_code} {resp.text[:300]}"
    )
    data = resp.json()
    return {"access_token": data["access_token"], "refresh_token": data["refresh_token"]}


def attach_session(page: Page, access_token: str) -> None:
    """Attach an API-issued token to the page (cookie + auth-proxy route)."""
    _setup_auth_proxy(page, access_token)


def wait_logged_in(page: Page, base_url: str, timeout: int = 15_000) -> None:
    """Navigate to the app root and FAIL loudly if bounced to /login."""
    page.goto(base_url, wait_until="domcontentloaded")
    try:
        page.wait_for_function(
            "() => !window.location.pathname.startsWith('/login')",
            timeout=timeout,
        )
    except PlaywrightTimeoutError as exc:
        raise AssertionError(
            "Navigation bounced to /login — the app/proxy rejected the session. "
            "E01 class: is AUTH_JWT_SECRET exported to the web process and equal "
            "to the API's signing key? N06 class: did the access token never "
            "hydrate (check attach_session order vs first goto)?"
        ) from exc


def build_stable_session(
    page: Page,
    base_url: str,
    api_session: http_requests.Session,
    api_url: str,
    *,
    email: str | None = None,
    password: str = "E2eTest123!pass",
    display_name: str = "E2E Audit User",
) -> dict[str, str]:
    """UI registration + deterministic logged-in state; returns creds + tokens.

    Registration goes through the REAL /register form (PO ruling
    2026-10-13) via :func:`register_user_via_ui` — fill form →
    POST /auth/register → auto-login. The auto-login session is then made
    deterministic: one API login harvests a fresh access token for the
    narrare_auth cookie + auth-proxy route (the UI keeps its token in
    memory only — N06), and ``wait_logged_in`` pins the state.

    ``email=None`` generates one unique address per call, so the calling
    fixture's scope fixes the user identity — call once per module for a
    shared registration, once per test for full isolation.
    """
    user = register_user_via_ui(
        page, base_url, email=email, password=password, display_name=display_name
    )
    tokens = login_via_api(api_session, api_url, user["email"], user["password"])
    attach_session(page, tokens["access_token"])
    wait_logged_in(page, base_url)
    return {**user, **tokens}
```

Extend `tests/e2e/helpers/__init__.py` (imports + `__all__`) with `register_user_via_ui`, `login_via_api`, `attach_session`, `wait_logged_in`, `build_stable_session`.

- [ ] **Step 2: Verify against the running stack (no new spec yet — exercise via the existing auth flow)**

Run: `E2E_PYTEST_ARGS="tests/e2e/test_auth_flow.py" just e2e`
Expected: PASS (the existing suite proves the login/register surfaces the helper drives — including the registration form that `build_stable_session` now exercises on every `stable_user` construction; the helper's own end-to-end pin lands in Task 8's `test_environment_smoke.py` via `stable_user`).
Also: `uv run --all-packages pytest tests/unit -q -p no:randomly -k "e2e"` — helper modules import cleanly (no collection errors).

- [ ] **Step 3: Commit**

```bash
git add tests/e2e/helpers/audit_user.py tests/e2e/helpers/__init__.py
git commit -m "test(e2e): stable auth-session helpers (register-through-UI, build_stable_session)"
```

---

### Task 7: Novel factory (`helpers/novel_factory.py`)

**Layer:** Platform

**Files:**
- Create: `tests/e2e/helpers/novel_factory.py`
- Modify: `tests/e2e/helpers/__init__.py` (re-exports)

**Interfaces:**
- Produces:
  - Constants `STARTER_BLANK = "blank"`, `STARTER_IMPORT = "import"`, `STARTER_DEMO_FANTASY = "demo_fantasy"`, `STARTER_DEMO_SCIFI = "demo_scifi"`, `STARTER_DEMO_GERMAN = "demo_german"` (values = `StarterContent` union in `packages/web/types`; card order in `WizardStep2.tsx`: blank=0, import=1, demo_fantasy=2, demo_scifi=3, demo_german=4 among `button[aria-pressed]` cards).
  - `complete_wizard(page, base_url, *, starter: str = "blank", novel_title: str = "Factory Novel", import_file: Path | None = None) -> dict[str, str]` — assumes a LOGGED-IN page (compose with `build_stable_session` / the Task 8 fixtures); drives the current 5-step wizard and returns `{"novel_id": …}` after the editor redirect.
  - `create_volume_via_api(api_request, novel_id, *, title="Act I", subtitle=None, description=None) -> dict` — POST `/api/v1/novels/{id}/volumes` (`CreateVolumeRequest`), asserts 201, returns JSON.
  - `create_chapter_via_api(api_request, novel_id, *, title="New Chapter", content="", volume_id=None) -> dict` — POST `/api/v1/novels/{id}/chapters` (`CreateChapterRequest`), asserts 201, returns JSON.
- `api_request` is the existing conftest fixture: `api_request(method, path, **kwargs) -> requests.Response` with `path` relative to the API root.
- Demo prefill neutrality (audit N17): for demo starters the factory does NOT overwrite an already-prefilled title — the prefill-vs-empty question is asserted by the onboarding spec plan, not smuggled into the factory.

- [ ] **Step 1: Implement the factory**

Create `tests/e2e/helpers/novel_factory.py`:

```python
"""Novel factory: wizard completion + volume/chapter API setup (spec §4).

``complete_wizard`` drives the CURRENT 5-step wizard (WizardShell.tsx):
1 project name + language · 2 starter selection (blank/import/demo cards,
   ``button[aria-pressed]`` in render order) · 3 novel details
   (``#novel_title``) · 4 provider (LLM-mocked, Next disabled until a model
   auto-selects) · 5 complete → editor redirect.

The page must ALREADY be logged in (compose with audit_user helpers or the
conftest stable_* fixtures) — the factory owns no auth concerns (RULE-04).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from tests.e2e.mocks.llm_responses import setup_llm_mocks
from tests.e2e.test_helpers import _click_next, _wait_for_wizard_ready

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from playwright.sync_api import Page

STARTER_BLANK = "blank"
STARTER_IMPORT = "import"
STARTER_DEMO_FANTASY = "demo_fantasy"
STARTER_DEMO_SCIFI = "demo_scifi"
STARTER_DEMO_GERMAN = "demo_german"

# StarterCard render order in WizardStep2.tsx (blank, import, then DEMO_OPTIONS).
_STARTER_CARD_INDEX = {
    STARTER_BLANK: 0,
    STARTER_IMPORT: 1,
    STARTER_DEMO_FANTASY: 2,
    STARTER_DEMO_SCIFI: 3,
    STARTER_DEMO_GERMAN: 4,
}


def complete_wizard(
    page: Page,
    base_url: str,
    *,
    starter: str = STARTER_BLANK,
    novel_title: str = "Factory Novel",
    import_file: Path | None = None,
) -> dict[str, str]:
    """Complete the setup wizard on a logged-in page → ``{"novel_id": …}``."""
    if starter not in _STARTER_CARD_INDEX:
        raise ValueError(
            f"Unknown starter {starter!r}; known: {sorted(_STARTER_CARD_INDEX)}"
        )
    if starter == STARTER_IMPORT and import_file is None:
        raise ValueError("starter='import' requires import_file=")

    setup_llm_mocks(page)  # provider validation + model listing (step 4)

    page.goto(f"{base_url}/wizard")
    _wait_for_wizard_ready(page)

    # Step 1: project name (+ language default en).
    project_name_input = page.locator(
        'input[name="project_name"], input[id="project_name"], '
        'input[placeholder*="project" i]'
    ).first
    if project_name_input.is_visible():
        project_name_input.fill(novel_title)
    _click_next(page, expected_step=2)

    # Step 2: starter card selection (positional among aria-pressed cards).
    cards = page.locator("button[aria-pressed]")
    cards.wait_for(state="visible", timeout=10_000)
    card = cards.nth(_STARTER_CARD_INDEX[starter])
    card.click()
    page.wait_for_function(
        """(index) => {
            const card = document.querySelectorAll('button[aria-pressed]')[index];
            return card && card.getAttribute('aria-pressed') === 'true';
        }""",
        arg=_STARTER_CARD_INDEX[starter],
        timeout=10_000,
    )
    if starter == STARTER_IMPORT:
        page.locator('[data-testid="wizard-import-section"]').wait_for(
            state="visible", timeout=10_000
        )
        page.set_input_files("#import-file-input", str(import_file))
        page.wait_for_timeout(500)  # client-side parse + onSelectionChange
    _click_next(page, expected_step=3)

    # Step 3: novel details — fill title ONLY when not prefilled (N17-neutral).
    title_input = page.locator("#novel_title").first
    title_input.wait_for(state="visible", timeout=10_000)
    if not title_input.input_value():
        title_input.fill(novel_title)
    _click_next(page, expected_step=4)

    # Step 4: provider (mocked) — wait until Next is enabled (model selected).
    page.wait_for_function(
        "document.querySelector('[data-testid=\"wizard-next\"]')"
        " && !document.querySelector('[data-testid=\"wizard-next\"]').disabled",
        timeout=15_000,
    )
    _click_next(page)

    # Step 5: complete → editor redirect.
    page.locator('[data-testid="wizard-complete"]').first.wait_for(
        state="visible", timeout=15_000
    )
    page.locator('[data-testid="wizard-complete"]').first.click()
    page.wait_for_url(lambda url: "/novel/" in url or "/dashboard" in url, timeout=15_000)
    if "/novel/" not in page.url:
        page.wait_for_timeout(1_000)
        novel_link = page.locator('a[href*="/novel/"]').first
        novel_link.click()
        page.wait_for_url(lambda url: "/novel/" in url, timeout=15_000)

    match = re.search(r"/novel/([a-f0-9-]+)", page.url)
    if not match:
        raise ValueError(f"No novel ID found in URL: {page.url}")
    return {"novel_id": match.group(1)}


def create_volume_via_api(
    api_request: Callable[..., object],
    novel_id: str,
    *,
    title: str = "Act I",
    subtitle: str | None = None,
    description: str | None = None,
) -> dict:
    """Create a volume via the API (CreateVolumeRequest contract)."""
    resp = api_request(
        "POST",
        f"/api/v1/novels/{novel_id}/volumes",
        json={"title": title, "subtitle": subtitle, "description": description},
    )
    assert resp.status_code == 201, f"Volume create failed: {resp.status_code} {resp.text[:300]}"
    return resp.json()


def create_chapter_via_api(
    api_request: Callable[..., object],
    novel_id: str,
    *,
    title: str = "New Chapter",
    content: str = "",
    volume_id: str | None = None,
) -> dict:
    """Create a chapter via the API (CreateChapterRequest contract)."""
    body: dict[str, object] = {"title": title, "content": content}
    if volume_id is not None:
        body["volume_id"] = volume_id
    resp = api_request("POST", f"/api/v1/novels/{novel_id}/chapters", json=body)
    assert resp.status_code == 201, f"Chapter create failed: {resp.status_code} {resp.text[:300]}"
    return resp.json()
```

Note on `page.wait_for_function(..., arg=…)`: the sync API accepts the arg positionally — pass it as the second positional parameter (`page.wait_for_function(expression, arg, timeout=…)`) if the keyword form differs in this Playwright version; check with `uv run python -c "import inspect; from playwright.sync_api import Page; print(inspect.signature(Page.wait_for_function))"` and adjust the call accordingly (this is a call-signature detail, not a design change).

Extend `tests/e2e/helpers/__init__.py` (imports + `__all__`) with `complete_wizard`, `create_volume_via_api`, `create_chapter_via_api`, and the five `STARTER_*` constants.

- [ ] **Step 2: Verify against the running stack (existing wizard specs prove the driven surfaces)**

Run: `E2E_PYTEST_ARGS="tests/e2e/test_setup_wizard.py tests/e2e/test_wizard_completion.py" just e2e`
Expected: PASS (the wizard surfaces the factory drives — step testids, provider wait, complete redirect — stay green; the factory's own end-to-end pin is Task 8's `stable_novel` self-check).
Also: `uv run --all-packages pytest tests/unit -q -p no:randomly -k "e2e"` — imports clean.

- [ ] **Step 3: Commit**

```bash
git add tests/e2e/helpers/novel_factory.py tests/e2e/helpers/__init__.py
git commit -m "test(e2e): novel factory (wizard starters, volume/chapter API setup)"
```

---

### Task 8: conftest extension + environment smoke spec (E01 pin, fixture self-check)

**Layer:** Platform

**Files:**
- Modify: `tests/e2e/conftest.py` (append fixtures + session checks; no changes to existing fixtures)
- Create: `tests/e2e/test_environment_smoke.py`

**Interfaces:**
- Produces (conftest):
  - `verify_e2e_environment` (session-scoped, autouse) — fail-fast: TestModel banner check in `logs/e2e-api.log` (skipped-with-note if the log is absent, e.g. manual runs) + requests-level E01 proxy probe (login dev user → GET `/dashboard` with `narrare_auth` cookie → must NOT redirect to `/login`).
  - `_validate_mock_catalog` (session-scoped, autouse) — runs `validate_catalog()` before any test.
  - `StableUser` dataclass (`page`, `email`, `password`, `access_token`) and fixture `stable_user` — fresh unique user via `build_stable_session`: UI registration on the real `/register` form (PO ruling 2026-10-13 — the audit-proven fill form → POST /auth/register → auto-login flow; NO API registration) + `login_via_api` token harvest + `attach_session` + `wait_logged_in`. Function-scoped = isolation default, one UI registration per test.
  - fixture `module_stable_user` — identical construction at `scope="module"`: ONE UI registration shared across a spec module, for modules whose tests do not mutate user-level state (fixture-scoping guidance, PO 2026-10-13 — keeps per-spec UI registration cheap within the ≤25 min suite budget). Depends only on session-scoped fixtures (`browser`, `browser_context_args`, `api_session`), so module scope is legal.
  - `NovelContext` dataclass (`page`, `novel_id`, `email`, `password`, `access_token`) and fixture `stable_novel` — `stable_user` + `complete_wizard` (blank starter) → editor.
- Produces (spec): `tests/e2e/test_environment_smoke.py` — E01 browser pin, provider-host pin, a11y-dump pin, `mock_llm` fulfillment pin, `stable_*` fixture self-checks.

- [ ] **Step 1: Write the failing smoke spec**

Create `tests/e2e/test_environment_smoke.py`:

```python
"""Environment smoke pins (spec §8) + foundation fixture self-check.

Fails FAST and ACTIONABLY on the environment couplings the 2026-10-11
audit found (E01/E04) so per-area specs never debug infrastructure:
- E01: proxy must keep an authenticated user OUT of /login.
- Spec §3: zero browser-side LLM provider calls.
- Spec §10: mock_llm serves exactly what the catalog validated.
- Foundation: stable_user/stable_novel fixtures reach the editor.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from tests.e2e.helpers import capture_console, capture_network, dump_a11y, mock_llm
from tests.e2e.helpers.novel_factory import complete_wizard

if TYPE_CHECKING:
    from playwright.sync_api import Page

_E01_MSG = (
    "Bounced to /login while authenticated — E01: the Next.js proxy verifies "
    "narrare_auth with AUTH_JWT_SECRET ?? SECRET_KEY ?? dev-default. Is "
    "AUTH_JWT_SECRET exported to the web process and equal to the API's "
    "signing key? (scripts/run_e2e.sh exports it; standalone `pnpm dev` "
    "starts do NOT inherit it.)"
)


@pytest.mark.e2e
class TestEnvironmentSmoke:
    def test_proxy_keeps_authenticated_user_out_of_login(
        self, authenticated_page: Page, base_url: str
    ) -> None:
        """E01 pin — protected navigation must not bounce to /login."""
        authenticated_page.goto(f"{base_url}/dashboard")
        authenticated_page.wait_for_load_state("domcontentloaded")
        assert "/login" not in authenticated_page.url, _E01_MSG

    def test_browser_never_calls_llm_providers(self, fresh_page: Page, base_url: str) -> None:
        """Spec §3 pin — no browser-side request to any provider host."""
        network = capture_network(fresh_page)
        console = capture_console(fresh_page)
        fresh_page.goto(base_url)
        fresh_page.goto(f"{base_url}/login")
        network.assert_no_provider_calls()
        console.assert_no_page_errors()

    def test_mock_llm_fulfills_catalog_entry_via_page_route(
        self, fresh_page: Page, base_url: str
    ) -> None:
        """mock_llm + catalog end-to-end: an in-page fetch gets the fixture."""
        from tests.e2e.mocks.catalog import entries_for

        mock_llm(fresh_page, "beta_reader")
        expected = json.loads(entries_for("beta_reader", "happy")[0].body)

        fresh_page.goto(base_url)
        result = fresh_page.evaluate(
            """async () => {
                const resp = await fetch('/api/v1/analysis/beta-reader?novel_id=00000000-0000-0000-0000-0000000000f1', {method: 'POST'});
                return {status: resp.status, body: await resp.json()};
            }"""
        )
        assert result["status"] == 200
        assert result["body"] == expected

    def test_a11y_dump_captures_tree(self, fresh_page: Page, base_url: str) -> None:
        """probes.dump_a11y produces a parseable AXTree for debugging."""
        from pathlib import Path

        fresh_page.goto(f"{base_url}/login")
        out = dump_a11y(fresh_page, Path("test-results") / "a11y-login.json")
        tree = json.loads(out.read_text(encoding="utf-8"))
        assert tree["role"] == "WebArea"


@pytest.mark.e2e
class TestFoundationFixtures:
    def test_stable_user_reaches_app_root_logged_in(self, stable_user) -> None:
        """stable_user self-check: deterministic session, not on /login."""
        assert "/login" not in stable_user.page.url

    def test_stable_novel_reaches_editor(self, stable_novel) -> None:
        """stable_novel self-check: fresh user + wizard → novel editor URL."""
        assert "/novel/" in stable_novel.page.url
        assert stable_novel.novel_id

    def test_module_stable_user_shares_one_ui_registration(self, module_stable_user) -> None:
        """module_stable_user self-check: module-scoped UI-registered session."""
        assert "/login" not in module_stable_user.page.url
        assert module_stable_user.email.startswith("e2e-ui-")
```

- [ ] **Step 2: Run it to verify it fails**

Run: `E2E_PYTEST_ARGS="tests/e2e/test_environment_smoke.py" just e2e`
Expected: FAIL — `stable_user` / `module_stable_user` / `stable_novel` fixtures not defined (fixture-not-found errors). The other four tests may pass already; record which. Record output.

- [ ] **Step 3: Extend conftest**

Append to `tests/e2e/conftest.py` (after `register_unique_user`; adjust the existing module imports at the top by adding `from dataclasses import dataclass` and `from pathlib import Path`):

```python
# ---------------------------------------------------------------------------
# Foundation: environment fail-fast checks (spec §8) + shared stable fixtures
# ---------------------------------------------------------------------------


def _api_log_banner_present() -> bool | None:
    """True/False if logs/e2e-api.log exists; None when the log is absent
    (manual runs without the runner) — advisory only in that case (RULE-11)."""
    log_path = Path("logs/e2e-api.log")
    if not log_path.exists():
        return None
    return "e2e_test_mode_active" in log_path.read_text(encoding="utf-8", errors="replace")


@pytest.fixture(scope="session", autouse=True)
def verify_e2e_environment(api_session: http_requests.Session) -> None:
    """Fail the whole session fast on the audit's environment couplings.

    - E04/spec §3: the API must run under NARRARE_E2E_TEST=1 (TestModel
      banner ``e2e_test_mode_active`` in logs/e2e-api.log). Skipped with a
      note when the log is absent (manual stack starts).
    - E01: the Next.js proxy must accept the API-issued narrare_auth cookie
      (requests-level probe — no browser needed).
    """
    banner = _api_log_banner_present()
    if banner is None:
        print("\n  [e2e-env] NOTE: logs/e2e-api.log absent — TestModel banner not verified")
    else:
        assert banner, (
            "NARRARE_E2E_TEST banner (e2e_test_mode_active) missing from "
            "logs/e2e-api.log — the API is making REAL LLM calls (spec §3). "
            "Restart the stack via scripts/run_e2e.sh."
        )

    login = api_session.post(
        f"{API_URL}/api/v1/auth/login",
        json={"email": DEV_EMAIL, "password": DEV_PASSWORD},
    )
    if login.status_code == 429:
        pytest.skip("Rate limited — retry later")
    assert login.status_code == 200, f"Dev-user login failed: {login.status_code} {login.text[:300]}"
    access_token = login.json()["access_token"]

    probe = api_session.get(
        f"{BASE_URL}/dashboard",
        cookies={"narrare_auth": access_token},
        allow_redirects=False,
    )
    location = probe.headers.get("location", "")
    bounced = probe.status_code >= 300 and probe.status_code < 400 and "/login" in location
    assert not bounced, (
        "E01: proxy redirected /dashboard → /login with a valid narrare_auth "
        "cookie. AUTH_JWT_SECRET is not exported to the web process or does "
        "not match the API's signing key (see scripts/run_e2e.sh env block)."
    )


@pytest.fixture(scope="session", autouse=True)
def _validate_mock_catalog() -> None:
    """Spec §10: every catalog entry validates against the real models."""
    from tests.e2e.mocks.catalog import validate_catalog

    validate_catalog()


@dataclass
class StableUser:
    """Fresh unique user with a deterministic logged-in page session."""

    page: Any
    email: str
    password: str
    access_token: str


@dataclass
class NovelContext:
    """StableUser plus a wizard-created novel open in the editor."""

    page: Any
    novel_id: str
    email: str
    password: str
    access_token: str


def _new_stable_user(
    browser: Browser,
    browser_context_args: dict[str, Any],
    api_session: http_requests.Session,
) -> tuple[StableUser, Any]:
    """Shared construction for stable_user / module_stable_user (RULE-04).

    Creates a browser context, registers a fresh user through the REAL
    /register form, and pins the deterministic logged-in state. Returns
    ``(user, context)`` — the caller owns scope and context teardown.
    """
    from tests.e2e.helpers.audit_user import build_stable_session

    context = browser.new_context(**browser_context_args)  # type: ignore[arg-type]
    page = context.new_page()
    page.add_init_script("localStorage.setItem('narrare:featureTourCompleted', 'true');")
    session = build_stable_session(page, BASE_URL, api_session, API_URL)
    user = StableUser(
        page=page,
        email=session["email"],
        password=session["password"],
        access_token=session["access_token"],
    )
    return user, context


@pytest.fixture
def stable_user(
    browser: Browser,
    browser_context_args: dict[str, Any],
    api_session: http_requests.Session,
) -> Generator[StableUser]:
    """Fresh UI-registered user + stable session (spec §4; N06 mitigation).

    PO ruling (2026-10-13): ALL registration goes through the REAL
    /register form — fill form → POST /auth/register → auto-login (the
    audit-proven flow) — driven by audit_user.build_stable_session. No
    API-registration shortcut. Function scope is the isolation default:
    one UI registration + one browser context per test. Prefer
    module_stable_user when the module doesn't need that isolation.
    """
    user, context = _new_stable_user(browser, browser_context_args, api_session)
    yield user
    context.close()


@pytest.fixture(scope="module")
def module_stable_user(
    browser: Browser,
    browser_context_args: dict[str, Any],
    api_session: http_requests.Session,
) -> Generator[StableUser]:
    """Module-scoped stable_user: ONE UI registration per spec module.

    Fixture-scoping guidance (PO 2026-10-13, suite budget ≤ 25 min): UI
    registration costs a few seconds; sharing one user — and one page —
    across a module keeps per-spec registration cheap. Safe ONLY when no
    test in the module mutates user-level state (settings, credentials,
    feature-tour flags, auth store) or logs out; otherwise use the
    function-scoped stable_user. Tests sharing the page run sequentially
    within the module — navigate explicitly at each test start. Depends
    only on session-scoped fixtures (browser, browser_context_args,
    api_session), so module scope is legal; session scope is possible via
    the same _new_stable_user but discouraged (cross-area state bleed).
    """
    user, context = _new_stable_user(browser, browser_context_args, api_session)
    yield user
    context.close()


@pytest.fixture
def stable_novel(stable_user: StableUser) -> NovelContext:
    """stable_user + blank-starter wizard completion → novel editor."""
    novel = complete_wizard(stable_user.page, BASE_URL)
    return NovelContext(
        page=stable_user.page,
        novel_id=novel["novel_id"],
        email=stable_user.email,
        password=stable_user.password,
        access_token=stable_user.access_token,
    )
```

Add `complete_wizard` to the conftest imports at the top: `from tests.e2e.helpers.novel_factory import complete_wizard`. Use `Any` from `typing` for the dataclass page fields (already imported in conftest's `TYPE_CHECKING`-adjacent block — conftest imports `Any` at runtime already; verify and extend if needed: the file has `from typing import TYPE_CHECKING, Any`).

- [ ] **Step 4: Run the spec to verify green**

Run: `E2E_PYTEST_ARGS="tests/e2e/test_environment_smoke.py" just e2e`
Expected: ALL PASS (7 tests).
Then run the full suite once to prove nothing regressed: `just e2e`
Expected: existing 12 spec files pass; new smoke + fixture specs pass. Record the summary line.

- [ ] **Step 5: Commit**

```bash
git add tests/e2e/conftest.py tests/e2e/test_environment_smoke.py
git commit -m "test(e2e): conftest stable fixtures, catalog validation, E01 smoke pins"
```

---

### Task 9: Nightly-failure triage — `test_settings_persistence.py`

**Layer:** Platform (triage; product findings route to Frontend/Backend via the coordinator)

**Files:**
- Modify: `tests/e2e/test_settings_persistence.py` (both tests migrate to the foundation fixtures; `test_settings_general_tab_renders` additionally gets the triage outcome)

**Interfaces:**
- Consumes: `stable_novel` fixture (Task 8), `goto_with_retry` (existing), settings tab testids `button[data-testid^="settings-tab-"]`.
- Evidence basis (nightly run 38231495215, pre-merge main): 30s timeout waiting on settings-tab nth(4) (5th tab) while only 4 rendered; mid-wait bounce to /login; `POST /auth/login` 401 "Invalid email or password" in the API log. Canonical tab config: `packages/web/components/studio/settings/settings-view-config.ts` lists NINE categories (`novel-details, general, writing, ai, prompts, kb-templates, learning, shortcuts, about`) — only 4 rendered at failure time.

**Triage protocol (run before choosing a branch):**

1. Reproduce (3× to separate flake from deterministic):
   ```bash
   E2E_PYTEST_ARGS="tests/e2e/test_settings_persistence.py" just e2e
   ```
2. Answer, with evidence, in this order:
   - **Q1 — which tabs SHOULD render?** Read `packages/web/components/studio/settings/SettingsSidebar.tsx`: does it filter `settings-view-config.ts` categories (e.g. AI-dependent tabs hidden until a provider is configured — our factory user has a mocked provider from wizard step 4)? `grep -n "filter\|enabled\|hidden" packages/web/components/studio/settings/SettingsSidebar.tsx`
   - **Q2 — why did the session bounce mid-test?** Check `logs/e2e-api.log` from the repro: timestamp of the `POST /auth/login` 401 vs the spec's navigation; was a `GET /auth/refresh` attempted before it? (N06: memory-only access token + failed refresh → /login; the 401 login POST means the LOGIN PAGE auto-submitted — inspect `packages/web/app/(auth)/login/page.tsx` + the auth store for an auto-submit/prefill path; if the app auto-submits, that is a PRODUCT bug → Branch C.)
   - **Q3 — did a product change remove/hide tabs?** `git log --oneline -5 -- packages/web/components/studio/settings/`

**Branches (pick by evidence; the branch decision is recorded in the task report):**

- **Branch A — gated subset is CORRECT behaviour** (Q1 shows legitimate filtering, e.g. AI tabs require configured providers): the test's `min(count, 5)` walk was a stale expectation. Fix: pin the tab list explicitly with a pointer to the config SSOT, walk exactly what renders.
- **Branch B — test-side session fragility** (Q2 shows the bounce reproduced the N06 race; tabs render fine on a healthy session): fix = migrate to `stable_novel` (deterministic session) + Branch A's explicit tab list (both harden the spec).
- **Branch C — product regression** (Q1/Q3 show tabs removed/hidden unintentionally, or Q2 exposes an app auto-submit of the login form): write the RED pin below (it will fail), STOP, and hand the evidence to the coordinator — the product fix goes to Frontend/Backend through the normal spec→plan pipeline. This task still lands the fixture migration so the spec is session-robust, but the tab assertion stays red and is marked `xfail(strict=True)` with the finding ID until the fix slice lands (spec §5 regression-first rule).

- [ ] **Step 1: Migrate both tests to the foundation fixtures (all branches)**

In `tests/e2e/test_settings_persistence.py`:
1. Replace the imports of `_complete_wizard_to_editor` and `_setup_auth_proxy` with `goto_with_retry` (keep) — the fixtures replace both.
2. Rewrite `test_settings_general_tab_renders` as:

```python
    def test_settings_general_tab_renders(self, stable_novel, base_url) -> None:
        """Settings page loads with tabs and content (nightly 38231495215 triage).

        Tab list pinned against settings-view-config.ts — the SSOT for
        settings categories. If the product legitimately gates a subset
        (triage Branch A), keep ONLY the always-rendered tabs in this list
        and document the gate here with the filtering rule's location.
        """
        page = stable_novel.page
        goto_with_retry(page, f"{base_url}/novel/{stable_novel.novel_id}/settings")
        page.wait_for_timeout(2000)

        assert "/settings" in page.url, f"Expected settings URL, got: {page.url}"
        assert "/login" not in page.url, (
            "Session bounced mid-navigation (N06 class) — stable_novel should "
            "make this impossible; treat as a product regression, not a flake."
        )

        # SSOT: packages/web/components/studio/settings/settings-view-config.ts
        expected_tabs = [
            "novel-details",
            "general",
            "writing",
            "ai",
            "prompts",
            "kb-templates",
            "learning",
            "shortcuts",
            "about",
        ]
        tab_buttons = page.locator('button[data-testid^="settings-tab-"]')
        rendered_ids = [
            tab_buttons.nth(i).get_attribute("data-testid").removeprefix("settings-tab-")
            for i in range(tab_buttons.count())
        ]
        assert rendered_ids == expected_tabs, (
            f"Settings tabs drifted from settings-view-config.ts: rendered "
            f"{rendered_ids}, expected {expected_tabs}"
        )

        for i in range(tab_buttons.count()):
            tab = tab_buttons.nth(i)
            tab.wait_for(state="visible", timeout=10_000)
            tab.click()
            page.wait_for_timeout(300)
```

   (Branch A adjustment: `expected_tabs` becomes the gated always-rendering subset, with a comment naming the filter location; Branch C: wrap the `rendered_ids == expected_tabs` assertion block in `pytest.xfail(strict=…)` form — `@pytest.mark.xfail(reason="<finding-id>: tabs …", strict=True)` on the test — until the fix slice lands.)

3. Rewrite `test_settings_novel_details_persist_after_reload` head (the body after navigation stays as-is):

```python
    def test_settings_novel_details_persist_after_reload(self, stable_novel, base_url) -> None:
        """Changing novel title in settings persists after page reload."""
        page = stable_novel.page
        novel_id = stable_novel.novel_id

        goto_with_retry(page, f"{base_url}/novel/{novel_id}/settings")
        page.wait_for_timeout(2000)
        # … existing selector/save/reload body unchanged from here …
```

- [ ] **Step 2: Run the triaged spec (3×)**

Run: `E2E_PYTEST_ARGS="tests/e2e/test_settings_persistence.py" just e2e` (three times)
Expected per branch: A/B → PASS all three runs (deterministic); C → the tab assertion fails red (or xfails strictly) with the drift message. Record branch + evidence.

- [ ] **Step 3: Run the full suite**

Run: `just e2e`
Expected: green (Branches A/B) or green-except-documented-red (Branch C, xfail). Record the summary.

- [ ] **Step 4: Commit**

```bash
git add tests/e2e/test_settings_persistence.py
git commit -m "test(e2e): triage settings persistence nightly failure; migrate to stable fixtures"
```

---

### Task 10: Docs — testing-standards E2E section + coverage matrix skeleton

**Layer:** Docs

**Files:**
- Modify: `docs/development/testing-standards.md` (new E2E section)
- Create: `docs/development/e2e-coverage.md`
- Modify: `CHANGELOG.md` (one entry under the current unreleased section)

**Interfaces:**
- Consumes: everything this plan built (runner levers, helper package, catalog contract, fixtures). No code.

- [ ] **Step 1: Add the E2E section to testing-standards.md**

Append a `## End-to-End (E2E)` section (after the existing integration-testing content, before any closing matter) with exactly this content (adjust heading level to the file's convention):

```markdown
## End-to-End (E2E)

Scope: full-stack browser tests against API + DB + frontend with ALL AI
functions deterministically mocked (`tests/e2e/`, marker `e2e`). Not part of
default runs; the existing main/nightly CI `test-e2e` job runs the suite.

### Runner

- Canonical entry: `just e2e` → `scripts/run_e2e.sh` (CI-faithful:
  `narrare_test` DB on :5433, migrate+seed, `ENVIRONMENT=test`, CSRF off,
  `NARRARE_E2E_TEST=1`, cleanup trap; browser-presence preflight).
- Subsets: `E2E_PYTEST_ARGS="tests/e2e/test_<area>.py" just e2e`.
- Frontend mode: `E2E_FRONTEND_MODE=build just e2e` (CI-exact standalone).
- Env lever (E01): `AUTH_JWT_SECRET` MUST be exported to the web process —
  the Next.js proxy verifies `narrare_auth` with it. The runner exports it;
  standalone web starts do not inherit it (every navigation bounces to
  /login). Pinned by `tests/e2e/test_environment_smoke.py`.

### AI mocking (two layers)

1. Factory layer: `NARRARE_E2E_TEST=1` → `pydantic_ai.TestModel` for all
   providers (tolerance-loose surfaces: chat, WS, ghost text, …).
2. Browser layer: the deterministic catalog (`tests/e2e/mocks/catalog*.py`)
   for validator-strict surfaces (audit E04). Install per capability:

   ```python
   from tests.e2e.helpers import mock_llm
   mock_llm(page, "generation_stream")                    # happy
   mock_llm(page, "coreference_stream", fixture="error")  # failure path
   ```

   Catalog contract (spec §10): every entry validates against the real app
   pydantic models — enforced at session start (conftest
   `_validate_mock_catalog`) and in `tests/unit/test_e2e_mock_catalog.py`.
   Adding an entry = fixture constant + `RouteSpec` + module `validate()`
   case + unit test, in the same commit.

### Helper package (`tests/e2e/helpers/`)

| Module | Use |
|---|---|
| `probes` | `capture_console` / `capture_network` / `dump_a11y` + assertions (incl. `assert_no_provider_calls`) |
| `llm_mocks` | `mock_llm(page, capability, fixture=…)` |
| `audit_user` | `register_user_via_ui`, `build_stable_session`, `wait_logged_in` |
| `novel_factory` | `complete_wizard` (blank/import/demo starters), `create_volume_via_api`, `create_chapter_via_api` |

Shared fixtures (conftest): `stable_user` (fresh user registered through
the real `/register` form + deterministic session; function-scoped
isolation default), `module_stable_user` (one UI registration shared per
spec module — only when no test mutates user-level state), `stable_novel`
(+ wizard-created novel in the editor). All registration goes through the
UI (PO 2026-10-13). Prefer these over hand-rolled login/wizard flows —
they are the mitigation for the auth-race flake class (N06).

### When to add an E2E spec

Add here ONLY browser-visible behaviour that needs the full stack. Contract
drift belongs in integration tests; component behaviour in vitest. Track
coverage in `docs/development/e2e-coverage.md` (spec §5 matrix).
```

- [ ] **Step 2: Create the coverage skeleton `docs/development/e2e-coverage.md`**

```markdown
# E2E Coverage Matrix

Source of truth: `docs/superpowers/specs/2026-10-11-e2e-full-suite-design.md` §5.
Update the Status column with every suite task; gates reference audit
findings (`docs/superpowers/reports/2026-10-11-e2e-ui-audit.md`).

| Spec | Features | Audit gates | Status |
|---|---|---|---|
| *(foundation)* helpers + catalog + runner + smoke | — | E01 E04 | ✅ done (2026-10-12) |
| test_ai_writing.py | WRITE-002/003/004/005/006/007/009 | B01 B02 B08 B09 M06 | pending |
| test_kb_management.py | KB-001/008/009 | B04 B06 M01 N14 N15 N16 | pending |
| test_kb_ai.py | KB-002/003/004/005/007 + corpus | B03 B05 B06 | pending |
| test_wiki.py | WIKI-001 | M11 | pending |
| test_analysis.py | ANAL-001..005/007/008/009 | B07 E03 N11 N12 N13 | pending |
| test_import_export.py | SETUP-003, export | N18 | pending |
| test_stats_budget.py | STATS-001/002 | M02 | pending |
| test_volumes_scenes.py | WRITE-011, PLAN-001 | M09 M10 | pending |
| test_series_scratchpad.py | SERIES-001..004, NOTES-001 | N02 | pending |
| test_settings_auth.py | SETUP-004, auth, i18n | M03 M04 M05 M07 M08 N04 N05 N06 | pending |
| test_onboarding.py | SETUP-001/002, ONBOARD-001 | N17 | pending |

Existing pre-foundation specs (auth, wizard, editor, chapters, dashboard,
settings, KB worldbuilding, WS ticket, hero flow) are maintained in place.
```

- [ ] **Step 3: CHANGELOG entry**

Add under the current unreleased section of `CHANGELOG.md`:

```markdown
- E2E suite foundation: helper package (stable sessions, novel factory,
  probes), deterministic AI-response catalog with schema validation,
  runner preflight/subset lever, and environment smoke pins (E01/E04).
```

- [ ] **Step 4: Verify + commit**

Run: `uv run --all-packages pytest tests/unit -q -p no:randomly -k "e2e" && just check-architecture`
Expected: unit tests pass; architecture gate clean (docs-only + test-infra changes must not trip anything).
Verify markdown links resolve (the two spec/report paths exist).

```bash
git add docs/development/testing-standards.md docs/development/e2e-coverage.md CHANGELOG.md
git commit -m "docs(testing): E2E suite foundation docs and coverage matrix"
```

---

## Decisions log (PO rulings, 2026-10-13)

The plan's five open questions were ruled on by the PO on 2026-10-13. All
are DECIDED and already reflected in the tasks above:

| # | Question | Ruling | Where it lands |
|---|----------|--------|----------------|
| 1 | Do spec/helper files count against the ≤3 files / ≤250 LOC task cap? | **CONFIRMED exempt** — spec/helper files are the deliverable and don't count; `scripts/run_e2e.sh` and `docs/` changes DO count. | Global Constraints (task-cap bullet) — unchanged wording |
| 2 | Mock boundary for generation: start POST vs stream GET? | **CONFIRMED** — only the SSE stream GET is intercepted; the generation start POST stays real (real request row keeps accept/reject working). | Task 3 (Route decision); Task 4 wiring unchanged |
| 3 | `E2E_PYTEST_ARGS` subset lever on the runner? | **CONFIRMED** — default stays the full CI-faithful invocation; per-run override for subsets/triage. | Task 2 Step 3 |
| 4 | Session helper: API registration for `stable_user` vs UI? | **OVERRULED the plan's original API split — ALL registration goes through the UI.** `stable_user`/`module_stable_user` register via the real `/register` form (fill form → `POST /auth/register` → auto-login, the audit-proven flow) through `build_stable_session`; the API-registration shortcut is REMOVED. `login_via_api` survives as a login-only token harvester (never registers). Fixture-scoping guidance added (module-scoped user fixtures where isolation permits) to keep the suite budget ≤25 min. | Tasks 6 + 8 (+ Task 10 fixture docs); Global Constraints bullet |
| 5 | Triage exit: is red-pin/strict-xfail + separate fix-slice handoff a legitimate Task 9 outcome? | **CONFIRMED** — Branch C (red pin + `xfail(strict=True)` + coordinator-routed fix slice) is a legitimate outcome. | Task 9 Branch C — unchanged wording |

Scope note on ruling 4: the pre-existing `register_unique_user` conftest
fixture (API registration, consumed by today's spec files) predates this
plan, is not extended to new specs, and stays untouched per this plan's
additive-only conftest constraint.

---

## Self-Review (performed 2026-10-12, before publication; amended 2026-10-13 per the PO rulings above)

**1. Spec coverage (foundation scope only — §5 matrix is follow-on by design):**
- §4 structure: helpers package (Tasks 1, 5, 6, 7), conftest growth (Task 8), mocks/ catalog beside `llm_responses.py` (Tasks 3–4) — exact module names match the spec's tree.
- §3 catalog: all ten named validator-strict surfaces covered — generation SSE chunks (T3), coreference (T4), character-voices (T4), beta-reader (T4), consistency (T4), extraction (T4), wiki (T4), improve (T4), scene draft/refine (T3); error variants for every SSE capability (asserted by `validate_catalog`); `mock_llm(page, capability, fixture=…)` installer (T5); zero-provider-call pin + TestModel banner check (T8).
- §8 levers: `AUTH_JWT_SECRET` comment + assertion (T2) + fail-fast smoke pin (T8 conftest probe + browser spec). WS-origin (E02/N08) and sentiment (E03) red pins belong to the analysis / ai-writing follow-on plans per spec §8 — noted in the closing section.
- §9 docs gates: testing-standards E2E section + `e2e-coverage.md` skeleton (T10); CHANGELOG entry (T10).
- §10 risks: schema-typed fixtures + conftest validation (T3/T4/T8); browser-cache drift preflight (T2); headless-DnD and remaining risks are follow-on-plan concerns.
- Audit findings shaping the foundation: E01 (T2 runner + T8 pins), E04 (catalog exists because of it), N06/nightly failure class (T6 stable sessions + T9 triage), N17 (factory neutral to demo prefill — asserted later by the onboarding plan).
- The nightly failure (run 38231495215) gets its dedicated triage task (T9) with the three-branch protocol and per-branch code.

**2. Placeholder scan:** no "TBD/TODO/similar to Task N". Every code step carries the actual code. The three inherently conditional spots — Task 9's branches, Task 7's `wait_for_function` arg-signature check, Task 9's "body unchanged from here" — each carry their exact content or an exact verification command, not a deferral.

**3. Type consistency (cross-task):** `RouteSpec(capability, variant, pattern, method, status, content_type, body, url_exclude)` defined T3, constructed identically in T4; `entries_for(capability, variant)` (T3) consumed by `mock_llm` (T5) and the T8/T4 unit tests. `mock_llm(page, capability, *, fixture="happy")` (T5) matches the spec §3 signature. `attach_session`/`wait_logged_in`/`login_via_api` (T6) consumed by `build_stable_session` (T6, now UI-registration-first per PO ruling 4); `stable_user` and `module_stable_user` (T8) consume `build_stable_session` via `_new_stable_user` and return `StableUser(page, email, password, access_token)` built from its `email`/`password`/`access_token` keys. `complete_wizard(page, base_url, *, starter, novel_title, import_file) -> {"novel_id"}` (T7) consumed by `stable_novel` (T8) unchanged. `stable_novel.page/.novel_id` field names match Task 9's usage. `capture_console/capture_network/dump_a11y` (T1) match the T8 smoke spec calls. Catalog capability names are identical across T3, T4, T5 tests, and the T10 docs table.

**4. Boundary/dependency-direction check:** no product code touched; helpers import only from `tests/e2e/*` and Playwright; catalog validators import app models read-only (schema reuse, no app logic dependency); conftest additions are additive — existing fixtures (`authenticated_page`, `fresh_page`, `register_unique_user`) unchanged, so the existing 12 spec files run unmodified. RULE-04 respected (one responsibility per helper module; catalog split writing/analysis/kb under the LOC caps). Task ordering is dependency-safe: 3 → 4 → 5; 6 → 7 → 8; 2 enables subset verification for 6–9; every task ends green and committable.

**5. Verification path:** each task names exact commands and expected outcomes (unit red→green where pure; targeted `E2E_PYTEST_ARGS` runs; Task 8 and 9 additionally run the full `just e2e`). Final coordinator verification after Task 10: `just e2e` full-suite green (or green + documented Branch-C red), `uv run --all-packages pytest tests/unit -p no:randomly -k e2e` green, `just check-architecture` clean.

---

## Follow-on plan series (context only — no tasks here)

This foundation is plan 1 of the Phase-B suite program. The remaining work is
**eleven per-area spec plans**, one per §5 matrix row, each a separate plan
consuming this foundation's helpers, catalog, fixtures, and subset runner.
Ordering follows spec §6 (fix-wave 1 = PR #252 already merged; M-item gates
interleave as fix-wave 2). The PO may reshuffle.

| # | Plan (docs/superpowers/plans/) | Spec file | Gates / notes |
|---|---|---|---|
| 1 | `2026-10-XX-e2e-spec-ai-writing.md` | `test_ai_writing.py` | B01/B02/B08/B09 fixed (PR #252); M06 gate = fix-wave 2; extends catalog with rewrite/extend/unblock variants |
| 2 | `2026-10-XX-e2e-spec-kb-management.md` | `test_kb_management.py` | B04/B06 fixed; M01 extraction-storm pin; B05 fixed (session cache) |
| 3 | `2026-10-XX-e2e-spec-kb-ai.md` | `test_kb_ai.py` | B03/B05/B06 fixed; bulk-corpus happy + cancel |
| 4 | `2026-10-XX-e2e-spec-wiki.md` | `test_wiki.py` | M11 gate (first-generation UI path) |
| 5 | `2026-10-XX-e2e-spec-analysis.md` | `test_analysis.py` | B07 fixed; includes E03 sentiment graceful-degradation spec (503/422 not 500) |
| 6 | `2026-10-XX-e2e-spec-import-export.md` | `test_import_export.py` | pin already-strong flow; N18 |
| 7 | `2026-10-XX-e2e-spec-stats-budget.md` | `test_stats_budget.py` | M02 gate (word-count staleness) |
| 8 | `2026-10-XX-e2e-spec-volumes-scenes.md` | `test_volumes_scenes.py` | M09/M10 gates; consumes `create_volume_via_api`/`create_chapter_via_api` |
| 9 | `2026-10-XX-e2e-spec-series-scratchpad.md` | `test_series_scratchpad.py` | N02 |
| 10 | `2026-10-XX-e2e-spec-settings-auth.md` | `test_settings_auth.py` | M03/M04 gates; N06 refresh-race pin; consumes `stable_user` |
| 11 | `2026-10-XX-e2e-spec-onboarding.md` | `test_onboarding.py` | N17 demo-prefill pin (factory stays neutral for it); consumes `register_user_via_ui` + import starter |

Out of series but specced (spec §8): the WS-origin red pin (N08) lands in the
ai-writing plan (WS session surface); the sentiment degradation spec (E03)
lands in the analysis plan. Runtime budget (spec §7 ≤ 25 min local) is
measured at each plan's close; the nightly split (`test-e2e-core` /
`test-e2e-full`) stays a PO decision point, default single suite.
