## Why

The Volume backend CRUD exists (`apps/api/narrare/volumes/`) but the feature is incomplete: two API endpoints from the spec (volume statistics and volume switching) are missing, the Volume model lacks metadata fields (subtitle, description, word-count target), no default volume is auto-created with a novel, and there is zero frontend — users cannot see, create, or switch between volumes in the UI. Without this, longer works with multiple arcs or parts have no organizational structure beyond a flat chapter list.

## What Changes

- **Backend — Volume model enrichment**: Add `subtitle`, `description`, `word_count_target`, `is_default` columns to the `volumes` table. Add Alembic migration.
- **Backend — Default volume auto-creation**: When a novel is created, automatically create a default volume ("Volume 1"). Chapters without an explicit volume_id belong to this default.
- **Backend — Volume statistics endpoint**: `GET /novels/{novel_id}/volumes/{volume_id}/stats` returning word count, chapter count, completion percentage.
- **Backend — Volume reordering**: `PATCH /novels/{novel_id}/volumes/reorder` for drag-and-drop position updates.
- **Backend — Chapter–volume assignment**: Update chapter CRUD to support `volume_id` in create/update requests, and add a filter-by-volume query parameter to the chapters list endpoint.
- **Frontend — Volume selector**: Dropdown/tabs in the editor sidebar to switch the active volume, filtering the chapter list.
- **Frontend — Volume management page**: CRUD UI at `/novel/{id}/volumes` for creating, editing, reordering, and deleting volumes.
- **Frontend — Volume statistics**: Display word count, chapter count, and completion in the volume selector and management page.

## Capabilities

### New Capabilities
- `volume-stats`: Volume-scoped statistics (word count, chapter count, completion percentage) — backend endpoint + frontend display
- `volume-frontend-ui`: Complete frontend for volume management — selector in editor sidebar, management page, chapter filtering by active volume

### Modified Capabilities
- *(none — no existing openspec specs are being modified at the requirements level)*

## Impact

- **Backend**: `apps/api/narrare/volumes/` (models, schemas, repository, service, router, contracts), `apps/api/narrare/chapters/` (schemas, repository, service for volume_id handling), `apps/api/narrare/novels/service.py` (default volume creation on novel create)
- **Frontend**: New components in `packages/web/components/editor/` (VolumeSelector), new page at `packages/web/app/(app)/novel/[id]/volumes/`, updated ChapterSidebar to filter by active volume, updated API client (`lib/api/`)
- **Database**: New Alembic migration for `volumes` table schema changes (subtitle, description, word_count_target, is_default columns)
- **i18n**: New translation keys in `packages/i18n/messages/{en,de,fr}/volumes.json`
- **Dependencies**: No new external dependencies
