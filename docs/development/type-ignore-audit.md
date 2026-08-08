# Type-Ignore Audit — Findings & Action Plan

> **Status:** ✅ Completed (revalidated 2026-06-29; ADR-080-Nachbehandlung 2026-08-08)
> **Audit-Datum:** 2026-06-10
> **Letzte Aktualisierung:** 2026-08-08 (ADR-080 — `tasks/broker.py` entfernt, `wiki/tasks.py`-Dependency korrigiert)
> **Scope:** Python `# type: ignore` und TypeScript `@ts-ignore` / `@ts-expect-error`
> **Ziel:** Systematische Reduktion auf 0 in Production-Code, strengere Agent-Vorgaben

---

## Executive Summary

Das Narrare-Projekt hatte **887 `# type: ignore`** Einträge in Python-Dateien (Stand 2026-06-10).
Nach der vollständigen Sanierung (Phasen 1–5) und anschließender Feature-Arbeit:

| Bereich | Vorher | Nachher (2026-06-11) | Aktuell (2026-06-29) | Veränderung |
|---------|--------|----------------------|---------------------|-------------|
| Production (`apps/api/narrare/` + `packages/core/`) | ~180 | **16** | **25** | −155 seit Baseline, +9 durch neue Features |
| Tests (`tests/`) | ~700 | **176** | **~488** | −212 seit Baseline, +312 durch neue Tests |
| Other (Scripts, fakes) | ~7 | **11** | **~11** | stabil |
| TypeScript (`@ts-ignore`/`@ts-expect-error`) | ~1 | **0** | **0** | ✅ unverändert |
| **Total** | **~887** | **203** | **~524** | **✅ −363 seit Baseline** |

**Kernerkenntnis:** `# type: ignore` wurde zu oft als "Quick Fix" von AI Agents vergeben,
anstatt die Root Cause zu beheben. Die aktuellen 25 Production-Einträge sind:
- **25 Production:** überwiegend Drittanbieter ohne Type-Stubs (mem0, pgvector, opentelemetry,
  structlog) plus wenige defensive Runtime-Checks. *(Hinweis: `taskiq`/`redis` waren vor ADR-080
  in dieser Liste; ADR-080 (2026-08-07) entfernte beide Dependencies, sodass deren
  Production-Suppressions entfallen sind.)* Neue Einträge seit der
  Baseline stammen aus ANAL-008 (character_voice_service), CR-AUFG-07-22 (style_variant_service),
  ADR-054 (writing/ws_draft_dispatch) und weiteren Feature-Arbeiten — alle mit Error-Code und
  Reason-Kommentar (RULE-23 konform).
- **~488 Tests:** mit `cast()`-Pattern oder Reason-Kommentar. Anstieg durch neue Testdateien
  für Phase-6-Features (ANAL-005, ANAL-008, WRITE-009, PLAN-006, INFRA-007, u.a.).
- **11 Other:** Baseline-Scripts
- **0 naked ignores:** alle mit Error-Code und Reason-Kommentar

---

## Kategorisierung der Fundstellen

### Kategorie A: Ungetypte Drittanbieter-Pakete (LEGITIM)

Diese `# type: ignore` sind akzeptabel, solange keine Type Stubs existieren:

| Paket | Typ | Count (geschätzt) |
|-------|-----|-------------------|
| `mem0` | `import-untyped`, `reportMissingTypeStubs` | ~12 |
| `redis.asyncio` | `import-untyped` | ~4 |
| `opentelemetry.*` | `import-untyped`, `reportUnknownVariableType` | ~6 |
| `bcrypt` | `import-untyped` | ~2 |
| `TaskIQ` | `attr-defined` | ~6 |

**Richtlinie:** Diese Suppressions sind dokumentiert pro Datei.
**Aber:** Auch hier könnte man `types-*` Stub-Pakete prüfen oder eigene `.pyi`-Stubs schreiben
für stark genutzte APIs (z. B. mem0 `AsyncMemory`).

### Kategorie B: Fehlende Typannotationen (PROBLEMATISCH)

