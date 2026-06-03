# apps/api — Implementation Agent

Du arbeitest im **Service Layer** von Narrare. Hier lebt die Business-Logik.

**Lies zuerst:**
- `../../docs/agents/_shared/CONSTRAINTS.md`
- `../../docs/agents/implementation/CODING_STANDARDS.md`
- `../../docs/agents/implementation/AGENT.md`

---

## Deine Rolle hier

Du implementierst Features die der Architecture Agent spezifiziert hat.
Du schreibst **keinen Code ohne vorhandenen Contract** (Protocol in `contracts.py`).
Du schreibst **immer Tests** zur Implementation.

---

## Modul-Struktur (jedes Domain-Modul gleich aufgebaut)

```
{domain}/
├── contracts.py    ← Protocol-Definitionen (ZUERST schreiben)
├── schemas.py      ← Pydantic Request/Response-Modelle
├── models.py       ← SQLAlchemy ORM-Modelle
├── repository.py   ← DB-Queries (nur hier SQLAlchemy)
├── service.py      ← Business-Logik (kein SQL, kein HTTP)
└── router.py       ← FastAPI-Routes (delegiert sofort an Service)
```

**Wenn ein Service > 300 Zeilen wird:** aufteilen in `{name}_service.py` Dateien.
**Wenn ein Router > 150 Zeilen wird:** aufteilen in `router_{group}.py` Dateien.

---

## LLM-Calls — Agents-First (neues Pattern)

Services rufen Agents auf, nicht LLMs direkt. Model kommt aus ModelRegistry.

```python
# ✅ Korrekt: Agent aus narrare_core.agents, Model aus ModelRegistry
from narrare_core.agents.summary_agent import ChapterSummaryAgent, SummaryDeps
from narrare_core.llm.gateway import ModelRegistry

class ChapterSummaryService:
    def __init__(
        self,
        registry: ModelRegistry,
        config: ResolvedModelConfig,
        chapter_repo: ChapterRepository,
    ) -> None:
        self._registry = registry
        self._config = config
        self._chapter_repo = chapter_repo

    async def summarize(self, chapter_id: UUID) -> SummaryResult:
        chapter = await self._chapter_repo.get(chapter_id)
        model = await self._registry.get_model(self._config)
        agent = ChapterSummaryAgent(model=model)
        deps = SummaryDeps(language="en", chapter_title=chapter.title)
        result = await agent.run(
            prompt=f"Summarize {chapter.content}",
            deps=deps,
        )
        return SummaryResult(summary=result.summary)

# ❌ Verboten: direkter LLM-Import
import openai  # RULE-01 Verletzung → CI schlägt fehl

# ❌ Verboten: Prompt-Bau im Service (RULE-02/RULE-02a)
#
#     Anpassbare Feature-Prompts → core/prompts/ + PromptComposer cascade
#     Garantierte Meta-/Universal-Regeln → ADR-026 Capabilities
#     Dynamische Agent-Instructions → @agent.instructions in core/agents/
#
#     Services dürfen nur Laufzeit-Input an agent.run(prompt=...) übergeben
#     (z. B. Textinhalt oder Nutzeranfrage), aber keine System-/Task-
#     Anweisungen, Rollen oder Prompt-Templates als Inline-String bauen.
```

**Pattern-Zusammenfassung:**
1. Service injected `ModelRegistry` + `ResolvedModelConfig` (from routing)
2. `model = await registry.get_model(config)` — holt LLM-Modell
3. `agent = SomeNarrareAgent(model=model)` — instantiiert Agent
4. `deps = SomeDeps(...)` — baut Dependencies für den Agent
5. `result = await agent.run(prompt=..., deps=deps)` — führt Agent aus
6. Agent returned strukturiertes `OutputT` (Pydantic-Modell)

---

## Repository-Pattern

```python
# ✅ Korrekt: Repository hat nur DB-Queries
class ChapterRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, chapter_id: UUID) -> Chapter | None:
        result = await self._session.execute(
            select(Chapter).where(Chapter.id == chapter_id)
        )
        return result.scalar_one_or_none()

# ❌ Verboten: SQLAlchemy direkt im Service
class ChapterService:
    async def get(self, id: UUID) -> Chapter:
        result = await self._session.execute(...)  # Nur im Repository!
```

---

## Error Handling (RULE-11)

```python
# ✅ Korrekt
try:
    model = await self._registry.get_model(self._config)
    agent = ChapterSummaryAgent(model=model)
    result = await agent.run(prompt=prompt, deps=deps)
except NotFoundError:
    raise
except Exception as exc:
    logger.error("operation_failed", error=str(exc), exc_info=True)
    raise WritingError("Operation failed") from exc

# ❌ Verboten: stille Fehler
try:
    result = await something()
except Exception:
    pass  # RULE-11 Verletzung → CI schlägt fehl
```

---

## FastAPI Dependency Injection

```python
# router.py — thin, delegiert sofort
@router.post("/chapters/{id}/write")
async def write_chapter(
    chapter_id: UUID,
    request: WriteChapterRequest,
    service: ChapterWritingService = Depends(get_chapter_writing_service),
) -> ChapterDraftResponse:
    result = await service.write(chapter_id=chapter_id, request=request)
    return ChapterDraftResponse.model_validate(result)
# Keine Business-Logik hier. Fertig.
```

---

## Beim Abschluss einer Session

Berichte:
```
✅ Implementiert: [Methoden-Liste]
✅ Tests: [Test-Dateien]
⏳ Offen: [was noch fehlt, warum]
🔴 Blockiert: [was fehlt bevor weitergemacht werden kann]
```
