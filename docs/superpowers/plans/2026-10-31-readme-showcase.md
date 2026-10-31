# README Showcase Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the README into a showcase page whose five images the app produced, and correct the claims the code has overtaken.

**Architecture:** A capture script boots the E2E stack with a local chat stand-in, seeds a demo book through the real API and UI, and writes five frames into `assets/screenshots/`. The README embeds them with captions, and says where they came from.

**Tech Stack:** Python 3.14, pytest-playwright, the kernel's `run_stack`, `app/kernel/testing/vendor.py`, Markdown.

**Spec:** `docs/superpowers/specs/2026-10-31-readme-showcase-design.md`

## Global Constraints

- **No commit before the review is green** (`AGENTS.md`). Tasks 1–3 end with their
  gates; Task 4 commits.
- Images: `assets/screenshots/`, relative paths, `alt` text on every image,
  < 1 MB each, 1600×1000 px, light theme, English UI.
- The capture script runs in no gate and adds no `just` recipe. Invocation is
  `uv run python -m scripts.screenshots`.
- The README stays English; `docs/user/INDEX.md` is generated and is not touched.
- Every claim in the README must resolve to code that exists today.
- Conventional commits; `feat`/`fix` need a `User-visible:` line. None of this work
  is user-visible, so the commits are `test`, `chore` and `docs`.

## Review Focus

- **A screenshot shows text the product did not produce.** The stand-in answers
  with authored prose; the README must say so in one line, and that line stays.
- **A broken image path.** Nothing tests it; `README.md` is rendered on GitHub only
  after merge. Task 3 checks every path resolves on disk.
- **A status claim drifts again.** The two closed gaps (provider profiles, export/
  import) are pinned by a checklist in Task 3 that names the code proving each.
- **A capture run leaks a port or a stack.** A failed shot must still stop the web
  and API processes; Task 2 proves it by running twice in a row.
- **Images too heavy or too wide.** Task 2 checks size and dimensions; Task 3 checks
  the `width` attributes.
- **Missing `alt` text.** Every `<img>` in Task 3 carries one; the hero's `alt`
  describes the ghost text, not "screenshot".

---

### Task 1: The chat stand-in can answer with chosen prose

**Files:**
- Modify: `app/kernel/testing/vendor.py` (`CHAT_DELTAS`, `_chat_frames`, `ChatVendor`, `_ChatHandler.do_POST`)
- Test: `app/kernel/tests/test_llm_openai_chat.py`

**Interfaces:**
- Consumes: the existing `chat_vendor()` context manager and `EXPECTED_EVENTS`.
- Produces: `ChatVendor.set_answer(text: str) -> None`. After it, every completion
  streams `text` as ordered `Delta` events whose concatenation equals `text`, then
  one `Usage` and `DONE`. The default answer stays `CHAT_DELTAS`, so existing
  assertions are unmoved.

- [ ] **Step 1: Write the failing test** in `app/kernel/tests/test_llm_openai_chat.py`, after the `[DONE]`-marker test:

```python
async def test_a_vendor_answers_with_the_prose_the_caller_chose() -> None:
    """The stand-in says what it was told to say, in pieces, in order."""
    prose = "The fog lifted off the lake and laid itself over the road."
    with chat_vendor() as vendor:
        vendor.set_answer(prose)
        events = [
            event async for event in _provider(vendor.base_url).stream(CompletionRequest.user("Hi"))
        ]
    deltas = [event.text for event in events if isinstance(event, Delta)]
    assert len(deltas) > 1
    assert "".join(deltas) == prose
```

The file's tests are `async def` with the event list built inline; follow that.

- [ ] **Step 2: Run it to see it fail**

Run: `just test-file app/kernel/tests/test_llm_openai_chat.py`
Expected: `AttributeError: 'ChatVendor' object has no attribute 'set_answer'`.

- [ ] **Step 3: Implement the setter and the frames it feeds**

In `app/kernel/testing/vendor.py`:

```python
def _split_answer(text: str) -> tuple[str, ...]:
    """Cut prose into stream-sized pieces, the way a vendor would."""
```

Four words per piece, a trailing space on every piece but the last (the same shape
as `app/kernel/llm/fake.py::_pieces`). Then:

- `_chat_frames(*, done_line: bool, answer: tuple[str, ...])` builds its delta frames
  from `answer` instead of the module constant, keeping the finish frame, the usage
  frame and the `[DONE]` line exactly as they are;
- `ChatVendor.__init__` stores `self._server.answer = CHAT_DELTAS`;
- `ChatVendor.set_answer(text)` sets `self._server.answer = _split_answer(text)`;
- `_ChatHandler.do_POST` passes `answer=server.answer`.

- [ ] **Step 4: Run the file and the whole kernel suite**

