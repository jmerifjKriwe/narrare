# Screenshot font determinism

## Intent

The post-merge `Screenshots` run opened PR #1010 because local and CI renders use different system fonts for `⌘` and every `font-mono` surface. The PNGs have real glyph-rasterization differences, not compression noise. Remove the remaining system-font lookups so environment-only changes cannot open screenshot PRs.

## Goals

- Self-host IBM Plex Mono 400/500/600/700 from the pinned `@fontsource/ibm-plex-mono@5.3.0` package, with its OFL license.
- Make `--font-mono` use the bundled family first for keycaps, badges, code, dates and numeric metadata.
- Replace the visible `⌘` text glyph in TopBar and InspectorDock with a repo-owned SVG command icon; keep accessible shortcut labels unchanged.
- Verify through the strict CI Screenshots run that the bundled fonts make environment-only glyph differences disappear.
- Rebaseline all 25 masters once and keep the generated collection index byte-identical.
- Preserve the workflow's strict rule: real pixel changes still open a PR.

## Non-goals

- No perceptual tolerance or coordinate mask that could hide real UI changes.
- No runner-image or CI font-package pinning as the primary fix.
- No PNG re-encoding helper; the discarded exact-pixel alignment experiment does not address this incident.
- No browser-side font guard or meta E2E test: it tests screenshot tooling, not the app, and costs full-gate time without being the real acceptance signal.
- No new route, API, schema or user-visible surface.

## Approaches considered

1. **Bundle the missing fonts and draw `⌘` as SVG — chosen.** Removes the cause rather than suppressing its output. Costs one visual rebaseline and a small font/license addition.
2. **Pin CI fonts and runner to the local environment.** Stabilizes CI only; arbitrary developer machines can still differ and the removed font-install cost returns.
3. **Ignore known glyph regions or use a pixel tolerance.** Smaller, but can hide real text changes in exactly those regions.

## Implementation shape

- Add four WOFF2 assets and `IBMPlexMono-OFL.txt` under `web/public/fonts/`.
- Add `@font-face` declarations and point `--font-mono` at `IBM Plex Mono` in `web/globals.css`.
- Add a `command` SVG to `web/ui/icons.tsx`; render it inside the `⌘K` and `⌘J` keycaps with the bundled mono face for `K`/`J`.
- Keep the existing `document.fonts.ready` wait; do not add a browser-side font guard.
- Add focused component/asset tests for the command icon, font assets/token and the strict workflow gate.
- Regenerate all 25 masters from two identical local runs; inspect keycap, badge and representative prose frames.

## Acceptance

- No rendered U+2318 text depends on a system font.
- All `font-mono` CSS resolves to the bundled family as the first choice.
- Two independent local captures are byte-identical.
- A CI Screenshots run on the fix branch produces no new screenshot PR after the rebaseline.
- A deliberate one-pixel fixture change still counts as a real difference; no tolerance is introduced.
- Existing screenshot, component, accessibility and E2E gates remain green.

## Commit

One reviewed task commit: `fix(web): use bundled fonts for keycaps and badges`, including the font assets, component/CSS changes, tests and regenerated masters. It carries a real `User-visible:` line and the Assisted-by trailer. No issue is closed twice and no merge occurs without owner approval.
