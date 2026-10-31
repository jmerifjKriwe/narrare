# The README as a showcase, with images the app produced

**Status:** approved 2026-10-31 · **Owner:** kiesow · **Size:** one work package

## Intent

A GitHub visitor gives a repository about ten seconds before deciding whether to
scroll. Narrare's README currently spends that time on prose: no image of the
product, six feature bullets without a visible result, and a status section that
has been overtaken by the code.

The README becomes the showcase page: what the product looks like, what makes it
different, and the truth about what is built. The audience is the passer-by who
will never clone — not the contributor deciding how to run the tests (that is
`CONTRIBUTING.md`).

## Evidence the status section is stale

| README claim | Reality | Commit |
| --- | --- | --- |
| "provider settings inside the app are planned" | Settings area with provider profiles and per-task assignment | `a3259e55` (2026-10-30) |
| "a manuscript cannot be exported or imported yet" | Export/import on the shelf, with a hostile-archive refusal path | `1133dab9` (2026-10-28) |
| "series do not exist" | still true | — |

A README that misstates the product in the section meant to build trust costs more
than a missing screenshot.

## Goals

- A visitor sees the workspace within the first screen, above the fold.
- Five images, each carrying one claim that prose cannot make as cheaply.
- Every claim in the README resolves to code that exists today.
- The images are reproducible by one command, so the next UI change is a re-run
  rather than a photo session.

## Non-goals

- No hosted demo, no installer, no container image. Narrare still runs from source.
- No change to `GETTING STARTED`'s mechanics or to the prerequisites list.
- No README translation; the README stays English.
- No change to `docs/user/INDEX.md` (generated) or to any gate.
- No new `just` recipe: the 22 recipes are the command surface, and a docs tool is
  not a gate. The script is invoked as `uv run python -m scripts.screenshots`.

## Anti-goals

- A screenshot that implies a feature the app does not have, or prose that looks
  like model output but came from a fixture without saying so.
- Images that dwarf the text, break the column, or make the README a 10 MB load.
- A second CI job. The capture script never runs in a gate.

## Constraints

**The model boundary.** The kernel's fake provider answers every unmarked prompt
with the same three German chunks (`app/kernel/llm/fake.py`, `CHUNKS`), and the
continuation prompt carries no source marker — so a continuation screenshot against
the default provider would show German ghost text in an English UI, identical in
every shot. The chat stand-in at the test boundary already speaks the real wire
(`app/kernel/testing/vendor.py`: `chat_vendor()`, SSE deltas, no key on localhost),
and `run_stack` documents this exact use: "a stack may point a provider at a
test-owned stand-in (the one boundary a fake may hold)". The screenshot run
therefore uses `NARRE_LLM_PROVIDER=openai-chat` plus `NARRE_LLM_BASE_URL` at the
stand-in, and the stand-in learns to answer with chosen prose. No new fake enters
the product tree.

**The README says the images are staged.** One line tells the reader that the
images come from the real app with a stand-in model supplying the prose. That line
is what keeps the showcase honest and is not negotiable.

**Frames.** Light theme, because the app has no toggle and follows
`prefers-color-scheme` (`web/globals.css`); the capture pins the browser's scheme.
English locale, matching the README; the browser's own locale is pinned too, since
the app's default is "auto". A 1600×1000 viewport at device scale 1: the browser
lays out at 1600 CSS px and GitHub draws the image at 800 (hero) or 440 (gallery),
so the downscale carries the detail and no file needs resizing.

**GitHub's image rules.** Relative paths, `alt` text on every image, < 1 MB each,
stable filenames. GitHub serves repository images through a cache keyed by URL: an
image replaced at the same path may show the old bytes for a while, so a materially
changed shot gets a new filename.

## Approaches considered

**A — four hand-made stills.** Half a day, and the images are stale the first time
the UI moves. Rejected: narration without a rerun path.

**B — a capture script on the real stack (chosen).** `scripts/screenshots.py` boots
`run_stack` with a stand-in model, seeds a demo book through the API and the UI,
captures five frames, writes `assets/screenshots/`. One day; afterwards "redo the
images" is a command. Cost: ~200 lines of tooling outside the gates, which nothing
notices when it rots — mitigated by the docstring naming when to re-run and by the
PR text telling the reviewer.

**C — B plus a hero GIF.** The strongest proof of the ghost-text interaction, but
it needs frame-accurate capture, an encoder, and 5–10 MB in the repository, and it
delays the four images that carry the rest of the page. Deferred, not refused.

## The five images

| File | Surface | The claim in its caption |
| --- | --- | --- |
| `01-workspace-continuation.png` | novel workspace, chapter rail, editor, ghost text at the caret | "Continue writing" leaves the suggestion grey until you press Tab |
| `02-chat-sources.png` | chat dock beside the chapter | The answer streams, and the passages behind it sit underneath |
| `03-entities-review.png` | knowledge: extraction review queue | Proposes the cast; you accept or discard each name |
| `04-consistency-check.png` | knowledge: whole-book findings | Reports contradictions one at a time, to acknowledge or dismiss |
| `05-shelf.png` | shelf with three novels and their export actions | A shelf of books, not a folder of files |

The hero is `01`; the gallery pairs `02`–`05` two per row.

## README structure after the change

1. Badges, logo, tagline (unchanged).
2. **Hero image** (`01`) with `alt` text, then the two-sentence product paragraph.
3. **What it looks like** — the four gallery images, each with a caption line and
   the stand-in note underneath.
4. **What you do with it** — five bullets, each naming a visible result: write the
   book (shelf, rail, autosave, `F9`); continue without leaving the page (Tab/Esc);
   make notes searchable (chunk, embed, re-embed on a model change); read the whole
   book (extraction queue, contradictions); three languages.
5. **Why local** (unchanged).
6. **Getting started** — mechanisms unchanged; one added line: this is a developer
   setup, and the default provider answers without a key.
7. **Status** — corrected to the table above: provider profiles in the app, export
   and import from a portable archive, series still missing.
8. **Where to look next** (unchanged) plus the note that
   `uv run python -m scripts.screenshots` recaptures the images.

## Repository settings (not files)

`gh repo edit` can set description and topics; GitHub's social preview has no API
and stays a manual click. Current state: description already carries the tagline,
eight topics, no homepage. Plan: add `fiction`, `ai-writing`, `pgvector`; keep the
homepage empty until something deployable exists; set the social preview to
`assets/logo/social-og.png` by hand.

## What is left to the builder

- The demo book's content: a title, three chapter titles, ~300 words of English
  prose, four character names, two notes — authored so the shots read like a novel
  rather than a fixture.
- The exact wording of the new paragraphs between the sections (the captions, the
  stand-in note and the status paragraph are fixed above).
- Which UI path each shot takes where several exist (the capability E2E tests are
  the reference for every flow).
