# Frontend Integration Tests

> **Status**: Noch nicht implementiert — Unit-Tests + E2E bevorzugt

## Warum kein separater Integration-Tests-Ordner?

Narrare verwendet für das Frontend einen vereinfachten Test-Stack:

| Test-Typ | Ort | Zweck |
|----------|-----|-------|
| **Unit-Tests** | `packages/web/**/*.test.tsx` | Komponenten, Hooks, Utils isoliert testen |
| **E2E-Tests** | Noch nicht vorhanden | Vollständige User-Journeys via Playwright |

### Begründung

1. **Keine Backend-Interaktion**: Frontend-Tests mocken die API komplett via MSW (`packages/web/mocks/`). Es gibt keine echte DB/Redis-Verbindung.

2. **TanStack Query übernimmt Integration**: Die React Query Layer ist der einzige "Integration Point" — und die wird bereits in Unit-Tests mit gemockten Handlern abgedeckt.

3. **E2E deckt echte Integration ab**: Wenn E2E-Tests (Playwright) hinzukommen, testen sie die vollständige Integration Frontend ↔ Backend ↔ DB.

4. **Keine doppelte Test-Schicht**: Separate Integration-Tests (die z.B. eine echte DB starten) würden dieselben Pfade wie E2E-Tests abdecken — Redundanz.

## Wann wäre ein Integration-Tests-Ordner sinnvoll?

Falls das Projekt wächst und folgende Bedürfnisse entstehen:

- **Partielle Integration**: Bestimmte Flows ohne vollen E2E-Setup testen (z.B. mit einer Test-DB)
- **Performance-Tests**: Langsame Queries ohne UI messen
- **Contract-Tests**: API-Response-Shapes gegen Schemas validieren

In diesem Fall würde ein Ordner wie `tests/integration/frontend/` mit Playwright-Tests oder pytest-Tests für API-Integration entstehen.

## Aktueller Stand

- **197 Unit-Tests** in `packages/web/` — alle bestehend
- **0 E2E-Tests** — TODO: Playwright einrichten
- **0 Frontend-Integration-Tests** — bewusst nicht nötig aktuell

Siehe auch:
- `packages/web/setupTests.ts` — Test-Setup und globale Mocks
- `docs/development/testing-standards.md` — Test-Strategie
