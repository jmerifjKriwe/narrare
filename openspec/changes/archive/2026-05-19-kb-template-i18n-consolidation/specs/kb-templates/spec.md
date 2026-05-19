## MODIFIED Requirements

### Requirement: Cascade resolution in API layer
The API SHALL implement a `CascadeResolver` that implements the core `TemplateResolver` protocol. Resolution order: user project overrides → user global overrides → bundled defaults. First match wins. Resolution is by `entity_type` only — there is no language dimension.

#### Scenario: User project override takes precedence
- **WHEN** a user has a custom character template in their project overrides
- **THEN** the cascade resolver returns the user's version, not the bundled default

#### Scenario: Fallback to bundled default
- **WHEN** no user overrides exist for the requested entity type
- **THEN** the cascade resolver returns the bundled default template

#### Scenario: No language fallback needed
- **WHEN** a template is requested for entity type "character"
- **THEN** the resolver returns the single bundled character template — there is no language-specific lookup or fallback to English

### Requirement: Template versioning tracks override baseline
Each template carries `template_version` in its frontmatter. When a user overrides a template, the system records the `based_on_version` (the version of the default template at override time). When the bundled default is updated in a new release, the system detects the version mismatch. Overrides are keyed by `(entity_type, scope, scope_id)` — no language dimension.

#### Scenario: Detect outdated override
- **WHEN** a user override has based_on_version="2.0.0" and the current bundled default is version "3.0.0"
- **THEN** the system returns a notification indicating the override is based on an older template version

#### Scenario: No notification for current override
- **WHEN** a user override has based_on_version="3.0.0" and the current bundled default is version "3.0.0"
- **THEN** no version mismatch notification is generated

### Requirement: Bundled defaults shipped with core package
The system SHALL bundle default templates for all 8 entity types under `packages/core/narrare_core/templates/defaults/`. Templates are loaded via `importlib.resources` for deployment portability. Each entity type has exactly one template file — no language variants.

#### Scenario: Load bundled character template
- **WHEN** the system requests the default character template
- **THEN** the bundled `defaults/character.md` is loaded and parsed

#### Scenario: Bundled defaults available in Docker
- **WHEN** the app runs inside a Docker container
- **THEN** bundled templates are accessible via `importlib.resources` regardless of filesystem layout

### Requirement: Template resolver protocol in core
The system SHALL define a `TemplateResolver` protocol in core that accepts an entity type and returns a `Template` model. The protocol has no IO — concrete implementations handle cascade resolution. There is no language parameter.

#### Scenario: Resolve template via protocol
- **WHEN** the TemplateResolver protocol is called with entity_type="character"
- **THEN** it returns a Template model containing the template's fields, field_groups, sections, version, and content

## REMOVED Requirements

### Requirement: Language fallback to English
**Reason**: Templates are now language-neutral. There is no language dimension in template resolution, so there is no need for language fallback. All display text comes from the i18n system, which has its own language fallback logic.
**Migration**: The i18n system already handles language fallback (missing key → key itself, or configured fallback locale). No migration needed — language fallback for display text was always handled by i18n.

### Requirement: Template parser handles language-specific frontmatter
**Reason**: The `template_language` frontmatter key is removed from the v3 template format. The parser ignores it in legacy templates for backward compatibility but does not use it.
**Migration**: Existing v2 templates with `template_language` still parse correctly — the field is ignored.
