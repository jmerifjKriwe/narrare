## Context

The KB template system currently ships 24 bundled template files (8 entity types × 3 languages). Each template contains both structural data (field names, types, ordering) and display text (translated descriptions, labels). The i18n system already provides the same display text in `packages/i18n/messages/{en,de,fr}/studio.json` under `kb.groups.*`, `kb.groupLabels.*`, and `kb.sections.*`. This creates triple maintenance and YAML parsing fragility (e.g. French `(ex: ...)` patterns breaking YAML parsing).

The frontend (`KBEntryDetail.tsx`) already uses i18n as its primary text source via the `label()` helper — it reads `kb.groups.{name}` for group titles and `kb.groupLabels.{group}.{field}` for field labels. The template's `description` field is only used as a fallback placeholder in `KBTypeField.tsx`. The infrastructure for i18n-only display text is 80% in place.

## Goals / Non-Goals

**Goals:**

- Eliminate redundant display text from templates — templates become pure structural definitions
- Reduce bundled template files from 24 to 8 (one per entity type, no language dimension)
- Make all KB display text flow exclusively through the i18n system
- Simplify the cascade resolver (no language parameter, no language fallback logic)
- Make adding new languages a pure i18n task (zero template changes)

**Non-Goals:**

- Changing the template override UI (KBTemplatesTab/KBTemplateEditor) — it still edits raw YAML, just without language-specific content
- Changing how user/project overrides work structurally — cascade still works, just without language dimension
- Changing KB schemas (`CharacterMetadata`, etc.) — they remain unchanged
- Changing the DB `kb_entries` table — only `kb_templates` is affected
- Migrating existing user-created template overrides — the migration handles this via data cleanup

## Decisions

### D1: Templates drop `template_language`, descriptions become optional

**Decision**: The `template_language` field is removed from `TemplateMeta`. Field `description` on `TemplateField` becomes optional (default `""`). All display text comes from i18n via `label_key` and `description_key` references.

**Rationale**: The template's job is structure — what fields exist, what types they are, how they're ordered. Display text is the i18n system's job. Removing descriptions from templates eliminates the YAML parsing fragility and the 3× maintenance burden.

**Alternatives considered**:
- Keep descriptions but auto-generate them from i18n at parse time: adds coupling between core (parser) and i18n (which core doesn't import). Violates architecture boundaries.
- Keep language-specific templates but strip descriptions: still 24 files to maintain, just with less content. Doesn't solve the fundamental duplication.

### D2: New i18n namespace `kb.fieldDesc` for field descriptions/placeholders

**Decision**: Add `kb.fieldDesc.{groupName}.{fieldName}` keys to all locale files. These provide the placeholder/description text currently embedded in template `description` fields.

**Rationale**: The frontend currently uses `field.description` as placeholder text in input fields. Moving this to i18n keeps the text translatable and centrally managed. The `description_key` pattern already exists for groups/sections — extending it to fields is consistent.

**Alternatives considered**:
- Use `kb.groupLabels.{group}.{field}` for both label and description: conflates two different UX concepts (short label vs. explanatory placeholder).
- Drop field descriptions entirely: loses helpful placeholder text in forms. Users benefit from hints like "Scars, tattoos, birthmarks, or other distinctive features".

### D3: Bundled templates live in `defaults/` without language subdirectories

**Decision**: Templates move from `defaults/{en,de,fr}/character.md` to `defaults/character.md`. The `defaults/` directory has 8 files, no subdirectories.

**Rationale**: No language dimension means no need for language subdirectories. Flat structure is simpler to navigate and load.

**Alternatives considered**:
- Keep language subdirectories with identical files: pointless duplication, defeats the purpose.
- Single `defaults/templates/` subdirectory: unnecessary nesting for 8 files.

### D4: DB migration drops `language` column from `kb_templates`

**Decision**: A new Alembic migration removes the `language` column from `kb_templates` and adjusts the unique constraint from `(entity_type, language, scope, scope_id)` to `(entity_type, scope, scope_id)`.

**Rationale**: Without language-specific templates, the column is meaningless. The unique constraint must be updated to match. Existing rows with different languages for the same type are consolidated — keep the highest-version entry per `(entity_type, scope, scope_id)`.

**Migration strategy**:
1. For each `(entity_type, scope, scope_id)` group, keep the row with the highest `based_on_version`, delete the rest.
2. Drop the old unique constraint.
3. Drop the `language` column.
4. Add the new unique constraint on `(entity_type, scope, scope_id)`.

### D5: Cascade resolver simplified to entity-type-only

**Decision**: `TemplateResolver.resolve(entity_type)` drops the `language` parameter. Resolution is: user override → project override → bundled default, all keyed by `entity_type` only.

**Rationale**: No language dimension in templates means no language parameter needed. The frontend already uses i18n for all display — it only needs the structural template to know which fields/groups/sections exist.

## Risks / Trade-offs

**[Breaking API change]** → The `GET /novels/{id}/kb/templates/{entity_type}?language=en` query parameter becomes a no-op and is deprecated. Frontend already doesn't pass it in most cases. Low risk.

**[User template overrides may have language-specific content]** → Existing user/project overrides in the DB may contain translated descriptions. After migration, these descriptions are ignored (field-level descriptions no longer rendered from templates). The structural data (field names, types, groups, sections) is preserved. Low impact: overrides are rare, and the visual difference is minimal (descriptions become placeholders from i18n instead).

**[Migration data consolidation]** → If a user has overrides for the same entity type in multiple languages, the migration keeps only the highest-versioned one. This is acceptable because template overrides define structure, not text — the structure is the same across languages.

**[Template editor shows raw YAML without descriptions]** → The template management UI (`KBTemplateEditor`) currently shows the full template including descriptions. After this change, templates are shorter and more focused. This is an improvement — less noise, clearer structure. The raw YAML editor still works, just with less content.
