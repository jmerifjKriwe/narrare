# Stitch design drafts — narrare

The design exploration for the Narrare shell, exported from the Stitch project
`narrare` (`projects/15314899202287259920`) on 2026-11-11. It is the design
record of a proposal, not a decision and not a specification: the implemented UI
lives in `app/` and `web/`, and where this folder and the
[frontend design](../superpowers/specs/2026-10-22-frontend-design.md) disagree,
the specification and the
[architecture design](../superpowers/specs/2026-10-21-narrare-v2-architecture-design.md)
decide.

## How to read it

Each screen is a pair in `screens/<area>/`:

- `<name>.webp` — the rendered draft, 2560 px wide (2× the 1280 px canvas), WebP
  quality 82. Opens offline and in the browser.
- `<name>.html` — the generated source, as Stitch produced it. It loads Tailwind
  and Google Fonts from CDNs, so it needs a network connection to render; the
  preview is the offline view. The source is the editable form: change it in
  Stitch and re-export, or copy structures out of it — never edit it here.

Visual comparison against the drafts needs a populated instance: see
[`SCREENSHOT-COMPARISON.md`](SCREENSHOT-COMPARISON.md).

The design system behind every screen is in [`DESIGN.md`](DESIGN.md)
(`Literary Modernism`: EB Garamond for prose, Plus Jakarta Sans for chrome,
parchment and terracotta, light and dark tokens). It is the Stitch design-system
file unchanged — YAML front matter with all tokens, then the rationale — so it
can be uploaded back through Stitch's `upload_design_md` or read by any agent as
plain markdown. Its dark half is completed by [`dark-tokens.md`](dark-tokens.md):
the S0 round's Midnight-Ink values with measured contrasts and the divergences
between its two generated screens.

Documents from the same project are under [`documents/`](documents/):

- [`design-tokens.md`](documents/design-tokens.md) — the token specification:
  palette, typography, spacing, component tokens, light and dark.
- [`screen-architecture.md`](documents/screen-architecture.md) — the functional
  and conceptual screen architecture (backend and AI blueprint).
- [`style-directions.pdf`](documents/style-directions.pdf) — the uploaded style
  directions.
- [`midnight-ink-swatches.html`](documents/midnight-ink-swatches.html) — the S0
  round's dark token reference card (area hues and state colours, with contrast
  figures).
- [`midnight-ink-surface-ladder.html`](documents/midnight-ink-surface-ladder.html)
  — the second S0 card: the dark surface ladder, outline pair, secondary pairs
  and inverse pairs.

## Screens

