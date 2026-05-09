# apps/api — Implementation Agent

Du arbeitest im **Service Layer** von Narrare. Hier lebt die Business-Logik.

**Lies zuerst:**
- `docs/_shared/CONSTRAINTS.md`
- `docs/development/coding-standards.md`

**Verfügbare Skills:**
- `/narrare-implementation` — Für Code-Implementierung
- `/narrare-testing` — Für Test-Schreiben
- `/check-constraints` — Für Constraint-Prüfung

---

## Deine Rolle hier

Du implementierst Features die vom Architecture Skill spezifiziert wurden.
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

## LLM-Calls: So und nicht anders

```python
# ✅ Korrekt: Gateway injiziert, Prompt aus Composer
class ChapterService:
    def __init__(self, gateway: LLMGateway, composer: PromptComposer) -> None:
        self._gateway = gateway
        self._composer = composer

    async def write(self, request: WriteRequest) -> WriteResult:
        ctx = PromptContext(language=request.language, mode="new_chapter", ...)
        prompt = await self._composer.build(LLMIntent.WRITE, ctx)
        result = await self._gateway.run(
            intent=LLMIntent.WRITE,
            system_prompt=prompt.system,
            user_prompt=prompt.user,
        )
        return WriteResult(content=result.text)

# ❌ Verboten: direkter LLM-Import
import openai  # RULE-01 Verletzung → CI schlägt fehl

# ❌ Verboten: f-String Prompt-Bau
system_prompt = f"You are a {role}..."  # RULE-02 Verletzung → CI schlägt fehl
```

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
    result = await self._gateway.run(...)
except LLMGatewayError as e:
    logger.error("chapter_write_failed", chapter_id=str(id), error=str(e))
    raise WritingError("Generation failed") from e

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

## Referenz-Dokumentation

| Thema | Datei |
|-------|-------|
| Architektur-Regeln | `docs/_shared/CONSTRAINTS.md` |
| Coding Standards | `docs/development/coding-standards.md` |
| Testing Standards | `docs/development/testing-standards.md` |

---

## Beim Abschluss einer Session

Berichte:
```
✅ Implementiert: [Methoden-Liste]
✅ Tests: [Test-Dateien]
⏳ Offen: [was noch fehlt, warum]
🔴 Blockiert: [was fehlt bevor weitergemacht werden kann]
```
