## MODIFIED Requirements

### Requirement: Editable novel metadata fields
The form SHALL provide editable fields for: title (text input), author (text input), genre (text input with `<datalist>` suggestions), writing_language (text input, default = UI language, freetext for any language), tone (select: unified list of bundled tones + user custom tones), story structure (select: three_act/five_act/heros_journey/save_the_cat/seven_point), logline (text input), synopsis (textarea).

#### Scenario: User edits genre with suggestions
- **WHEN** the user focuses the genre input field
- **THEN** a `<datalist>` dropdown appears with suggestions: Fantasy, Sci-Fi, Modern, Romance, Thriller, Horror, Historical, Literary Fiction, Mystery, Western, Crime, Comedy
- **AND** the user can type any freetext value including compound genres like "Dark Urban Fantasy mit Noir-Elementen"

#### Scenario: User edits writing language
- **WHEN** the user focuses the writing_language input field
- **THEN** the field shows the current writing language as freetext
- **AND** the user can type any language description (e.g. "Deutsch", "Australisches Englisch", "Klingonisch")

#### Scenario: User selects tone from unified list
- **WHEN** the user opens the tone selector
- **THEN** the dropdown shows all bundled tones: balanced, dramatic, humorous, suspenseful, contemplative, romantic, dark, adventurous, quiet
- **AND** if the user has custom tones, they appear below a visual separator
- **AND** the user can select any tone from either group

#### Scenario: Writing language defaults to UI language
- **WHEN** a new novel is created via the Wizard
- **THEN** the writing_language field defaults to the current UI language (e.g. "de" if the UI is in German)

## ADDED Requirements

### Requirement: Genre datalist suggestions
The genre input field SHALL provide `<datalist>` suggestions for common genres to guide new users while allowing freetext input for any value.

#### Scenario: Datalist shows genre suggestions
- **WHEN** the user types in the genre field
- **THEN** the browser shows filtered suggestions from a predefined list including: Fantasy, Sci-Fi, Modern, Romance, Thriller, Horror, Historical, Literary Fiction, Mystery, Western, Crime, Comedy
- **AND** the user can ignore all suggestions and type any custom text

#### Scenario: Compound genre accepted
- **WHEN** the user enters "Dark Urban Fantasy mit Noir-Elementen" as genre
- **THEN** the value is accepted and stored as-is
- **AND** the value is injected into the prompt as "Genre: Dark Urban Fantasy mit Noir-Elementen"

### Requirement: Writing language prompt injection
The writing_language field SHALL be injected into all writing prompts as an instruction to the LLM about the output language. The UI language SHALL determine which prompt file is loaded, while writing_language determines the content language instruction.

#### Scenario: Writing language in writing prompt
- **WHEN** a generation is triggered for a novel with writing_language "Schweizerdeutsch"
- **THEN** the prompt contains the instruction "Schreibe den Text auf: Schweizerdeutsch"
- **AND** the prompt file is selected based on UI language (not writing language)

#### Scenario: Writing language in name generator
- **WHEN** the name generator is opened for a novel with writing_language "Deutsch"
- **THEN** the explanation_language field defaults to "Deutsch"

### Requirement: Unified tone list across all UI surfaces
The tone selector SHALL use a single canonical list of bundled tones across Wizard Step 3, Settings NovelDetailsTab, and Editor GenerationPanel. The canonical list is: balanced, dramatic, humorous, suspenseful, contemplative, romantic, dark, adventurous, quiet.

#### Scenario: Wizard shows unified tone list
- **WHEN** the user reaches Step 3 of the Wizard
- **THEN** the tone selector shows all 9 bundled tones

#### Scenario: GenerationPanel shows unified tone list
- **WHEN** the user opens the tone selector in the Editor's GenerationPanel
- **THEN** the tone selector shows all 9 bundled tones (not the previous 4)

#### Scenario: Settings shows unified tone list
- **WHEN** the user opens the Novel Details tab in Settings
- **THEN** the tone selector shows all 9 bundled tones

## REMOVED Requirements

### Requirement: Language as dropdown with fixed options
**Reason**: Replaced by freetext writing_language field that supports any language description.
**Migration**: The "language" dropdown (en/de/fr) is replaced by a freetext "writing_language" input. Existing novels with language codes will have their values preserved as-is (e.g. "en" remains "en" until the user changes it).
