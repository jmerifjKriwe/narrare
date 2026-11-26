# README and screenshot pipeline — design

**Status:** approved in conversation, 2026-11-26 · **Owner:** kiesow · **Size:** one work package

## Intent

Close #903 and #848 on the post-W9 product. The README becomes a focused,
truthful product overview; the screenshot pipeline becomes a reproducible source
for both that overview and a larger, browsable master collection.

## Baseline

- `main` is `12186926e46932dfd01759f5777d780687052f9b`.
- W9 is complete through #956, #973 and #974. Its wave record, index #975,
  follow-ups row, roadmap and feature inventory are present.
- The update check from #965 is live but absent from the roadmap, feature
  inventory and README, and has open follow-ups #959–#964. It is outside this
  change until that inventory catches up.
- #903 and #848 are open, unassigned follow-ups before this work is claimed.

## Goals

- Show the writing workspace, Zen, knowledge, planning, settings/prompts and the
  W9 entity interview in a focused README.
- Keep one canonical PNG collection under `assets/screenshots/`, with additional
  live surfaces beyond the README subset.
- Make every capture deterministic and every image reference mechanically
  checkable.
- Re-enable manual, weekly and relevant-`main`-push regeneration without a bot
  feedback loop.

## Non-goals

- No product route, API, schema, migration or application behavior change.
- No update-check banner, release-notes modal, update-settings frame or README
  claim in this work package.
- No duplicate `gallery/` or `showcase/` PNG tree.
- No new `just` recipe and no required screenshot check.

## Anti-goals

- A screenshot implies a designed-only or not-yet-inventoried feature.
- A materially changed image overwrites an old URL and serves stale cached bytes.
- A failed capture leaves a partial master set.
- The workflow treats its own generated assets or documentation as a UI change.

## Constraints

- The five standing rules in `docs/_shared/CONSTRAINTS.md` apply.
- Frames are 1600×1000 at device scale 1, `en-US`, light by default; dark frames
  are explicit pairs. Every PNG is below 1 MB and every embedded image has
  descriptive alt text.
- Capture uses the real stack, API seeding and the fake provider at the model
  boundary. No production fake, database shortcut or mocked screenshot surface.
- `NARRE_UPDATE_CHECK_URL=off` is pinned at the capture call site. Captures do not
  use `NARRE_E2E_ATTACH`, because an attached process cannot be reconfigured by
  the caller's environment.
- Two consecutive captures produce identical PNG hashes and identical generated
  overview Markdown. The browser clock and all time/random-dependent pixels are
  pinned.
- Materially changed images receive new stable filenames. The legacy 01–19 set is
  audited keep/rename/remove before canonical generation.
- The workflow remains advisory. Schedule is Sunday 06:00 UTC; push is `main`
  only. `README.md`, `docs/**` and `assets/screenshots/**` are not UI-change
  triggers.
- Every dispatch names implementer and reviewer models explicitly, chosen from
  the local assignment. No concrete model pins belong in shared instructions.

## Approaches considered

1. **Trigger-only fix.** Re-enable `schedule` and `push` and leave the recipe
   alone. Rejected: #903 remains open, the last manual run used a dead selector,
   and Zen/W9 faces still cannot be captured.
2. **All images in the README.** Publish every master inline. Rejected: the page
   becomes noisy and images dominate the product explanation.
3. **Manifest plus curated README plus full index (chosen).** A pure manifest
   owns shot metadata and the README subset; the capture script writes PNGs and
   `docs/screenshots/README.md`; the README embeds eight curated frames and links
   to the full collection.

## Decisions

- New required faces are `20-workspace-rebuilt` through
  `34-entity-interview-dark`, covering W4 workspace/Zen, setup, knowledge,
  planning, settings/prompts and W9 create/interview.
- The README selection, in order, is:

  ```text
  20-workspace-rebuilt
  21-workspace-rebuilt-dark
  22-zen
  25-dossiers
  27-causality
  28-settings-hub
  30-prompts
  33-entity-interview
  ```

- `scripts/screenshot_manifest.py` owns `Shot`, `SHOTS`, `README_SHOTS`,
  `validate_shots` and `render_index`.
- `app/kernel/tests/test_screenshot_manifest.py` and
  `app/kernel/tests/test_screenshot_assets.py` run inside the normal backend test
  gate and pin names, selection, paths, dimensions, sizes and overview links.
- Legacy image-path corrections land with the renamed/generated assets, never in
  a later cleanup commit.
- The workflow live switch is the final implementation task. #848 and #903 close
  from that commit after capture, README, workflow lint and full-branch gates are
  green.

## Acceptance

- Both screenshot test files pass.
- Two independent captures have identical hashes and index Markdown.
- The canonical PNG directory exactly matches the manifest, with no stale files.
- The README uses exactly the eight curated frames and no stale settings claim.
- `docs/screenshots/README.md` is linked from the documentation indexes.
- actionlint and zizmor are clean.
- `just verify` passes with the full current E2E set.
- A whole-branch review is green.
- After merge, one manual `Screenshots` run succeeds and opens no PR when the
  committed assets and index are current.
