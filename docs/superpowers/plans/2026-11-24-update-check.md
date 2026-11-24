# Update check Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tell a Narrare user that a newer release exists, show its notes in a modal, and let them defer or ignore it — without a blocking startup path or telemetry.

**Architecture:** A kernel service fetches the latest GitHub release over `httpx`, compares it with `app/kernel/version.py`, and persists the answer and the user's preference on the `users` row. `GET /api/updates` and `POST /api/updates/dismiss` serve the shell; the shell renders a persistent banner, a start toast and a `react-markdown` dialog. The interval setting joins the existing settings preference write.

**Tech Stack:** Python 3.14, FastAPI, SQLAlchemy async, Alembic, `httpx`; React 19, TanStack Query/Router, Tailwind, `react-markdown`; pytest, Vitest, Playwright E2E.

**Spec:** `docs/superpowers/specs/2026-11-24-update-check-design.md`

## Global Constraints

- Follow `docs/_shared/CONSTRAINTS.md`; the shell never imports capability code.
- Keep `app/kernel/version.py` the one version literal.
- Release source URL: `NARRA_UPDATE_CHECK_URL`, default
  `https://api.github.com/repos/jmerifjKriwe/narrare/releases/latest`.
  The literal `off` (or an empty value) disables the check.
- Cache TTL: `NARRA_UPDATE_CHECK_CACHE_SECONDS`, default `3600`; `0` disables the
  in-memory cache (E2E uses `0`).
- Every user-visible string exists in en, de and fr; catalogs are sorted and
  key-identical. Shell copy lives in `i18n/*.json`, settings copy in
  `app/capabilities/settings/web/i18n/*.json`.
- The banner is a conditional sibling in `web/components/ChromeFrame.tsx`
  between `<TopBar />` and the content wrapper; never wrap `<Outlet />`.
- React-markdown is the only new runtime dependency.
- Test commands: `just test-file <path>`, `CI=true pnpm --dir web vitest run <path>`,
  `just test-e2e-file <path>`, `just generate`, `just check-generated`.
- Commits: conventional, hidden type for docs/tests/tooling; `feat` commits carry
  a real `User-visible:` line; append `Assisted-by: OpenCode (DeepSeek V4.1 Flash)`.

## Review Focus

- A GitHub outage or a 500 must not surface as an app error; the last known
  answer or "no update" is shown.
- A tag that is not `vMAJOR.MINOR.PATCH` (prerelease, `nightly`, empty) must not
  be announced as newer.
- A dismissed version must stay dismissed across reloads, and a newer-than-
  dismissed version must reappear.
- The start check must not fire on `/setup` or before the settings gate opens.
- The modal must trap focus and return it to its opener; Escape closes it.

---

### Task 1: Kernel update service, user state and endpoints

**Files:**
- Create: `app/kernel/updates/__init__.py`
- Create: `app/kernel/updates/semver.py`
- Create: `app/kernel/updates/schemas.py`
- Create: `app/kernel/updates/service.py`
- Create: `app/kernel/updates/router.py`
- Modify: `app/kernel/contracts/user.py`
- Modify: `app/capabilities/settings/schemas.py`
- Modify: `app/capabilities/settings/service.py`
- Modify: `app/capabilities/settings/router.py`
- Modify: `app/api/main.py`
- Create: `app/kernel/db/migrations/versions/<rev>_users_carry_update_check_state.py`
- Test: `app/kernel/updates/tests/test_semver.py`
- Test: `app/kernel/updates/tests/test_service.py`
- Test: `app/kernel/updates/tests/test_router.py`
- Test: `app/capabilities/settings/tests/test_settings.py`

**Interfaces:**
- Consumes: `app.kernel.version.__version__`, `app.kernel.auth.current_user_id`,
  `app.kernel.db.session.get_session`, the `User` row.
