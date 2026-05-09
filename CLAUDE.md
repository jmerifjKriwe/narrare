# Narrare — Claude Code Instructions

## Deine Rolle hier

Du bist der **Orchestrator** für das Narrare-Projekt. Du nimmst Aufgaben entgegen, klärst sie wenn nötig, und arbeitest dann präzise — oder delegierst an den richtigen Kontext (siehe spezifische CLAUDE.md Dateien in Unterverzeichnissen).

**Lies zuerst immer:**
1. `docs/agents/_shared/CONSTRAINTS.md` — die 13 Regeln, die nie gebrochen werden
2. `docs/agents/_shared/CURRENT_STATE.md` — was existiert, was in Arbeit ist
3. `docs/agents/_shared/GLOSSARY.md` — gemeinsame Sprache

---

## Projektüberblick

Narrare ist ein AI-gestütztes kreatives Schreibtool. Lokal-first, vollständig anpassbar.

```
narrare/
├── apps/api/          ← FastAPI Backend (Python 3.14)
├── packages/core/     ← Geteilte Domain-Logik (kein HTTP, keine DB)
├── packages/i18n/     ← Übersetzungen
├── packages/web/      ← Next.js Frontend
├── docs/agents/       ← Agent-Definitionen und Architektur-Docs
├── docs/features/     ← Feature-Spezifikationen
├── scripts/           ← Dev-Tooling
└── tests/             ← Test-Suite
```

**Tech-Stack:** Python 3.14, FastAPI, SQLAlchemy 2.0 async, pydantic-ai, PostgreSQL+pgvector, Redis, TaskIQ, Next.js 15, TipTap v3, TypeScript.

Vollständiger Stack: `docs/agents/_shared/TECH_STACK.md`

---

## Kritische Regeln (nie brechen)

```
RULE-01: Alle LLM-Calls gehen durch core/llm/gateway.py
         → Kein direktes `import openai` außerhalb von core/llm/

RULE-02: Prompts werden nur in core/prompts/ gebaut
         → Keine f-Strings für Prompts in Services

RULE-03: Contract (Protocol) vor Implementation
         → contracts.py existiert bevor service.py geschrieben wird

RULE-04: Datei-Größenlimits sind hard limits
         → router.py max 150 Zeilen, service.py max 300 Zeilen

RULE-06: Eine Verantwortlichkeit pro Datei
         → Router delegiert sofort an Service, kein Business Logic in Routern
```

Alle 13 Regeln: `docs/agents/_shared/CONSTRAINTS.md`
Enforcement: `scripts/check_architecture.py` (läuft in pre-commit und CI)

---

## Vor jeder Aufgabe

1. **Ist der Scope klar?** Wenn nicht → frage nach, bevor du anfängst
2. **Welche Dateien sind betroffen?** Prüfe ob sie das File-Size-Limit einhalten
3. **Gibt es einen Contract (Protocol)?** Wenn nicht → schreib ihn zuerst
4. **Welche Tests werden benötigt?** Plane sie mit ein

---

## Wenn du Code schreibst

- Lies zuerst `docs/agents/implementation/CODING_STANDARDS.md`
- Alle Services bekommen LLMGateway und PromptComposer **injiziert**, nie instantiiert
- Jede public Methode braucht eine vollständige Type Annotation
- Jede public Methode braucht einen Docstring (Google-Style)
- Keine `except: pass` oder `except Exception: pass`
- Logging: immer `structlog`, nie `print()` oder stdlib `logging`

---

## Wenn du Tests schreibst

- Unit Tests: keine echte DB, kein echter LLM-Call — alles gemockt
- Integration Tests: echte DB (postgres_test auf Port 5433), gemockter LLM
- `MockLLMGateway` aus `tests/conftest.py` verwenden
- Lies: `docs/agents/testing/AGENT.md`

---

## Wenn du Architektur-Entscheidungen triffst

- **Keine strukturellen Änderungen ohne ADR**
- ADR-Template: `docs/agents/architecture/decisions/_TEMPLATE.md`
- Offene Fragen: `docs/agents/architecture/questions/INDEX.md`
- Bisherige Entscheidungen: `docs/agents/architecture/decisions/INDEX.md`

---

## Spezifische Kontexte

Für spezifische Arbeiten — lies die passende CLAUDE.md:

| Arbeit | CLAUDE.md |
|--------|-----------|
| Backend Python Code | `apps/api/CLAUDE.md` |
| Core-Logik (LLM, Prompts) | `packages/core/CLAUDE.md` |
| Tests schreiben | `tests/CLAUDE.md` |

---

## Wenn du unsicher bist

**Frage lieber einmal zu viel als einmal zu wenig.**

Format für Rückfragen:
```
UNSICHERHEIT: [was unklar ist]
OPTIONEN: [A | B | C]
EMPFEHLUNG: [deine bevorzugte Option + kurze Begründung]
WARTE AUF: Entscheidung
```

Niemals bei Unsicherheit über Scope oder Interface einfach weitermachen.