Pyright in `strict`-Mode moniert, weil Typinformation fehlt oder nicht präzise genug ist:

| Code | Problem | Beispiele |
|------|---------|-----------|
| `reportUnknownVariableType` | Variable hat `Any`-Typ | `name_service.py:169`, `mem0_client.py` |
| `reportUnknownMemberType` | Zugriff auf unbekanntes Member | `mem0_client.py` |
| `reportUnknownArgumentType` | Argument vom Typ `Unknown` | `name_service.py:196-198` |
| `reportMissingTypeStubs` | Fehlende `.pyi`-Stubs | `telemetry.py`, `dependencies.py` |

**Root Cause:** AI Agents rufen `json.loads()` oder andere `Any`-rückgebende Funktionen auf
und annotieren das Ergebnis nicht mit einem konkreten Typ. Statt:
```python
raw = json.loads(cleaned)  # type: ignore[reportUnknownVariableType]
```
Muss es heißen:
```python
raw: dict[str, Any] = json.loads(cleaned)
```

### Kategorie C: Fehlerhafte Argument-Typen (ARG-TYPE / CALL-ARG)

`# type: ignore[arg-type]` und `# type: ignore[call-arg]` werden verwendet,
wenn tatsächlich falsche oder unpassende Argumente übergeben werden:

**Production-Code (kritisch):**
- `kb/dependencies.py` (3x): `ProactiveContextService(embedding_store=embedding_service)` —
  Typkonflikt zwischen EmbeddingServiceProtocol und dem tatsächlichen service-Objekt
- `token_limits/service.py` (8x): `kwargs.get("output_limit", base.output_limit)` —
  Default-Typ passt nicht zum erwarteten Feld-Typ
- `custom_tone_service.py` (4x): `UpdateUserSettingsRequest(custom_tones=...)` —
  wrong keyword arguments
- `evidence/repository.py` (2x): type mismatch zwischen Domain-Modell und DB-Modell

**Tests (sehr häufig):**
- Muster: `Service(repo=FakeRepo())  # type: ignore[arg-type]`
- Root Cause: Fakes implementieren nicht das korrekte Protocol, oder das Protocol
  erwartet exakt den konkreten Typ statt des Protocols

### Kategorie D: Union-Narrowing (PROBLEMATISCH)

`# type: ignore[union-attr]` und `# type: ignore[assignment]`:

- `event_listener.py` (7x): Redis pubsub-Zugriffe ohne Type Narrowing
- `session_mapper.py`: `current = nested  # type: ignore[assignment]`
- `chapters/repository.py`: `return result.rowcount  # type: ignore[union-attr]`

**Root Cause:** Fehlende Type Guards / `isinstance()`-Checks vor dem Zugriff auf
Union-Typen. AI Agents supprimieren statt korrektes Narrowing einzubauen.

### Kategorie E: MagicMock in Tests (PYRIGHT-LIMITATION)

Tests verwenden `MagicMock` / `AsyncMock` und pyright kann deren Typ nicht auflösen:

```python
service = SceneService(repo=_FakeRepo())  # type: ignore[arg-type]
```

Aktuell ist pyright für `tests/` bereits gelockert:
```toml
reportUnknownMemberType = false
reportUnknownVariableType = false
```

**Trotzdem gibt es hunderte arg-type Suppressions in Tests.** Das deutet darauf hin,
dass Fakes/Stubs die Protocols nicht korrekt implementieren, oder dass Services
konkrete Typen statt Protocols als Parameter erwarten.

---

## Root-Cause-Analyse

### Warum passiert das?

1. **AI Agents nehmen den einfachsten Weg.** `# type: ignore` ist ein einziger Kommentar,
   während die Root-Cause-Fix oft 3-5 Zeilen Typannotation, ein neues Protocol oder
   einen Type Guard erfordert.

2. **Es gibt keine Regel gegen `# type: ignore`.** Kein RULE-XX verbietet es.
   Kein CI-Gate prüft auf Suppressions. Kein Standard definiert, wann `type: ignore`
   akzeptabel ist und wann nicht.