Run: `just test-file app/kernel/tests/test_llm_openai_chat.py`
Expected: PASS, including `EXPECTED_EVENTS`'s verbatim deltas.

Run: `just test`
Expected: PASS — nothing else depends on the default answer's identity.

- [ ] **Step 5: Take the gate**

Run: `just check`
Expected: ruff and pyright clean.

---

### Task 2: The capture script and the five frames

**Files:**
- Create: `scripts/screenshots.py`
- Create: `assets/screenshots/01-workspace-continuation.png`, `02-chat-sources.png`,
  `03-entities-review.png`, `04-consistency-check.png`, `05-shelf.png`
- Reference (read, do not modify): `app/capabilities/writing/e2e/test_novels_e2e.py`,
  `test_chapters_e2e.py`, `test_continuation_e2e.py`,
  `app/capabilities/chat/e2e/test_chat_e2e.py`,
  `app/capabilities/knowledge/e2e/test_knowledge_e2e.py`,
  `app/capabilities/knowledge/e2e/test_knowledge_dock_e2e.py`,
  `app/capabilities/writing/e2e/test_coherence_e2e.py`

**Interfaces:**
- Consumes: `ChatVendor.set_answer` (Task 1), `run_stack(database=..., seed_user=..., env=...)`,
  `url_for`, the settings API (`PATCH /api/settings {"locale": "en"}`).
- Produces: `capture(out: Path) -> list[Path]` and `main()`; five PNGs named as above.

- [ ] **Step 1: Write the script's skeleton and its demo content**

Module docstring (fixed, this is the discoverability mechanism):

```
"""Capture the README's images from the real app.

Run: uv run python -m scripts.screenshots. Needs Docker's Postgres (`just dev-services`).
Re-run when a surface below changes; a stale image claims a UI that no longer exists.
The prose in the shots comes from the test boundary's chat stand-in, not from a model:
the README says so, and says it plainly.
"""
```

Then, as module constants, `DEMO`:

- novel title `The Salt Road`;
- chapters `One — The Tide Line`, `Two — Salt and Ash`, `Three — The Lighthouse Keeper`,
  the first carrying ~200 words of English prose, the others ~80 each;