- Produces:
  - `parse_version(tag: str) -> tuple[int, int, int] | None`
  - `is_newer(candidate: str, current: str) -> bool`
  - `UpdateService(session: AsyncSession, user_id: UUID)`
    - `async def read(self, *, force: bool) -> UpdateRead`
    - `async def dismiss(self, version: str) -> UpdateRead`
  - `UpdateRead` (`current_version: str`, `latest_version: str | None`,
    `update_available: bool`, `release_notes: str | None`,
    `release_url: str | None`, `dismissed: bool`,
    `checked_at: datetime | None`)
  - `UpdateDismiss` (`version: str`)
  - `GET /api/updates?force=false`, `POST /api/updates/dismiss`
  - `SettingsRead.update_check_interval_days: int | None`,
    `SettingsUpdate.update_check_interval_days: int | None`

- [ ] **Step 1: Write the failing semver tests**

Create `app/kernel/updates/tests/__init__.py` and
`app/kernel/updates/tests/test_semver.py`:

```python
import pytest

from app.kernel.updates.semver import is_newer, parse_version


@pytest.mark.parametrize(
    ("tag", "expected"),
    [
        ("v0.6.0", (0, 6, 0)),
        ("0.6.0", (0, 6, 0)),
        ("v1.10.3", (1, 10, 3)),
    ],
)
def test_parse_version_accepts_release_tags(tag: str, expected: tuple[int, int, int]) -> None:
    assert parse_version(tag) == expected


@pytest.mark.parametrize("tag", ["v1.0.0-rc.1", "nightly", "", "v1.0"])
def test_parse_version_refuses_non_releases(tag: str) -> None:
    assert parse_version(tag) is None


@pytest.mark.parametrize(
    ("candidate", "current", "expected"),
    [
        ("v0.6.0", "0.5.0", True),
        ("v1.0.0", "0.9.9", True),
        ("v0.5.0", "0.5.0", False),
        ("v0.4.9", "0.5.0", False),
        ("v0.6.0-rc.1", "0.5.0", False),
    ],
)
def test_is_newer(candidate: str, current: str, expected: bool) -> None:
    assert is_newer(candidate, current) is expected
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `just test-file app/kernel/updates/tests/test_semver.py`
Expected: FAIL — `ModuleNotFoundError: app.kernel.updates`.

- [ ] **Step 3: Implement `semver.py`**

```python
import re

_RELEASE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


def parse_version(tag: str) -> tuple[int, int, int] | None:
    match = _RELEASE.match(tag.strip())
    if match is None:
        return None
    major, minor, patch = (int(part) for part in match.groups())
    return major, minor, patch


def is_newer(candidate: str, current: str) -> bool:
    parsed = parse_version(candidate)
    base = parse_version(current)
    if parsed is None or base is None:
        return False
    return parsed > base
