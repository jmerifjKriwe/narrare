## Why

Users can currently create novels through the setup wizard with rich metadata (title, author, genre, language, tone, story structure, logline, synopsis). Once created, there is **no way to edit these metadata fields**. The backend API (`PATCH /novels/{novel_id}`) and frontend client (`novelsApi.update()`) already support updates, but no UI surface exposes this capability.

## What Changes

- Add a "Novel Details" tab to the existing SettingsView at `/novel/[id]/settings`
- The tab displays an editable form with all novel metadata fields: title, author, genre, language, tone, story structure, logline, synopsis
- Changes are saved via the existing `novelsApi.update()` call (`PATCH /novels/{novel_id}`)
- Add i18n keys for the new tab and form labels in all 3 locales (en, de, fr)
- Add an "edit" entry point on the Dashboard novel cards (pencil icon) that navigates to the novel's settings page

## Capabilities

### New Capabilities

- `novel-metadata-edit`: UI for viewing and editing novel metadata (title, author, genre, language, tone, story_structure, logline, synopsis) from the novel settings page

### Modified Capabilities

_(No existing specs require requirement-level changes — the backend API and frontend client already support this.)_

## Impact

- **Frontend**: New tab component in `SettingsView`, new i18n keys across 3 locales, minor addition to `DashboardView` (edit icon on cards)
- **Backend**: No changes — existing `PATCH /novels/{novel_id}` endpoint and `UpdateNovelRequest` schema cover all fields
- **API Client**: No changes — `novelsApi.update(novelId, payload)` already exists
- **Tests**: Unit tests for the new settings tab component, integration test coverage already exists for the update endpoint
