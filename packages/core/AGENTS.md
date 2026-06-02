# packages/core — Core Infrastructure

Du arbeitest im **Fundament** von Narrare. Core-Code hat keine HTTP-Dependencies, keine FastAPI-Imports, keine SQLAlchemy-Sessions. Core muss von API, MCP, CLI und Tests gleichermassen verwendbar sein.

**Lies zuerst:**
- `docs/_shared/CONSTRAINTS.md`
- `docs/development/coding-standards.md`

**Verfügbare Skills:**
- `/narrare-implementation` — Für Core-Implementierung
- `/narrare-testing` — Für Test-Schreiben
- `/check-constraints` — Für Constraint-Prüfung

---

## Was hier lebt (und was nicht)

```
narrare_core/
├── agents/      ← Agents (pydantic-ai) — PRIMÄRER Weg zu LLMs
│                   Agents sind erste-Klasse-Bürger (ADR-015)
├── llm/         ← ModelRegistry, Intents, Provider-Adapter
│                   NUR HIER dürfen LLM-Clients importiert werden (RULE-01)
├── prompts/     ← Registry, Composer, Context, Variable Engine
│                   NUR HIER werden Prompts gebaut (RULE-02)
├── shared/      ← Errors, Result-Types, Frontmatter, Pagination
├── context/     ← Context-Assembler (KB + Chapters → PromptContext)
├── embeddings/  ← pgvector-Abstraktionsschicht
├── memory/      ← mem0-Adapter
├── cache/       ← Redis-Abstraktion
└── schemas/     ← Geteilte Pydantic-Schemas
```

**Hier NICHT erlaubt:**
- `from fastapi import ...` — kein HTTP
- `from sqlalchemy import ...` — keine DB
- `AsyncSession` als Parameter — keine DB-Sessions
- Direktes `import openai/anthropic` außerhalb von `llm/`

---

## Agents — der primäre Weg zu LLMs

`narrare_core/agents/` enthält alle Narrare-Agents. Agents sind
erste-Klasse-Bürger (ADR-015). Jeder Agent ist ein pydantic-ai Agent,
der über `NarrareAgent` (Basisklasse) standardisierte Capabilities erbt.

```python
# Verwendung im Backend-Service:
from narrare_core.agents.summary_agent import ChapterSummaryAgent, SummaryDeps
from narrare_core.llm.gateway import ModelRegistry

model = await registry.get_model(config)
agent = ChapterSummaryAgent(model=model)
deps = SummaryDeps(language="en", genre="Fantasy", chapter_title="Ch 1")
result = await agent.run(prompt="Content...", deps=deps)
# → result.summary, result.key_points
```

**Meta-Prompt Integration:**

Meta-prompt and universal rules are architecturally guaranteed via Capabilities (ADR-026).
Every `NarrareAgent` automatically injects `NarrareObservability`, `NarrareUniversalRules`,
and `NarrareMeta` — no manual meta-prompt loading needed.

| Content | Mechanism | Source |
|---------|-----------|--------|
| Observability | `NarrareObservability` Capability | auto-injected |
| Universal rules (fiction, conflict, injection defense) | `NarrareUniversalRules` Capability | `_bundled/universal/` |
| Meta-prompt (identity, role, guardrails) | `NarrareMeta` Capability | `_bundled/meta/` |
| Feature-specific prompts | `PromptComposer` cascade | `_bundled/{category}/` |

**No `with_meta()` needed** — removed in ADR-026 Phase 3 (commit `45b7395`).

**Neuen Agent hinzufügen:**
1. Type-Datei `*_types.py` erstellen (Pydantic Output-Modell)
2. Agent-Datei `*_agent.py` erstellen (extends `NarrareAgent[DepsT, OutputT]`)
3. Prompt in `prompts/_bundled/{category}/{lang}/{mode}/system.md` (optional)
4. In `agents/__init__.py` exportieren
5. Service im Backend schreiben (siehe `apps/api/AGENTS.md`)
6. Tests: Agent-Level (TestModel) + Service-Level (Fake)