```

- [ ] **Step 4: Run the semver tests**

Run: `just test-file app/kernel/updates/tests/test_semver.py`
Expected: PASS.

- [ ] **Step 5: Add the user columns and the migration**

Add to `app/kernel/contracts/user.py` after `daily_goal_words`:

```python
update_check_interval_days: Mapped[int] = mapped_column(default=7, server_default="7")
last_update_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
dismissed_update_version: Mapped[str | None] = mapped_column(String(64))
last_known_latest_version: Mapped[str | None] = mapped_column(String(64))
last_known_release_notes: Mapped[str | None] = mapped_column(Text)
last_known_release_url: Mapped[str | None] = mapped_column(String(2048))
```

Import `Text` from `sqlalchemy` if absent. Generate the revision with
`just db-revision "users carry update check state"`, then edit the generated
file to `op.add_column` the six columns exactly as modelled; the
`update_check_interval_days` column is `nullable=False, server_default="7"`,
the rest nullable; `downgrade()` raises the project's usual
`RuntimeError("...restore the pre-migration dump (design D6, ADR-103)")`.

- [ ] **Step 6: Extend the settings preference**

In `app/capabilities/settings/schemas.py`, add
`update_check_interval_days: int | None = None` to `SettingsRead` and
`SettingsUpdate`, with `Field(ge=1, le=365)` on the update field.
In `app/capabilities/settings/service.py`, include the field in `read()` and in
`write()` under the `model_fields_set` contract (a carried `None` resets to 7).
In `app/capabilities/settings/router.py`, include it in `_settings()`; an
uninstalled instance answers `None`.

- [ ] **Step 7: Write the failing service and router tests**

Create `app/kernel/updates/tests/test_service.py` with a real local release
vendor (see `app/kernel/tests/vendor_server.py` for the shape) and these cases:

```python
async def test_a_newer_release_is_available(session, user, vendor): ...
async def test_a_dismissed_version_is_not_available(session, user, vendor): ...
async def test_a_failed_fetch_keeps_the_last_known_answer(session, user, vendor): ...
async def test_a_disabled_url_answers_no_update(monkeypatch, session, user): ...
async def test_the_interval_skips_the_fetch_until_due(session, user, vendor): ...
```

Set `NARRA_UPDATE_CHECK_URL` to the vendor's `base_url` and
`NARRA_UPDATE_CHECK_CACHE_SECONDS` to `"0"` with `monkeypatch.setenv`.
The vendor's body is a GitHub release JSON:
`{"tag_name": "v999.0.0", "name": "v999.0.0", "body": "## Notes\n\n- new",
"html_url": "https://example.test/release"}`.
A failed fetch test points at a vendor returning 500 after a successful read,
then asserts the first answer survives with `update_available` unchanged.

Create `app/kernel/updates/tests/test_router.py` following the settings router
tests' `client`/`session` fixtures: `GET /api/updates` answers the read shape;
`POST /api/updates/dismiss` sets the version and a second `GET` reports
`update_available: false`.

Run: `just test-file app/kernel/updates/tests/test_service.py`
Expected: FAIL — no `UpdateService`.

- [ ] **Step 8: Implement schemas, service and router**

`app/kernel/updates/schemas.py`:

```python
class UpdateRead(BaseModel):
    current_version: str
    latest_version: str | None
    update_available: bool
    release_notes: str | None
    release_url: str | None
    dismissed: bool
    checked_at: datetime | None


class UpdateDismiss(BaseModel):
    version: str
```

`app/kernel/updates/service.py`: a module-level
`_CACHE: dict[str, tuple[float, Release | None]]` keyed by URL, a
`Release` dataclass (`tag`, `notes`, `url`), `_fetch(url) -> Release | None`
using `httpx.AsyncClient(timeout=5.0)` with headers
`{"Accept": "application/vnd.github+json", "User-Agent": f"narrare/{__version__}"}`,
and `UpdateService.read(force)` / `.dismiss(version)`. `read`:

- return no-update without touching the row when the URL is `off`/empty;
- read the `User` by `session.get(User, user_id)`, raise `SetupRequiredError`
  when absent;
- fetch when `force`, when `last_update_check_at is None`, or when
  `last_update_check_at + timedelta(days=interval) <= now`; store the release
  fields and `last_update_check_at`, commit;
- `update_available = latest is newer than __version__ and latest != dismissed`;
- a `None` fetch keeps the stored fields and still stamps `last_update_check_at`.

`app/kernel/updates/router.py` follows `app/kernel/jobs/router.py`:
`APIRouter(prefix="/api/updates", tags=["updates"])`, `SessionDep`, `UserDep`,
`GET ""` with `force: bool = False`, `POST "/dismiss"`. Map
`SetupRequiredError` to a 409 `"setup required"` as the settings router does.

- [ ] **Step 9: Mount the router**

In `app/api/main.py`, import `router as updates_router` beside the jobs import
and call `app.include_router(updates_router)` beside `app.include_router(jobs_router)`.

- [ ] **Step 10: Run the backend tests and regenerate**

Run: `just test-file app/kernel/updates/tests/test_service.py`,
`just test-file app/kernel/updates/tests/test_router.py`,
`just test-file app/capabilities/settings/tests/test_settings.py`
Expected: PASS.
Run: `just generate` then `just check-generated`.
Expected: the OpenAPI document and typed client include `/api/updates`; no drift.

- [ ] **Step 11: Commit**

```bash
git add app/kernel/updates app/kernel/contracts/user.py \
  app/capabilities/settings app/api/main.py \
  app/kernel/db/migrations/versions web/lib/api/openapi.json \
  web/lib/api/schema.d.ts
