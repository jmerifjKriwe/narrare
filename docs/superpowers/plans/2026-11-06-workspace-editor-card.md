# Workspace Editor Card Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** The writing surface becomes a card whose edge carries the focus ring, so the caret's ring never sits on the glyphs; the dock narrows by 32 px to give the card its edge and a 16 px gap.

**Architecture:** NovelPage stops painting a full-width band and leaves the card to `ChapterEditor`, which owns the runhead, the text and the footer. The continue action moves above the card so the ring never encloses a control. `MarkdownEditor`'s ring becomes a prop: the chapter hands it to the card, the entity dialog keeps its own.

**Tech Stack:** React 19, Tailwind v4, TipTap, vitest, pytest-playwright.

**Spec:** `docs/superpowers/specs/2026-10-31-narrare-ui-b-pur-design.md` §8.7 (workspace), §8.9 (focus).

## Global Constraints

- **No commit before the review is green** (`AGENTS.md`). The branch's commits happen after Task 3.
- The prose measure stays **544 px**; opening the dock never reflows it (F25).
- The container stays `max-w-[1200px]`: `TopBar`, `NovelsPage` and the E2E container selector share that axis.
- English in code and tests; no user-visible string changes, so the i18n catalogs are untouched.

## Arithmetic

```
container content 1168 = rail 224 + column 592 + dock 352
column 592            = card 576 + gap 16
card 576              = edge 1 + pad 15 + measure 544 + pad 15 + edge 1
```

The 15 px pad plus the 1 px edge is the 16 px of air the measure leaves on each side; the padding is 15 so the border does not eat into the 544.

---

### Task 1: The pins (red)

**Files:**
- Modify: `app/capabilities/writing/web/ChapterEditor.test.tsx`
- Modify: `web/ui/markdown-editor.test.tsx`
- Modify: `app/capabilities/writing/e2e/test_focus_e2e.py`
- Modify: `app/capabilities/writing/e2e/test_viewport_e2e.py`

**Interfaces:**
- Consumes: the current `ChapterEditor` (button, runhead, editor, footer) and `MarkdownEditor`.
- Produces: `[data-editor-card]` — the card element the focus E2E reads; `MarkdownEditor`'s `focusRing` prop (default `true`).

- [x] **Step 1: Pin the card in the component test** — add to `ChapterEditor.test.tsx`:

```tsx
it("paints the focus ring on the card, not on the prose", async () => {
  render(<Harness body={"Ein Satz."} />);
  const card = document.querySelector("[data-editor-card]");
  expect(card).not.toBeNull();
  expect(card!.className).toContain("focus-within:ring-2");
  expect(card!.className).toContain("focus-within:ring-focus");

  const proseWrapper = document.querySelector(".ProseMirror")!.parentElement!;
  expect(proseWrapper.className).not.toContain("focus-within:ring-2");

  const action = screen.getByRole("button", { name: t("chapters.continue") });
  expect(card!.contains(action)).toBe(false);
});
```

- [x] **Step 2: Pin the prop in the editor test** — add to `markdown-editor.test.tsx`:

```tsx
it("can hand the focus ring to its host", async () => {
  render(<MarkdownEditor label="Text" value="" onChange={() => {}} focusRing={false} />);
  const box = await screen.findByRole("textbox", { name: "Text" });
  expect(box.parentElement?.className).not.toContain("focus-within:ring-2");
});
```

- [x] **Step 3: Read the ring from the card in the focus E2E** — in `test_focus_e2e.py`, replace the shadow probe and the wrapper with:

```python
card = page.locator("[data-editor-card]")
shadow = """getComputedStyle(document.querySelector('[data-editor-card]')).boxShadow"""
```

and the final visibility assertion with `expect(card).to_be_visible()`. Update the docstring: the ring lives on the card, the measure still does not move.

- [x] **Step 4: Pin the three widths in the viewport E2E** — in `test_the_prose_keeps_its_measure_when_the_dock_opens`, after the dock opens:

```python
dock_box = page.locator(DOCK).bounding_box()
editor_box = page.locator(EDITOR).bounding_box()
card_box = page.locator("[data-editor-card]").bounding_box()
assert dock_box is not None and editor_box is not None and card_box is not None
assert abs(dock_box["width"] - 352) <= 1, f"the dock is {dock_box['width']}px, not 352±1"
assert abs(editor_box["width"] - 592) <= 1, f"the column is {editor_box['width']}px, not 592±1"
assert abs(card_box["width"] - 576) <= 1, f"the card is {card_box['width']}px, not 576±1"
```

- [x] **Step 5: Watch them fail** — `just test-file app/capabilities/writing/web/ChapterEditor.test.tsx`, `just test-file web/ui/markdown-editor.test.tsx`, `just test-e2e writing -k "rings or measure"` (or the equivalent arg pass-through).

**Expected:** the two component tests fail on the missing card/prop; the two E2E tests fail on the old geometry and the missing card.

---

### Task 2: The surface (green)

