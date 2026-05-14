## ADDED Requirements

### Requirement: Translations are organized in per-namespace files per locale
The system SHALL store translation files under `packages/i18n/messages/{locale}/{namespace}.json` where `{locale}` is a BCP-47 language tag and `{namespace}` is a logical grouping of translation keys. Each namespace file SHALL contain a valid JSON object with nested keys matching the current structure (e.g., `wizard.step4.title`).

#### Scenario: Namespace file structure for English locale
- **WHEN** the messages directory is inspected
- **THEN** it SHALL contain directories `en/`, `de/`, `fr/`
- **AND** each directory SHALL contain `common.json`, `auth.json`, `wizard.json`, `dashboard.json`, `editor.json`, `errors.json`, `settings.json`
- **AND** each file SHALL be valid JSON with the same key structure as the current monolithic files

#### Scenario: Key structure preserved after split
- **WHEN** `useTranslations("wizard.step4")` is called
- **THEN** the returned translation function SHALL resolve `t("title")` to the same value as before the split

### Requirement: packages/i18n is the single source of truth for translations
The system SHALL store all translation files in `packages/i18n/messages/`. No other location in the repository SHALL contain translation message files. The `packages/web/messages/` directory SHALL NOT exist.

#### Scenario: Frontend loads from shared location
- **WHEN** `packages/web/lib/i18n/request.ts` processes a request for locale "de"
- **THEN** it SHALL load namespace files from `packages/i18n/messages/de/`
- **AND** merge them into a single messages object for next-intl

#### Scenario: No duplicate message directories
- **WHEN** the repository is searched for `messages/*.json` or `messages/**/*.json` patterns
- **THEN** results SHALL only exist under `packages/i18n/messages/`

### Requirement: next-intl calling convention is preserved
The system SHALL NOT require changes to existing `useTranslations()` calls in components. The namespace resolution SHALL work identically to the current flat-file approach.

#### Scenario: Existing component code unchanged
- **WHEN** a component calls `useTranslations("editor")` or `useTranslations("wizard.step4")`
- **THEN** the translation function SHALL resolve keys exactly as before the migration

### Requirement: packages/i18n Python stub documents its future purpose
The `packages/i18n/narrare_i18n/__init__.py` file SHALL contain a docstring or comment explaining that it will become a Python translation loader when CLI, MCP, or A2A support is added.

#### Scenario: Stub documentation is present
- **WHEN** `packages/i18n/narrare_i18n/__init__.py` is read
- **THEN** it SHALL contain a comment explaining the future role as Python i18n loader

### Requirement: ADR-013 documents i18n architectural decisions
An Architecture Decision Record SHALL be created at `docs/architecture/decisions/ADR-013-i18n.md` recording the i18n framework choice, file structure, validation strategy, locale list, and plans for Python loader integration.

#### Scenario: ADR exists and is indexed
- **WHEN** `docs/architecture/decisions/INDEX.md` is inspected
- **THEN** it SHALL list ADR-013 with title "Internationalization Architecture" and status "Accepted"
