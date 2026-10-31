# Narrare Brand Assets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Narrare's brand asset family: tile-N icon, EB Garamond wordmark (hardened paths), horizontal lockup, favicons (SVG + PNG), GitHub social preview and repo avatar; favicon links in `web/index.html`, lockup embed in `README.md`.

**Architecture:** Every SVG shares one glyph source: EB Garamond 600, subset "Narrare", extracted to paths via `fontTools`. Raster derivatives are rendered offline with `cairosvg`. One canonical fixed palette, computed from the tokens in `web/globals.css`; no token change, no web font introduction.

**Tech Stack:** Python 3.14 (`.venv`), fontTools + brotli, cairosvg, Pillow; git + gh CLI; `just check` / `just verify` as gates.

**Spec:** `~/.opencode/plan/2026-10-30-brand-assets-design.md` (this build
moves it together with this plan to `docs/superpowers/specs/` and
`docs/superpowers/plans/` respectively and commits both; move, never copy).

## Global Constraints

Work happens on branch `openchamber/brand-assets` (started from `main`);
`main` is branch-protected — no direct push. **Nothing is committed before
the review is green.** The commit comes only after Task 7. No `--no-verify`.

**Fixed palette (verbatim, computed from tokens):**
- tile `#743B1F` (← `oklch(0.42 0.09 45)`)
- glyph on tile `#FCFAF6` (← `oklch(0.985 0.005 85)`)
- ink/wordmark `#24211C` (← `oklch(0.25 0.01 85)`)
- `#D39562` is used by no asset in this plan.

**Script boundaries:** no `<text>`, `<font>` or `font-family` strings in a
committed SVG; paths from Task 1 only. Canonical fixed palette, no theme
variants. The prose surface and the tokens stay unchanged.

**Expected file set (porcelain boundary for Task 7; coordinator ruling
"asset family, one-off"):**
Create: `assets/logo/icon.svg`, `assets/logo/wordmark.svg`,
`assets/logo/lockup.svg`, `web/public/favicon.svg`,
`web/public/favicon-32.png`, `web/public/favicon-16.png`,
`web/public/apple-touch-icon-180.png`, `assets/logo/social-og.png`,
`assets/logo/avatar.png`.
Modify: `web/index.html`, `README.md`.
Nothing outside this set goes into the commit.

**Task report path:** `/tmp/opencode/brand/task-report.md` — the implementer
keeps it current (field vocabulary: status, files, ledger, verify,
deviations, concerns; terse, one field per line block).

**Verification stance:** run command by command, read the output; a gate
counts only with its output read. Missing tools get installed locally
(`.venv`), no skip guards.

## Review Focus

The inputs the spec implies but no task test catches, plus the test that
pins each one (in its own task):

1. **16 px favicon in a dark tab** — the glyph must stay legible without
   theme help (the tile carries its ground). Pinned in Task 3: visual
   screenshot check on a dark surface + pixel probe (centre = `#743B1F` on
   the tile, corner transparent).
2. **README on GitHub without the font installed** — an accidental
   `<text>`/`font-family` would fall back to Georgia. Pinned in Task 2:
   `rg -ic 'text|font-family'` over all three SVGs must return 0.
3. **Kerning jumps at "aa"/"ar"** (advances only, no GPOS) — pinned in
   Task 5: screenshot at working width; correctable only via the logged
   letter offset (±6 units, recorded in deviations).
4. **GitHub social image composition** (2:1, edges free of ink): exactly
   1280×640, ink ≥64 px from the edge. Pinned in Task 4: pixel probe + bbox.
5. **Local-first:** build/CI must not depend on the network — font and
   raster tools only in Task 1; no font file is committed. Pinned in
   Task 7: porcelain contains no `.woff2`/`.ttf`.

---

### Task 1: Tools + glyph extraction

**Files:**
- Create: `/tmp/opencode/brand/glyphs.json` (output), `/tmp/opencode/brand/task-report.md`
- No repo file.

**Interfaces:**
- Consumes: EB Garamond subset WOFF2 (see step 2).
- Produces: `glyphs.json`: `{"upem": <int>, "glyphs": {"N": {"name": <str>, "d": <str>, "advance": <int>}, "a": …, "r": …, "e": …}}`. Paths in font units (y-up, not yet mirrored). Tasks 2–4 consume exactly this schema.

- [ ] **Step 1: Install tools and log versions**

`.venv/bin/pip install fonttools brotli cairosvg Pillow`, then
`.venv/bin/python -c "import fontTools, brotli, cairosvg, PIL; print(fontTools.version)"`.
Expected: a version line. If it fails: abort the task, report.

- [ ] **Step 2: Obtain the subset font (network-tolerant, offline-first)**

