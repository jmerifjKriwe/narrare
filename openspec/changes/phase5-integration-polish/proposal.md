## Why

Phases 0-4 haben das MVP-Fundament gebaut: Repository-Struktur, Core-Infrastruktur, API, Setup Wizard, und Frontend mit Editor. Phase 5 ist der Abschluss — Integration, Test-Abdeckung, und Polish — damit `v0.1.0` getaggt werden kann. Aktuell gibt es keine E2E-Tests, signifikante Testlücken in Backend und Frontend, und mehrere Dokumentations-Inkonsistenzen (stale Architecture Questions, CURRENT_STATE driftet in Post-MVP Scope).

## What Changes

- **Playwright E2E Infrastruktur:** Setup von Playwright mit Config, Fixtures, und CI-Integration. Keine echten LLM-Tokens — Provider-Responses werden via `route.fulfill()` gemockt.
- **Hero E2E Flow:** Ein durchgehender Test: signup → wizard → demo content → editor → autosave. Abdeckt wird der kritischste User-Pfad des MVP.
- **Backend Testlücken schließen:** Unit Tests für Settings, Integration Tests für seed()/DemoLoader, Absicherung der untested hotspots (gateway._classify_error, retry.with_retry, etc.).
- **Frontend Testlücken schließen:** Tests für Editor-Komponenten (Autosave, Word Count, Chapter-Switch), Setup Wizard (Form-Flow, Validation, Navigation), DashboardView, StatusBar, ErrorBoundary. Kein Test von Third-Party Internals (TipTap, Radix).
- **Dokumentation aufräumen:** Q-001-to-Q-004.md aktualisieren (Q-004 als resolved, Q-003 als post-MVP), INDEX.md Links korrigieren, CURRENT_STATE "Next Session" klar als Post-MVP markieren, testing-standards.md E2E-Sektion korrigieren (kein "real LLM"), README mit Setup-Instructions, CHANGELOG v0.1.0 Eintrag.

## Capabilities

### New Capabilities

- `e2e-playwright`: Playwright E2E Test-Infrastruktur, Fixtures, CI-Integration, Hero Flow Test mit gemockten LLM-Responses
- `test-coverage-gaps`: Backend Unit/Integration Tests für untested hotspots + Frontend Komponenten-Tests für Editor, Setup Wizard, Dashboard, und Shared Components
- `docs-polish-phase5`: Aufräumen der Architecture Questions, Korrektur von CURRENT_STATE, README und CHANGELOG für v0.1.0

### Modified Capabilities

_(keine existierenden Specs betroffen)_

## Impact

- **Tests:** Neues Verzeichnis `tests/e2e/` mit Playwright-Infrastruktur. Neue Unit/Integration-Tests in `tests/unit/` und `tests/integration/`. Neue Frontend-Tests in `packages/web/`.
- **CI:** `ci.yml` muss Playwright-Tests unterstützen (nur main branch).
- **Dokumentation:** `docs/architecture/questions/`, `docs/_shared/CURRENT_STATE.md`, `docs/development/testing-standards.md`, `README.md`, `CHANGELOG.md`.
- **Dependencies:** `playwright` als dev-Dependency, ggf. `@playwright/test` im Frontend.
- **Keine Änderungen** an produktivem Backend- oder Frontend-Code. Nur Tests und Docs.
