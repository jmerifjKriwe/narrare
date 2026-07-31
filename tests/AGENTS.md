# tests/ — Testing Agent

Du schreibst Tests für Narrare. Dein Ziel: jedes Verhalten ist beweisbar korrekt.

> **SSOT Notice:** All architecture rules are defined in `docs/_shared/CONSTRAINTS.md`.
> This file provides testing-specific context — it does NOT redefine or relax any
> RULE-XX. See CONSTRAINTS.md §8 for the full SSOT hierarchy.

**Lies zuerst:**
- `docs/development/testing-standards.md`
- `docs/_shared/CONSTRAINTS.md`

**Verfügbare Skills:**
- `/narrare-testing` — Für Test-Strategie und Test-Schreiben
- `/check-constraints` — Für Constraint-Prüfung

---

## Test-Ebenen

```
tests/
├── unit/        ← Schnell (<5s gesamt), kein I/O, kein DB, kein LLM
├── integration/ ← Echte DB (postgres_test:5433), gemockter LLM
└── e2e/         ← Vollständig, nur auf main branch CI
```

**Faustregel:** Teste auf der niedrigsten Ebene wo es sinnvoll ist.

---

## Was immer getestet wird

Für jede public Service-Methode:
1. **Happy path** — korrekter Input, erwarteter Output
2. **Domain error** — ungültiger Input, korrekte Exception
3. **Edge case** — mindestens eine Grenzwertbedingung

Für jeden Router-Endpoint:
1. `200/201` mit korrektem Response-Schema
2. `401` wenn Auth fehlt
3. `404` für nicht existierende Ressourcen
4. `422` für ungültige Inputs

---

## LLM mocken (immer in Unit Tests)

**Standard ist Fake-basiert, nicht MagicMock** (ADR-030). Domain-Dependencies
(LLMGateway, Repositories, Services) bekommen eine echte Fake-Implementierung
aus `tests/fakes/`. `MagicMock(spec=...)` ist **nur** für Nicht-Domain-
Infrastruktur erlaubt (z. B. reine Wert-Container ohne Verhalten).

```python
# tests/fakes/fake_llm_gateway.py ist der Kanon — bevorzugt für neue Tests.
# Für pydantic-ai-Agent-Tests gibt es zusätzlich tests/fakes/fake_pydantic_agent.py.
from tests.fakes.fake_llm_gateway import FakeLLMGateway


@pytest.fixture
def fake_gateway() -> FakeLLMGateway:
    gateway = FakeLLMGateway()
    gateway.returns("Generated text.", model="claude-haiku")
    return gateway
```

`FakeLLMGateway` zeichnet Calls auf (`gateway.calls`), lässt sich über
`.returns()` / `.returns_stream()` / `.raises()` konfigurieren und
implementiert das echte `LLMGateway`-Protokoll — kein verhaltensbasierter
MagicMock, der bei Refactors silently green wird.

**Niemals** einen echten LLM-Call in Unit Tests. Nie.

---

## DB in Integration Tests

**Schema entsteht ausschließlich über echte Alembic-Migrationen** (RULE-14).
`Base.metadata.create_all()` ist in Integration-Tests **verboten** — es
würde das Migrations-Setup umgehen und Maskierungen von Migrationsfehlern
erlauben. Das session-scierte Setup in `tests/integration/conftest.py`
führt `alembic upgrade head` einmal pro Session via Subprocess aus
(idempotent, läuft in CI vor den Tests durch).

```python
# Fixture-Nutzung (Pattern aus tests/integration/conftest.py):
# - Session wird pro Test bezogen, nicht pro Modul.
# - Jeder Test läuft in einer Transaction, die am Ende zurückgerollt wird
#   → Isolation ohne create_all().
@pytest.fixture
async def db_session(db_session_factory):
    """Rolled-back session — isoliert jeden Test."""
    async with db_session_factory() as session:
        yield session
        await session.rollback()
```

Das zugrundeliegende Engine-/Migration-Setup liegt in
`tests/integration/conftest.py` (`alembic upgrade head` per Subprocess,
weil `alembic/env.py` asyncio.run nutzt). Neue Fixtures sollten dieses
Pattern wiederverwenden, nicht ihr eigenes Schema aufbauen.

---

## Test-Benennung

```python
# Format: test_{was}_{bedingung}_{erwartetes_ergebnis}
def test_write_chapter_with_valid_request_returns_draft(): ...
def test_write_chapter_when_llm_fails_raises_writing_error(): ...
def test_gateway_run_with_rate_limit_retries_three_times(): ...
```

---

## Coverage-Ziele

| Bereich | Minimum | Ziel |
|---------|---------|------|
| `core/llm/` | 95% | 100% |
| `core/prompts/` | 95% | 100% |
| `core/shared/` | 90% | 95% |
| `apps/api/*/service.py` | 85% | 90% |
| `apps/api/*/repository.py` | 80% | 90% |
| `apps/api/*/router*.py` | 80% | 85% |

Coverage unter Minimum = CI-Fehler.

---

## Architecture-Constraint Enforcement

Architektur-Constraints (RULE-01b, 02, 04, 11, …) werden **nicht** über
einen pytest-Subprocess-Test durchgesetzt, sondern über zwei dedizierte
Gates — das ist robuster als ein Test, der `check_architecture.py` nur
als returncode-0-Assertion aufruft:

1. **Pre-commit-Hook** `architecture-constraints`
   (`.pre-commit-config.yaml`) — läuft pro Commit lokal.
2. **CI-Job** `architecture`
   (`.github/workflows/ci.yml`) — läuft blockierend pro Push/PR, inkl.
   Exception-Baseline-Sync gegen `CONSTRAINTS.md §7`.

```bash
# Lokaler Check vor dem Commit (das, was früher der subprocess-Test tat):
just check-architecture
```

Tests, die Architektur-Verhalten prüfen sollen, verwenden stattdessen
zielgerichtete Assertions (z. B. „dieses Modul importiert kein `openai`
direkt") über die echten Domain-Fakes, nicht einen Subprocess-Aufruf.

---

## Referenz-Dokumentation

| Thema | Datei |
|-------|-------|
| Architektur-Regeln | `docs/_shared/CONSTRAINTS.md` |
| Testing Standards | `docs/development/testing-standards.md` |
| Coding Standards | `docs/development/coding-standards.md` |

---

## Beim Abschluss einer Test-Session

```
Coverage vorher: writing/ → 62%
Coverage nachher: writing/ → 84%
Verbleibende Lücken: session_service.py Zeilen 145-180 (3 Methoden)
Schwache Tests: test_write_success prüft nur Status-Code (braucht Body-Assertion)
```
