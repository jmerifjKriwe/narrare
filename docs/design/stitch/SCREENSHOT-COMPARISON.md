# Screenshot comparison against the Stitch drafts

The Stitch exports under `screens/` are design drafts, not specifications (see
the README). A visual comparison needs a *populated* instance, because empty
shelves and empty graphs tell nothing about density, spacing or chrome. The
showcase specs seed one.

> **Suspended for the rebuild interim (W0).** The capability screens were
> demolished for the frontend rebuild, and the showcase specs left with them
> (`app/capabilities/*/e2e/`). The comparison workflow below is suspended
> until the screens return and new showcase specs ship with them; the drafts
> under `screens/` stay here as the reference W1 harmonizes and W2 ports.

## Showcase specs

Three E2E specs seed a real instance with Stitch-canonical data and capture
screenshots:

| Capability | Spec | Screenshots |
|---|---|---|
| Writing | `app/capabilities/writing/e2e/test_showcase_e2e.py` | `shelf.png`, `workspace-dead-signal.png` |
| Knowledge | `app/capabilities/knowledge/e2e/test_showcase_e2e.py` | `knowledge-graph.png` |
| Planning | `app/capabilities/planning/e2e/test_showcase_e2e.py` | `planning-chronology.png`, `planning-storyboard.png`, `planning-structure.png` |

They are marked `@pytest.mark.showcase` and are **excluded from the CI E2E
matrix** (`just test-e2e` runs `-m "e2e and not showcase"`). Run them on
demand:

```bash
just test-e2e writing      # then inspect /tmp/opencode/showcase/
```

or directly:

```bash
uv run pytest app/capabilities/writing/e2e/test_showcase_e2e.py -m showcase
```

Screenshots land in `/tmp/opencode/showcase/` (gitignored location; copy them
wherever you compare).

## What the seeds contain

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

1. Run the relevant showcase spec.
2. Open the captured PNG next to the corresponding `.webp`:
   - `shelf.png` ↔ `screens/library/shelf.webp`
   - `workspace-dead-signal.png` ↔ `screens/writing/workspace*.webp`
   - `knowledge-graph.png` ↔ `screens/knowledge/lore-graph*.webp`
   - `planning-chronology.png` ↔ `screens/planning/chronology-timeline.webp`
   - `planning-storyboard.png` ↔ `screens/planning/three-act-storyboard.webp`
3. Read for drift in layout, spacing, typography scale and component chrome.
   The Stitch drafts are not the spec — where they and the frontend-design spec
   disagree, the spec decides (`docs/superpowers/specs/`).

## Adding a new showcase

- Create `app/capabilities/<cap>/e2e/test_showcase_e2e.py`.
- Mark it `pytestmark = [pytest.mark.e2e, pytest.mark.showcase, pytest.mark.timeout(300)]`.
- Seed through the real API (no DB shortcuts, no mocks).
- Capture with `page.screenshot(path=str(SHOTS / "<name>.png"), full_page=True)`.
- Document the new row above.

## Why not a unified seed for the automated suites

The automated E2E suites keep their own minimal per-test seeds: isolation
between tests, CI narrowing to touched capabilities, and the different shapes
each test needs (empty DB, 50 scenes, …). The showcase is a development and
visual-review tool, not a test fixture.
