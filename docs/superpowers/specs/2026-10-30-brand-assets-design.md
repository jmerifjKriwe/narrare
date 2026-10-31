# Brand assets (logo family) — design

Date: 2026-10-30. Status: approved by the owner (chat, 2026-10-30).

## What gets built

Narrare has no brand asset at all (no favicon, no logo, no `public/`). This
builds the full family on the identity that already exists in
`web/globals.css` (warm paper at hue 85, sepia primary at hue 45). No rebrand:
the tokens are and remain the single design surface.

## Design decisions (chosen by the owner)

1. Motif: variant D, the tiled monogram. A rounded tile in `--primary` with a
   serifed N in the paper tone. The tile carries its own ground, so it reads
   on light and dark themes and at 16 px (verified in the mockup session).
2. Serif: EB Garamond, weight 600. Chosen from four candidates (EB Garamond,
   Fraunces, Newsreader, Cormorant Garamond), compared live as subsets.
3. Glyph hardening: the N and "Narrare" are converted from the font into SVG
   paths. No `<text>` and no font file in the repo, so the mark renders
   identically everywhere: README, GitHub, SVG, PNG.

## Fixed colours

Derived from the tokens (`oklch` → sRGB, rounded to 8 bits):

- tile: `#743B1F` (from `--primary`, light)
- glyph on tile: `#FCFAF6` (from `--background`, light)
- ink (wordmark): `#24211C` (from `--foreground`, light)
- `#D39562` (`--primary`, dark) is used by no asset in this build; the tile
  covers both themes.

There is one canonical palette. Alternative variants (dark tile,
`currentColor`) were rejected: no second consumer, more files.

## Expected file set

Created: `assets/logo/icon.svg`, `assets/logo/wordmark.svg`,
`assets/logo/lockup.svg`, `web/public/favicon.svg`,
`web/public/favicon-32.png`, `web/public/favicon-16.png`,
`web/public/apple-touch-icon-180.png`, `assets/logo/social-og.png` (1280×640),
`assets/logo/avatar.png` (1024×1024).
Modified: `web/index.html` (favicon links), `README.md` (header embed).

This exceeds the ≤3 production-files budget. Coordinator ruling (2026-10-30,
chat): "asset family, one-off" — the file set above is the plan's allowlist,
and any deviation aborts the guarded commit.

## Rejected approaches

- SVG `<text>` with `font-family`: renders differently without the installed
  font; unusable for README and GitHub.
- EB Garamond as a bundled web font in the app: no consumer of the assets
  needs it; kept as a separate follow-up issue (see below), not this task.

## Follow-up (a separate issue, not this task)

"Brand type at the prose surface": `web/globals.css` `.ProseMirror` uses a
Georgia serif. EB Garamond there instead of Georgia would tie the brand type
to the writing surface. Self-hosted subset in `web/public` (~50 KB, OFL,
local-first compatible). Layout metrics change slightly; gates:
`just test-frontend` plus the editor E2E.

## Parked items

- The GitHub uploads are the owner's: `social-og.png` into the repo settings
  ("Social preview"), `avatar.png` into the profile/repo settings. We only
  ship the assets.
- Favicon PNGs at 32/16/180; apple-touch is full-bleed (the OS rounds the
  corners).
