## MODIFIED Requirements

### Requirement: Base prompt with culture placeholder
The system SHALL support a `{{culture_guidelines}}` placeholder in any bundled prompt template. When a prompt is composed and a name_style is specified in context, the placeholder SHALL be replaced with the resolved name-style definition content if a matching file exists, or with a generic instruction containing the raw name_style string if no file exists.

#### Scenario: Name-style definition file resolved
- **WHEN** `PromptComposer.build()` is called with `context.extra["name_style"]` = `"fantasy"` and a name-style definition file exists at `_bundled/generation/name-styles/{language}/fantasy.md`
- **THEN** the `{{culture_guidelines}}` placeholder is replaced with the content of the resolved file

#### Scenario: No definition file — freetext fallback
- **WHEN** `PromptComposer.build()` is called with `context.extra["name_style"]` = `"Klingonische Namen aus Star Trek"` and no matching definition file exists
- **THEN** the `{{culture_guidelines}}` placeholder is replaced with "Generate names fitting the following style: Klingonische Namen aus Star Trek"

#### Scenario: No name_style specified
- **WHEN** `PromptComposer.build()` is called with no `name_style` in context
- **THEN** the `{{culture_guidelines}}` placeholder is replaced with an empty string

### Requirement: Culture definition file resolution (renamed to name-style definition)
The system SHALL resolve name-style definitions from the path `_bundled/{category}/name-styles/{language}/{style_id}.md`. The resolution SHALL fall back to English if the requested language has no definition file. This is opportunistic — if no file matches the name_style string, the raw string is used as fallback.

#### Scenario: Name-style resolved in requested language
- **WHEN** the composer resolves name_style `"fantasy"` for language `"de"`
- **THEN** it loads `_bundled/generation/name-styles/de/fantasy.md`

#### Scenario: Fallback to English name-style
- **WHEN** the composer resolves name_style `"fantasy"` for language `"fr"` and `_bundled/generation/name-styles/fr/fantasy.md` does not exist
- **THEN** it falls back to `_bundled/generation/name-styles/en/fantasy.md`

#### Scenario: Freetext name_style with no matching file
- **WHEN** the composer resolves name_style `"Nordische Mythologie, aber futuristisch"` and no matching definition file exists
- **THEN** no file is loaded; the raw string is used as a prompt variable instead

## RENAMED Requirements

### FROM: Culture definition cascade override
### TO: Name-style definition cascade override

### FROM: Culture definition YAML frontmatter
### TO: Name-style definition YAML frontmatter

Each name-style definition file SHALL contain YAML frontmatter with at minimum `style_id`, `style_name`, `language`, and `version` fields.

#### Scenario: Name-style metadata available
- **WHEN** a name-style definition file is loaded
- **THEN** the parsed frontmatter contains `style_id`, `style_name`, `language`, and `version` fields
