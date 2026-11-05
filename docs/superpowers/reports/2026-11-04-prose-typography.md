# Prose typography — task report

Branch `fix/prose-typography`, worktree from `main` (`ffd7ab44`). One production
file: `web/globals.css`. No behaviour, no token, no font, no screenshot touched.

## The defect

`web/globals.css` styled only the surface of the editor (family, 18 px, 1.75,
34 rem). Tailwind's preflight resets `h1–h6` to `font-size: inherit;
font-weight: inherit`, lists to `list-style: none`, every block margin to 0 and
draws `hr` in `currentColor`. A chapter's Markdown therefore arrived as one
undifferentiated wall: measured 31–32 px pitch between paragraph breaks inside
the README frame, headings and paragraphs identical, list markers gone, strong
text synthesized at 700 (the subset carries a real 600 face and no 700).

## What changed

Scoped document rules under `.ProseMirror`:

- one block rhythm (`> * + * { margin-top: .75em }`, `> :first-child` 0) plus
  `p + p` for nested paragraphs; no first-line indent
- `h1`–`h6` at 1.5/1.3/1.15/1.05/1/0.95 em, weight 600, line-height 1.25,
  1.4 em above and 0.4 em below
- `ul`/`ol` markers restored (`disc`/`decimal`, nested `circle`), 1.5 em inset,
  0.25 em between items; a nested list sits 0.25 em below its item's paragraph
- blockquote: 2 px `--border` edge, 1 em inset, italic
- `code`/`pre`: `--rule` ground, `--radius`, mono family; long code lines wrap
  (TipTap's own `.ProseMirror pre { white-space: pre-wrap }` loads after this
  file), so `overflow-x: auto` takes the unbreakable token, not the line
- `hr` on `--rule`; `strong` 600; links underlined, ink unchanged

## Proof, both directions

Measured through the real stack (Playwright, `getComputedStyle`) on the same
chapter, once with the change stashed:

| property | before | after |
| --- | --- | --- |
| second paragraph `margin-top` | 0 px | 13.5 px |
| `h1` size / weight | 18 px / 400 | 27 px / 600 |
| `h2` size / weight | 18 px / 400 | 23.4 px / 600 |
| `h5` size / weight | 18 px / 400 | 18 px / 600 |
| second paragraph in one list item | 0 px | 13.5 px |
| `ul` marker / inset | none / 0 px | disc / 27 px |
| `ol` marker | none | decimal |
| blockquote border / style | 0 px / normal | 2 px / italic |
| `code` background | transparent | `--rule` |
| `strong` weight | 700 (synthesized) | 600 |
| `hr` top border | 1 px currentColor | 1 px `--rule` |

Built CSS carries every selector (`rg -o 'ProseMirror[^{,]*' web/dist/assets/*.css`):
`>*+*`, `>:first-child`, `p+p`, `h1`–`h6`, `ul`, `ol`, `ul ul`, `li+li`,
`li>ul`, `li>ol`, `blockquote`, `code`, `pre`, `pre code`, `hr`,
`strong`, `a`, plus the unchanged root and `:focus`.

Images (analysis output, not committed): `/tmp/opencode/ui-review/t1-editor-markdown-before.png`
and `-after.png`. The before is the wall; the after shows heading, list,
numbered list, quote, inline code.

## Gates

| gate | result |
| --- | --- |
| `just check` | ruff clean, pyright 0/0/0, tsc clean |
| `just build` | ✓ built, 89 packages |
| `just test-frontend` | 33 files, **257 passed** |
| `just test-e2e writing` | **62 passed** (second run) |
| `just test-e2e knowledge` | **27 passed** (the entity dialog shares the editor) |

Every gate above was re-run after review round 1's fixes; the counts are that
post-fix run.

`just verify all` was not run: no screenshot changed, so the gate stays at the
suites that render a ProseMirror (writing, knowledge). Backend tests are not
affected by a stylesheet and were not run.

## Review round 1

An independent review on a separate model returned FIX: the typography passed
every dimension, three items needed work.

1. **`li > p { margin: 0 }` removed.** Its comment claimed a loose list's inner
   paragraphs would otherwise take the document break — they never could: a
   paragraph of one item is not a sibling of another item's. The rule's only
   real effect was deleting the 0.75 em break between two paragraphs inside one
   item, the opposite of the intent. Nothing replaces it; `p + p` gives a
   multi-paragraph item its break again.
2. **`h5`/`h6` added** at 1 em / 0.95 em, weight 600. They were still
   preflight-reset, and TipTap's Heading extension accepts levels 1–6.
3. **The report's "`pre` scrolls sideways" was false** and is corrected above:
   TipTap injects `.ProseMirror pre { white-space: pre-wrap }` after this file,
   so long lines wrap; the horizontal overflow handles unbreakable tokens.

The reviewer independently confirmed the 600 claim from the font files (two real
faces, 400/600, not a variable font) and re-ran every gate green (257 frontend,
62 writing, 27 knowledge).

## Findings: flaky gates (neither caused by this change)

### The writing E2E's chapter selection

The first `just test-e2e writing` run (pytest-randomly seed `2752707262`) failed
`test_the_workbench_names_the_chapter_and_counts_its_words` at
`expect(page.locator(".ProseMirror")).to_contain_text("Wort")` — the editor
mounted empty. The same node passed alone (9.33 s) and the full suite passed on
re-run (62 passed).

The race is in the test, not the app: `test_chapters_e2e.py:549-552` clicks
"Neues Kapitel" four times and waits on `re.compile(r"chapter=")`, which already
matches after the first iteration — clicks 2–4 do not await their SPA
navigation. An in-flight navigation can then overwrite the address between the
"Kapitel 2" click and `re.search(r"chapter=…", page.url)` (line 554), so the PUT
fills one chapter while the reload lands on another, empty one. CSS cannot
cause this; it is a pre-existing test race that a random order exposes.
Follow-up issue at PR time: `follow-up`, `area: writing`, `kind: flake`.

### The frontend suite's beforeunload test

The first `just test-frontend` run after the review fixes failed
`ChapterEditor.test.tsx > prevents beforeunload while a save is pending, not once
it landed` (`expected true to be false`, line 526): 1 failed / 256 passed. The
file passes 21/21 three times in isolation, and the full suite passes 257 on
re-run. A save-settling assertion under 33 parallel jsdom workers is
timing-sensitive; CSS cannot reach it. Same follow-up: `area: writing`,
`kind: flake`.

## Deviations

The task was implemented by the coordinator (`opencode-go/deepseek-v4.1-flash`)
instead of the pinned implementer: `zai-coding-plan/glm-5.3-flash` answered
"usage limit reached for 5 hour" at dispatch and the failed run produced
nothing. The owner chose "I implement T1 myself" on that card. The independent
review still owes a separate run before the commit.

## Concerns / follow-ups

1. **Real italics**: the subset has no italic face, so `em` and blockquotes are
   a synthesized oblique. Needs the EB Garamond Italic source and `pyftsubset`
   (not installed locally); separate task.
2. **Soft breaks**: a stored Markdown body with wrapped lines keeps the newline
   inside the paragraph and ProseMirror's `white-space: pre-wrap` renders it as
   a hard break (observed in the proof body: `…und niemand hatte je\neine
   Frage…` renders as two lines). This predates the change and affects any
   imported file wrapped at 80 columns; it needs a decision (collapse to a
   space or preserve the source layout) before import/export round-trips are
   judged. Not fixed here.
3. **Bundled demo**: its leaked metadata block (`## status`, `## word_count`, …)
   now renders as real headings instead of flat text — the leak is more legible,
   not new. Content fix, separate.
4. The single primary (`Continue writing`) and the editor surface's horizontal
   padding were not touched; they belong to T3.
