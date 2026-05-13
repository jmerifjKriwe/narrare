## Purpose

Automated validation ensuring key completeness across languages, placeholder consistency, and detection of hardcoded user-facing strings. Runs in pre-commit and CI via `scripts/validate-i18n.ts`.

## Requirements

### Requirement: Key completeness validation across locales
The validation script SHALL verify that every translation key present in the reference locale (en) also exists in all other locales, and vice versa. Missing keys SHALL be reported as errors. Extra keys (present in a non-en locale but not in en) SHALL be reported as warnings.

#### Scenario: Missing key in German translations
- **WHEN** `en/common.json` contains key `"common.retry"` but `de/common.json` does not
- **THEN** the validation script SHALL report an error: `de missing key "common.retry"`
- **AND** exit with non-zero status

#### Scenario: Extra key in French translations
- **WHEN** `fr/editor.json` contains key `"editor.legacyFeature"` but `en/editor.json` does not
- **THEN** the validation script SHALL report a warning: `fr has extra key "editor.legacyFeature"`
- **AND** exit with zero status (warnings do not fail CI)

#### Scenario: All locales complete
- **WHEN** all locale directories have exactly the same flattened key set as `en/`
- **THEN** the completeness check SHALL pass without errors

### Requirement: Placeholder consistency validation
The validation script SHALL extract ICU-style placeholders (patterns matching `{word}`, `{count}`, `{n}`, etc.) from translation values and verify that every key has the same set of placeholders across all locales. Mismatches SHALL be reported as errors.

#### Scenario: Missing placeholder in German translation
- **WHEN** `en/editor.json` has value `"{count} words"` for key `"editor.wordCount"`
- **AND** `de/editor.json` has value `"Wörter"` (missing `{count}` placeholder)
- **THEN** the validation script SHALL report an error: `de key "editor.wordCount" missing placeholders: {count}`
- **AND** exit with non-zero status

#### Scenario: Extra placeholder in French translation
- **WHEN** `fr/editor.json` has value `"{count} mots ({total})"`
- **AND** `en/editor.json` has value `"{count} words"` (no `{total}` placeholder)
- **THEN** the validation script SHALL report an error: `fr key "editor.wordCount" has extra placeholders: {total}`

#### Scenario: Matching placeholders across locales
- **WHEN** all locales have value `"{n} chapitres"` / `"{n} chapters"` / `"{n} Kapitel"` for key `"wizard.step3.demoChapters"`
- **THEN** the placeholder check SHALL pass for that key

### Requirement: Existing hardcoded-string checks preserved
The validation script SHALL continue to perform the existing checks: AST-based hardcoded string detection in TSX files and regex-based hardcoded error string detection in Python service/router files.

#### Scenario: TSX hardcoded text still detected
- **WHEN** a `.tsx` file contains `<div>Hello world</div>` (without useTranslations)
- **THEN** the validation script SHALL report an error as it does currently

#### Scenario: Python hardcoded error string still detected
- **WHEN** a Python service file contains `raise HTTPException(status_code=404, detail="File not found")`
- **THEN** the validation script SHALL report an error as it does currently

### Requirement: Validation runs in pre-commit and CI
The extended `validate-i18n.ts` script SHALL be invoked by the existing pre-commit hook and CI workflow without structural changes to `.pre-commit-config.yaml` or `.github/workflows/ci.yml`.

#### Scenario: Pre-commit runs validation
- **WHEN** a developer commits changes to `.tsx` files
- **THEN** the pre-commit hook SHALL run `validate-i18n.ts` including completeness and placeholder checks

#### Scenario: CI runs validation
- **WHEN** a pull request is opened or updated
- **THEN** the CI workflow SHALL run `validate-i18n.ts` including completeness and placeholder checks
