# WP0-B — Autosave tells the truth (Phase 0, §3.6)

Design, 2026-10-25. Small change: one hook, its caller, one catalog key pair, one E2E.
Authority for the *what*: `docs/superpowers/plans/2026-10-25-v2-foundation.md` §3.6.
Where this document departs from that section, the departure is named at the end.

## Intent and why

`web/lib/save.tsx` fires a `PUT`, never reads the answer, and then reports `saved`.

Two defects in one line: the status is a lie on any refused write, and the body is
dropped from memory before the answer arrives, so there is nothing left to retry. The
user's only copy of a sentence is a tab about to close — and, because the chapter switch
is a component remount (`NovelPage.tsx:390`, `key={current.id}`), also a click away.

Success is: the indicator never says "Saved" unless the server said so, a failed body
stays in memory and retries, and leaving with unsaved text asks first — on tab close and
inside the app.

## Goals

- `SaveStatus` can express failure; the editor names it beside the text.
- A failed write keeps the body; the next keystroke and `visibilitychange` retry it.
- Leaving with a body that never reached the server asks before discarding it.
- `onSaved` (the `["novels"]` invalidation) runs on success only.
- Proven on the real stack: API stopped → named failure → API back → saved → reloaded
  row carries the text.

## Non-goals

- No draft store, no `sessionStorage` mirror, no offline queue, no background retry timer.
- No custom dialog component; no router-wide blocker API.
- No change to the debounce (800 ms) or to the endpoint's contract.
- No new state in the shell; the workspace does not learn about saving.

## Constraints

- One capability's frontend stays in `app/capabilities/writing/web/`; the hook stays in
  `web/lib/` because it is shell-level (it already lives there).
- en/de/fr for every user-visible string; a missing key is a build error.
- E2E on the real stack, real backend, real database. `Stack.stop_api()` is the outage;
  nothing is simulated.
- `just generate` after the catalog change (catalogs are generated, not hand-edited).

## Approaches considered

1. **Tab close only** — `beforeunload` guard, status made honest. Cheapest, and it
   leaves the chapter switch silently lossy: the more frequent path in daily use.
2. **Guard every leave with a confirm** — `beforeunload` plus a guard at the points that
   change the selection. One mechanism, one meaning, no second copy of the text.
   Costs a native `window.confirm` (its buttons are browser chrome) and parent state.
3. **Tab close plus an in-memory draft** — restore the unsaved body on the next mount of
   the same chapter. No dialog, no loss, but a second truth next to the server that has
   to be surfaced anyway ("restored, not saved"), and TipTap initializes content once.

**Chosen: 2** (coordinator, 2026-10-25). 3 buys a second state machine to avoid a
dialog that only appears when something is genuinely unsaved.

## Design

### The hook (`web/lib/save.tsx`)

`SaveStatus = "idle" | "pending" | "saving" | "saved" | "failed"`.

- `idle` — nothing typed since mount, or the last write landed and nothing follows.
- `pending` — a body is waiting for the debounce (or for a retry).
- `saving` — a `PUT` is in flight.
- `saved` — the last `PUT` answered without error.
- `failed` — the last `PUT` did not land; the body is still in memory.

`failed` survives further keystrokes: typing sets `pending`, the *flushed* success sets
`saved`, and only that clears the failure. A message that vanishes on the next keystroke
and returns 800 ms later is flicker, not information.

`flush()`:

- takes body and chapter id, and does **not** clear the pending body before the answer;
- a success clears pending only if it still holds the flushed body — a newer body
  arrived during the request and must not be discarded;
- success means `error === undefined`: openapi-fetch *resolves* on 4xx/5xx and throws
  only on a network failure, so both count as failed;
- returns `"saved" | "failed"`, calls `onSaved` only on `"saved"`.

`SaveIndicator` renders text for `saving`, `saved` and `failed`; `failed` is an
`role="alert"` in `text-danger`. `idle` and `pending` render nothing — the existing test
`test_typed_text_survives_a_chapter_switch` pins that (status count 0 while pending).

### Ownership (my call)

