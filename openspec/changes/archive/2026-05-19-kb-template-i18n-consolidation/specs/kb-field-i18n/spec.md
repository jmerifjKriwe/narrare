## ADDED Requirements

### Requirement: i18n field description namespace
All locale files SHALL provide field-level description/placeholder text under `kb.fieldDesc.{groupName}.{fieldName}` keys. These replace the `description` values previously embedded in template files.

#### Scenario: Get field description from i18n
- **WHEN** the frontend looks up `kb.fieldDesc.appearance.hair_color` in the English locale
- **THEN** it returns "Hair color and style" (or equivalent descriptive placeholder text)

#### Scenario: Missing field description falls back gracefully
- **WHEN** a field description key `kb.fieldDesc.features.architecture` is missing from the locale
- **THEN** the i18n system returns the key itself, and the frontend falls back to the formatted field name (e.g. "Architecture")

### Requirement: Complete field description coverage for all entity types
The i18n files SHALL contain `kb.fieldDesc` entries for every field in every entity type's template across all 3 locales (en, de, fr).

#### Scenario: Character field descriptions complete
- **WHEN** all field description keys for character template groups (basic_info, appearance, personality, background, relationships, development, speech) are queried
- **THEN** all keys return non-empty translated strings in en, de, and fr

#### Scenario: Location field descriptions complete
- **WHEN** all field description keys for location template groups (basic_info, features, inhabitants, history) are queried
- **THEN** all keys return non-empty translated strings in en, de, and fr

### Requirement: Frontend uses i18n for field placeholders
The `KBTypeField` component SHALL use i18n `kb.fieldDesc.{group}.{field}` as placeholder text instead of `field.description` from the template.

#### Scenario: Text input with i18n placeholder
- **WHEN** a text input for `appearance.hair_color` is rendered
- **THEN** the placeholder text comes from `kb.fieldDesc.appearance.hair_color`, not from `field.description`

#### Scenario: Tag input with i18n placeholder
- **WHEN** a tag input for `personality.traits` is rendered
- **THEN** the placeholder text comes from `kb.fieldDesc.personality.traits`

### Requirement: Frontend uses i18n for group and section descriptions
The `KBFieldGroup` and `KBSectionEditor` components SHALL use i18n for description/hint text exclusively via `description_key` from the template (which references an i18n key).

#### Scenario: Group description from description_key
- **WHEN** a field group has `description_key: "kb.groups.appearanceHint"`
- **THEN** the component looks up that i18n key and displays the translated hint text

#### Scenario: Group without description_key
- **WHEN** a field group has `description_key: ""` (empty)
- **THEN** no description text is displayed below the group title
