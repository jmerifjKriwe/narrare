# WP0-B — Autosave tells the truth · Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps
> use checkbox (`- [ ]`) syntax for tracking.

**Goal:** An autosave that never says "Saved" unless the server said so, keeps a failed
body for retry, and asks before leaving with text that never reached the server.

**Architecture:** `useAutosave` gains `pending`/`failed` states and honest `flush`
semantics, moves from `ChapterEditor` to `NovelPage`, and the page owns one `leave()`
guard used by the chapter rail, chapter creation, the shelf link and `beforeunload`.

**Tech Stack:** React 19, TipTap, openapi-fetch, Vitest + Testing Library (jsdom, real
local HTTP), pytest + Playwright against the real stack (API, Postgres, browser).

**Spec:** `~/.opencode/plan/2026-10-25-wp0b-autosave-design.md` → moves to
`docs/superpowers/specs/2026-10-25-wp0b-autosave-design.md` in the build session.

## Global Constraints

- One capability's frontend lives in `app/capabilities/writing/web/`; the hook stays in
  `web/lib/` (shell). `web/lib` never imports from `app/`.
- Every user-visible string in en, de and fr; catalogs are generated — `just generate`
  after touching `i18n/*.json`. A missing key is a build error.
- No new dependency. No `--no-verify`, no force push.
- `just check` before every commit, output read. Nothing is committed before the review
  is green (AGENTS.md, Git).
- Touch only the files a task names. `git status --porcelain` before staging.
- The browser-visible contract stays: `PUT /api/writing/chapters/{chapter_id}`, 800 ms
  debounce, indicator hidden while `idle` and `pending`.
- English in code, comments, tests and docs.

## Review Focus

- **A PUT that is accepted and never answered.** The click waits on the flush; the
  page's own load already behaves this way. Not fixed here — but the state stays
  `saving` and never shows "Saved"; the wait is the existing convention, not a new hole.
- **An answer that lands after the user left anyway.** Its result must not paint on the
  next chapter. A generation counter in the hook drops stale answers.
