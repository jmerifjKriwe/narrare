## ADDED Requirements

### Requirement: Name generation base prompts
The system SHALL provide bundled base prompt templates for name generation at `_bundled/generation/{language}/names/system.md` for each supported language (en, de, fr). Each prompt SHALL contain `{{culture_guidelines}}` placeholder and generation-specific variables (`{{name_type}}`, `{{count}}`, `{{gender}}`, `{{existing_names}}`).

#### Scenario: English name generation prompt exists
- **WHEN** `PromptRegistry.resolve()` is called with category=`"generation"`, language=`"en"`, mode=`"names"`
- **THEN** a valid prompt file is found and its content contains the `{{culture_guidelines}}` placeholder

#### Scenario: German name generation prompt exists
- **WHEN** `PromptRegistry.resolve()` is called with category=`"generation"`, language=`"de"`, mode=`"names"`
- **THEN** a valid prompt file is found in German

#### Scenario: French name generation prompt exists
- **WHEN** `PromptRegistry.resolve()` is called with category=`"generation"`, language=`"fr"`, mode=`"names"`
- **THEN** a valid prompt file is found in French

### Requirement: Culture definition files
The system SHALL provide bundled culture definition files at `_bundled/generation/cultures/{language}/{culture_id}.md` for cultures: `fantasy`, `modern`, `scifi` in each supported language (en, de, fr).

#### Scenario: Fantasy culture definitions exist
- **WHEN** the system resolves culture `"fantasy"` for any supported language
- **THEN** a valid culture definition file is found containing naming conventions, phonetic patterns, and examples

#### Scenario: Modern culture definitions exist
- **WHEN** the system resolves culture `"modern"` for any supported language
- **THEN** a valid culture definition file is found containing contemporary naming conventions

#### Scenario: Scifi culture definitions exist
- **WHEN** the system resolves culture `"scifi"` for any supported language
- **THEN** a valid culture definition file is found containing technological/alien naming patterns

### Requirement: Prompt YAML frontmatter
Each bundled prompt file SHALL contain YAML frontmatter with at minimum `prompt_type`, `prompt_language`, and `prompt_version` fields.

#### Scenario: Frontmatter is parseable
- **WHEN** a bundled prompt file is loaded
- **THEN** the frontmatter contains `prompt_type: "generation"`, `prompt_language` matching the directory language, and a `prompt_version` semver string