| Area | Screen | Original label (German) | Height |
|---|---|---|---|
| Library and entry | [`shelf`](screens/library/shelf.webp) | Bücherregal | 2474 px |
|  | [`shelf-dark`](screens/library/shelf-dark.webp) | Bücherregal — Midnight Ink (S0, dark) | 1246 px |
|  | [`shelf-empty`](screens/library/shelf-empty.webp) | Bücherregal — Leerstand (G-4) | 1024 px |
|  | [`shelf-states`](screens/library/shelf-states.webp) | Bücherregal — Zustände: laden, Fehler, viele Bücher, langer Titel (G-4) | 1024 px |
|  | [`welcome-onboarding`](screens/library/welcome-onboarding.webp) | Willkommen & Autoren-Onboarding | 2570 px |
|  | [`integrated-suite`](screens/library/integrated-suite.webp) | Narrare — Integrierte Gesamtsuite (Regal, Workspace & KI-Dock) | 3664 px |
| Writing | [`workspace`](screens/writing/workspace.webp) | Schreib-Workspace | 3434 px |
|  | [`workspace-ai-dock`](screens/writing/workspace-ai-dock.webp) | Schreib-Workspace & KI-Dock | 4410 px |
|  | [`workspace-lore-dock`](screens/writing/workspace-lore-dock.webp) | Schreib-Workspace & Lore-Dock (Kausalitäts-Konflikt gelöst) | 4104 px |
|  | [`workspace-continued-manuscript`](screens/writing/workspace-continued-manuscript.webp) | Schreib-Workspace — Manuskript fortgeführt | 5154 px |
|  | [`workspace-aria-dialogue`](screens/writing/workspace-aria-dialogue.webp) | Schreib-Workspace — ARIAs Dialogreaktion eingefügt | 5814 px |
|  | [`workspace-chapter-2-nevada-echoes`](screens/writing/workspace-chapter-2-nevada-echoes.webp) | Schreib-Workspace (Kapitel 2, Szene 2: Nevada Echoes) | 3600 px |
|  | [`zen-focus`](screens/writing/zen-focus.webp) | Zen-Fokus & Atmosphärischer Schreibmodus | 2648 px |
| Editing and revision | [`editorial-comments`](screens/editing/editorial-comments.webp) | Lektorats- & Kommentar-Workspace | 3878 px |
|  | [`revision-history`](screens/editing/revision-history.webp) | Revisions- & Diff-Historie (Time-Machine) | 4038 px |
| Knowledge and lore | [`knowledge-ai-dock`](screens/knowledge/knowledge-ai-dock.webp) | Knowledge- & KI-Dock | 3172 px |
|  | [`lore-graph`](screens/knowledge/lore-graph.webp) | Großansicht Entitäten- & Lore-Graph | 2232 px |
|  | [`lore-graph-causality-harmonized`](screens/knowledge/lore-graph-causality-harmonized.webp) | Großansicht Entitäten- & Lore-Graph (Kausal harmonisiert) | 2252 px |
|  | [`lore-graph-aria-sluice-event`](screens/knowledge/lore-graph-aria-sluice-event.webp) | Großansicht Entitäten- & Lore-Graph (ARIAs Schleusen-Ereignis) | 2628 px |
|  | [`character-setting-dossiers`](screens/knowledge/character-setting-dossiers.webp) | Figuren- & Schauplatz-Dossiers | 4150 px |
|  | [`dossier-research-station-7-aria`](screens/knowledge/dossier-research-station-7-aria.webp) | Dossier: Forschungsstation 7 & ARIA | 4848 px |
|  | [`worldbuilding-atlas`](screens/knowledge/worldbuilding-atlas.webp) | Weltenbau- & Geografie-Atlas | 2940 px |
|  | [`worldbuilding-atlas-dark`](screens/knowledge/worldbuilding-atlas-dark.webp) | Weltenbau- & Geografie-Atlas (Dark Mode) | 3068 px |
|  | [`entity-genesis-ai-dialog`](screens/knowledge/entity-genesis-ai-dialog.webp) | Entitäten-Genesis im KI-Dialog | 2496 px |
|  | [`sources-research-archive`](screens/knowledge/sources-research-archive.webp) | Quellen-, Recherche- & Fakten-Archiv | 2740 px |
| Planning and structure | [`three-act-storyboard`](screens/planning/three-act-storyboard.webp) | 3-Akt-Storyboard & Szenen-Struktur - Dead Signal | 3900 px |
|  | [`chronology-timeline`](screens/planning/chronology-timeline.webp) | Chronologie- & Timeline-Ansicht - Dead Signal | 3062 px |
|  | [`causality-matrix-plot-twist`](screens/planning/causality-matrix-plot-twist.webp) | Kausalitäts-Matrix & Plot-Twist-Simulator | 3024 px |
| Analysis and feedback | [`beta-reader-analysis`](screens/analysis/beta-reader-analysis.webp) | Beta-Reader & Literarische Analyse-Suite | 3596 px |
|  | [`subtext-scene-analysis`](screens/analysis/subtext-scene-analysis.webp) | Subtext- & Szenen-Sezierer | 4100 px |
|  | [`dialogue-voice-lab`](screens/analysis/dialogue-voice-lab.webp) | Dialog-Stimm-Labor & Figuren-Simulator | 3614 px |
|  | [`writing-analytics`](screens/analysis/writing-analytics.webp) | Autoren-Produktivität & Schreib-Analytik | 4072 px |
| Production and publishing | [`export-typesetting`](screens/production/export-typesetting.webp) | Export- & Buchsatz-Studio (Print & ePub) | 2122 px |
|  | [`cover-blurb-marketing`](screens/production/cover-blurb-marketing.webp) | Cover-, Klappentext- & Marketing-Studio | 3428 px |
|  | [`expose-pitch`](screens/production/expose-pitch.webp) | Exposé- & Pitch-Studio | 5120 px |
|  | [`series-architecture`](screens/production/series-architecture.webp) | Serien- & Mehrbänder-Architektur | 3224 px |
|  | [`series-architecture-dark`](screens/production/series-architecture-dark.webp) | Serien- & Mehrbänder-Architektur (Dark Mode) | 3340 px |
|  | [`agency-submission-manager`](screens/production/agency-submission-manager.webp) | Agentur-, Verlags- & Einreichungs-Manager | 3698 px |
| Import and capture | [`manuscript-lore-import`](screens/io/manuscript-lore-import.webp) | Manuskript- & Lore-Import Studio | 2048 px |
|  | [`audio-dictation-voice-to-lore`](screens/io/audio-dictation-voice-to-lore.webp) | Audio- & Diktat-Studio (Voice-to-Lore) | 2988 px |
| Shell and settings | [`command-palette`](screens/shell/command-palette.webp) | Befehlspalette & Universalsuche (⌘K) | 2048 px |
|  | [`settings-ai-rules`](screens/shell/settings-ai-rules.webp) | Atelier-Einstellungen & KI-Regeln | 3734 px |
|  | [`ai-prompts-overrides`](screens/shell/ai-prompts-overrides.webp) | KI-Prompts & Feature-Überschreibung | 3008 px |
|  | [`help-center`](screens/shell/help-center.webp) | Hilfe-Zentrum & Kontext-Handbuch | 2144 px |
| Mobile | [`pocket-quick-capture`](screens/mobile/pocket-quick-capture.webp) | Narrare Pocket — Unterwegs-Studio & Quick Capture | 3238 px |

