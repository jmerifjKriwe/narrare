## Context

Narrare uses `next-intl` for frontend internationalization with three locales (en, de, fr). Translations currently live in `packages/web/messages/` as three monolithic JSON files (~160 lines each). A separate `packages/i18n` Python package exists as an empty stub, already wired as a workspace dependency in `packages/core` and `apps/api`. The validation script (`scripts/validate-i18n.ts`) checks for hardcoded strings but does not verify cross-language key completeness.

When CLI, MCP, and A2A support arrive, Python consumers will need the same translations. A unified source of truth avoids duplicating translation work.

## Goals / Non-Goals

**Goals:**
- Establish `packages/i18n/messages/` as the single source of truth for all translations
- Split monolithic JSON files into per-namespace files to reduce merge conflicts and improve reviewability
- Add automated key-completeness and placeholder-consistency validation
- Document i18n architecture decisions in ADR-013
- Preserve existing `useTranslations()` call patterns — no component changes required

**Non-Goals:**
- Python loader implementation (deferred to CLI/MCP/A2A work)
- Backend error message i18n (API responses stay English for now)
- Adding new languages beyond en/de/fr
- Translation management platform integration (Crowdin, Weblate, etc.)
- Changing the next-intl framework or message format

## Decisions

### D1: File layout — directory-per-locale with per-namespace files

```
packages/i18n/messages/
  en/
    common.json
    auth.json
    wizard.json
    dashboard.json
    editor.json
    errors.json
    settings.json
  de/
    ...
  fr/
    ...
```

**Why not keep flat files**: Monolithic files become unwieldy at scale. Every feature PR touches the same file, causing merge conflicts and making reviews harder.

**Why not one file per namespace at root level** (`messages/en.common.json`): Directory-per-locale is the convention next-intl documentation recommends and makes "add a new locale" a single directory copy.

**Why these seven namespaces**: They match the existing top-level keys in the current JSON files. Each corresponds to a distinct UI area. No further splitting needed at ~160 total lines — `wizard.json` is the largest at ~50 keys and still manageable.

### D2: Shared location — packages/i18n owns the message files

`packages/i18n/messages/` is the source of truth. `packages/web` reads from this location via relative path import in `request.ts`.

**Why not keep in packages/web**: Two i18n locations (web/messages + packages/i18n stub) would persist. When CLI/MCP/A2A arrive, we'd need to migrate anyway. Moving now eliminates the technical debt.

**Why not a third neutral location**: Adds unnecessary indirection. `packages/i18n` already exists and is already a workspace dependency for both `packages/web` (implicitly) and `apps/api` + `packages/core` (explicitly).

### D3: request.ts loads via dynamic import with glob

`request.ts` will import all namespace JSON files for the requested locale and merge them into a single messages object (required by next-intl's `getRequestConfig`).

**Approach**: Use `import.meta.glob` or a dynamic import per namespace file, then deep-merge. This preserves the existing `useTranslations("wizard.step4")` calling convention.

### D4: Validation extension — completeness + placeholder consistency

Extend `scripts/validate-i18n.ts` with two new checks:

1. **Key Completeness**: Flatten all JSON files per locale, compare key sets against `en` as reference. Report missing and extra keys. Fail CI on any missing keys.

2. **Placeholder Consistency**: For each key, extract ICU-style placeholders (e.g., `{count}`, `{seconds}`, `{n}`) via regex. Verify all languages have the same set of placeholders for the same key. Fail CI on mismatch.

**Why en as reference**: English is the development language and default locale. All new keys are added there first.

**Why custom script over external tool**: The validation needs are specific (3 languages, ~100 keys, monorepo paths). External tools (i18next-parser, formatjs) solve extraction/synthesis problems we don't have. A ~80-line addition to the existing script covers it cleanly.

### D5: packages/i18n as hybrid package

`packages/i18n` remains a Python package but owns JSON data files alongside Python code. The JSON files are not included in the Python wheel (they're consumed at build/import time via filesystem paths). When the Python loader is implemented later, `narrare_i18n` will use `__file__`-relative paths to locate the messages directory.

## Risks / Trade-offs

- **[Path coupling between packages]** → `packages/web` imports from `packages/i18n/messages/` via relative path. This creates a filesystem coupling between packages. **Mitigation**: The path is a single constant in `request.ts`. If needed later, a workspace alias can abstract it.

- **[Python wheel excludes JSON files]** → If someone installs `narrare-i18n` via pip independently, the messages won't be included. **Mitigation**: In the monorepo, filesystem access is always available. When CLI/MCP need it, we'll configure `pyproject.toml` to include JSON as package data.

- **[Namespace split granularity]** → Seven namespaces may not be fine enough as the project grows. **Mitigation**: Splitting a namespace (e.g., `wizard.json` → `wizard-setup.json` + `wizard-structure.json`) is a non-breaking change — just update the merge logic in `request.ts`.
