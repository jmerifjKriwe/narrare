## ADDED Requirements

### Requirement: Templates contain no display text
Bundled template files SHALL contain only structural data: field names, field types, ordering, `label_key` references, and `description_key` references. No translated strings, descriptions, or display text SHALL be embedded in template files.

#### Scenario: Parse language-neutral character template
- **WHEN** a character template is parsed that contains `field_groups.basic_info.fields.age.type: int` with no `description` field
- **THEN** the resulting `TemplateField` has `name="age"`, `field_type="int"`, `description=""`

#### Scenario: Field description is optional in frontmatter
- **WHEN** a template field definition omits the `description` key entirely
- **THEN** the parser creates a `TemplateField` with `description=""` (empty string default)

### Requirement: TemplateMeta drops template_language field
The `TemplateMeta` model SHALL NOT include a `template_language` field. Templates are language-neutral structural definitions.

#### Scenario: Parse template without language field
- **WHEN** a template's frontmatter contains `template_type: character` but no `template_language` key
- **THEN** the parser creates a `TemplateMeta` without error and `template_type` is set correctly

#### Scenario: Legacy templates with template_language still parse
- **WHEN** an old template still contains `template_language: "en"` in frontmatter
- **THEN** the parser ignores the `template_language` key without error (backward compat)

### Requirement: Bundled templates stored flat without language subdirectories
Bundled default templates SHALL be stored directly in `packages/core/narrare_core/templates/defaults/` as 8 files (one per entity type), not in language subdirectories. The `list_default_templates()` function returns `(entity_type,)` tuples without language.

#### Scenario: List available templates
- **WHEN** `list_default_templates()` is called
- **THEN** it returns 8 entries, one for each entity type: character, location, faction, object, system, timeline, concept, setting

#### Scenario: Load character template
- **WHEN** `load_default_template("character")` is called
- **THEN** it returns the raw content of `defaults/character.md`

#### Scenario: Load nonexistent template
- **WHEN** `load_default_template("nonexistent")` is called
- **THEN** it returns `None`

### Requirement: Template frontmatter format v3
Templates SHALL use a v3 format that removes `template_language` and makes `description` optional on fields:

```yaml
---
template_type: character
template_version: "3.0.0"
schema_version: "2.0.0"
field_groups:
  basic_info:
    label_key: kb.groups.basicInfo
    description_key: kb.groups.basicInfoHint
    order: 1
    fields:
      age:
        type: int
      role:
        type: str
---
```

#### Scenario: Parse v3 template
- **WHEN** a template with version "3.0.0" and no `template_language` is parsed
- **THEN** the parser produces a valid `Template` with correct field_groups, no `template_language` in meta, and empty descriptions

#### Scenario: v2 templates still parse correctly
- **WHEN** an existing v2 template with `template_language` and field `description` values is parsed
- **THEN** the parser produces a valid `Template`, ignoring `template_language` and preserving `description` values for backward compatibility
