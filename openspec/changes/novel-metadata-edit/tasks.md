## 1. Frontend — NovelDetailsTab Component

- [x] 1.1 Create `packages/web/components/studio/settings/NovelDetailsTab.tsx` — React component with editable form for all 8 novel metadata fields (title, author, genre, language, tone, story_structure, logline, synopsis), grouped into 3 card sections (Basic Info, Story, Summary), with dirty tracking and explicit save via `novelsApi.update()`
- [x] 1.2 Add unit tests for `NovelDetailsTab` in `packages/web/components/studio/settings/NovelDetailsTab.test.tsx` — test: renders form with pre-populated data, tracks dirty state on edit, calls `novelsApi.update()` on save with changed fields only, shows loading spinner while fetching, handles save error

## 2. Frontend — SettingsView Integration

- [x] 2.1 Update `packages/web/components/studio/SettingsView.tsx` — add "Novel Details" as first category in `CATEGORIES` array with `BookOpen` icon, set it as `defaultActiveCategory`, add case in `renderContent()` switch that renders `<NovelDetailsTab novelId={novelId} />`
- [x] 2.2 Update the `useState` initial value from `"general"` to `"novel-details"` so Novel Details is the default active tab

## 3. Frontend — Dashboard Edit Entry Point

- [x] 3.1 Update `packages/web/components/studio/DashboardView.tsx` — add `Pencil` icon import from lucide-react, add edit button next to delete button on novel cards (visible on hover), clicking navigates to `/novel/${novel.id}/settings`

## 4. i18n — Add Translation Keys

- [x] 4.1 Add "Novel Details" tab and form i18n keys to `packages/i18n/messages/en/studio.json` under a new `settings.novelDetails` section (tab label, section titles, field labels, field descriptions, save button text, success/error messages)
- [x] 4.2 Add matching German translations to `packages/i18n/messages/de/studio.json`
- [x] 4.3 Add matching French translations to `packages/i18n/messages/fr/studio.json`
- [x] 4.4 Run i18n validation (`npm run validate-i18n` in `packages/web/`) to verify key completeness and placeholder consistency across all 3 locales

## 5. Validation

- [x] 5.1 Run frontend tests (`npm run test` in `packages/web/`) — all existing + new tests pass
- [x] 5.2 Run architecture check (`python scripts/check_architecture.py`) — no new violations
- [x] 5.3 Manual verification: open settings page, confirm Novel Details tab loads with data, edit and save works, dashboard edit icon navigates correctly
