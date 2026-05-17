## 1. Backend — Model & Migration

- [ ] 1.1 Add `subtitle`, `description`, `word_count_target`, `is_default` columns to `Volume` model in `apps/api/narrare/volumes/models.py`
- [ ] 1.2 Update `VolumeResponse` and `CreateVolumeRequest` schemas in `schemas.py` to include new fields
- [ ] 1.3 Create Alembic migration for new columns (nullable defaults for existing data)
- [ ] 1.4 Update `VolumeRepositoryProtocol` in `contracts.py` with new method signatures (e.g., `get_default_volume`, `get_stats`)
- [ ] 1.5 Implement new repository methods: `get_default_volume`, `get_stats` (aggregation query), `reorder`, `set_default` in `repository.py`

## 2. Backend — Service Layer

- [ ] 2.1 Implement default volume auto-creation in `NovelService.create()` — create default volume in same transaction
- [ ] 2.2 Implement `VolumeService.get_stats()` — compute word_count, chapter_count, completion_percentage via repository aggregation
- [ ] 2.3 Implement `VolumeService.reorder()` — validate all volume IDs present, update positions in transaction
- [ ] 2.4 Add default volume deletion protection in `VolumeService.delete()` — raise error if `is_default=True`
- [ ] 2.5 Update chapter schemas (`CreateChapterRequest`, `UpdateChapterRequest`) to include optional `volume_id` field
- [ ] 2.6 Update `ChapterService.create()` to default `volume_id` to the novel's default volume when not specified
- [ ] 2.7 Update `ChapterRepository.list_by_novel()` to accept optional `volume_id` filter parameter

## 3. Backend — Router Endpoints

- [ ] 3.1 Add `GET /novels/{novel_id}/volumes/{volume_id}/stats` endpoint
- [ ] 3.2 Add `PATCH /novels/{novel_id}/volumes/reorder` endpoint accepting `{ volume_ids: [uuid] }`
- [ ] 3.3 Update `GET /novels/{novel_id}/chapters` to accept optional `volume_id` query parameter
- [ ] 3.4 Update volume router response models to include new fields (subtitle, description, word_count_target, is_default)

## 4. Backend — Tests

- [ ] 4.1 Unit test: default volume auto-creation on novel creation
- [ ] 4.2 Unit test: volume stats computation (with chapters, empty volume, no target)
- [ ] 4.3 Unit test: volume reorder validation (success, missing IDs)
- [ ] 4.4 Unit test: default volume deletion protection
- [ ] 4.5 Unit test: chapter creation defaults to default volume
- [ ] 4.6 Unit test: chapter list filtered by volume_id
- [ ] 4.7 Integration test: full volume CRUD lifecycle (create novel → default volume exists → create volume → get stats → reorder → delete)

## 5. Frontend — API Client & Types

- [ ] 5.1 Add volume types to `packages/web/types/` (Volume, VolumeStats, CreateVolumeRequest, UpdateVolumeRequest, ReorderVolumesRequest)
- [ ] 5.2 Add `volumesApi` methods to `packages/web/lib/api/client.ts`: list, create, update, delete, getStats, reorder
- [ ] 5.3 Update `chaptersApi.list()` to accept optional `volumeId` parameter

## 6. Frontend — State Management

- [ ] 6.1 Add `activeVolumeId` (string | null, null = "All") and `setActiveVolumeId` to `editorStore`
- [ ] 6.2 Add volumes query hook in sidebar: `useQuery(["novels", novelId, "volumes"], ...)`

## 7. Frontend — Sidebar Volume Selector

- [ ] 7.1 Add volume dropdown above chapter list in `Sidebar.tsx` — fetches volumes, shows dropdown with "All" + volume names
- [ ] 7.2 Hide dropdown when novel has only the default volume (single volume = no filtering needed)
- [ ] 7.3 Filter chapter list by `activeVolumeId` — pass `volumeId` to `chaptersApi.list()`
- [ ] 7.4 Auto-assign `activeVolumeId` when creating a new chapter from sidebar

## 8. Frontend — Volume Management Page

- [ ] 8.1 Replace `VolumeManagementPlaceholder` with `VolumeManagementView` component
- [ ] 8.2 Build volume list UI: ordered cards showing title, subtitle, chapter count, word count, stats
- [ ] 8.3 Build create volume form (inline or modal): title + optional subtitle, description, word_count_target
- [ ] 8.4 Build edit volume form: same fields pre-filled, save via PUT/PATCH
- [ ] 8.5 Add delete action: confirmation dialog, disabled for default volume with tooltip
- [ ] 8.6 Add reorder controls: up/down arrow buttons per volume card, calling reorder endpoint
- [ ] 8.7 Update `/novel/{id}/volumes/page.tsx` to render `VolumeManagementView`

## 9. Frontend — MetadataSidebar Volume Stats

- [ ] 9.1 Update `MetadataSidebar` to receive active volume stats
- [ ] 9.2 When volume is active and has `word_count_target`: show volume progress instead of novel-level progress
- [ ] 9.3 When "All" is selected: keep current novel-level progress behavior

## 10. Frontend — i18n

- [ ] 10.1 Expand `studio.volumes` namespace in `en/studio.json` with all new keys (form labels, buttons, stats, errors)
- [ ] 10.2 Add German translations in `de/studio.json`
- [ ] 10.3 Add French translations in `fr/studio.json`
- [ ] 10.4 Run i18n validation to ensure key completeness and placeholder consistency

## 11. Documentation & Cleanup

- [ ] 11.1 Update `docs/features/writing/WRITE-011-volume-management.md` status to reflect implementation
- [ ] 11.2 Update `docs/features/INDEX.md` — change WRITE-011 status from 📋 to ✅
- [ ] 11.3 Update `docs/_shared/CURRENT_STATE.md` with volume management completion
- [ ] 11.4 Delete `VolumeManagementPlaceholder.tsx` (replaced by VolumeManagementView)
