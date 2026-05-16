# Capability: Prompt Culture Injection

## Purpose
Support culture-aware prompt composition by providing a `{{culture_guidelines}}` placeholder mechanism that resolves culture definition files and injects their content into prompts. Includes cascade override support for project-level culture customizations and language fallback to English.

## Requirements

### Requirement: Base prompt with culture placeholder
The system SHALL support a `{{culture_guidelines}}` placeholder in any bundled prompt template. When a prompt is composed and a culture is specified in context, the placeholder SHALL be replaced with the resolved culture definition content.

#### Scenario: Culture injection into prompt
- **WHEN** `PromptComposer.build()` is called with a prompt containing `{{culture_guidelines}}` and `context.extra["culture"]` is `"fantasy"`
- **THEN** the `{{culture_guidelines}}` placeholder is replaced with the content of the resolved culture definition file for `"fantasy"` in the appropriate language

#### Scenario: No culture specified
- **WHEN** `PromptComposer.build()` is called with a prompt containing `{{culture_guidelines}}` and no culture is specified in context
- **THEN** the `{{culture_guidelines}}` placeholder is replaced with an empty string (no error raised)

### Requirement: Culture definition file resolution
The system SHALL resolve culture definitions from the path `_bundled/{category}/cultures/{language}/{culture_id}.md`. The resolution SHALL fall back to English if the requested language has no culture definition.

#### Scenario: Culture resolved in requested language
- **WHEN** the composer resolves culture `"fantasy"` for language `"de"`
- **THEN** it loads `_bundled/generation/cultures/de/fantasy.md`

#### Scenario: Fallback to English culture
- **WHEN** the composer resolves culture `"fantasy"` for language `"fr"` and `_bundled/generation/cultures/fr/fantasy.md` does not exist
- **THEN** it falls back to `_bundled/generation/cultures/en/fantasy.md`

#### Scenario: Culture not found
- **WHEN** the composer resolves culture `"unknown_culture"` and no matching definition file exists in any language
- **THEN** the `{{culture_guidelines}}` placeholder is replaced with an empty string and a warning is logged

### Requirement: Culture definition cascade override
The system SHALL support user overrides of culture definitions via the standard cascade: project-level `.narrare/prompts/{category}/cultures/{language}/{culture_id}.md` overrides bundled defaults.

#### Scenario: Project-level culture override
- **WHEN** a project has `.narrare/prompts/generation/cultures/en/fantasy.md` and the bundled `_bundled/generation/cultures/en/fantasy.md` also exists
- **THEN** the project-level override is used for culture resolution

### Requirement: Culture definition YAML frontmatter
Each culture definition file SHALL contain YAML frontmatter with at minimum `culture_id`, `culture_name`, `language`, and `version` fields.

#### Scenario: Culture metadata available
- **WHEN** a culture definition file is loaded
- **THEN** the parsed frontmatter contains `culture_id`, `culture_name`, `language`, and `version` fields
