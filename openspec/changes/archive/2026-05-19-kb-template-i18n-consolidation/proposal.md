## Why

KB templates currently exist in 3 language variants (en/de/fr) — each containing translated `description` strings for every field, group, and section. The same labels are also maintained in the i18n JSON files (`packages/i18n/messages/{en,de,fr}/studio.json` under `kb.groupLabels.*`). This creates **triple maintenance**: adding a field requires editing 3 template files AND 3 i18n files. French templates also suffer from YAML parsing failures when descriptions contain `(ex: ...)` patterns. The template format conflates two concerns — structural definition (field names, types, ordering) and display text (labels, descriptions, hints) — that should be separated.

## What Changes

- **BREAKING**: Bundled templates become language-neutral — 8 files instead of 24. Each template contains only structural data: field names, types, ordering, `label_key` references, and `description_key` references. No translated strings.
- **BREAKING**: The `template_language` frontmatter field is removed. Templates are no longer language-specific.
- **BREAKING**: The `kb_templates` DB table no longer has a `language` column. The seed service inserts 8 global templates instead of 24.
- The template parser (`parse_template`) is updated: `description` on fields becomes optional; `label_key` and `description_key` on groups/sections remain the authoritative references.
- i18n files gain a new namespace: `kb.fieldDesc.{groupName}.{fieldName}` for field placeholder/description text (currently embedded in template descriptions).
- The frontend reads all display text exclusively from i18n — `field.description` is no longer used as a visible string. The `KBTypeField` component uses i18n for both label and placeholder.
- The cascade resolver no longer needs a `language` parameter — resolution is by `entity_type` only.
- The API endpoint `GET /novels/{id}/kb/templates/{entity_type}` drops the `?language=` query parameter.
- Adding a new language to the KB UI requires only i18n file changes — zero template changes.

## Capabilities

### New Capabilities
- `language-neutral-templates`: Templates as pure structural definitions (field names, types, ordering, i18n key references) with no embedded display text. Parser support for the simplified format.
- `kb-field-i18n`: Complete i18n coverage for all KB field labels, descriptions, group titles, group hints, and section labels. New `kb.fieldDesc.*` namespace for field-level descriptions/placeholders.

### Modified Capabilities
- `kb-templates`: Cascade resolution simplified to entity-type-only (no language dimension). Seed service inserts 8 templates. DB schema drops `language` column. API drops `?language=` parameter.

## Impact

- **Core**: `packages/core/narrare_core/templates/` — parser, models, bundled defaults (24 → 8 files)
- **Backend**: `apps/api/narrare/templates/` — cascade resolver, service, router, schemas, seed service, DB migration
- **Backend**: `apps/api/narrare/setup/seed_templates.py` — simplified to 8 templates
- **Frontend**: `packages/web/components/studio/kb/KBEntryDetail.tsx`, `KBTypeField.tsx` — i18n-only display text
- **Frontend**: `packages/web/lib/api/kb.ts`, `packages/web/lib/hooks/useKB.ts` — API types drop language param
- **i18n**: All 3 locale files gain `kb.fieldDesc.*` namespace
- **DB Migration**: New migration drops `language` column from `kb_templates`, removes language dimension from unique constraint
- **Tests**: Parser tests, seed tests, cascade resolver tests, frontend component tests all updated