3. **Tests werden weniger streng auditiert.** Die pyright-Lockerungen für Tests
   (`reportUnknownMemberType = false`) suggerieren, dass Typ-Korrektheit in Tests
   weniger wichtig sei — aber hunderte `arg-type`-Suppressions sind kein "Type Inference
   Problem" sondern ein "Interface Mismatch" Problem.

4. **`reportUnknown*Type` erzeugt akustische Täuschung.** Weil pyright in `strict`-Mode
   läuft, moniert es viele `Unknown`-Typen. Statt die Quelle des `Unknown` zu fixieren
   (z. B. `json.loads()`-Rückgabe annotieren), wird die Warnung unterdrückt.

### Warum ist das ein Problem?

- **Jede `type: ignore` ist ein Blindflug.** Pyright kann diesen Code nicht mehr prüfen.
- **Fehler werden versteckt.** Ein Refactoring, das einen echten Typfehler einführt,
   wird nicht gefangen, weil die Suppression den gesamten Ausdruck maskiert.
- **Code-Qualität sinkt.** `# type: ignore` erlaubt es, unsaubere Interfaces,
   fehlende Protocols und falsche Abstraktionen zu kaschieren.
- **Neue Agents lernen das falsche Pattern.** Wenn Agents `type: ignore` im Code sehen,
   wiederholen sie das Muster bei neuen Aufgaben.

---

## Action Items

### Phase 1: Sofort (Vorgaben verschärfen) ✅

- [x] **P1-A: RULE-23 in CONSTRAINTS.md** — `# type: ignore` verboten ohne Error-Code,
  arg-type/call-arg für Mocks verboten, Reason-Kommentar-Pflicht, production nur für
  untyped third-party

- [x] **P1-B: AI Agent Guideline verschärft** — RULE-23 ist fester Bestandteil aller
  Narrare-Specialist-Delegation-Prompts

- [x] **P1-C: CI-Gate implementiert** — `python -m scripts.check_type_ignores` prüft:
  Baseline-Vergleich, naked ignores, uncommented production, Reason-Kommentar-Konformität

### Phase 2: Production-Code sanieren (Hochprioritär)

- [x] **P2-A–P2-J:** Alle ~180 Production-Suppressions eliminiert
- [x] **Verbleibend: 16 legitime Einträge** — alles Drittanbieter ohne Type-Stubs:
  - `mem0_client.py` (2): mem0
  - `embeddings/models.py` (2): pgvector
  - `telemetry.py` (3): opentelemetry
  - `auth/security.py` (2): python-jose
  - `generation/graph_store.py` (2): networkx
  - `runtime.py` (1): defensive check
  - `wiki/tasks.py` (1): taskiq
  - `dependencies.py` (1): structlog
  - `user_ai_settings_service.py` (1): structlog
  - `events.py` (1): structlog

### Phase 3: Tests sanieren (Hochprioritär) ✅

- [x] **P3-A: `cast()`-Pattern konsequent eingesetzt** — `cast("ExpectedType", wert)` als Standard
- [x] **P3-B: Alle Top-Offender behoben (Batch 1 + 2):**
  - `test_embedding_hooks.py` (23 → 0)
  - `test_apply_extraction_advanced.py` (20 → 0)
  - `test_coauthor_apply_service.py` (21 → 0)
  - `test_chat_service_history.py` (16 → 0)
  - `test_kb_metadata.py` (13 → 0)
  - `test_observability.py` (13+13 → 0)
  - `test_setting_schema.py` (13 → 0)
  - `test_temporal.py` (12 → 0)
  - `test_cache_metrics.py` (12 → 0)
  - `test_kb_improve_analyzer.py` (22 → 0)
  - `test_ws_handler.py` (12 → 0)
  - `test_coauthor_feedback_service.py` (11 → 0)
  - + alle weiteren Top-Dateien
- [x] **Gesamt: ~524 Test-Suppressions eliminiert**, 176 verbleiben (je 1–8, überwiegend `import-untyped`)

### Phase 4: TypeScript prüfen ✅

- [x] **P4-A:** Keine `@ts-ignore` / `@ts-expect-error` im Frontend (`packages/web/src/`) gefunden

