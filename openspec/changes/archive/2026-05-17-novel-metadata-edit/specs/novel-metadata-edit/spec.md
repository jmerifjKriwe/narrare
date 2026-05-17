## ADDED Requirements

### Requirement: Novel Details tab in SettingsView
The SettingsView at `/novel/[id]/settings` SHALL include a "Novel Details" tab as the first category in the settings sidebar. When selected, it SHALL display an editable form with all novel metadata fields.

#### Scenario: User navigates to Novel Details tab
- **WHEN** the user opens `/novel/{id}/settings`
- **THEN** a "Novel Details" tab is visible as the first item in the settings sidebar
- **AND** selecting it displays the novel metadata form

#### Scenario: Novel Details tab is the default active tab
- **WHEN** the user opens `/novel/{id}/settings`
- **THEN** the "Novel Details" tab is selected by default (replacing "General" as default)

### Requirement: Novel metadata form displays current values
The form SHALL load the current novel data via `novelsApi.get(novelId)` and populate all fields with existing values.

#### Scenario: Form loads with existing novel data
- **WHEN** the user selects the Novel Details tab
- **THEN** all fields are pre-populated with the novel's current metadata: title, author, genre, language, tone, story structure, logline, synopsis

#### Scenario: Loading state while fetching novel data
- **WHEN** the novel data is being fetched
- **THEN** a loading spinner is displayed in the content area

### Requirement: Editable novel metadata fields
The form SHALL provide editable fields for: title (text input), author (text input), genre (text input), language (select: en/de/fr), tone (select: dramatic/humorous/suspenseful/contemplative/romantic/dark/adventurous), story structure (select: three_act/five_act/heros_journey/save_the_cat/seven_point), logline (text input), synopsis (textarea).

#### Scenario: User edits a text field
- **WHEN** the user modifies the title field
- **THEN** the local state updates and the form becomes dirty

#### Scenario: User edits a select field
- **WHEN** the user changes the language from "en" to "de"
- **THEN** the local state updates and the form becomes dirty

### Requirement: Save novel metadata changes
The form SHALL display a "Save" button when any field has been modified (dirty state). Clicking save SHALL call `novelsApi.update(novelId, payload)` with only the changed fields, invalidate the novels query cache, and clear the dirty state.

#### Scenario: Save button appears on modification
- **WHEN** the user modifies any field
- **THEN** a "Save" button appears at the bottom of the form

#### Scenario: Successful save
- **WHEN** the user clicks "Save"
- **THEN** the system calls `PATCH /novels/{novel_id}` with the modified fields
- **AND** the novels query cache is invalidated
- **AND** the dirty state is cleared
- **AND** the "Save" button disappears

#### Scenario: Save failure
- **WHEN** the save API call fails
- **THEN** an error message is displayed
- **AND** the form retains the user's modifications (dirty state persists)

### Requirement: Dashboard edit entry point
The DashboardView novel cards SHALL display a pencil (edit) icon that navigates to the novel's settings page.

#### Scenario: Edit icon on novel card
- **WHEN** the user hovers over a novel card on the dashboard
- **THEN** a pencil icon is visible alongside the existing delete icon
- **AND** clicking the pencil icon navigates to `/novel/{id}/settings`

### Requirement: i18n support for Novel Details tab
All labels, descriptions, and button text for the Novel Details tab SHALL be available in all 3 supported locales (en, de, fr).

#### Scenario: German locale display
- **WHEN** the user's locale is set to "de"
- **THEN** all Novel Details tab labels and form field labels are displayed in German
