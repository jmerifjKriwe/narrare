## 1. Backend — Model & Migration

- [x] 1.1 Add `subtitle`, `description`, `word_count_target`, `is_default` columns to `Volume` model in `apps/api/narrare/volumes/models.py`
- [x] 1.2 Update `VolumeResponse` and `CreateVolumeRequest` schemas in `schemas.py` to include new fields
- [x] 1.3 Create Alembic migration for new columns (nullable defaults for existing data)
- [x] 1.4 Update `VolumeRepositoryProtocol` in `contracts.py` with new method signatures (e.g., `get_default_volume`, `get_stats`)
- [x] 1.5 Implement new repository methods: `get_default_volume`, `get_stats` (aggregation query), `reorder`, `set_default` in `repository.py`

## 2. Backend — Service Layer

- [x] 2.1 Implement default volume auto-creation in `NovelService.create()` — create default volume in same transaction
- [x] 2.2 Implement `VolumeService.get_stats()` — compute word_count, chapter_count, completion_percentage via repository aggregation
- [x] 2.3 Implement `VolumeService.reorder()` — validate all volume IDs present, update positions in transaction
- [x] 2.4 Add default volume deletion protection in `VolumeService.delete()` — raise error if `is_default=True`
- [x] 2.5 Update chapter schemas (`CreateChapterRequest`, `UpdateChapterRequest`) to include optional `volume_id` field
- [x] 2.6 Update `ChapterService.create()` to default `volume_id` to the novel's default volume when not specified
- [x] 2.7 Update `ChapterRepository.list_by_novel()` to accept optional `volume_id` filter parameter

## 3. Backend — Router Endpoints

- [x] 3.1 Add `GET /novels/{novel_id}/volumes/{volume_id}/stats` endpoint
- [x] 3.2 Add `PATCH /novels/{novel_id}/volumes/reorder` endpoint accepting `{ volume_ids: [uuid] }`
- [x] 3.3 Update `GET /novels/{novel_id}/chapters` to accept optional `volume_id` query parameter
- [x] 3.4 Update volume router response models to include new fields (subtitle, description, word_count_target, is_default)

## 4. Backend — Tests

- [x] 4.1 Unit test: default volume auto-creation on novel creation
- [x] 4.2 Unit test: volume stats computation (with chapters, empty volume, no target)
- [x] 4.3 Unit test: volume reorder validation (success, missing IDs)
- [x] 4.4 Unit test: default volume deletion protection
- [x] 4.5 Unit test: chapter creation defaults to default volume
- [x] 4.6 Unit test: chapter list filtered by volume_id
- [x] 4.7 Integration test: full volume CRUD lifecycle (create novel → default volume exists → create volume → get stats → reorder → delete)

## 5. Frontend — API Client & Types

- [x] 5.1 Add volume types to `packages/web/types/` (Volume, VolumeStats, CreateVolumeRequest, UpdateVolumeRequest, ReorderVolumesRequest)
- [x] 5.2 Add `volumesApi` methods to `packages/web/lib/api/client.ts`: list, create, update, delete, getStats, reorder
- [x] 5.3 Update `chaptersApi.list()` to accept optional `volumeId` parameter

## 6. Frontend — State Management

- [x] 6.1 Add `activeVolumeId` (string | null, null = "All") and `setActiveVolumeId` to `editorStore`
- [x] 6.2 Add volumes query hook in sidebar: `useQuery(["novels", novelId, "volumes"], ...)`

## 7. Frontend — Sidebar Volume Selector

- [x] 7.1 Add volume dropdown above chapter list in `Sidebar.tsx` — fetches volumes, shows dropdown with "All" + volume names
- [x] 7.2 Hide dropdown when novel has only the default volume (single volume = no filtering needed)
- [x] 7.3 Filter chapter list by `activeVolumeId` — pass `volumeId` to `chaptersApi.list()`
- [x] 7.4 Auto-assign `activeVolumeId` when creating a new chapter from sidebar

## 8. Frontend — Volume Management Page

- [x] 8.1 Replace `VolumeManagementPlaceholder` with `VolumeManagementView` component
- [x] 8.2 Build volume list UI: ordered cards showing title, subtitle, chapter count, word count, stats
- [x] 8.3 Build create volume form (inline or modal): title + optional subtitle, description, word_count_target
- [x] 8.4 Build edit volume form: same fields pre-filled, save via PUT/PATCH
- [x] 8.5 Add delete action: confirmation dialog, disabled for default volume with tooltip
- [x] 8.6 Add reorder controls: up/down arrow buttons per volume card, calling reorder endpoint
- [x] 8.7 Update `/novel/{id}/volumes/page.tsx` to render `VolumeManagementView`

## 9. Frontend — MetadataSidebar Volume Stats

- [x] 9.1 Update `MetadataSidebar` to receive active volume stats
- [x] 9.2 When volume is active and has `word_count_target`: show volume progress instead of novel-level progress
- [x] 9.3 When "All" is selected: keep current novel-level progress behavior

## 10. Frontend — i18n

- [x] 10.1 Expand `studio.volumes` namespace in `en/studio.json` with all new keys (form labels, buttons, stats, errors)
- [x] 10.2 Add German translations in `de/studio.json`
- [x] 10.3 Add French translations in `fr/studio.json`
- [x] 10.4 Run i18n validation to ensure key completeness and placeholder consistency

## 11. Documentation & Cleanup

- [x] 11.1 Update `docs/features/writing/WRITE-011-volume-management.md` status to reflect implementation
- [x] 11.2 Update `docs/features/INDEX.md` — change WRITE-011 status from 📋 to ✅
- [x] 11.3 Update `docs/_shared/CURRENT_STATE.md` with volume management completion
- [x] 11.4 Delete `VolumeManagementPlaceholder.tsx` (replaced by VolumeManagementView)
