## ADDED Requirements

### Requirement: Template resolver protocol in core
The system SHALL define a `TemplateResolver` protocol in core that accepts an entity type and language, and returns a `Template` model. The protocol has no IO — concrete implementations handle cascade resolution.

#### Scenario: Resolve template via protocol
- **WHEN** the TemplateResolver protocol is called with entity_type="character" and language="en"
- **THEN** it returns a Template model containing the template's fields, sections, version, and content

### Requirement: Template parser handles Markdown with YAML frontmatter
The system SHALL provide a `parse_template` function in core that takes a raw Markdown+YAML string and returns a structured `Template` model with metadata (template_type, template_version, schema_version) and a list of `TemplateField` objects extracted from the frontmatter.

#### Scenario: Parse character template
- **WHEN** the character.md template is parsed
- **THEN** the resulting Template has template_type="character", template_version from frontmatter, and TemplateField entries for each frontmatter key (name, aliases, age, role, etc.)

#### Scenario: Parse template with missing frontmatter
- **WHEN** a template file has no YAML frontmatter delimiter
- **THEN** the parser treats the entire content as body with empty metadata

### Requirement: Bundled defaults shipped with core package
The system SHALL bundle default templates for all 6 entity types in English, German, and French under `packages/core/narrare_core/templates/defaults/`. Templates are loaded via `importlib.resources` for deployment portability.

#### Scenario: Load bundled English character template
- **WHEN** the system requests the default character template for language "en"
- **THEN** the bundled `defaults/en/character.md` is loaded and parsed

#### Scenario: Bundled defaults available in Docker
- **WHEN** the app runs inside a Docker container
- **THEN** bundled templates are accessible via `importlib.resources` regardless of filesystem layout

### Requirement: Cascade resolution in API layer
The API SHALL implement a `CascadeResolver` that implements the core `TemplateResolver` protocol. Resolution order: user project overrides → user global overrides → bundled defaults. First match wins.

#### Scenario: User project override takes precedence
- **WHEN** a user has a custom character.md in their project overrides
- **THEN** the cascade resolver returns the user's version, not the bundled default

#### Scenario: Fallback to bundled default
- **WHEN** no user overrides exist for the requested type and language
- **THEN** the cascade resolver returns the bundled default template

#### Scenario: Language fallback to English
- **WHEN** a template is requested for language "fr" but no French template exists at any cascade level
- **THEN** the cascade resolver falls back to the English ("en") version

### Requirement: Template versioning tracks override baseline
Each template carries `template_version` in its frontmatter. When a user overrides a template, the system records the `based_on_version` (the version of the default template at override time). When the bundled default is updated in a new release, the system detects the version mismatch.

#### Scenario: Detect outdated override
- **WHEN** a user override has based_on_version="1.0.0" and the current bundled default is version "1.1.0"
- **THEN** the system returns a notification indicating the override is based on an older template version

#### Scenario: No notification for current override
- **WHEN** a user override has based_on_version="1.1.0" and the current bundled default is version "1.1.0"
- **THEN** no version mismatch notification is generated

### Requirement: Schema bridge connects templates to metadata schemas
The system SHALL provide a `schema_bridge` that maps template fields to the corresponding KB metadata schema fields. This enables the frontend to render type-appropriate form fields and validate input against the schema.

#### Scenario: Get form fields for character creation
- **WHEN** the frontend requests form configuration for entity_type "character"
- **THEN** the schema bridge returns a list of fields with their types, labels, and validation rules, derived from the CharacterMetadata schema and the character template

### Requirement: Templates are recommendations, not enforcement
The system SHALL NOT require entries to fill all template fields or sections. Metadata validation enforces types of provided fields but does not require presence. Body sections are entirely optional.

#### Scenario: Character entry without optional fields
- **WHEN** a character entry is created with only name "Anna" and entity_type "character", no metadata, no body
- **THEN** the entry is created successfully

#### Scenario: Character with partial metadata
- **WHEN** a character entry is created with metadata `{"age": 32}` (no role, no gender, no other fields)
- **THEN** the entry is created and the missing fields are treated as null/absent