git commit --trailer "Assisted-by: OpenCode (DeepSeek V4.1 Flash)" \
  -m "feat(settings): the app can tell when a newer release exists" \
  -m "User-visible: Narrare can report that a newer release is available."
```

---

### Task 2: Shell banner, start toast, release-notes dialog and E2E leg

**Files:**
- Modify: `web/package.json`, `pnpm-lock.yaml` (add `react-markdown`)
- Create: `web/lib/updates.ts`
- Create: `web/lib/updates.test.ts`
- Create: `web/components/UpdateBanner.tsx`
- Create: `web/components/UpdateBanner.test.tsx`
- Create: `web/components/ReleaseNotesDialog.tsx`
- Modify: `web/components/ChromeFrame.tsx`
- Modify: `i18n/en.json`, `i18n/de.json`, `i18n/fr.json`
- Create: `app/kernel/testing/release_vendor.py`
- Modify: `app/kernel/testing/stack.py`
- Modify: `app/capabilities/settings/e2e/conftest.py`
- Create: `app/capabilities/settings/e2e/test_updates_e2e.py`

**Interfaces:**
- Consumes: `UpdateRead` via the generated client; `GET /api/updates?force=`,
  `POST /api/updates/dismiss`; `@shell/ui/modalKeys`.
- Produces: `useUpdateCheck()` returning the `UpdateRead | undefined`;
  `<UpdateBanner />` mounted in `ChromeFrame`; `ReleaseVendor` with a mutable
  `state` dict (`tag`, `notes`, `url`).

- [ ] **Step 1: Add `react-markdown`**

Run: `CI=true pnpm --dir web add react-markdown`
and confirm `web/package.json` and `pnpm-lock.yaml` changed.

- [ ] **Step 2: Write the failing web unit tests**

`web/lib/updates.test.ts` pins the fetch and the cache update with a stubbed
client (the existing `web/lib` tests' `vi.mock` pattern):
`fetchUpdate(true)` calls `GET /api/updates` with `{ force: true }` and returns
the body; a failed response rejects. `UpdateBanner.test.tsx` renders with a
mocked `useUpdateCheck` and asserts: no banner when
`update_available: false`; the version text and the notes door when true; the
toast has `role="status"` and disappears after the delay; `ReleaseNotesDialog`
renders the markdown heading and the dismiss callback posts the version.

Run: `CI=true pnpm --dir web vitest run web/lib/updates.test.ts web/components/UpdateBanner.test.tsx`
Expected: FAIL — modules missing.

- [ ] **Step 3: Implement `web/lib/updates.ts`**

```ts
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import { client } from "./api/client";
import type { components } from "./api/schema";

export type UpdateRead = components["schemas"]["UpdateRead"];
export const UPDATE_KEY = ["updates"] as const;

export async function fetchUpdate(force: boolean): Promise<UpdateRead> {
  const { data, response } = await client.GET("/api/updates", {
    params: { query: { force } },
  });
  if (!response.ok || data === undefined) {
    throw new Error(`update check failed: ${response.status}`);
  }
  return data;
}