`/tmp/opencode/fs/ebgaramond.woff2` already exists (session 2026-10-30).
If missing, reproduce exactly:
`curl -s -A "<browser UA, Chrome format>" "https://fonts.googleapis.com/css2?family=EB+Garamond:wght@600&text=Narrare&display=swap"`,
then fetch the single `https://fonts.gstatic.com/…` URL from that CSS.
Expected: the file exists, `file` says "Web Open Font Format (Version 2)".

- [ ] **Step 3: Extract glyphs (script body, binding)**

```python
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
import json

font = TTFont("/tmp/opencode/fs/ebgaramond.woff2")
upem = font["head"].unitsPerEm
cmap = font.getBestCmap()
glyphset = font.getGlyphSet()
hmtx = font["hmtx"]
glyphs = {}
for ch in ["N", "a", "r", "e"]:
    gname = cmap[ord(ch)]
    pen = SVGPathPen(glyphset)
    glyphset[gname].draw(pen)
    glyphs[ch] = {"name": gname, "d": pen.getCommands(), "advance": hmtx[gname][0]}
assert all(g["d"] for g in glyphs.values()), "empty path"
assert upem == 1000, f"unexpected upem: {upem}"
json.dump({"upem": upem, "glyphs": glyphs}, open("/tmp/opencode/brand/glyphs.json", "w"))
print("upem", upem, "| advances:", {k: v["advance"] for k, v in glyphs.items()})
```

- [ ] **Step 4: Read the output and verify**

N, a, r, e each with a non-empty `d`; `upem == 1000`; log the advances
(N > a ≥ r with e-advance > r-advance, sanity-checked). Record the four real
glyph names from `name` (e.g. `N: uniN`); file the result under a "Task 1"
heading in the report.

### Task 2: SVG family (icon, wordmark, lockup)

**Files:**
- Create: `assets/logo/icon.svg`, `assets/logo/wordmark.svg`, `assets/logo/lockup.svg`

**Interfaces:**
- Consumes: `glyphs.json` (Task 1).
- Produces: SVG family with a geometry contract: tile in a 96 viewBox (rect x=4 y=4 w=88 h=88 rx=20, fill `#743B1F`); N with ink-box height 62 units, baseline y=71, horizontally centred on 48. Wordmark: N cap height 34, baseline y=24, glyphs from x=0 with advance offsets, viewBox from the ink bbox with 2 units padding. Lockup: icon at x=0, wordmark group at x=112, baseline formula "tile centre + cap height/2" = y=65 (±6 units correction allowed, recorded in deviations).

- [ ] **Step 1: Write and run the builder script**

A Python script (annexed to the report) that writes the three SVGs from
`glyphs.json`. Per-glyph transform: `Transform(s, 0, 0, -s, dx, baseline_y)`
with `s = target_height / bbox_height` (compute the bbox numerically from
the path). Kerning: advances without GPOS kerning — pin with its reason:
EB Garamond kerning for N-a/a-r/a-r is visually near-zero, checked in
Task 5.

- [ ] **Step 2: Verification (full only, otherwise abort)**

`.venv/bin/python - <<'EOF'` check script with exactly these assertions:
1. XML parseability of every SVG (xml.etree).
2. `rg -ic 'text|font-family' assets/logo/*.svg` → 0 matches.
3. Wordmark: exactly 6 `<path>` children, order n-a-r-a-r-e.
4. Icon: exactly 1 `rect` + ≥1 path; colour `#743B1F`/`#FCFAF6` verbatim.
5. Wordmark: only `#24211C` as fill.
6. Lockup: congruent copy of the defined tile + wordmark group.
7. Colour location: `rg -c '#743B1F' icon.svg lockup.svg` → ≥1 each.
Paste the output verbatim into the report.

### Task 3: Favicons + index.html

**Files:**
- Create: `web/public/favicon.svg`, `web/public/favicon-32.png`, `web/public/favicon-16.png`, `web/public/apple-touch-icon-180.png`
- Modify: `web/index.html` (after `<title>`)

**Interfaces:**
- Consumes: `icon.svg` geometry (Task 2).
- Produces: favicon sets; 4 exact `<link>` lines in `web/index.html` (block: rel=icon svg + 32 + 16 + apple-touch-icon).

- [ ] **Step 1: Build favicon.svg + the apple-touch source**

`favicon.svg` = icon geometry unchanged (the 96 viewBox scales in browsers).
Apple-touch needs a full edge: a separate 96 source with `rx=0`
(rect 0,0,96,96, ink `#FCFAF6`), temporary only.

- [ ] **Step 2: Rasterize the PNGs (cairosvg)**

favicon.svg → 32 and 16 px; apple-temp.svg → 180 px. Output into
`web/public/`. Command + log into the report.