**Bestehende Agents:**
- `ChapterSummaryAgent` — Kapitel zusammenfassen
- `DraftAgent` — Entwürfe schreiben
- `OutlineAgent` — Gliederungen erstellen
- `ReviewAgent` — Texte reviewen
- `KBAgent` — Knowledge-Base-Operationen
- WritingGraph — Multi-Step-Workflow orchestriert mehrere Agents

**Provider hinzufügen** (altes Gateway-Zeug):
1. `llm/_providers/{name}.py` erstellen
2. `register("name", factory_function)` aufrufen
3. In `llm/_providers/__init__.py` importieren

---

## Prompt-Composer (für interne Agent-Nutzung)

```python
# Agent-interne Nutzung (nicht direkt in Services)
from narrare_core.prompts import PromptComposer, PromptContext
from narrare_core.llm import LLMIntent

ctx = PromptContext(language="de", project_title="Im stillen Wald", mode="summarize")
prompt = await composer.build(LLMIntent.SUMMARIZE, ctx)
# → prompt.system, prompt.user
```

Der Composer wird primär *innerhalb* von Agent-Implementierungen genutzt.
Backend-Services rufen Agents auf, nicht den Composer direkt.

**Neuen Intent hinzufügen (selten nötig):**
1. `LLMIntent` in `llm/intents.py` erweitern
2. `MODEL_ROUTING` Eintrag hinzufügen
3. `_INTENT_TO_CATEGORY` und `_INTENT_TO_MODE` in `prompts/composer.py` erweitern
4. Prompt-Datei in `prompts/_bundled/{category}/{lang}/{mode}/system.md` erstellen

---

## Bundled Prompts

```
prompts/_bundled/
├── meta/              ← Identity + role (loaded by NarrareMeta Capability)
│   ├── en/system.md
│   ├── en/system.lite.md
│   ├── de/system.md
│   └── fr/system.md
├── universal/         ← Universal rules (loaded by NarrareUniversalRules Capability)
│   ├── en/system.md
│   ├── de/system.md
│   └── fr/system.md
├── writing/
│   └── en/new_chapter/system.md   ← (noch zu erstellen)
├── kb/
│   └── en/create/system.md        ← (noch zu erstellen)
└── analysis/
    └── en/general/system.md       ← (noch zu erstellen)
```

Prompt-Format:
```markdown
---
prompt_type: writing
prompt_language: en
prompt_version: "1.0.0"
---

## System Prompt

[System-Anweisungen hier. Variablen: {{project_title}}, {{language}}, etc.]

## First Message

[Erste Nachricht der KI an den Autor (nur bei interaktiven Prompts)]
```

---

## Tests für Core

Unit Tests in `tests/unit/core/` — kein I/O, keine echte API:

### Agent-Level Tests (TestModel)
```python
from pydantic_ai.models.test import TestModel
from narrare_core.agents.summary_agent import ChapterSummaryAgent, SummaryDeps

async def test_summary_agent_returns_output():
    model = TestModel(custom_output_text="Summary text.")
    agent = ChapterSummaryAgent(model=model)
    deps = SummaryDeps(language="en")
    result = await agent.run(prompt="Content.", deps=deps)
    assert isinstance(result.summary, str)
```

### Service-Level Tests (Fake)
```python
async def test_summary_service_persists(
    self, service: ChapterSummaryService, fake_repo: FakeChapterRepository
) -> None:
    chapter = make_chapter()
    fake_repo.seed(chapter)
    result = await service.summarize(chapter.id)
    assert fake_repo.last_summary is not None
```

Coverage-Ziel für `core/`: **90% minimum**, 95% angestrebt.

---

## Referenz-Dokumentation

| Thema | Datei |
|-------|-------|
| Architektur-Regeln | `docs/_shared/CONSTRAINTS.md` |
| Coding Standards | `docs/development/coding-standards.md` |
| Tech Stack | `docs/_shared/TECH_STACK.md` |