- **A refused body, not just an outage.** A 413/422 must take the same failure path as a
  dead wire; the hook parses no error body (Task 1 test drives a 500 and asserts the
  indicator, not the server's words).
- **Two writes racing.** A held response plus a newer body: the newer body wins and
  nothing is dropped (the existing in-flight test in `ChapterEditor.test.tsx` stays
  unmodified and is the proof; the hook's clear-only-if-unchanged rule serves it).
- **An answer that lands after `discard()`.** It must not flip the indicator to "Saved"
  (Task 3 test through the harness).
- **Leaving by the shelf link.** `beforeunload` cannot see it and the editor unmounts;
  the same confirm covers it (Task 3 E2E asserts the link, not only the rail).

---

## Task 1: A refused save is named, the body kept

**Files:**
- Modify: `app/capabilities/writing/web/editorApiServer.ts` (add `refuseSave`)
- Modify: `web/lib/save.tsx` (states, flush, indicator)
- Modify: `i18n/en.json`, `i18n/de.json`, `i18n/fr.json` + `just generate` (`save.failed` only)
- Test: `app/capabilities/writing/web/ChapterEditor.test.tsx`
- Test: `app/capabilities/writing/e2e/test_autosave_e2e.py` (new)

**Interfaces:**
- Produces: `SaveStatus = "idle" | "pending" | "saving" | "saved" | "failed"`;
  `flush(): Promise<"clean" | "saved" | "failed">`; `useAutosave(chapterId, onSaved?)`
  returns `{ status, schedule, flush }` (unchanged shape, new status values).

- [ ] **Step 1: Teach the test server to refuse one save**

In `editorApiServer.ts`, next to `refuseContinue`, add:

```ts
  /** Answer the next autosave PUT with a 500 — a refused write, one shot. */
  refuseSave: false,
```

and in the request handler, before the response is recorded as answered:

```ts
      if (editorServer.refuseSave) {
        editorServer.refuseSave = false;
        response.writeHead(500, { "content-type": "application/json" });
        response.end('{"detail":"refused"}');
        return;
      }
```

- [ ] **Step 1b: Add the `save.failed` key — the tests type against it**

`save.failed`: en "Not saved", de "Nicht gespeichert", fr "Non enregistré", in all
three of `i18n/{en,de,fr}.json`, then `just generate` (`save.confirmLeave` is Task 3's).
Without it the tests below are a type error, not a failing assertion.

- [ ] **Step 2: Write the failing unit test — a refused save is named**

In `ChapterEditor.test.tsx`, after the in-flight test:

```tsx
it("names a refused save, drops nothing and reports no save", { timeout: 10_000 }, async () => {
  const saved: [string, string][] = [];
  editorServer.refuseSave = true;
  render(
    <ChapterEditor
      chapterId={CHAPTER}
      body="Anfang."
      onSaved={(id, body) => saved.push([id, body])}
    />,
  );
  const user = await focusEditor();
  await user.keyboard("Der Satz.");
  await waitFor(
    () => expect(screen.getByRole("alert")).toHaveTextContent(t("save.failed")),
    { timeout: 5000 },
  );
  expect(screen.queryByText(t("save.saved"))).toBeNull();
  expect(saved).toEqual([]);
  expect(document.querySelector(".ProseMirror")?.textContent).toContain("Der Satz.");
});
```

- [ ] **Step 3: Run it and confirm it fails**

Run: `pnpm --dir web test -t "names a refused save"`
Expected: FAIL — no `alert`; the indicator reads "Gespeichert".

- [ ] **Step 4: Write the failing unit test — the retry**

```tsx
it("retries a failed save on the next keystroke and clears the failure", { timeout: 10_000 }, async () => {
  editorServer.refuseSave = true;
  render(<ChapterEditor chapterId={CHAPTER} body="" />);
  const user = await focusEditor();
  await user.keyboard("A");
  await screen.findByRole("alert", {}, { timeout: 5000 });
  editorServer.refuseSave = false;
  await user.keyboard("B");
  await waitFor(() => expect(screen.getByText(t("save.saved"))).toBeVisible(), {
    timeout: 5000,
  });
  expect(editorServer.requests.at(-1)?.body).toContain("AB");
});
```

- [ ] **Step 5: Run it and confirm it fails**

Run: `pnpm --dir web test -t "retries a failed save"`
Expected: FAIL — no `alert` to find.

- [ ] **Step 6: Implement the hook**

In `web/lib/save.tsx`:

```ts
export type SaveStatus = "idle" | "pending" | "saving" | "saved" | "failed";
export type FlushOutcome = "clean" | "saved" | "failed";
```

- `flush` keeps `pending.current` until the answer; it captures `const body` and
  `const attempt = generation.current`, and after the answer:
  - stale (`attempt !== generation.current`) → return `"failed"` without touching state;
  - success (`error === undefined` **and** no throw) → clear `pending` only when it still
    holds `body`, `setStatus("saved")`, `saved.current?.(target, body)`;
  - refusal or thrown network error → leave `pending` as it is (restore `body` only when
    `pending.current === null`), `setStatus("failed")`;
  - nothing to send → `setStatus` untouched, return `"clean"`.
- `schedule` keeps `failed` visible: `setStatus((s) => (s === "failed" ? "failed" : "pending"))`.
- The unmount cleanup bumps `generation.current`, so a late answer is dropped.

`SaveIndicator`: `saving` and `saved` stay as they are; `failed` renders
`<p role="alert" className="text-sm text-danger">{t("save.failed")}</p>`.

- [ ] **Step 7: Run the suite**

Run: `just test-frontend`
Expected: all pass, the four older autosave/ghost tests included.

- [ ] **Step 8: Write the E2E and record its red half**

`app/capabilities/writing/e2e/test_autosave_e2e.py`, with the module's own `_create_book`
(same 8 lines as `test_chapters_e2e.py`):

```python
pytestmark = [pytest.mark.e2e, pytest.mark.timeout(240)]


def test_a_refused_save_is_named_and_never_shown_as_saved(page: Page, stack: Stack) -> None:
    _create_book(page, "Die Bucht")
    page.get_by_role("button", name="Neues Kapitel").click()
    page.locator(".ProseMirror").click()

    stack.stop_api()
    page.keyboard.type("Der Satz, den niemand speichert.")
    expect(page.get_by_text("Nicht gespeichert", exact=True)).to_be_visible(timeout=10_000)
    expect(page.get_by_text("Gespeichert", exact=True)).to_have_count(0)

    stack.start_api()
    page.keyboard.type(" Und noch ein Wort.")
    expect(page.get_by_text("Gespeichert", exact=True)).to_be_visible(timeout=10_000)

    page.reload()
    expect(page.locator(".ProseMirror")).to_contain_text("Und noch ein Wort.")
    assert_accessible(page)
```

`exact=True` is required: without it "Gespeichert" matches inside "Nicht gespeichert".

Run: `git stash push web/lib/save.tsx && just test-file app/capabilities/writing/e2e/test_autosave_e2e.py && git stash pop`
Expected: FAIL at the first assertion — the indicator says "Gespeichert" after the write
was refused. Record the output in the report; restore and continue.

Run: `just test-file app/capabilities/writing/e2e/test_autosave_e2e.py`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add web/lib/save.tsx app/capabilities/writing/web/editorApiServer.ts \
        i18n/en.json i18n/de.json i18n/fr.json web/lib/generated/catalogs.ts \
        app/capabilities/writing/web/ChapterEditor.test.tsx \
        app/capabilities/writing/e2e/test_autosave_e2e.py
git commit -m "fix(save): a refused write is named, not worn as saved"
```

---

## Task 2: Saving belongs to the page

**Files:**
- Modify: `app/capabilities/writing/web/ChapterEditor.tsx` (props, no hook)
- Modify: `app/capabilities/writing/web/NovelPage.tsx` (hook call)
- Test: `app/capabilities/writing/web/ChapterEditor.test.tsx` (harness)

**Interfaces:**
- Consumes: `useAutosave`, `SaveStatus` from Task 1.
- Produces: `ChapterEditor` props
  `{ chapterId, body, status: SaveStatus, schedule: (body: string) => void, proposal?, onProposalResolve? }`;
  `NovelPage` calls `useAutosave(current?.id ?? null, remember)` and destructures
  `{ status, schedule, flush }` (Task 3 adds `discard`).

- [ ] **Step 1: Change the editor to take its saving from outside**

Remove the `useAutosave` import and call. Take `status` and `schedule` as props; keep the
`SaveIndicator` where it is. Update the doc comment: the editor no longer owns saving.

- [ ] **Step 2: Call the hook in the page**

In `NovelPage.tsx`, after `remember` is defined:
`const { status, schedule } = useAutosave(current?.id ?? null, remember);`
(`current` is declared below — move the `current` line above the hook.)

Pass `status={status} schedule={schedule}` at the `<ChapterEditor>` call, and drop
`onSaved={remember}` (the hook owns it now).

- [ ] **Step 3: Give the test file one editor renderer**

Replace the ten `render(<ChapterEditor … />)` sites with a local helper that runs the real
hook, so the existing assertions keep their subject:

```tsx
function Harness(props: { chapterId?: string; body?: string; proposal?: string;
  onProposalResolve?: (accepted: boolean) => void;
  onSaved?: (id: string, body: string) => void }) {
  const save = useAutosave(props.chapterId ?? CHAPTER, props.onSaved);
  return (
    <>
      <ChapterEditor
        chapterId={props.chapterId ?? CHAPTER}
        body={props.body ?? ""}
        status={save.status}
        schedule={save.schedule}
        proposal={props.proposal}
        onProposalResolve={props.onProposalResolve}
      />
      <button type="button" onClick={() => save.flush()}>flush</button>
      {/* Task 3 adds: <button type="button" onClick={save.discard}>discard</button> */}
    </>
  );
}
```

`render(<Harness … />)` replaces each old call; nothing else in those tests changes.

- [ ] **Step 4: Run the suites**

Run: `just test-frontend` → PASS (every older test unchanged in behaviour).
Run: `just test-file app/capabilities/writing/e2e/test_autosave_e2e.py` → PASS.
Run: `just typecheck` → PASS.

- [ ] **Step 5: Commit**

```bash
git add app/capabilities/writing/web/ChapterEditor.tsx \
        app/capabilities/writing/web/NovelPage.tsx \
        app/capabilities/writing/web/ChapterEditor.test.tsx
git commit -m "refactor(save): the page owns leaving, the editor owns the text"
```

---

## Task 3: Leaving with unsaved text asks

**Files:**
- Modify: `app/capabilities/writing/web/NovelPage.tsx` (guard, `beforeunload`, call sites)
- Modify: `web/lib/save.tsx` (`discard`)
- Modify: `i18n/en.json`, `i18n/de.json`, `i18n/fr.json` + `just generate`
- Test: `app/capabilities/writing/e2e/test_autosave_e2e.py`
- Test: `app/capabilities/writing/web/ChapterEditor.test.tsx` (the discard test)
- Test: `app/capabilities/writing/e2e/test_chapters_e2e.py` (unchanged, must stay green)

**Interfaces:**
- Consumes: Task 1's `flush(): Promise<FlushOutcome>`, Task 2's props.
- Produces: `discard(): void` on the hook — clears the pending body, `setStatus("idle")`.

- [ ] **Step 1: Write the failing E2E — the switch and the shelf link ask**

```python
def test_leaving_with_a_failed_save_asks_first(page: Page, stack: Stack) -> None:
    _create_book(page, "Der Priel")
    page.get_by_role("button", name="Neues Kapitel").click()
    page.get_by_role("button", name="Neues Kapitel").click()
    page.get_by_role("button", name="Kapitel 1", exact=True).click()
    page.locator(".ProseMirror").click()

    stack.stop_api()
    page.keyboard.type("Bleibt hier.")
    expect(page.get_by_text("Nicht gespeichert", exact=True)).to_be_visible(timeout=10_000)

    seen: list[str] = []

    def dismiss(dialog: Dialog) -> None:
        seen.append(dialog.type)
        dialog.dismiss()

    page.on("dialog", dismiss)

    page.get_by_role("button", name="Kapitel 2", exact=True).click()
    expect(page.get_by_role("button", name="Kapitel 1", exact=True)).to_have_attribute(
        "aria-pressed", "true"
    )
    expect(page.locator(".ProseMirror")).to_contain_text("Bleibt hier.")

    page.get_by_role("link", name="Alle Romane").click()
    expect(page.get_by_role("heading", name="Der Priel")).to_be_visible()

    assert seen == ["confirm", "confirm"]
    stack.start_api()


def test_closing_a_tab_with_a_failed_save_asks(page: Page, stack: Stack) -> None:
    _create_book(page, "Der Grund")
    page.get_by_role("button", name="Neues Kapitel").click()
    page.locator(".ProseMirror").click()

    stack.stop_api()
    page.keyboard.type("Nicht verlieren.")
    expect(page.get_by_text("Nicht gespeichert", exact=True)).to_be_visible(timeout=10_000)

    seen: list[str] = []
    page.on("dialog", lambda dialog: (seen.append(dialog.type), dialog.dismiss()))
    page.close(run_before_unload=True)
    assert seen == ["beforeunload"]
```

`Dialog` comes from `playwright.sync_api`.

- [ ] **Step 2: Write the failing unit test — a late answer after `discard()`**

Add `discard` to the harness (`<button type="button" onClick={save.discard}>discard</button>`)
and the test to `ChapterEditor.test.tsx`:

```tsx
it("does not report a save that answers after the body was discarded", { timeout: 10_000 }, async () => {
  const saved: [string, string][] = [];
  editorServer.holdNext = 1;
  render(<Harness body="" onSaved={(id, body) => saved.push([id, body])} />);
  const user = await focusEditor();
  await user.keyboard("Zu spät.");
  await waitFor(() => expect(editorServer.requests).toHaveLength(1));

  await user.click(screen.getByRole("button", { name: "discard" }));
  editorServer.requests[0].respond();
  await new Promise((resolve) => setTimeout(resolve, 50));

  expect(screen.queryByText(t("save.saved"))).toBeNull();
  expect(saved).toEqual([]);
});
```

- [ ] **Step 3: Run them and confirm they fail**

Run: `uv run pytest app/capabilities/writing/e2e/test_autosave_e2e.py -k "asks" -v -m e2e --timeout=60`
Expected: FAIL — the switch happens without a dialog, `seen` stays empty and the text is
gone.
Run: `pnpm --dir web test -t "does not report a save that answers after"`
Expected: FAIL — there is no `discard` to click (and no generation to drop the answer).

- [ ] **Step 4: Add the catalog keys**

```
save.failed        en "Not saved"                         de "Nicht gespeichert"            fr "Non enregistré"
save.confirmLeave  en "This chapter has text that was not saved. Leave anyway?"
                   de "In diesem Kapitel steht Text, der nicht gespeichert wurde. Trotzdem wechseln?"
                   fr "Ce chapitre contient du texte non enregistré. Quitter quand même ?"
```

Run: `just generate` — the generated catalogs must gain both keys in all three locales.

- [ ] **Step 5: Implement `discard` and the guard**

In the hook:

```ts
/** Drop the unsaved body: the user chose to leave it behind. */
const discard = useCallback(() => {
  pending.current = null;
  generation.current += 1;
  setStatus("idle");
}, []);
```

In `NovelPage`:

```ts
const unsaved = status === "pending" || status === "failed";

/** Leave a chapter: save first, ask only when the save did not land. */
async function leave(then: () => void) {
  const outcome = await flush();
  if (outcome === "failed" && !window.confirm(t("save.confirmLeave"))) return;
  if (outcome === "failed") discard();
  then();
}
```

Wire it: the rail button `onClick={() => void leave(() => setActive(chapter.id))}`, the
create button `onClick={() => void leave(() => void createChapter())}`, and the shelf link
becomes

```tsx
<Link
  to="/"
  onClick={(event) => {
    if (!unsaved) return;
    event.preventDefault();
    void leave(() => void navigate({ to: "/" }));
  }}
>
```

`beforeunload`, in an effect next to the guard:

```ts
useEffect(() => {
  function guard(event: BeforeUnloadEvent) {
    if (status !== "pending" && status !== "failed") return;
    event.preventDefault();
    event.returnValue = "";
  }
  window.addEventListener("beforeunload", guard);
  return () => window.removeEventListener("beforeunload", guard);
}, [status]);
```

Remove the old `beforeunload` listener from the hook, and reset the hook on a chapter
change: `useEffect(() => { discard(); }, [current?.id, discard])` — after `leave` nothing
is pending, so this only drops a stale failure.

- [ ] **Step 6: Run the E2E and the neighbours**

Run: `just test-file app/capabilities/writing/e2e/test_autosave_e2e.py` → PASS (all three).
Run: `just test-file app/capabilities/writing/e2e/test_chapters_e2e.py` → PASS; the
debounce-switch test still sees its `PUT` and no dialog.
Run: `just test-frontend` → PASS.

- [ ] **Step 7: Commit**

```bash
git add app/capabilities/writing/web/NovelPage.tsx web/lib/save.tsx \
        i18n/en.json i18n/de.json i18n/fr.json web/lib/generated/catalogs.ts \
        app/capabilities/writing/e2e/test_autosave_e2e.py
git commit -m "fix(save): leaving with unsaved text asks first"
```

---

## Task 4: The gate and the record

- [ ] **Step 1: Run the full gate**

Run: `just verify`
Expected: `just check`, backend tests, frontend tests, the production build and every
capability E2E green. Read the output; a skip is a failure.

- [ ] **Step 2: Check the tree names only the brief's files**

Run: `git diff --stat <base>..HEAD`
Expected: `web/lib/save.tsx`, `web/lib/generated/catalogs.ts`, `i18n/{en,de,fr}.json`,
`app/capabilities/writing/web/{NovelPage,ChapterEditor,ChapterEditor.test,editorApiServer}.tsx|ts`,
`app/capabilities/writing/e2e/test_autosave_e2e.py`, plus this plan and its design doc.

- [ ] **Step 3: Write the report**

`docs/superpowers/reports/2026-10-25-wp0b-report.md`, naming: the red outputs captured in
Task 1 Step 8 and Task 3 Step 3; the four deviations from §3.6 (five states; the guard
covers in-app leaving; the confirm follows a failed flush; the unmount flush moved to
`leave`); and the Review Focus line that stays unfixed (a hung PUT).

---

## Verify

1. Every commit: `just check` ran, output read.
2. `git stash`-red proof exists for both E2E tests and is quoted in the report.
3. `test_chapters_e2e.py` and `ChapterEditor.test.tsx` pass **unmodified** in behaviour —
   the only edits are the `Harness` wrapper and the new tests.
4. `just verify` green at close, output read.
5. `grep -c "save.failed" i18n/*.json web/lib/generated/catalogs.ts` → 1 in each of four.

## Report

Terse, pipe-delimited, English, nothing else:

```
status: DONE|BLOCKED
files: <commits with files, one token each>
ledger: <n>/4 tasks, one token each
verify: <per-commit just check, final just verify counts>
deviations: none | <what and why>
concerns: none | <what>
```
