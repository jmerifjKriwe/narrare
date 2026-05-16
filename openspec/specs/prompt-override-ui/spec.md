# Capability: Prompt Override UI

## Purpose
Provide a Settings UI for browsing, viewing, editing, and resetting AI prompt overrides. Users can see bundled defaults, create project-level overrides, compare versions with diff views, and receive notifications when bundled prompts are updated.

## Requirements

### Requirement: Prompt settings tab
The frontend SHALL provide a "AI Prompts" tab in the Settings area that displays all available prompts organized by category (generation, writing, analysis, kb).

#### Scenario: Settings page shows prompt tab
- **WHEN** a user navigates to Settings
- **THEN** an "AI Prompts" tab is visible and accessible

### Requirement: Prompt list view
The prompt settings tab SHALL display prompts in a browsable list showing: prompt name, language, source (bundled/override), and update status badge.

#### Scenario: Prompt list displays categories
- **WHEN** the AI Prompts tab is opened
- **THEN** prompts are grouped by category (generation, writing, analysis, kb) and each shows name, language, and source indicator

#### Scenario: Override indicator
- **WHEN** a prompt has a user override
- **THEN** the list entry shows a visual indicator (e.g., badge or icon) distinguishing it from bundled defaults

### Requirement: Prompt editor
The UI SHALL provide an editor that displays the current prompt content (bundled or override), available variables with descriptions, and action buttons to edit, save, or reset.

#### Scenario: View bundled prompt
- **WHEN** a user clicks on a bundled prompt with no override
- **THEN** the editor shows the bundled content in read-only mode with an "Edit as Override" button

#### Scenario: Edit and save override
- **WHEN** a user clicks "Edit as Override", modifies content, and clicks "Save"
- **THEN** the override is saved and the prompt source changes to "project" (or "user-global")

#### Scenario: Reset override
- **WHEN** a user clicks "Reset to Default" on an overridden prompt
- **THEN** the override is deleted and the bundled default is restored

### Requirement: Update notification
The UI SHALL display a notification badge on prompts where the bundled version has been updated since the user created their override.

#### Scenario: Update badge displayed
- **WHEN** the prompt list is loaded and a prompt has an override based on v1.0.0 but the bundled version is now v1.1.0
- **THEN** a visual badge (e.g., orange dot or "Update available" label) is shown on that prompt entry

### Requirement: Diff comparison view
The UI SHALL provide a side-by-side diff view comparing the user's override with the current bundled default, with options to keep the user's version, accept the new default, or manually merge.

#### Scenario: Side-by-side diff
- **WHEN** a user clicks "Show Diff" on a prompt with an available update
- **THEN** a side-by-side view shows the user's override on the left and the new bundled default on the right, with differences highlighted

#### Scenario: Accept new default
- **WHEN** a user clicks "Accept New Default" in the diff view
- **THEN** the override is deleted and the bundled default becomes active

#### Scenario: Keep user version
- **WHEN** a user clicks "Keep My Version" in the diff view
- **THEN** the override is retained and the `override_of_version` is updated to the current bundled version (suppressing the update notification)
