# Update check — design

**Status:** approved in conversation, 2026-11-24.

**Intent.** A person running Narrare should learn that a newer release exists
without watching the repository, and should be able to read what changed
without leaving the app. The check is a convenience, never a gate: the app
works offline, and a failed check is silent.

## Goals

- On every app start, ask whether a newer release exists, and once more every
  N days while the app keeps running (N defaults to 7 and is configurable).
- Show a transient notice at start and a persistent banner until the release is
  dismissed.
- Open the release notes in a modal, rendered from the release's Markdown body.
- Let the reader defer (close for now) or ignore this version.
- Work with no network: show the last known release and notes, or nothing.
- No telemetry. The only outbound request is the release lookup itself.

## Non-goals

- Downloading or applying an update. Narrare ships as a container image; the
  app names the newer release and links to it, nothing more.
- Release channels, prereleases, or downgrades.
- A per-device sync of dismissed/seen state. One local user, one database.

## Anti-goals

- A blocking startup path. The check runs after first paint and its failure
  never reaches the user as an error.
- A second source of truth for the version. `app/kernel/version.py` stays the
  one literal.
- A test branch in production code. The release source URL is configuration.

## Constraints

- The five standing rules in `docs/_shared/CONSTRAINTS.md` apply.
- The banner is shell UI. The shell does not import a capability's code; the
  check therefore lives in the kernel and is served at `/api/updates`, beside
  `/api/health`.
- Every user-owned row carries `user_id`. The update preferences live on the
  existing `users` row (like `locale`, `theme`, `author_name`,
  `daily_goal_words`), read through the scoped access the settings service
  already uses.
- New user-visible text goes through the catalogs (en, de, fr); a missing key
  is a build error.
- A new endpoint, a migration and a new surface make this a Lane A change: a
  design doc, a plan, per-task implementer and reviewer, a whole-branch review
  and a new E2E leg.

## Approaches considered

1. **Frontend-only.** The web fetches `api.github.com/.../releases/latest`
   directly and caches in `localStorage`. Cheapest, but the version literal
   would have to be injected into the bundle, the dismissal state would live
   outside the database, and the E2E could not exercise the fetch without
   browser-level interception. Rejected: weaker testability, two stores of
   truth.

2. **Backend endpoint in the kernel plus user columns (chosen).** A kernel
   service fetches the latest release over `httpx`, caches it in memory and in
   the `users` row, and returns the answer at `/api/updates`. The shell reads
   it and renders the banner, toast and modal. This keeps one version literal,
   makes the fetch mockable at the HTTP boundary with a configurable URL, and
   keeps dismissal on the user row the settings surface already owns.

3. **A new `updates` capability.** Clean isolation, but it would add a
   capability folder, registry rows, generated views and a migration for a
   feature the shell alone consumes; the banner cannot live in a capability
   without breaking the shell boundary. Rejected as more surface than the
   feature needs.

## The chosen design

### Backend

- Kernel module `app/kernel/updates/`:
  - `version.py`-adjacent comparison: parse `vMAJOR.MINOR.PATCH` tags into a
    tuple; an unparsable tag is not newer.
  - `service.py`: read the current user row, decide whether the stored answer
    is due, fetch
    `https://api.github.com/repos/jmerifjKriwe/narrare/releases/latest` (URL
    overridable with `NARRA_UPDATE_CHECK_URL`), store the answer, return it.
  - A module-level cache keyed by URL with a one-hour TTL, so a reload storm
    does not spend the unauthenticated GitHub quota.
  - `router.py`, mounted beside the jobs router: `GET /api/updates` and
    `POST /api/updates/dismiss`.
- `users` columns: `update_check_interval_days` (int, default 7),
  `last_update_check_at`, `dismissed_update_version`,
  `last_known_latest_version`, `last_known_release_notes`,
  `last_known_release_url`.
- `GET /api/updates` answers `{ current_version, latest_version,
  update_available, release_notes, release_url, dismissed, checked_at }`.
  `update_available` is server-computed: latest is newer than current and not
  dismissed. A failed fetch returns the last known answer with
  `update_available` unchanged, never a 5xx.
- `POST /api/updates/dismiss` carries the version and sets
  `dismissed_update_version`.
- The interval is written through the existing settings preference write (the
  field joins `SettingsRead`/`SettingsUpdate`) so the settings page keeps one
  form contract.

### Web

- `web/lib/updates.ts`: the query key, the fetch, and a small hook for the
  start check and the interval re-check while the app runs.
- `web/components/UpdateBanner.tsx`: the persistent banner in the chrome, with
  the deferred notice at start and the door into the modal.
- `web/components/ReleaseNotesDialog.tsx`: the modal on the shell's modal
  keyboard discipline (`@shell/ui/modalKeys`), Markdown rendered with
  `react-markdown`, the two answers (defer, ignore this version).
- An accessible toast/live-region at start (the shell's own, since none
  exists) or the banner alone when motion is reduced.
- Settings: an "Updates" section with the interval field, speaking the
  settings capability's catalogs.

### Copy and tests

- Shell text in `i18n/{en,de,fr}.json`; settings text in the settings
  capability catalogs. Sorted, same keys, plural categories where needed.
- Unit tests: version comparison, the due/not-due decision, the failed-fetch
  fallback, the banner and dialog states.
- E2E leg: a fake release server named by `NARRA_UPDATE_CHECK_URL` in the E2E
  stack; the test starts the app, sees the banner, opens the modal, reads the
  notes, dismisses, and sees the banner stay away.

## What is left to the builder

- The exact SQLAlchemy column types and migration shape, following the
  existing revision style.
- Whether the periodic in-app check uses `setInterval` or a visibility-driven
  re-check; either is acceptable if it stops when the tab is hidden.
- The toast's exact motion; the banner is the required surface, the toast the
  start notice.
- The `NARRA_UPDATE_CHECK_URL` hook for the E2E stack (the plan pins it).
