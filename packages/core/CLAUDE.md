# packages/core — Core Infrastructure

Du arbeitest im **Fundament** von Narrare. Core-Code hat keine HTTP-Dependencies, keine FastAPI-Imports, keine SQLAlchemy-Sessions. Core muss von API, MCP, CLI und Tests gleichermassen verwendbar sein.

**Lies zuerst:**
- `../../docs/agents/_shared/CONSTRAINTS.md`
- `../../docs/agents/implementation/CODING_STANDARDS.md`

---

## Was hier lebt (und was nicht)

```
narrare_core/
├── llm/         ← Gateway, Intents, Provider-Adapter, Embeddings
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

## Das Gateway — die wichtigste Datei

`llm/gateway.py` ist der einzige Weg zu jedem LLM-Provider.

```python
# Verwendung (von überall außer core/llm/):
from narrare_core.llm import LLMGateway, LLMIntent

result = await gateway.run(
    intent=LLMIntent.WRITE,
    system_prompt=prompt.system,
    user_prompt=prompt.user,
)
```

**Provider hinzufügen:**
1. `llm/_providers/{name}.py` erstellen
2. `register("name", factory_function)` aufrufen
3. In `llm/_providers/__init__.py` importieren

---

## Der Prompt-Composer — zweite kritische Datei

```python
# Verwendung (von überall außer core/prompts/):
from narrare_core.prompts import PromptComposer, PromptContext
from narrare_core.llm import LLMIntent

ctx = PromptContext(
    language="de",
    project_title="Im stillen Wald",
    mode="new_chapter",
)
prompt = await composer.build(LLMIntent.WRITE, ctx)
# → prompt.system, prompt.user sind fertig für gateway.run()
```

**Neuen Intent hinzufügen:**
1. `LLMIntent` in `llm/intents.py` erweitern
2. `MODEL_ROUTING` Eintrag hinzufügen
3. `_INTENT_TO_CATEGORY` und `_INTENT_TO_MODE` in `prompts/composer.py` erweitern
4. Prompt-Datei in `prompts/_bundled/{category}/{lang}/{mode}/system.md` erstellen

---

## Bundled Prompts

```
prompts/_bundled/
├── meta/
│   ├── en/system.md        ← Persona-Prompt Englisch
│   ├── en/system.lite.md   ← Kurzvariante für knappe Token-Budgets
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

```python
# Gateway mocken
from unittest.mock import AsyncMock, patch

with patch.object(gateway, "_make_agent", return_value=mock_agent):
    result = await gateway.run(...)
```

Coverage-Ziel für `core/`: **90% minimum**, 95% angestrebt.
