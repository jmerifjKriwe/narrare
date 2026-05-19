## 1. Core: Template Models Update

- [x] 1.1 Remove `template_language` field from `TemplateMeta` in `packages/core/narrare_core/templates/models.py`. Keep backward compat: parser silently ignores `template_language` in legacy templates.
- [x] 1.2 Update `TemplateField.description` to be explicitly optional (default `""` — already is, just document that it's deprecated for display purposes and will be empty in v3 templates).
- [x] 1.3 Write/update unit tests for `TemplateMeta` without `template_language`, backward compat with legacy templates.

## 2. Core: Template Parser Update

- [x] 2.1 Update `parse_template()` in `parser.py`: remove `template_language` from meta extraction, ignore the key in frontmatter instead of requiring it.
- [x] 2.2 Remove `template_language` from `_META_KEYS` set.
- [x] 2.3 Update `list_default_templates()` and `load_default_template()` in `__init__.py`: functions take only `entity_type`, no `language` parameter. Scan `defaults/*.md` instead of `defaults/{lang}/*.md`.
- [x] 2.4 Write unit tests: parse v3 template (no language, no descriptions), parse v2 template (legacy compat — language ignored, descriptions preserved), list/load functions.

## 3. Core: Bundled Template Migration

- [x] 3.1 For each entity type (character, location, faction, object, system, timeline, concept, setting): create new `defaults/{type}.md` by taking the current English template, removing `template_language`, bumping to version "3.0.0", and removing all `description` values from field definitions.
- [x] 3.2 Delete old language subdirectories: `defaults/en/`, `defaults/de/`, `defaults/fr/`.
- [x] 3.3 Verify all 8 templates parse correctly with `parse_template()` and produce valid `Template` objects with field_groups.

## 4. Core: i18n Field Description Namespace

- [x] 4.1 Add `kb.fieldDesc.{groupName}.{fieldName}` keys to `packages/i18n/messages/en/studio.json` for all fields across all 8 entity types. Text sourced from current English template descriptions.
- [x] 4.2 Add same keys to `packages/i18n/messages/de/studio.json` with German translations.
- [x] 4.3 Add same keys to `packages/i18n/messages/fr/studio.json` with French translations.
- [x] 4.4 Verify i18n validation passes (key completeness + placeholder consistency across locales).

## 5. Backend: Cascade Resolver & Service Update

- [x] 5.1 Update `CascadeResolver` in `apps/api/narrare/templates/cascade_resolver.py`: remove `language` parameter from `resolve()`, query by `entity_type` only.
- [x] 5.2 Update `TemplateService` in `service.py`: all methods drop `language` parameter.
- [x] 5.3 Update `schemas.py`: request/response models drop `language` field.
- [x] 5.4 Update `router.py`: `GET /novels/{id}/kb/templates/{entity_type}` drops `?language=` query param.
- [x] 5.5 Write/update unit tests for cascade resolver without language, service without language.

## 6. Backend: DB Migration

- [x] 6.1 Create Alembic migration: consolidate duplicate `(entity_type, scope, scope_id)` rows (keep highest version), drop old unique constraint, drop `language` column, add new unique constraint on `(entity_type, scope, scope_id)`.
- [x] 6.2 Update `KBTemplate` SQLAlchemy model in `models.py`: remove `language` column.
- [x] 6.3 Update `seed_templates.py`: load 8 templates instead of 24, insert without `language` field.
- [x] 6.4 Write migration regression test: verify upgrade/downgrade works, verify data consolidation.

## 7. Frontend: i18n-Only Display Text

- [x] 7.1 Update `KBEntryDetail.tsx`: pass group name to `KBTypeField` so it can look up `kb.fieldDesc.{group}.{field}` for placeholder.
- [x] 7.2 Update `KBTypeField.tsx`: use i18n `kb.fieldDesc.{group}.{field}` as placeholder instead of `field.description`. Accept `groupName` prop or derive from context.
- [x] 7.3 Update `KBEntryDetail.tsx`: ensure group description uses `description_key` i18n lookup exclusively (already does this — verify no `field.description` used for group hints).
- [x] 7.4 Update `packages/web/lib/api/kb.ts`: remove `language` from `KBTemplate` type and API calls.
- [x] 7.5 Update `packages/web/lib/hooks/useKB.ts`: `useKBTemplate(novelId, entityType)` drops language param.

## 8. Validation & Cleanup

- [ ] 8.1 Run `scripts/check_architecture.py` and fix any violations.
- [ ] 8.2 Run full test suite (unit + integration) and ensure all tests pass.
- [ ] 8.3 Run pre-commit hooks on all changed files.
- [ ] 8.4 Verify parser backward compat: old v2 templates (with language + descriptions) still parse without error.
- [ ] 8.5 Update `docs/_shared/CURRENT_STATE.md` to reflect the consolidation.
