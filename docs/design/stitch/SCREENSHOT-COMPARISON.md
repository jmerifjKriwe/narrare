# Screenshot comparison against the Stitch drafts

The Stitch exports under `screens/` are design drafts, not specifications (see
the README). A visual comparison needs a *populated* instance, because empty
shelves and empty graphs tell nothing about density, spacing or chrome. The
showcase specs that once seeded one were removed with the frontend rebuild (W0)
and have not returned.

> **Suspended for the rebuild interim (W0).** The capability screens were
> demolished for the frontend rebuild, and the showcase specs left with them.
> No showcase spec exists in the tree. The `showcase` pytest marker and the
> `just test-e2e` filter that excluded it were removed on 2026-11-28. The drafts
> under `screens/` stay here as the reference W1 harmonizes and W2 ports.

## The removed capture specs

Three E2E specs once seeded a real instance with Stitch-canonical data and
captured screenshots:

| Capability | Screenshots |
|---|---|
| Writing | `shelf.png`, `workspace-dead-signal.png` |
| Knowledge | `knowledge-graph.png` |
| Planning | `planning-chronology.png`, `planning-storyboard.png`, `planning-structure.png` |

They were deleted with W0 and have not been rebuilt. A screenshot or visual
comparison harness is maintainer-only tooling: it has no user-reachable path, so
it gets no E2E suite and owes unit or integration tests instead
([`CONSTRAINTS.md`](../../_shared/CONSTRAINTS.md), rule 2). Rebuild the capture as
a tool, not as a browser test.

## What the seeds contained

- **Writing**: Dead Signal (3 chapters, 3.384 words), Winterhaus (0), The Salt
  Road (12 chapters, 24.144 words), Der Nebel von Arkona (5 chapters, 11.200
  words) — word totals taken from `screens/library/shelf.webp`. Dead Signal's
  first chapter carries the prose the workspace screen draws, padded to its
  stated 765 words.
- **Knowledge**: one novel whose chapter body names the capitalized entities the
  fake provider turns into nodes (Maya, Chen, Horizon, Station, Kavic, …). The
  entities are derived, not curated — read the screenshot for chrome/density,
  not for exact labels.
- **Planning**: one novel with five timeline events and one chapter carrying
  four scenes.

## How to compare

When a populated capture exists, open it next to the corresponding `.webp`:

- `shelf.png` ↔ `screens/library/shelf.webp`
- `workspace-dead-signal.png` ↔ `screens/writing/workspace*.webp`
- `knowledge-graph.png` ↔ `screens/knowledge/lore-graph*.webp`
- `planning-chronology.png` ↔ `screens/planning/chronology-timeline.webp`
- `planning-storyboard.png` ↔ `screens/planning/three-act-storyboard.webp`

Read for drift in layout, spacing, typography scale and component chrome. The
Stitch drafts are not the spec — where they and the frontend-design spec
disagree, the spec decides (`docs/superpowers/specs/`).

## Why not a unified seed for the automated suites

The automated E2E suites keep their own minimal per-test seeds: isolation
between tests, CI narrowing to touched capabilities, and the different shapes
each test needs (empty DB, 50 scenes, …). The removed showcase was a development
and visual-review tool, not a test fixture.
