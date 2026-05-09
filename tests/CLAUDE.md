# tests/ — Testing Agent

Du schreibst Tests für Narrare. Dein Ziel: jedes Verhalten ist beweisbar korrekt.

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

```python
# tests/conftest.py stellt MockLLMGateway bereit
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture
def mock_gateway() -> MagicMock:
    gateway = MagicMock(spec=LLMGateway)
    gateway.run = AsyncMock(return_value=LLMResult(
        text="Generated text.",
        usage=TokenUsage(prompt_tokens=10, completion_tokens=50, total_tokens=60),
        model="claude-haiku",
        intent="write",
    ))
    return gateway
```

**Niemals** einen echten LLM-Call in Unit Tests. Nie.

---

## DB in Integration Tests

```python
@pytest.fixture
async def db_session(db_engine):
    """Rolled-back session — isoliert jeden Test."""
    async with db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        async with AsyncSession(conn) as session:
            yield session
            await conn.rollback()
```

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

## Architecture-Constraint Test

Dieser Test läuft immer mit:

```python
# In tests/conftest.py bereits definiert
def test_architecture_constraints() -> None:
    """RULE-01, 02, 04, 11: Alle Architektur-Constraints bestehen."""
    result = subprocess.run(["python", "scripts/check_architecture.py"])
    assert result.returncode == 0
```

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