- [ ] **Step 3: index.html gets exactly these 4 lines** after the `<title>`:

```html
<link rel="icon" href="/favicon.svg" type="image/svg+xml" />
<link rel="icon" href="/favicon-32.png" sizes="32x32" type="image/png" />
<link rel="icon" href="/favicon-16.png" sizes="16x16" type="image/png" />
<link rel="apple-touch-icon" href="/apple-touch-icon-180.png" />
```

- [ ] **Step 4: Verification**

Pillow IHDR: 32×32, 16×16, 180×180; pixel probes: apple-touch (0,0) =
`#743B1F`; favicon-32/-16: corner transparent (alpha 0), centre = `#743B1F`
(the tile starts at 4/96, the corner is outside). `rg -c 'rel="icon"'
web/index.html` → 2, `rg -c 'apple-touch-icon' web/index.html` → 1.
`just check` → PASS (unabridged output into the report).

### Task 4: GitHub assets + README

**Files:**
- Create: `assets/logo/social-og.png` (1280×640), `assets/logo/avatar.png` (1024×1024)
- Modify: `README.md` (one line after the badge block, before the `> Local-first, …` quote)

**Interfaces:**
- Consumes: tile + wordmark geometry (Task 2).
- Produces: PNGs as finished assets; README line:
  `<img src="assets/logo/lockup.svg" alt="Narrare" width="180" />`

- [ ] **Step 1: Build social-og.svg (temp)**

Paper ground (1280×640, 100 % `#FCFAF6`), lockup centred: tile 260 px,
wordmark cap height 92, gap 65, baseline = 320+46 (±6, deviation log).
Every part ≥64 px from the edge.

- [ ] **Step 2: Build avatar.svg (temp)**

1024×1024, entirely `#743B1F` (rx=0, full edge), N ink height 560, glyph
centre (512, 512).

- [ ] **Step 3: Rasterize and set the README line**

`cairosvg` both; README line exactly as above, one line after the last badge
line, one blank line before `> Local-first`.

- [ ] **Step 4: Verification**

Pillow: 1280×640 and 1024×1024; pixel probes: og corner = `#FCFAF6`,
avatar corner = `#743B1F`; `rg -c 'assets/logo/lockup.svg' README.md` → 1.
`just check` → PASS.

### Task 5: Visual check (preview + screenshots)

**Files:**
- Create: `/tmp/opencode/brand/preview.html` (temp), 3 screenshots.

**Interfaces:**
- Consumes: all assets.

- [ ] **Step 1: Build the preview page**

Lockup, favicon chips at 24 px and 16 px, wordmark alone on paper, next to
it a dark strip with the tile, below og/avatar as PNGs.

- [ ] **Step 2: Screenshots + kerning checks**

`python3 -m http.server` in `/tmp/opencode/brand`, browser shell (openchamber
browser.open → capture): lockup 1:1, favicon row 1:1, og/avatar 1:1 each.
Report: screenshot paths + kerning assessment ("ra" pair) — if needed,
correct the baseline offset in code, ±6 only, then re-verify the Task 2 SVGs.

- [ ] **Step 3: Trigger the owner check**

Show the screenshots to the owner in the report (verdict: correction pass or
sign-off). No silent sign-off replaces this step.

### Task 6: Open the follow-up issue (EB Garamond web font)

- [ ] **Step 1: Validate the issue draft and create it**

`gh issue create --label follow-up --title "brand: EB Garamond web font for the prose surface" --body-file /tmp/opencode/brand/issue-body.md`
(the draft lives in the design doc, §Follow-up). Keep the title grammar;
`User-visible:` belongs in the commit, not in an issue.

### Task 7: Branch, commit, PR (after review!)

**Files:** only the Create/Modify paths listed under Global Constraints.

- [ ] **Step 1: Branch and worktree**

`openchamber/brand-assets` from `main` (full isolation via the worktree
skill where needed: `superpowers:using-git-worktrees`). Porcelain pre-check:
tree clean, nothing beyond the expected set (committable files only),
otherwise abort.

- [ ] **Step 2: `just verify`**

Full gate run, unabridged. PASS, output into the report. Failure → abort,
no fix across task boundaries without a ruling.

- [ ] **Step 3: Guarded commit (porcelain pre-flight)**

Stage exactly and only the set listed above (no ADR draft, no font files,
no temp SVGs), then one commit:

```text
feat(brand): logo icon, wordmark and favicon family

Adds the first brand asset set: tile-N icon (#743B1F/#FCFAF6), EB Garamond
wordmark traced to paths, horizontal lockup, favicon SVG + PNG 32/16/180
and GitHub avatar + social preview raster. Palette read verbatim from
web/globals.css; the token surface is unchanged.

User-visible: the browser tab shows the Narrare favicon; README and repo
carry the Narrare logo.

Provenance: glyphs N,a,r,e from the EB Garamond subset (600), advances only
(GPOS kerning for the pairs visually near-zero, verified in the preview).

Deviations: [from the task report, verbatim]

Verify: just verify green; PNG dims 32/16/180/1280x640/1024 confirmed.
```

