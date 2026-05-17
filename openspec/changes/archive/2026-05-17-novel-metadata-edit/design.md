## Context

Narrare allows users to create novels via a setup wizard (WizardStep3) where they provide metadata: title, author, genre, language, tone, story structure, logline, and synopsis. Once a novel is created, there is no UI to edit these fields.

The backend already supports partial updates via `PATCH /novels/{novel_id}` with `UpdateNovelRequest` (all fields optional). The frontend API client already has `novelsApi.update(novelId, payload)`. The gap is purely a missing frontend UI.

The existing `SettingsView` at `/novel/[id]/settings` uses a tabbed layout with categories: General (user profile), Writing Goals, AI Setup, Prompts, Shortcuts, About. A new "Novel Details" tab is the natural place for novel metadata editing.

## Goals / Non-Goals

**Goals:**

- Provide an accessible UI for users to edit all novel metadata fields after creation
- Integrate cleanly into the existing SettingsView tab structure
- Add a quick entry point from the Dashboard (edit icon on novel cards)
- Support all 3 locales (en, de, fr)
- Follow the existing tab pattern (load data → local state → dirty tracking → save)

**Non-Goals:**

- No backend changes (API already complete)
- No changes to the setup wizard flow
- No new API client methods needed
- No validation beyond what the backend schema already enforces (field lengths)
- No bulk metadata editing across novels

## Decisions

### 1. Add "Novel Details" tab to existing SettingsView

**Decision**: Insert a new tab "Novel Details" as the first category in the SettingsView, before "General".

**Rationale**: The SettingsView is already per-novel (receives `novelId` prop). The existing pattern of tabbed navigation with card-based forms fits perfectly. Users naturally look for novel-specific settings in the settings page.

**Alternative considered**: A separate `/novel/[id]/details` page. Rejected because it fragments the settings experience and duplicates navigation patterns.

### 2. Form layout: card-based sections matching GeneralTab pattern

**Decision**: Use the same card-based layout as GeneralTab — grouped fields in bordered cards with icon headers.

**Rationale**: Consistency with existing UI. The fields naturally group into:
- **Basic info**: title, author, language
- **Story**: genre, tone, story structure
- **Summary**: logline, synopsis (longer text areas)

### 3. Dashboard entry point: pencil icon on novel cards

**Decision**: Add a `Pencil` icon button (lucide-react) next to the existing `Trash2` delete button on DashboardView novel cards. Clicking navigates to `/novel/{id}/settings`.

**Rationale**: Lowest-effort, discoverable entry point. The settings page is already the right destination. Users who want to edit metadata will find it quickly.

**Alternative considered**: Inline editing on the dashboard card. Rejected — too complex for 8 metadata fields, creates clutter.

### 4. Save behavior: explicit save with dirty tracking

**Decision**: Follow the GeneralTab pattern — local state tracks edits, "Save" button appears when dirty, save calls `novelsApi.update()` and invalidates the novel query cache.

**Rationale**: Consistent with existing patterns. Auto-save for metadata is overkill (these fields change rarely).

## Risks / Trade-offs

- **Novel data staleness**: If the novel is updated elsewhere (e.g., another tab), the settings form may show stale data. → Mitigation: TanStack Query invalidation on save, plus refetch on mount.
- **Synopsis field size**: Synopsis can be long text. → Mitigation: Use a `<textarea>` with reasonable max height, matching the pattern used in wizard step 3.
- **i18n key count**: 8 fields × 3 locales = 24 new label keys + tab/navigation keys. → Acceptable: follows existing namespace pattern in `studio.json`.
