## ADDED Requirements

### Requirement: Custom tone storage
The system SHALL store custom user-defined tones as part of user preferences. Each custom tone SHALL have a unique ID, a display name (1-50 characters), and instructions text (1-500 characters). A user SHALL be able to store up to 20 custom tones.

#### Scenario: Create a custom tone
- **WHEN** a user creates a custom tone with name "düster-melancholisch" and instructions "Verwende düstere Metaphern, schwere Atmosphäre, kurze abgehackte Sätze"
- **THEN** the tone is saved under the user's preferences with a unique ID
- **AND** the tone is immediately available in all tone selectors

#### Scenario: Maximum custom tones reached
- **WHEN** a user already has 20 custom tones and attempts to create another
- **THEN** the system rejects the creation with a validation error

#### Scenario: Custom tone name uniqueness
- **WHEN** a user creates a custom tone with a name identical to an existing custom tone
- **THEN** the system rejects the creation with a validation error

### Requirement: Custom tone CRUD API
The system SHALL provide REST endpoints for managing custom tones: `GET /api/v1/user/preferences/tones` (list), `POST /api/v1/user/preferences/tones` (create), `PUT /api/v1/user/preferences/tones/{tone_id}` (update), `DELETE /api/v1/user/preferences/tones/{tone_id}` (delete).

#### Scenario: List custom tones
- **WHEN** `GET /api/v1/user/preferences/tones` is called
- **THEN** a list of the user's custom tones is returned, each with `id`, `name`, and `instructions`

#### Scenario: Update a custom tone
- **WHEN** `PUT /api/v1/user/preferences/tones/{tone_id}` is called with updated instructions
- **THEN** the tone is updated and the new instructions take effect immediately

#### Scenario: Delete a custom tone
- **WHEN** `DELETE /api/v1/user/preferences/tones/{tone_id}` is called
- **THEN** the tone is removed from the user's preferences
- **AND** any novel currently using this tone retains the tone name but falls back to the name-only behavior (no custom instructions)

#### Scenario: Delete custom tone still referenced by a novel
- **WHEN** a custom tone is deleted and a novel has it set as its tone
- **THEN** the novel's tone field retains the name string
- **AND** the tone instructions for that novel become empty (graceful degradation)

### Requirement: Custom tones in tone selectors
All tone selectors in the application (Wizard Step 3, Settings NovelDetailsTab, Editor GenerationPanel) SHALL display the user's custom tones below the bundled tones, separated by a visual divider.

#### Scenario: Tone selector shows both bundled and custom tones
- **WHEN** a user opens a tone selector dropdown
- **THEN** bundled tones are listed first (balanced, dramatic, humorous, suspenseful, contemplative, romantic, dark, adventurous, quiet)
- **AND** a visual separator is displayed
- **AND** the user's custom tones are listed below the separator

#### Scenario: No custom tones
- **WHEN** a user has no custom tones defined
- **THEN** the tone selector shows only bundled tones without the separator

### Requirement: Custom tone management UI
The system SHALL provide a "Tone Library" management interface accessible from user settings. This interface SHALL allow creating, editing, and deleting custom tones with fields for name and instructions.

#### Scenario: Access tone library
- **WHEN** the user navigates to user settings
- **THEN** a "Tone Library" section is visible
- **AND** selecting it shows all custom tones with edit and delete actions

#### Scenario: Edit custom tone instructions
- **WHEN** the user edits the instructions of a custom tone in the library
- **THEN** the updated instructions are saved
- **AND** all future generations using this tone will use the new instructions