**Files:**
- Modify: `app/capabilities/writing/web/NovelPage.tsx`
- Modify: `app/capabilities/writing/web/ChapterEditor.tsx`
- Modify: `web/ui/markdown-editor.tsx`

- [x] **Step 1: NovelPage — the band becomes the column.** Replace

```tsx
<div className="w-full border-y border-rule bg-card py-6">
  <div className="mx-auto w-full max-w-[544px]">
```

with

```tsx
<div className="w-full py-6">
  <div className="mx-auto w-full max-w-[576px]">
```

and add `lg:pr-4` to the section (`flex min-w-0 flex-1 flex-col items-center`) for the 16 px gap to the dock. Replace the band comment with one that names the card and the arithmetic.

- [x] **Step 2: NovelPage — the dock.** `w-96` → `w-88` (22 rem = 352 px).

- [x] **Step 3: ChapterEditor — the card.** Move the action row above a new card wrapper; the runhead, editor and footer go inside it; the failure notice stays with the action:

```tsx
<div className="mb-4 flex items-center gap-3">
  <Button variant="primary" ...>{t("chapters.continue")}</Button>
</div>
{failed ? <Notice ... className="mb-4">…</Notice> : null}
<div
  data-editor-card
  /* 1 px edge + 15 px pad = the 16 px the measure leaves on each side;
     padding 16 would eat 2 px of the 544. */
  className="rounded-[var(--radius-lg)] border border-rule bg-card p-[15px] focus-within:ring-2 focus-within:ring-focus"
>
  {focusDepth < 2 ? <header ...>…</header> : null}
  <MarkdownEditor className="mt-4" ring={false} ... />
  {focusDepth < 2 ? <footer ...>…</footer> : null}
</div>
```

- [x] **Step 4: MarkdownEditor — the prop.** Add `focusRing = true`; compose the wrapper class from it:

```tsx
className={[focusRing ? "focus-within:ring-2 focus-within:ring-focus" : "", className]
  .filter(Boolean)
  .join(" ")}
```

Update the F18 comment: the ring is a prop because the chapter's card carries it.

- [x] **Step 5: Green.** `just check`; `just test-file app/capabilities/writing/web/ChapterEditor.test.tsx`; `just test-file web/ui/markdown-editor.test.tsx`; `just test-e2e writing -k "rings or measure"`.

**Expected:** all pass; the focus E2E sees the ring on the card while the caret is inside and none after the heading click.

---

### Task 3: The record

**Files:**
- Modify: `docs/superpowers/specs/2026-10-31-narrare-ui-b-pur-design.md` §8.7, §8.9
- Modify: `assets/screenshots/01-workspace-continuation.png`, `02-chat-sources.png`, `07-workspace-dark.png` (regenerated)

- [x] **Step 1: §8.7.** Dock 384 → 352; the workspace row's column arithmetic; note that the runhead, text and footer live in the card and the continue action sits above it. Correct the row's stale container figure (1152 → 1200, the value the code and the shelf row use).
- [x] **Step 2: §8.9.** The focus ring attaches to the editor card, not the ProseMirror surface.
- [x] **Step 3: Regenerate the gallery.** `uv run python -m scripts.screenshots`. Check the five files exist, 1600×1000, and look at 01/02/07: the card's edge visible, no ring on the glyphs.
- [x] **Step 4: Gates.** `just verify writing chat knowledge web`; `just check`.

**Expected:** green; the screenshots show the card.

---

## Review Focus

- **The ring still touches glyphs** when the dock is open: card 576, measure 544, 16 px air — check 01's replacement at 1:1.
- **The button inside the card** (the ring would enclose a control): the component test pins it outside.
- **A double ring** — the card and the ProseMirror both drawing one.
- **A measure that moved** — 544 at 1280, closed and open.
- **The dock's chat row** at 352: the question field shrinks first, the ask keeps its label, nothing overflows.
- **The depth-2 surface** — the runhead and footer hide, the card remains, the continue action stays visible (the door).

---

## Deviations from this plan

- **The bleed is scoped to `max-[36rem]`, not `max-lg`.** The plan's `max-lg`
  (below 1024) made the card 608 px at 768, around a 544 px measure: 15 px of
  air on the left, 49 on the right, and the runhead overhanging the text. It
  passed every gate the plan named. Ruled to bleed only where the column is
  narrower than the card (≤ 576 px); `test_the_card_centres_its_measure` pins
  the 768 case (red: card 608 px, green: 576 px).
- **The card takes 15 px of pad, not 16.** The 1 px edge is part of the 16 px
  of air; a 16 px pad would leave the measure at 542 and fail the 544 pin.
- **Spec §13.1 still says 384 px.** It records the decision taken with the
  owner on 2026-10-31; the current width lives in §8.7. Left as the record.
- **The review's minor comment drift is fixed** in `NovelPage.tsx`,
  `ChatPanel.tsx` and `app/kernel/testing/viewport.py`.