(Name note: every name string in the final commit reads exactly "Narrare".)

- [ ] **Step 4: Post-commit verification + push + PR**

`git status --porcelain` → clean; `git log --oneline -1` → one line, subject
matches the structure above. Push to `narrare` (the remote is named
`narrare`, not `origin`), `gh pr create --base main` with the title
`feat(brand): logo, favicon and wordmark family` and the report link in the
body. Finish the report (all six fields).

## Self-Review (completed)

- Spec coverage: design decisions → Tasks 1–4 (assets + integration), Task 5
  (visual check), Task 6 (follow-up issue), Task 7 (commit/PR). No gap.
- Step scan: no "TBD"; every step decides exactly one thing; the builder
  scripts live as an annex in the report (not in the plan transcript).
- Type consistency: `glyphs.json` schema defined once; `#743B1F`/`#FCFAF6`
  /`#24211C` verbatim consistent; the 96 viewBox constant across tasks.
- Review focus: 1→Task 3 (pixel + screenshot), 2→Task 2 (rg), 3→Task 5
  (kerning), 4→Task 4 (dims + edge), 5→Task 7 (porcelain).
- Proportion: the plan runs ~180 lines with 5 script blocks instead of a code
  transcript — proportionate to the density of design decisions.

## Corrections after execution (2026-10-30, commit ee6761d1)

The plan stays unchanged as the historical record; what differed during
execution is listed here and in the task report. For a re-run, these values
govern.

1. **The wordmark has seven glyphs**, not six: `N-a-r-r-a-r-e` (double r).
   Task 2 step 2 is wrong with "exactly 6 `<path>`".
2. **`rel="icon"` lines: three**, not two (SVG + 32 + 16); the Task 3
   verify line wrongly says 2.
3. **Pixel probe:** the favicon centre is ink, not tile colour. Tile pixels
   below the glyph are probed instead (32 px: (16,28); 16 px: (8,14));
   corners are transparent.
4. **Icon baseline:** the pin `y=71` contradicted its own centring; the
   computed value is `y = 77.35` (ink centre exactly 48).
5. **Task 7 file set: 13 files** — the plan's 11 plus the two documents the
   AGENTS.md plan-mode rule moves (design doc, plan).
6. **og ruling:** the three og pins were jointly unsatisfiable (tile 260
   with cap 92 from two frames of reference). What holds: visible tile 260,
   everything through `K = 260/88` → cap 100.45, baseline 370.23, tile N
   183.2, gap 59.1.
7. **Kerning:** the subset carries GPOS (N→a −11, N→r −8, N→e −16, r→e −8
   units); at shipped sizes that is ≤1.5 px, so it is not applied — wording
   "visually negligible" instead of "near-null".
8. **`sizes` attributes:** the SVG icon carries `sizes="any"`, apple-touch
   `sizes="180x180"` (Task 3 step 3 does not show them yet).

9. **Font source is pinned by hash, not by file type.** The subset actually used
   is `sha256 89b31e893f533c49fe658772242d9639b7083593c8bfe67c28c25032cc727e31`
   (6 glyphs, 17 tables, 1452 bytes, resolved from the pinned Google css2 URL).
   A re-run verifies that hash before extracting; a `file` check alone is not
   enough.
10. **SVG validation covers every committed SVG,** including
    `web/public/favicon.svg` (it is an unchanged copy of `icon.svg`). The
    text/font-family sweep over all four files returns 0
    (`rg -ic 'text|font-family' assets/logo/*.svg web/public/favicon.svg` →
    no matches), and the reviewer confirmed it independently.

11. **README alt text is empty by owner decision.** The lockup is decorative;
    the H1 directly above it is the accessible name, so `alt=""` is correct and
    the plan's `alt="Narrare"` in Task 4 is superseded. CodeRabbit's contrary
    finding was declined with this reason on PR #454.
12. **The forbidden-element sweep is `rg -ic 'text|font'`**, not
    `'text|font-family'`: the latter would let a literal `<font>` element
    through. Verified over all four SVGs (three in `assets/logo/`, plus
    `web/public/favicon.svg`): no matches, exit code 1.
13. **Preview assets are copied next to the page.** Task 5 serves
    `/tmp/opencode/brand`, while the assets live in `assets/logo/` and
    `web/public/`; before serving, all eight were copied into
    `/tmp/opencode/brand/a/` and `preview.html` references `a/<file>`. Without
    that copy step the relative URLs would 404.
