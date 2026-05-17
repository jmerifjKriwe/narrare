## ADDED Requirements

### Requirement: Volume selector in sidebar
The Sidebar component SHALL display a dropdown selector above the chapter list, showing the currently active volume name and a list of all volumes for the novel. An "All" option SHALL show chapters across all volumes without filtering. Selecting a volume SHALL filter the chapter list to chapters belonging to that volume. The active volume SHALL be stored in `editorStore` (Zustand).

#### Scenario: Single novel with multiple volumes
- **WHEN** a user opens a novel that has 3 volumes ("Part 1", "Part 2", "Part 3")
- **THEN** the sidebar dropdown shows "All", "Part 1", "Part 2", "Part 3" and defaults to "All"

#### Scenario: Switching volumes filters chapter list
- **WHEN** a user selects "Part 1" from the volume dropdown
- **THEN** the chapter list shows only chapters assigned to "Part 1"

#### Scenario: New chapter auto-assigned to active volume
- **WHEN** a user has "Part 2" selected in the volume dropdown and clicks "New Chapter"
- **THEN** the new chapter is created with `volume_id` set to "Part 2"'s ID

#### Scenario: Novel with single default volume
- **WHEN** a novel has only the default volume
- **THEN** the volume dropdown is hidden (no filtering needed, all chapters shown)

### Requirement: Volume management page
The route `/novel/{id}/volumes` SHALL replace the placeholder with a full volume management page. The page SHALL display: a list of all volumes ordered by position, each showing title, subtitle, chapter count, and word count. The page SHALL provide actions: create new volume, edit volume (title, subtitle, description, word_count_target), delete non-default volume, reorder volumes (up/down arrows).

#### Scenario: Volume list display
- **WHEN** a user navigates to the volumes page for a novel with 3 volumes
- **THEN** the page shows 3 volume cards ordered by position, each with title and stats

#### Scenario: Create new volume
- **WHEN** a user clicks "Create Volume" and enters a title "Part 2: The Journey"
- **THEN** a new volume is created with that title, position=3, and the page refreshes to show it

#### Scenario: Edit volume metadata
- **WHEN** a user edits a volume's subtitle to "The Dark Forest" and sets word_count_target to 50000
- **THEN** the volume is updated and the changes are reflected immediately

#### Scenario: Delete non-default volume
- **WHEN** a user deletes a non-default volume that has chapters
- **THEN** a confirmation dialog appears, and on confirm, the volume is deleted and its chapters become unassigned (volume_id=NULL)

#### Scenario: Attempt to delete default volume
- **WHEN** a user tries to delete the default volume
- **THEN** the delete button is disabled with a tooltip explaining why

#### Scenario: Reorder volumes
- **WHEN** a user clicks the down-arrow on volume at position 1
- **THEN** that volume swaps position with the volume at position 2, and the list reorders

### Requirement: Volume statistics in MetadataSidebar
The MetadataSidebar component SHALL show the active volume's word count target and completion percentage when a volume is active. When "All" is selected, it SHALL show aggregate statistics across all volumes (current behavior).

#### Scenario: Active volume with target
- **WHEN** a user has "Part 1" selected and "Part 1" has `word_count_target=40000` and 20000 words written
- **THEN** the MetadataSidebar's Novel Progress section shows the volume's progress (50%) instead of the global goal

#### Scenario: All volumes selected
- **WHEN** a user has "All" selected in the volume dropdown
- **THEN** the MetadataSidebar shows the novel-level progress as it does today

### Requirement: Volume-aware chapter fetching
The chapters API client SHALL accept an optional `volumeId` parameter for the list method. The Sidebar and EditorView components SHALL pass the active volume ID when fetching chapters. When no volume is selected ("All"), the fetch SHALL omit the filter parameter.

#### Scenario: Fetch chapters for specific volume
- **WHEN** the sidebar fetches chapters with `volumeId="abc-123"`
- **THEN** the API call is `GET /api/v1/novels/{novel_id}/chapters?volume_id=abc-123`

#### Scenario: Fetch all chapters
- **WHEN** the sidebar fetches chapters with no `volumeId`
- **THEN** the API call is `GET /api/v1/novels/{novel_id}/chapters` (no filter)

### Requirement: i18n for volume management
All volume management UI text SHALL use translation keys in the `studio.volumes` namespace. Keys SHALL be provided in all 3 locales (en, de, fr). This includes: volume form labels, button text, error messages, stats labels, and placeholder text.

#### Scenario: German locale volume management
- **WHEN** a user with locale "de" opens the volume management page
- **THEN** all labels, buttons, and messages appear in German

#### Scenario: Missing translation key
- **WHEN** a translation key is missing in a non-English locale
- **THEN** the English fallback is displayed (next-intl default behavior)
