# ADR-015 — Pydantic-AI Agents as First-Class Architecture Citizens

> **Status:** ✅ Accepted
> **Date:** 2026-05-20
> **Deciders:** Architecture Agent, Narrare Dev Coordinator
> **Supersedes:** ADR-001 (partial — RULE-01 redefined)

---

## Context

Narrare nutzt pydantic-ai seit Projektbeginn, jedoch nur als **Model-Client-Abstraktion**: Der Gateway erzeugt einen ephemeren `Agent`, ruft `run_sync()` auf und verwirft ihn. Tools, Capabilities, Structured Output, Hooks, Multi-Agent-Patterns und das gesamte Agent-Framework bleiben ungenutzt.

Parallel dazu wächst die Writing-Pipeline (`pipeline.py` + `draft_processor.py` + `context_assembler.py` + `session_manager.py`) auf über 1500 Zeilen manueller Orchestrierung — mit eigener Retry-Logik, eigenem Post-Processing, eigener Context-Assembly. Jedes dieser Features baut pydantic-ai-Fähigkeiten nach, die das Framework nativ bietet.

Die Architektur steht an einem Scheideweg:

- **Weg A**: Gateway bleibt dünne Model-Abstraktion. Narrare baut Agent-Features selbst. Kein Umbau.
- **Weg B**: Agents werden erste-Klasse-Bürger. Der Gateway liefert nur noch das Model. Agent-Features werden nativ genutzt. Umbau von Pipeline, Processor, Assembler.

Eine spätere Migration von Weg A zu Weg B ist unwahrscheinlich (technische Schuld, kein Budget für "nur Umbau"). Wenn wir Agents wollen, müssen wir den Schritt jetzt machen.

---

## Decision Drivers

- **Writing-Pipeline-Komplexität** — 1500+ Zeilen manuelle Orchestrierung vs. native pydantic-ai-Features
- **Token-Kosten** — Pro Request werden vollständige Context-Assemblies ans LLM geschickt; Tools + ToolSearch könnten das drastisch reduzieren
- **Observability** — Manuelle Metrik-Erfassung vs. native Hooks und OpenTelemetry-Spans (see ADR-031; Logfire is not used for core observability)
- **Structured Output** — Manuelle Validierung nach dem LLM-Call vs. `output_type=` mit nativem Retry
- **Testing** — AsyncMock-Pyramiden vs. `TestModel`/`FunctionModel`
- **Wartbarkeit** — Das Framework wird von Pydantic maintaint; Eigenbau muss selbst gewartet werden
- **MVP-Druck** — Phase 5 ist in Arbeit; ein zu großer Umbau gefährdet den Liefertermin

---

## Options Considered

### Option A — Gateway bleibt dünne Model-Abstraktion (Status Quo)

Der Gateway erzeugt pro Call einen Agent, nutzt aber nur `run_sync()`.

**Pros:**
- Kein Umbau nötig
- RULE-01 bleibt unverändert
- Writing-Pipeline bleibt, wie sie ist

**Cons:**
- Framework-Features bleiben ungenutzt (<5% von pydantic-ai)
- Eigenbau-Logik muss selbst gewartet werden (Pipeline, Processor, Assembler)
- Tools, Capabilities, Multi-Agent nicht nutzbar ohne erheblichen Eigenbau
- Token-Optimierung (ToolSearch, deferred loading) nicht möglich
- Testing aufwändiger (AsyncMock vs. TestModel)

### Option B — Agents als First-Class Citizens (gewählt)

`core/agents/` wird neues Modul für Agent-Definitionen. Der Gateway wird zur Model-Registry umgebaut: Er liefert konfigurierte Model-Instanzen (mit User-Credentials), aber Agents werden in `core/agents/` definiert. Kein Code außerhalb von `core/agents/` darf `Agent(...)` instantiieren. RULE-01 wird zu RULE-01b erweitert.

**Pros:**
- Volle Nutzung des Frameworks: Tools, Capabilities, Hooks, Output Types
- Writing-Pipeline schrumpkt dramatisch (Output Function statt DraftProcessor, Tool statt ContextAssembler)
- Natives Retry, native Validierung
- `TestModel` für deterministische Tests
- ToolSearch für Token-Einsparung
- Multi-Agent-Architektur möglich

**Cons:**
- Umbau der Writing-Pipeline (2–3 Wochen)
- RULE-01 muss angepasst werden (erzeugt Migrationaufwand in CI-Tooling)
- Tools kosten Tokens (Tool-Schemas im Request) — muss durch ToolSearch kompensiert werden
- Gateway wird komplexer (Model-Registry + Credential-Resolution)
- Gleichzeitiger Betrieb alter + neuer Pipeline nötig (Feature-Flag)

