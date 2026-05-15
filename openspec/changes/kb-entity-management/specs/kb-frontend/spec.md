## ADDED Requirements

### Requirement: KB browser page with entity type tabs
The frontend SHALL provide a KB browser page at `/novel/[id]/kb/` with tabs for each entity type (Characters, Locations, Factions, Objects, Systems, Timelines) and an "All" tab.

#### Scenario: Navigate to KB browser
- **WHEN** the user navigates to `/novel/{id}/kb/`
- **THEN** the KB browser is displayed with entity type tabs, defaulting to "All"

#### Scenario: Filter by entity type tab
- **WHEN** the user clicks the "Characters" tab
- **THEN** only character entries are displayed in the list

### Requirement: KB entry list view
The KB browser SHALL display entries as a list or grid of cards showing name, entity type icon, tags, status badge, and last updated date.

#### Scenario: Entry card displays key info
- **WHEN** the KB list is rendered for a novel with 15 entries
- **THEN** each entry card shows the entry name, entity type icon, up to 3 tags, status badge (draft/reviewed/canon/deprecated), and relative last-updated time

### Requirement: KB entry detail view
Clicking an entry card SHALL open a detail view showing the full entry: name, metadata fields, body (rendered Markdown), status, tags, and relationships.

#### Scenario: View character detail
- **WHEN** the user clicks on "Elara Thornwind" in the KB list
- **THEN** the detail view shows Elara's name, metadata fields (age: 19, role: protagonist, etc.), rendered body Markdown, status badge, tags, and a list of relationships

### Requirement: Create new KB entry
The KB browser SHALL provide a "New Entry" button that opens a form with entity type selection, name field, and a Markdown editor for the body.

#### Scenario: Create new character
- **WHEN** the user clicks "New Entry", selects "Character", enters name "Marcus Thorne", writes body content, and clicks "Save"
- **THEN** the character entry is created via the API and appears in the KB list

### Requirement: Edit existing KB entry
The detail view SHALL provide an "Edit" action that opens the entry in an editable form with name, metadata fields, body editor, tags, and status selector.

#### Scenario: Edit character name
- **WHEN** the user edits the name from "Elara" to "Elara Thornwind" and saves
- **THEN** the entry is updated via the API and the change is reflected in the detail view and list

### Requirement: Delete KB entry with confirmation
The detail view SHALL provide a "Delete" action that requires explicit confirmation before deleting.

#### Scenario: Delete entry with confirmation
- **WHEN** the user clicks "Delete" on an entry, confirms the deletion dialog, and the API responds with 204
- **THEN** the entry is removed from the list and a success notification is shown

#### Scenario: Cancel deletion
- **WHEN** the user clicks "Delete" but cancels the confirmation dialog
- **THEN** no deletion occurs and the entry remains unchanged

### Requirement: Manage relationships from entry detail
The entry detail view SHALL display existing relationships and provide controls to add new relationships and delete existing ones.

#### Scenario: Add relationship
- **WHEN** the user clicks "Add Relationship" on Elara's detail view, selects Verrick as target, chooses "mentor" as type, and saves
- **THEN** the relationship is created and displayed in Elara's relationship list

#### Scenario: Add relationship with inverse suggestion
- **WHEN** the user creates a "mentor" relationship from Elara to Verrick
- **THEN** the UI shows a prompt "Add inverse? Verrick considers Elara a 'mentee'"
- **WHEN** the user accepts
- **THEN** both relationships are created

#### Scenario: Delete relationship
- **WHEN** the user deletes a relationship from the relationship list
- **THEN** the relationship is removed and the list updates

### Requirement: Search within KB browser
The KB browser SHALL provide a search bar that filters entries by name and body content via the search API endpoint.

#### Scenario: Search for entry
- **WHEN** the user types "void magic" in the search bar
- **THEN** entries matching "void magic" in name or body are displayed, replacing the current list

#### Scenario: Clear search
- **WHEN** the user clears the search bar
- **THEN** the full entry list for the current entity type tab is restored

### Requirement: KB browser navigation from editor
The editor's sidebar or navigation SHALL provide a link to the KB browser for the current novel.

#### Scenario: Navigate from editor to KB
- **WHEN** the user clicks "Knowledge Base" in the editor navigation
- **THEN** the KB browser opens for the current novel

### Requirement: KB entry count in navigation
The novel navigation SHALL show the total KB entry count as a badge or label next to the "Knowledge Base" link.

#### Scenario: Display entry count
- **WHEN** a novel has 15 KB entries
- **THEN** the navigation shows "Knowledge Base (15)" or equivalent