export function useUpdateCheck() {
  const queryClient = useQueryClient();
  // The observer re-renders when fetchQuery writes the cache; it does not
  // fetch on its own, so the start check below is the only first request.
  const query = useQuery({
    queryKey: UPDATE_KEY,
    queryFn: () => fetchUpdate(false),
    enabled: false,
    staleTime: Infinity,
    retry: false,
  });
  useEffect(() => {
    void queryClient.fetchQuery({
      queryKey: UPDATE_KEY,
      queryFn: () => fetchUpdate(true),
      staleTime: 0,
    });
    const id = window.setInterval(() => {
      if (document.visibilityState === "visible") {
        void queryClient.fetchQuery({
          queryKey: UPDATE_KEY,
          queryFn: () => fetchUpdate(false),
          staleTime: 0,
        });
      }
    }, 60 * 60 * 1000);
    return () => window.clearInterval(id);
  }, [queryClient]);
  return query;
}
```

The observer is what re-renders on cache updates. The shell copy uses
`shell.update.*` keys.

- [ ] **Step 4: Implement `ReleaseNotesDialog.tsx`**

`role="dialog"`, `aria-modal="true"`, `aria-labelledby`, `useModalKeys(panelRef,
onClose)`, focus on the close button, focus returned to the opener on unmount.
Render `<ReactMarkdown>` with explicit `components` mapping (`h1`→styled `h2`,
`h2`, `h3`, `p`, `ul`, `ol`, `li`, `a`, `code`, `pre`) so the project needs no
typography plugin. Answers: close (Escape), "ignore this version" (calls
`onDismiss`), and a link to `release_url`.

- [ ] **Step 5: Implement `UpdateBanner.tsx`**

The banner is a `role="status"` strip below the topbar with the version and two
buttons ("Release notes", "Later"). The start toast is a fixed bottom-right
card, `aria-live="polite"`, shown once per version per page load for 8 seconds.
The banner renders `null` when the query is pending/errored, `update_available`
is false, or `dismissed` is true. "Ignore this version" posts the dismissal,
invalidates `["updates"]` and closes the dialog.

- [ ] **Step 6: Mount and copy**

In `web/components/ChromeFrame.tsx`, render `{!standalone && <UpdateBanner />}`
between `<TopBar />` and the content wrapper. Add the shell keys to all three
catalogs (sorted, identical):

```json
"shell.update.available": "Narrare {version} is available",
"shell.update.notes": "Release notes",
"shell.update.later": "Later",
"shell.update.ignore": "Ignore this version",
"shell.update.toast": "A newer release is available — {version}",
"shell.update.heading": "What changed in {version}",
"shell.update.openRelease": "Open the release on GitHub",
"shell.update.close": "Close"
```

German and French equivalents; no formality overlay entry unless the phrase
needs the formal register.

- [ ] **Step 7: Add the release vendor and the E2E default**

Create `app/kernel/testing/release_vendor.py` with a `ReleaseVendor` context
manager (`base_url`, mutable `state: dict[str, str]`) serving
`GET /repos/jmerifjKriwe/narrare/releases/latest` with
`{"tag_name": state["tag"], "name": state["tag"],
"body": state["notes"], "html_url": state["url"]}`. Default the state to the
current version so no banner appears unless a test changes it.

In `app/kernel/testing/stack.py`'s `_environment`, set
`base.setdefault("NARRA_UPDATE_CHECK_URL", "off")` before merging the caller's
`env`, so every E2E stack is offline unless it names a vendor.

In `app/capabilities/settings/e2e/conftest.py`, add a session-scoped
`release_vendor` fixture and pass
`env={"NARRA_UPDATE_CHECK_URL": release_vendor.base_url,
"NARRA_UPDATE_CHECK_CACHE_SECONDS": "0"}` to the settings `acquire_stack` call.

- [ ] **Step 8: Write the E2E leg**

`app/capabilities/settings/e2e/test_updates_e2e.py` (markers
`pytest.mark.e2e` and `pytest.mark.timeout(240)`): set
`release_vendor.state["tag"] = "v999.0.0"` and a Markdown body, navigate to the
installed settings page, assert the banner names `v999.0.0`, open the notes and
assert the heading text, dismiss, reload, and assert the banner is absent. Reset
the vendor and the dismissal in a `finally`/fixture so the shared database is
clean for the rest of the suite.

Run: `just test-e2e-file app/capabilities/settings/e2e/test_updates_e2e.py`
Expected: PASS.

- [ ] **Step 9: Verify and commit**

Run: `just generate`, `just check-generated`, `just check`,
`CI=true pnpm --dir web vitest run web/lib/updates.test.ts web/components/UpdateBanner.test.tsx`,
`just test-e2e-file app/capabilities/settings/e2e/test_updates_e2e.py`.
Expected: PASS; the generated catalogs include the new shell keys.

```bash
git add web/package.json pnpm-lock.yaml web/lib/updates.ts \
  web/lib/updates.test.ts web/components/UpdateBanner.tsx \
  web/components/UpdateBanner.test.tsx web/components/ReleaseNotesDialog.tsx \
  web/components/ChromeFrame.tsx i18n web/lib/generated/catalogs.ts \
  app/kernel/testing app/capabilities/settings/e2e