---

## Decision

**We choose Option B — Agents as First-Class Architecture Citizens.**

Der Gateway wird zur **Model Registry** umgebaut. Agents werden in `core/agents/` definiert. Die Writing-Pipeline wird schrittweise auf native Agents migriert. RULE-01 wird zu RULE-01b erweitert: "LLM-Aufrufe gehen durch Agents. Agents beziehen ihre Modelle aus dem Gateway. Kein Code ruft LLMs direkt auf."

---

## Rationale

Die Entscheidung ist pragmatisch: Wir stehen am Ende von Phase 5, die Pipeline ist noch überschaubar. Der Umbau ist jetzt machbar und zeitlich planbar. Nach Phase 5 kommen neue Features (Write-003, Write-004) die auf der Pipeline aufsetzen — jeder Tag mit der alten Architektur vergrößert die technische Schuld.

Das entscheidende Argument: **pydantic-ai ist ein maintaintes Framework.** Jede Zeile Eigenbau-Retry, Eigenbau-Postprocessing, Eigenbau-Context-Assembly muss von *uns* gewartet werden. Jedes pydantic-ai-Release kann unsere Eigenbauten obsolet machen — oder neue Features liefern, die wir nicht nutzen können, weil wir unsere eigene Abstraktion dazwischen haben.

Der Gateway als Model Registry bleibt die zentrale Kontrollinstanz für: Credential-Resolution, Provider-Auswahl, Routing, Usage-Limits, Cost-Tracking. Er wird nicht schwächer — er wird fokussierter.

---

## Consequences

**Positive:**
- Agents können Tools, Capabilities, Hooks nativ nutzen
- Writing-Pipeline-Komplexität sinkt drastisch
- Testbarkeit steigt (TestModel statt AsyncMock)
- Token-Kosten sinken durch ToolSearch (deferred tool loading)
- Multi-Agent-Patterns werden möglich
- Langfristig weniger Wartungsaufwand (Framework statt Eigenbau)

**Negative / Tradeoffs:**
- 2–3 Wochen Umbau der Writing-Pipeline
- Gleichzeitiger Betrieb alter + neuer Pipeline (Feature-Flag)
- Tools verursachen initial Token-Overhead (kompensiert durch ToolSearch)
- Team muss pydantic-ai Agent-Patterns lernen

**Constraints introduced / updated:**

RULE-01 wird zu RULE-01b (revised):

```python
# ERLAUBT (NEU):
from narrare_core.agents import DraftAgent  # Agent in core/agents/
agent = DraftAgent(model=gateway.get_model(...))  # Model aus Gateway

# VERBOTEN (WIE BISHER):
import openai  # Direkter LLM-Client
from pydantic_ai import Agent  # Agent instantiiert ohne Gateway-Model
```

Die AST-Checks in `scripts/check_architecture.py` müssen aktualisiert werden:
- `from pydantic_ai import Agent` bleibt in `core/agents/` erlaubt, wird aber in Service/API/Frontend-Code weiterhin geblockt
- `from pydantic_ai import Agent` in `core/llm/` wird jetzt eingeschränkt (Gateway importiert nur Model-Klassen)
- Neue Regel: `Agent(`-Instantiation nur in `core/agents/`

---

## Migration Plan

Der Umbau erfolgt in 4 Phasen:

| Phase | Inhalt | Aufwand |
|-------|--------|---------|
| 0 | ADR + RULE-01b + `core/agents/` Struktur + Gateway als ModelRegistry | 2–3 Tage |
| 1 | Usage Limits + Hooks für Observability | 3–4 Tage |
| 2 | Output Functions für DraftProcessor → `DraftAgent` | 5–7 Tage |
| 3 | KB-Tools + ToolSearch → ContextAssembler als Tool | 8–10 Tage |
| 4 | Pydantic Graph für Writing-Workflows | 10–14 Tage |

Details siehe [Implementation Plan](ADR-015-implementation-plan.md).

---

## Review Trigger

- [x] Nach Abschluss von Phase 2: Evaluieren, ob die alte Pipeline noch parallel laufen muss
  → Ergebnis: Ja, Legacy-Pipeline bleibt vorerst. Feature-Flags steuern Übergang.
- [x] Nach Abschluss von Phase 4: Gesamt-ADR-Review — ist die Architektur stabil?
  → Ergebnis: Architektur ist stabil. 4 Phasen implementiert, 123 Tests, 0 Violations.
  Offen: KBAgent-Integration mit echtem KB-Service (Task 7), Legacy-Entfernung (Task 5+6).
- [ ] Wenn pydantic-ai v2 erscheint: Verträgt sich der Umbau mit dem Major-Release?