`useAutosave` moves from `ChapterEditor` to `NovelPage`, which then passes `schedule`
down. Reasons: the guard belongs next to the two switch paths, and the hook's lifetime
must match the page rather than the chapter key — today the hook's unmount cleanup fires
on *every* chapter switch, which is what makes the failure invisible.

`ChapterEditor` keeps the indicator and the ghost-text logic; it no longer owns saving.

### The guard (`NovelPage`)

One function, three call sites:

```
async function leave(then: () => void) {
  const outcome = await flushIfPending();       // "clean" | "saved" | "failed"
  if (outcome !== "failed" || confirm(t("save.confirmLeave"))) then;
}
```

- **rail button** (`onClick={() => setActive(id)}`) — through `leave`.
- **"Neues Kapitel"** — through `leave`, *before* the create request: asking afterwards
  would leave a stray empty chapter behind on "cancel".
- **the `<Link to="/">` back to the shelf** — through `leave` with `preventDefault`,
  then `navigate`.

A healthy pending body is flushed, not questioned: the switch waits for the `PUT` and
proceeds on success. The dialog appears only after a write actually failed — the case
where no automatic path remains. That also keeps the existing chapter-switch test
unchanged: the click still produces the `PUT` its `expect_response` waits for.

### `beforeunload`

In `NovelPage`, next to the guard: `if (pending || failed) preventDefault()`. The text is
browser chrome and not translatable; the trigger is ours. This is the only place where
"unsaved" has a single owner.

### i18n

- `save.failed`: "Not saved" / "Nicht gespeichert" / "Non enregistré"
- `save.confirmLeave`: "This chapter has text that was not saved. Leave anyway?" /
  "In diesem Kapitel steht Text, der nicht gespeichert wurde. Trotzdem wechseln?" /
  "Ce chapitre contient du texte non enregistré. Quitter quand même ?"

## Verification

**Unit (jsdom, the real local HTTP server in `ChapterEditor.test.tsx`):** a scripted 500
→ `failed` named, no "Saved", `onSaved` not called, body still in the editor; the next
keystroke against a recovered server → `saved`. The existing in-flight test stays green.

**E2E, real stack (`app/capabilities/writing/e2e/test_autosave_e2e.py`):**

1. `stop_api`, type, assert "Nicht gespeichert" visible and "Gespeichert" absent;
   `start_api`, type, assert "Gespeichert"; `reload`, assert the text — the row, not the
   in-memory body.
2. `stop_api`, type until failed, click another chapter → dialog; dismiss → same chapter,
   text intact; then save and switch cleanly.
3. `page.close(run_before_unload=True)` on a page with a failed body → the browser's
   confirm is requested (Playwright `dialog` event).

**Red half:** (1) passes today by lying, (2) and (3) do not exist. Each test is run
before the fix and its failure recorded in the report.

`just check` before every commit; `just verify` before the WP closes.

## Files

- `web/lib/save.tsx` — states, flush semantics, indicator.
- `app/capabilities/writing/web/NovelPage.tsx` — hook, guard, `beforeunload`, link.
- `app/capabilities/writing/web/ChapterEditor.tsx` — takes `schedule`, drops the hook.
- `i18n/{en,de,fr}.json` + `just generate`.
- `app/capabilities/writing/web/ChapterEditor.test.tsx` — failure/retry unit test.
- `app/capabilities/writing/e2e/test_autosave_e2e.py` — new.

## Deviations from plan §3.6 (to be reported in the commit)

1. **Five states, not four.** `pending` is needed: the guard must tell "nothing to lose"
   from "inside the 800 ms debounce", and `idle` is both.
2. **The guard covers in-app leaving, not just tab close** — coordinator decision,
   approach 2. `beforeunload` alone cannot see a chapter switch, which is a remount.
3. **The confirm follows a failed flush, not a pending body.** The switch tries to save
   first; only a failure asks. A dialog on every switch inside the debounce would be
   noise, and the automatic flush already covers that case.
4. **The unmount-flush moved.** It no longer re-fires per chapter switch; the switch's
   own `leave` is the flush. The hook keeps it for page teardown.
