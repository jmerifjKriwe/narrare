## Context

Narrare MVP Phases 0-4 sind implementiert. Die Codebase umfasst:
- `packages/core/` — LLM Gateway (6 Provider), Prompt System, Shared Utils
- `apps/api/` — FastAPI mit auth, novels, chapters, volumes, settings, setup, metrics
- `packages/web/` — Next.js 15 mit TipTap v3 Editor, Setup Wizard, Dashboard
- `tests/` — 28 Unit-Test-Files, 7 Integration-Test-Files, 101 Frontend-Tests
- `tests/e2e/` — existiert, aber leer (nur `__init__.py`)

Knowledge Graph Analyse zeigt 20 untested hotspots (höchster Degree: 133 für Alembic upgrade). Settings-Modul hat keine Unit Tests (nur Integration). Frontend hat 22 Komponenten-Files, aber nur 6 Test-Files (27% Abdeckung). Architecture Questions (Q-001 bis Q-004) sind teilweise stale — Q-004 wurde via ADR-007 resolved aber nie im Question-File aktualisiert.

Constraints: Keine echten LLM-Tokens für Tests. Keine Änderungen an produktivem Code — nur Tests und Docs. Post-MVP-Features (SSE streaming, KB editor, AI analysis) bleiben Post-MVP.

## Goals / Non-Goals

**Goals:**
- Playwright E2E Infrastruktur aufsetzen mit CI-Integration
- Hero E2E Flow testen: signup → wizard → demo → editor → autosave (LLM gemockt)
- Backend Testlücken schließen: Settings, Seed, DemoLoader, Gateway Hotspots
- Frontend Testlücken schließen: Editor, Setup Wizard, Dashboard, Shared Components
- Documentation aufräumen: Questions, CURRENT_STATE, testing-standards, README, CHANGELOG
- v0.1.0 Release readiness herstellen

**Non-Goals:**
- Keine Änderungen an produktivem Backend- oder Frontend-Code
- Keine AI-Features (SSE Streaming, Writing Sessions, Analysis Panels)
- Keine Embedding/pgvector-Integration
- Keine KB Editor UI
- Kein Refactoring der Settings-Modul-Architektur (post-MVP)
- Kein Testing von Third-Party Internals (TipTap, Radix, ProseMirror)
- Keine visuellen Regression-Tests oder Screenshot-Tests

## Decisions

### DEC-1: Playwright E2E mit route.fulfill() statt Backend Test-Mode

**Entscheidung:** LLM-Provider-Responses werden auf Playwright-Ebene via `route.fulfill()` gemockt.

**Alternative betrachtet:** Backend `NARRARE_TEST_MODE` Flag das FakeLLMGateway injiziert.

**Begründung:** Sauberere Trennung — Backend-Code bleibt produktionsidentisch, Mocking passiert an der Netzwerkgrenze. Vermeidet Test-Infrastruktur im Produktivcode. Einfacher zu warten — Mock-Definitionen liegen bei den Tests, nicht im Application Code.

### DEC-2: Ein Hero E2E Test statt vieler isolierter Flows

**Entscheidung:** Ein durchgehender Test der den kompletten User-Pfad abdeckt, statt separater Tests für jeden Flow.

**Alternative betrachtet:** Separat tests für login, settings, wizard, editor.

**Begründung:** Der MVP hat genau einen kritischen Pfad. Ein Hero Test validiert die Integration aller Teile. Reduziert Setup-Komplexität (ein Test-Context, keine Fixture-Duplikation). Einzelne Flows werden durch Unit/Integration-Tests abgedeckt.

### DEC-3: Frontend Test-Priorisierung nach Risiko

**Entscheidung:** Tests priorisieren nach: eigene Logik (Autosave, Chapter-Switch) > Integration (Wizard Navigation, Dashboard Rendering) > Shell-Komponenten (ContextPanel, Toolbar).

**Begründung:** EditorSurface (Autosave-Debounce, Word Count) und ChapterSidebar (Chapter-Switch) enthalten unsere kritischste Logik. Setup Wizard ist der Onboarding-Pfad — muss funktionieren. ContextPanel und EditorToolbar sind leere Shells — Tests hätten keinen Wert.

### DEC-4: Architecture Questions als Docs-Only Cleanup

**Entscheidung:** Q-001 bis Q-004 werden dokumentatorisch aufgeräumt (Status-Updates, Link-Korrekturen) ohne inhaltliche Entscheidungen zu treffen.

**Begründung:** Q-001 (MCP auth), Q-002 (A2A streaming), Q-003 (Embedding abstraction) sind alle post-MVP. Q-004 ist resolved (→ TaskIQ). Keine dieser Fragen blockiert Phase 5. Aufräumen verhindert Verwirrung in zukünftigen Sessions.

## Risks / Trade-offs

- **[Playwright Setup-Komplexität]** → Erster E2E-Test-Setup ist aufwändig (Docker-Services, Fixtures, Mock-Definitionen). Mitigation: Playwright config konservativ halten, erst mal nur Chromium, keine Parallelisierung im E2E.

- **[Editor-Komponenten-Testbarkeit]** → TipTap ist ein komplexer Editor — Tests müssen TipTap rendern um unsere Autosave-Logik zu testen. Das kann flaky werden. Mitigation: Bei EditorSurface-Tests auf MSW für API-Intercept setzen statt echtes Editor-Rendering zu erzwingen. Ggf. nur die Hook/Utility-Funktionen testen die Autosave steuern.

- **[Settings-Modul hat keinen Service-Layer]** → Settings geht direkt vom Router zum Repository (bricht RULE-03 Contract-First). Mitigation: Im Rahmen von Phase 5 nur Tests schreiben, kein Refactoring. Als Post-MVP-TODO dokumentieren.

- **[CI-Laufzeit]** → Playwright-Tests + zusätzliche Unit/Integration-Tests erhöhen CI-Zeit. Mitigation: E2E nur auf main branch. Frontend-Tests laufen parallel via Vitest. Backend-Tests via xdist.