### Phase 5: Monitoring ✅

- [x] **P5-A:** Baseline via `python -m scripts.check_type_ignores --update` erzeugt (203 Suppressions, Stand 2026-06-11)
- [x] **P5-B:** CI-Gate integriert — schlägt fehl bei nackten `type:ignore` oder unkommentierten Production-Einträgen
- [x] **P5-C:** RULE-23 verlangt Reason-Kommentar-Pflicht; Budget 0 für neue Module

---

## Guidelines für AI Agents

### Für NarrareCoreSpecialist & NarrareBackendSpecialist

```markdown
## Type-Ignore Policy (MANDATORY)

### Erlaubt (mit Dokumentation)
- `# type: ignore[import-untyped]` für **untyped third-party packages** ohne Stubs
  → MUSS comment reason haben: `# type: ignore[import-untyped]  # no stubs for <package>`
- `# type: ignore[attr-defined]` für **dynamische Attribute** auf untyped Objekten
  → MUSS dokumentieren, welches externe Paket keinen Typ hat

### Verboten (außer mit explizitem User-OK)
- `# type: ignore` **ohne Error-Code** (nacktes `# type: ignore`) — STRICTLY FORBIDDEN
- `# type: ignore[arg-type]` für Mocks/Fakes — stattdessen Protocol implementieren
- `# type: ignore[assignment]` — stattdessen Typannotation korrigieren
- `# type: ignore[union-attr]` — stattdessen Type Guard / isinstance() einbauen
- `# type: ignore[call-arg]` — stattdessen korrekte Parameter übergeben
- `# type: ignore[return-value]` — stattdessen korrekten Rückgabetyp verwenden

### Alternative zu `# type: ignore`
Vor dem Setzen einer Suppression MÜSSEN mindestens 2 dieser Alternativen versucht werden:

1. `cast(Typ, wert)` — wenn du sicher bist, dass der Typ korrekt ist, pyright aber nicht
2. Type Guard / `isinstance(wert, Typ)` — für Union-Narrowing
3. Typannotation hinzufügen — `variable: KonkreterTyp = ...`
4. Protocol implementieren — `class FakeRepo(RepoProtocol):`
5. `# type: ignore[code]` mit Reason — **letzte Wahl, dokumentiert**
```

### Für NarrarePlatformSpecialist (CI/Quality Gates)

```markdown
## Quality Gate: Type-Ignore Count

