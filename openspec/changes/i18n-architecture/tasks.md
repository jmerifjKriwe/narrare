## 1. Namespace Split & Migration

- [x] 1.1 Create directory structure `packages/i18n/messages/{en,de,fr}/`
- [x] 1.2 Split `packages/web/messages/en.json` into 7 namespace files under `packages/i18n/messages/en/` (common, auth, wizard, dashboard, editor, errors, settings)
- [x] 1.3 Split `packages/web/messages/de.json` into 7 namespace files under `packages/i18n/messages/de/`
- [x] 1.4 Split `packages/web/messages/fr.json` into 7 namespace files under `packages/i18n/messages/fr/`
- [x] 1.5 Verify all namespace files are valid JSON and key structure is preserved

## 2. Frontend Integration

- [x] 2.1 Update `packages/web/lib/i18n/request.ts` to load namespace files from `packages/i18n/messages/{locale}/*.json` and merge into single messages object
- [x] 2.2 Verify `useTranslations()` calls resolve correctly with merged namespaces (no component changes expected)
- [x] 2.3 Update TypeScript config or path aliases if needed for the new import paths
- [x] 2.4 Run `pnpm build` in `packages/web` to verify build succeeds

## 3. Cleanup

- [x] 3.1 Delete `packages/web/messages/` directory (en.json, de.json, fr.json)
- [x] 3.2 Update `packages/i18n/pyproject.toml` to reflect package data setup
- [x] 3.3 Update `packages/i18n/narrare_i18n/__init__.py` with docstring explaining future Python loader purpose

## 4. Validation Extension

- [x] 4.1 Add key-completeness check to `scripts/validate-i18n.ts` — flatten all namespace files per locale, compare against en as reference, report missing keys (error) and extra keys (warning)
- [x] 4.2 Add placeholder-consistency check to `scripts/validate-i18n.ts` — extract ICU placeholders via regex, compare across locales, report mismatches (error)
- [x] 4.3 Update message file paths in existing hardcoded-string checks (TSX AST + Python regex) to point to `packages/i18n/messages/`
- [x] 4.4 Run `npx tsx scripts/validate-i18n.ts` locally and verify all checks pass

## 5. Documentation

- [x] 5.1 Create `docs/architecture/decisions/ADR-013-i18n.md` covering: next-intl as framework, namespace-based file structure, en as reference locale, validation strategy, packages/i18n as source of truth, future Python loader plan
- [x] 5.2 Add ADR-013 entry to `docs/architecture/decisions/INDEX.md`
- [x] 5.3 Update `docs/reference/directory-structure.md`: remove `messages/` section from `packages/web/` tree, add `messages/` section to `packages/i18n/` tree showing namespace-based structure
- [x] 5.4 Update `docs/_shared/CURRENT_STATE.md`: update `packages/i18n/` section to reflect it is now the active source of truth (no longer "content not yet populated"), update i18n line under packages/web to reference the new location
- [x] 5.5 Update `docs/development/coding-standards.md` i18n section: add guidance on namespace structure, how to add new translation keys (which file to edit), and the validation checks available

## 6. Verification

- [x] 6.1 Run pre-commit hooks and verify all pass
- [x] 6.2 Run frontend test suite (`pnpm test`) and verify no regressions
- [x] 6.3 Run frontend build (`pnpm build`) and verify success
- [x] 6.4 Run `scripts/validate-i18n.ts` in CI mode and verify all checks pass

## 7. Commit

- [x] 7.1 Stage all changed files and create conventional commit: `refactor(i18n): consolidate translations into packages/i18n with namespace structure and completeness validation`