- four character names the prose actually mentions (the extractor proposes the
  passage's capitalized words, so names must be capitalized and appear);
- two notes uploaded as plain text: a story bible paragraph and a timeline paragraph.

And the stand-in's answer, kept next to the demo prose it continues:

```python
CONTINUATION = (
    "The lamp swung once, and the fog answered it — a slow grey turning "
    "that swallowed the pier and gave nothing back."
)
```

- [ ] **Step 2: Write `capture(out)`**

One function, top to bottom, each step citing the E2E test it mirrors in a comment:

1. `with chat_vendor() as vendor:` — its `base_url` feeds `NARRE_LLM_BASE_URL`;
2. `with run_stack(database="narrare_v2_screenshots", seed_user=True, env={...})` where
   `env` is `NARRE_LLM_PROVIDER=openai-chat`, `NARRE_LLM_BASE_URL=<vendor>/v1`,
   `NARRE_LLM_MODEL=vendor-max`, and no key (localhost needs none — `needs_api_key`);
3. `vendor.set_answer(CONTINUATION)`;
4. `sync_playwright()` → `browser.new_context(viewport={"width": 1600, "height": 1000},
   locale="en-US", color_scheme="light", device_scale_factor=1)`;
5. `PATCH /api/settings` with `{"locale": "en"}`, then reload — the app's default is
   "auto" and the browser locale alone is not the setting the UI reads;
6. seed through the UI, in the order the tests do: create the novel, three chapters,
   type the prose, wait for `Saved`, upload both notes, run extraction and accept two
   entries, run the consistency check;
7. one `page.screenshot(path=out / name)` per frame at the state the frame's caption
   claims — the workspace shot with the ghost text visible and uncommitted (no Tab!);
8. return the written paths.

The context manager unwinds in the reverse order, so a raise in step 6 still stops
the web and API processes.

- [ ] **Step 3: Write `main()`**

`argparse` with `--out`, default `Path("assets/screenshots")`, created with
`mkdir(parents=True, exist_ok=True)`; print each path; exit non-zero when fewer than
five files were written.

- [ ] **Step 4: Run it**

Run: `just dev-services` then `uv run python -m scripts.screenshots`
Expected: five paths printed, five files on disk.

- [ ] **Step 5: Check weight, geometry and determinism**

```bash
file assets/screenshots/*.png     # every one: PNG image data, 1600 x 1000
du -h assets/screenshots/*.png    # every one under 1.0M
sha256sum assets/screenshots/*.png > /tmp/opencode/shots-a.txt
uv run python -m scripts.screenshots
sha256sum assets/screenshots/*.png > /tmp/opencode/shots-b.txt
diff /tmp/opencode/shots-a.txt /tmp/opencode/shots-b.txt
```

Expected: no diff — same state, same bytes. A diff means a clock, a random id or an
animation reached a frame; find it before continuing.

- [ ] **Step 6: Look at them**

Read all five images. Reject a frame that shows: an empty state, a German string, a
`Lorem`-like line, the ghost text already committed, a scrollbar mid-page, or a
focused control drawing a focus ring the reader cannot explain. Re-shoot until each
one carries its caption's claim.

- [ ] **Step 7: Take the gate**

Run: `just check`
Expected: ruff clean on `scripts/screenshots.py`.

---

### Task 3: The README rewrite

**Files:**
- Modify: `README.md` (sections 2–4 and 7 of the design's structure)
- Modify: `CONTRIBUTING.md` (one line, under the docs/quality material)

**Interfaces:**
- Consumes: the five files from Task 2, by their exact names.
- Produces: nothing other tasks read.

- [ ] **Step 1: Insert the hero image and the gallery**

Under the logo and tagline, before the product paragraph:

```html
<img src="assets/screenshots/01-workspace-continuation.png" alt="The Narrare workspace: a chapter rail on the left, the chapter in the editor, and a grey continuation waiting at the caret for Tab" width="800">
```

Then a `## What it looks like` section: four images in a two-column Markdown table,
`width="340"` each, each with the caption line from the design's image table, and
under the table exactly this sentence:

> The images come from the app itself, captured by `scripts/screenshots.py`; the
> prose in them is supplied by a stand-in model, so nothing here was written by one.

- [ ] **Step 2: Cut the feature list to five bullets**

One bullet per claim from the design's structure, each naming a visible result. Keep
`F9`, `Tab`, `Esc` and the three language names — they are the page's only concrete
details. Delete nothing else from the section.

- [ ] **Step 3: Correct the status**

Replace the three-gap sentence with the design's table in prose: provider profiles and
per-task assignment live in the app; a manuscript exports to and imports from a
portable archive; series do not exist. The "next on the list" sentence loses provider
settings and export.

- [ ] **Step 4: Add the developer-setup line to Getting started**

One sentence, after the two commands: this is a developer setup, and the default
provider answers without a key — the model is configured in the app's settings, or in
`.env` for the whole process. Delete the claim that provider settings are planned.

- [ ] **Step 5: Verify every claim and every path**

```bash
test -f assets/screenshots/01-workspace-continuation.png && ... # all five
rg -n "settings area|provider" app/capabilities/settings/web/ProviderPage.tsx
rg -n "ExportNovelDialog|ImportArchiveDialog" app/capabilities/writing/web/NovelsPage.tsx
```

Expected: each README claim has a file that proves it; no image path is missing.
Then read the README once as a visitor: no sentence promises what the code does not do.

- [ ] **Step 6: Add the recapture line**

Last bullet of `Where to look next`, and one line in `CONTRIBUTING.md`:
`uv run python -m scripts.screenshots` recaptures the README's images.

- [ ] **Step 7: Take the gate**

Run: `just check`
Expected: clean (Markdown is not linted in this repo; the check is that nothing else broke).

---

### Task 4: Review, commits, PR, repository settings

**Files:** none; this task moves what exists.

- [ ] **Step 1: Fresh reviewer**

Dispatch the reviewer on the uncommitted change. Findings that survive become commits
of their own or GitHub issues labelled `follow-up` (`AGENTS.md`), one per finding.

- [ ] **Step 2: Commit in three, after the review is green**

```bash
git add app/kernel/testing/vendor.py app/kernel/tests/test_llm_openai_chat.py
git commit -m "test(vendor): the chat stand-in can answer with chosen prose"

git add scripts/screenshots.py assets/screenshots
git commit -m "chore(screenshots): one command captures the README's five images"

git add README.md CONTRIBUTING.md
git commit -m "docs(readme): the page shows the app and the state it is in"
```

- [ ] **Step 3: Verify the gate the branch will meet**

Run: `just verify all`
Expected: every suite green. `just test-e2e` narrows to the capabilities the branch
touched — `app/kernel/testing/vendor.py` is shared, so the resolver may name every
suite; let it run.

- [ ] **Step 4: Open the PR**

Title: `docs(readme): the page shows the app and the state it is in`. Body: what the
page now claims, that the images are generated and how to recapture them, and the spec
link. Set the branch to auto-merge off (a human approves).

- [ ] **Step 5: After merge, the repository settings**

```bash
gh repo edit --add-topic fiction --add-topic ai-writing --add-topic pgvector
gh repo view --json description,repositoryTopics,homepageUrl
```

Expected: description unchanged (it already carries the tagline), eleven topics, no
homepage. The social preview has no API: report to the owner that
`assets/logo/social-og.png` is set under Settings → General → Social preview.