Reference screenshots uploaded into the same Stitch project are the files already
tracked in [`assets/screenshots/`](../../../assets/screenshots/); they are not
duplicated here:

| File | Shows |
|---|---|
| [`01-workspace-continuation.png`](../../../assets/screenshots/01-workspace-continuation.png) | Schreib-Workspace, continuation at the caret |
| [`02-chat-sources.png`](../../../assets/screenshots/02-chat-sources.png) | Chat dock with the passages its answer came from |
| [`03-knowledge-dock.png`](../../../assets/screenshots/03-knowledge-dock.png) | Knowledge dock, consistency finding, entities |
| [`04-knowledge-search.png`](../../../assets/screenshots/04-knowledge-search.png) | Knowledge page and search results |
| [`05-shelf.png`](../../../assets/screenshots/05-shelf.png) | Shelf, light |
| [`06-shelf-dark.png`](../../../assets/screenshots/06-shelf-dark.png) | Shelf, dark |
| [`07-workspace-dark.png`](../../../assets/screenshots/07-workspace-dark.png) | Workspace, dark |
| [`08-design.png`](../../../assets/screenshots/08-design.png) | Design gallery, light |
| [`09-design-dark.png`](../../../assets/screenshots/09-design-dark.png) | Design gallery, dark |
| [`10-graph.png`](../../../assets/screenshots/10-graph.png) | Lore graph, light |
| [`11-graph-dark.png`](../../../assets/screenshots/11-graph-dark.png) | Lore graph, dark |
| [`12-timeline.png`](../../../assets/screenshots/12-timeline.png) | Timeline, light |
| [`13-timeline-dark.png`](../../../assets/screenshots/13-timeline-dark.png) | Timeline, dark |
| [`14-storyboard.png`](../../../assets/screenshots/14-storyboard.png) | Storyboard, light |
| [`15-storyboard-dark.png`](../../../assets/screenshots/15-storyboard-dark.png) | Storyboard, dark |
| [`16-structure.png`](../../../assets/screenshots/16-structure.png) | Structure view, light |
| [`17-structure-dark.png`](../../../assets/screenshots/17-structure-dark.png) | Structure view, dark |
| [`18-shortcuts.png`](../../../assets/screenshots/18-shortcuts.png) | Keyboard shortcuts, light |
| [`19-shortcuts-dark.png`](../../../assets/screenshots/19-shortcuts-dark.png) | Keyboard shortcuts, dark |

## Refreshing the archive

The Stitch MCP exposes the export directly: `list_screens` with
`projectId: 15314899202287259920` returns every screen with the resource names of
its HTML and screenshot, and `download_file` returns their content. The same
project is editable at <https://stitch.withgoogle.com>. Re-export into the folder
that matches the screen's area, keep the file name stable, and update the table
above when a screen is added or renamed.
