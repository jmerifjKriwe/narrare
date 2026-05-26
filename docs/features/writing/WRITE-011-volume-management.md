---
id: WRITE-011
title: "Volume Management"
status: stable
area: writing
mvp: true

ui_tooltip: "Organize your novel into volumes with independent statistics and context switching."
ui_help_short: |
  Divide your novel into volumes — trilogies, story arcs, or thematic parts.
  Each volume has its own chapters, word count targets, and context scope,
  while sharing the novel's Knowledge Base and characters.
ui_help_long: |
  Volume Management introduces a hierarchical structure within a single novel.
  Each volume acts as a self-contained unit with its own chapters, statistics,
  and context scope, while sharing the novel's Knowledge Base, character profiles,
  and worldbuilding data.

  Switching between volumes preserves your place in each one, so you can work
  on Volume 3 in the morning and pick up Volume 1 where you left off in the
  afternoon. Context assembly automatically adjusts to focus on the active
  volume's content.

  Every novel starts with a single default volume. Create additional volumes
  to organize chapters into logical groups — narrative arcs, time periods,
  POV rotations, or thematic divisions.

  **API Endpoints:**
  - `POST /api/v1/novels/{novel_id}/volumes` — Create volume
  - `GET /api/v1/novels/{novel_id}/volumes` — List volumes
  - `GET /api/v1/novels/{novel_id}/volumes/{volume_id}` — Get volume details
  - `PATCH /api/v1/novels/{novel_id}/volumes/{volume_id}` — Update volume
  - `DELETE /api/v1/novels/{novel_id}/volumes/{volume_id}` — Delete volume
  - `GET /api/v1/novels/{novel_id}/volumes/{volume_id}/stats` — Volume statistics
  - `POST /api/v1/novels/{novel_id}/volumes/{volume_id}/switch` — Switch active volume

  **UI Location:** Sidebar volume selector (within novel context)

  **Shared vs Volume-Scoped Data:**
  - Knowledge Base: Shared across all volumes
  - Chapters: Volume-scoped (each chapter belongs to one volume)
  - Style Profile: Shared (Voice Cloning uses all volumes)
  - Word Count: Volume-scoped (each volume tracks independently)
  - Context History: Volume-scoped (recent chapters from active volume)

ui_available_in: [editor, sidebar]

service: novels/volumes_service.py
contract: novels/contracts.py#VolumeServiceProtocol
router: novels/router_volumes.py
requires: [WRITE-001, KB-001]
---

# WRITE-011 — Volume Management

## What it does

Organize longer works into volumes with independent statistics and context switching. Each volume groups related chapters within a novel, with its own word count targets and context scope, while the Knowledge Base remains shared.

## Why it exists

Long-form fiction often spans multiple volumes — trilogies, series of arcs, or thematic parts. Managing these as separate projects fragments the Knowledge Base and character data. Managing them as a single flat project creates an overwhelming chapter list and unwieldy context assembly. Volume Management provides a hierarchical structure that keeps related content together while maintaining a unified world.

## How it works (User perspective)

1. Open your novel and navigate to **Volumes** in the sidebar
2. Create volumes with title, optional subtitle, and description
3. Switch between volumes via the volume selector — your place in each volume is preserved
4. The chapter list, statistics, and context scope update to reflect the active volume
5. Knowledge Base entries and characters remain accessible across all volumes

## How it works (Technical)

- **Data model:** `volumes` table with `novel_id` FK, `position` ordering, and metadata fields
- **Chapter relationship:** Each chapter has a `volume_id` FK (defaults to the novel's default volume)
- **Context assembly:** When a volume is active, the history tier prioritizes chapters from that volume
- **Volume switching:** Saves current volume state (cursor, scroll, open panels), loads target volume state
- **Statistics:** Word count, chapter count, and completion percentage are computed per-volume
- **Default volume:** Every novel starts with one; chapters are never orphaned

### Backend (implemented)

- `apps/api/narrare/volumes/` — Full CRUD + stats + reorder: models, repository, service, router, contracts, schemas
- Volume model enriched with `subtitle`, `description`, `word_count_target`, `is_default` columns
- Default volume auto-creation on novel creation (same transaction)
- Volume statistics endpoint: `GET /volumes/{id}/stats` — word count, chapter count, completion percentage
- Volume reorder endpoint: `PATCH /volumes/reorder` — positional reordering in transaction
- Default volume deletion protection — cannot delete the default volume
- Chapter–volume assignment: create with `volume_id`, list filtered by `volume_id`
- Migration 0007 for volume enrichment columns
- API endpoints follow the standard contract-first pattern

### Frontend (implemented)

- Volume selector dropdown in sidebar (hidden when single volume — auto-detects)
- Volume management page at `/novel/{id}/volumes` with CRUD, reorder (up/down), stats display
- Volume progress in MetadataSidebar — shows active volume progress vs novel-level when "All" selected
- i18n support for en, de, fr locales (studio.volumes namespace)

## Constraints & Edge Cases

- A chapter belongs to exactly one volume (cannot span multiple)
- Deleting a volume does NOT delete chapters — they are reassigned to the default volume
- No hard limit on volume count, but 2-10 is typical
- Volume reordering updates the `position` field for all volumes in the novel
- The default volume cannot be deleted (only renamed)
- Cross-volume consistency checks are a separate feature (CONS-001)

## Related Features

- WRITE-001 (Writing Editor) — The editor that volumes organize
- KB-001 (Entity Management) — Shared KB across all volumes
- ANAL-003 (Readability Analysis) — Can run per-volume or across entire novel
- CONS-001 (Consistency Checker) — Cross-volume consistency checks
- IO-001 (Manuscript Export) — Export individual volumes or entire novel

## Status & History

- **2026-05-16:** Feature spec created
- **2026-05-17:** Implementation complete — backend enrichment, stats, reorder, frontend UI
- **2026-05-26:** Status updated to stable. Feature fully implemented and tested.