git commit --trailer "Assisted-by: OpenCode (DeepSeek V4.1 Flash)" \
  -m "feat(web): the app announces a newer release with its notes" \
  -m "User-visible: a new release is announced at start and in a banner, with its notes in a modal."
```

---

### Task 3: Settings Updates section

**Files:**
- Create: `app/capabilities/settings/web/UpdatesSection.tsx`
- Create: `app/capabilities/settings/web/UpdatesSection.test.tsx`
- Modify: `app/capabilities/settings/web/SettingsPage.tsx`
- Modify: `web/lib/query.ts`
- Modify: `app/capabilities/settings/web/i18n/en.json`, `de.json`, `fr.json`
- Modify: `app/capabilities/settings/e2e/test_updates_e2e.py`

**Interfaces:**
- Consumes: `useSettings()`, `useUpdateSettings()`,
  `SettingsRead.update_check_interval_days`.
- Produces: `<UpdatesSection row={SettingsRead} />` rendered after
  `<ProfileForm>`; `SettingsChanges.update_check_interval_days?: number | null`.

- [ ] **Step 1: Extend the settings change type**

In `web/lib/query.ts`, add
`update_check_interval_days?: number | null` to `SettingsChanges` and carry it
in `useUpdateSettings`'s PATCH body builder like the other partial fields.

- [ ] **Step 2: Write the failing section test**

`UpdatesSection.test.tsx` (the `SettingsPage.test.tsx` mocking pattern):
renders the stored interval; changing the number and pressing save calls
`useUpdateSettings` with `{ update_check_interval_days: 3 }`; an out-of-range
value disables save; the saved and error faces are shown.

Run: `CI=true pnpm --dir web vitest run app/capabilities/settings/web/UpdatesSection.test.tsx`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement `UpdatesSection.tsx` and mount it**

A section in the settings page's geometry: serif heading, sub-line, a labelled
number input (`min=1`, `max=365`, default 7), and a save button enabled only
when the value is valid and differs from the stored one. On success invalidate
`["settings"]`/`["settings", "read"]` (the hook already does) and show the saved
line; on failure show the retry line. Add the `settings.update.*` keys to all
three settings catalogs, sorted and identical.

In `SettingsPage.tsx`, render `<UpdatesSection row={settings.data} />` after
`<ProfileForm row={settings.data} />` inside the ready fragment.

- [ ] **Step 4: Extend the E2E leg**

In `test_updates_e2e.py`, add a step that sets the interval to `1`, reloads the
settings page, and asserts the field reads `1`; reset it to `7` in the cleanup.
Run: `just test-e2e-file app/capabilities/settings/e2e/test_updates_e2e.py`
Expected: PASS.

- [ ] **Step 5: Regenerate and verify**

Run: `just generate`, `just check-generated`, `just check`,
`CI=true pnpm --dir web vitest run app/capabilities/settings/web/UpdatesSection.test.tsx`,
`just test-e2e-file app/capabilities/settings/e2e/test_updates_e2e.py`.
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/capabilities/settings/web web/lib/query.ts \
  web/lib/generated/catalogs.ts
git commit --trailer "Assisted-by: OpenCode (DeepSeek V4.1 Flash)" \
  -m "feat(settings): the interval between update checks is configurable" \
  -m "User-visible: the update-check interval is set on the settings page."
```

---

## Whole-branch review

After Task 3, dispatch one reviewer on the whole branch diff. The reviewer
checks: the spec's goals and anti-goals, the five standing rules, the three
Review Focus inputs, the E2E leg's proof, the generated-file drift, and the
commit grammar. Fix findings before the PR; open a follow-up issue for any that
survive.

## PR

Open the PR as a plain-language sentence (not conventional) with the plan and
spec in the body. Push after each green task group. The branch lands as a merge
commit.
