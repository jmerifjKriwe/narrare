## Why

The i18n setup has two problems. First, all translations live in monolithic JSON files (one per language, ~160 lines and growing). As features are added, these files become merge-conflict magnets and hard to review. Second, there is no automated check that all languages have complete key coverage — a missing key in `de.json` or `fr.json` is only discovered when a user sees an empty string or raw key path at runtime. Additionally, `packages/i18n` exists as a ghost package (empty stub) while translations live in `packages/web/messages/`, creating two i18n locations with no plan for convergence. When CLI, MCP, and A2A support arrive later, they will need the same translations — requiring a single source of truth.

## What Changes

- Move translation files from `packages/web/messages/` to `packages/i18n/messages/` with namespace-based directory structure (`messages/{locale}/{namespace}.json` instead of `messages/{locale}.json`)
- Extend `scripts/validate-i18n.ts` with key-completeness checking (all languages have the same keys) and placeholder-consistency checking (ICU variables match across languages)
- Update `packages/web/lib/i18n/request.ts` to load from the new location and namespace structure
- Delete `packages/web/messages/` directory
- Document `packages/i18n/narrare_i18n/` stub with its future purpose (Python loader for CLI/MCP/A2A)
- Create ADR-013 recording i18n architectural decisions

## Capabilities

### New Capabilities
- `i18n-namespace-structure`: Namespace-based file organization for translations — one JSON file per namespace per locale, loaded by next-intl from a shared location
- `i18n-validation`: Automated validation ensuring key completeness across languages, placeholder consistency, and detection of hardcoded user-facing strings

### Modified Capabilities
<!-- No existing specs are being modified -->

## Impact

- **`packages/i18n/`**: Becomes the real source of truth for translations. `messages/` directory added. `pyproject.toml` updated for package data. Stub documented.
- **`packages/web/messages/`**: Deleted entirely
- **`packages/web/lib/i18n/request.ts`**: Path updated to load from `packages/i18n/messages/`
- **`packages/web/` TypeScript config**: May need path alias updates
- **`scripts/validate-i18n.ts`**: Path updates + two new validation checks (key completeness, placeholder consistency)
- **`.pre-commit-config.yaml`**: No structural change (already calls `validate-i18n.ts`)
- **`.github/workflows/ci.yml`**: No structural change (already calls `validate-i18n.ts`)
- **`docs/architecture/decisions/`**: New ADR-013
- **No API changes, no database changes, no core/backend code changes**