- `scripts/check_type_ignores/` package — CLI via `uv run python -m scripts.check_type_ignores`
- Prüft: Anzahl `# type: ignore` pro Datei gegen Baseline
- Error: Anstieg über Baseline (ratchet — nur Reduktion erlaubt)
- Error: Neues `# type: ignore` in production code ohne Reason-Kommentar
- Fail: `# type: ignore` ohne Error-Code (naked ignore)
- Baseline aktualisieren: `uv run python -m scripts.check_type_ignores --update`
```

---

## Baseline-Count pro Datei (Stand 2026-06-29)

### Production — 25 Suppressions (legitime third-party + defensive checks)

> **Snapshot-Hinweis:** Diese Tabelle ist der Stand **2026-06-29 (vor ADR-080)**.
> ADR-080 (2026-08-07) entfernte `taskiq`/`redis` als Dependencies. Die Zeile
> `apps/api/narrare/tasks/broker.py` (1 × taskiq) ist daher **Phantom** — die
> Datei wurde gelöscht und ist hier entfernt. `wiki/tasks.py` führt weiterhin
> 1 Eintrag, aber post-ADR-080 wegen pyright-TYPE_CHECKING-Narrowing
> (`attr-defined`), **nicht** mehr wegen taskiq. Autoritativ für CI ist die
> JSON-Baseline (`scripts/architecture/type-ignore-baseline.json`,
> regenerierbar via `uv run python -m scripts.check_type_ignores --update`),
> nicht diese manuelle Markdown-Snapshot-Tabelle.

| Datei | Ignore Count | Dependency |
|-------|-------------|------------|
| `apps/api/narrare/_app/events.py` | 1 | structlog |
| `apps/api/narrare/_app/middleware.py` | 2 | FastAPI duck-typing |
| `apps/api/narrare/_app/telemetry.py` | 3 | opentelemetry |
| `apps/api/narrare/analysis/character_voice_service.py` | 1 | pyright narrowing (ANAL-008) |
| `apps/api/narrare/auth/security.py` | 2 | python-jose/bcrypt |
| `apps/api/narrare/embeddings/models.py` | 2 | pgvector |
| `apps/api/narrare/generation/graph_store.py` | 2 | networkx |
| `apps/api/narrare/prompts/deps.py` | 1 | pyright DI narrowing |
| `apps/api/narrare/settings/user_ai_settings_service.py` | 1 | structlog |
| `apps/api/narrare/wiki/tasks.py` | 1 | pyright TYPE_CHECKING narrowing (post-ADR-080; vormals taskiq) |
| `apps/api/narrare/writing/_ws_draft_dispatch.py` | 3 | ADR-054 pipeline DI |
| `packages/core/narrare_core/ai_invocation/validators/runtime.py` | 1 | defensiver Check |
| `packages/core/narrare_core/memory/mem0_client.py` | 2 | mem0 |
| `packages/core/narrare_core/memory/availability.py` | 1 | mem0 |
| `packages/core/narrare_core/writing/session_state_codec.py` | 1 | pyright narrowing |

### Tests — Top 10 (Stand 2026-06-29)

| Datei | Ignore Count |
|-------|-------------|
| `tests/unit/api/auth/test_auth_cookie.py` | 8 |
| `tests/unit/api/kb/test_relationship_service_deletion.py` | 4 |
| `tests/unit/api/kb/test_session_models.py` | 4 |
| `tests/unit/api/kb/_extraction_helpers.py` | 4 |
| `tests/unit/api/kb/_test_fakes.py` | 4 |
| `tests/unit/api/memory/test_memory_service.py` | 4 |
| `tests/unit/api/memory/test_analysis_service.py` | 4 |
| `tests/unit/core/llm/test_embeddings.py` | 4 |
| `tests/fakes/fake_memory_repos.py` | 4 |
| `tests/integration/kb/test_kb_embedding_hooks.py` | 4 |

---

## Anhang: Error-Codes und ihre Bedeutung

| Pyright Error-Code | Bedeutung | Typische Ursache |
|--------------------|-----------|------------------|
| `arg-type` | Argument-Typ passt nicht zum Parameter | Falscher Fake, falscher Service-Aufruf |
| `assignment` | Wert-Typ passt nicht zum Variablen-Typ | Variable umdeklariert, Union nicht aufgelöst |
| `attr-defined` | Zugriff auf nicht-existierendes Attribut | Untyped Dependency, dynamisches Attribut |
| `call-arg` | Falsche Argumente beim Aufruf | Missing/Extra Parameter |
| `union-attr` | Attribut existiert nicht auf allen Union-Membern | Fehlender Type Guard |
| `return-value` | Rückgabewert-Typ passt nicht zum deklarierten Typ | Fehlerhafte Rückgabe |
| `import-untyped` | Import hat keine Typinformation | Third-party ohne Stubs |
| `reportUnknownVariableType` | Variable hat `Unknown` Typ | `json.loads()`, `dict.get()` |
| `reportUnknownMemberType` | Member-Zugriff auf `Unknown` | Fehlende Annotation |
| `reportUnknownArgumentType` | Argument ist `Unknown` | `**kwargs` ohne Typ |
| `reportMissingTypeStubs` | Keine `.pyi`-Datei für Import | Third-party ohne Stubs |
| `type[abstract]` | Instantiierung einer abstrakten Klasse | Falsche Basisklasse |
| `no-redef` | Neu-Deklaration einer Variable | `x: A = ...; x: B = ...` |
| `method-assign` | Methode überschrieben (kein Property) | `obj.method = lambda ...` |
| `truthy-bool` | Immer-truthy Wert in boolean context | `if obj.attr:` auf non-Optional |
| `no-untyped-def` | Funktion ohne Typannotation | Fehlende Signature (veraltet) |
