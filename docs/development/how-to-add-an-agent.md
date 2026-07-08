# How to Add a New Agent

> **Kurzanleitung:** Von der Idee zum auslieferbaren Agent (alle 13+ Schritte).
> **Stand:** Gültig ab ADR-054 (Mode-1 PromptComposer-Zwang), ADR-045 (Runtime Adoption),
> ADR-046 (Prompt-Path-Compliance), ADR-055 (Character Voice — aktuellstes Agent-Modell).
>
> **Letzte Aktualisierung:** 2026-06-29

---

## Überblick

Ein neuer Narrare-Agent durchläuft diese 13+ Schritte:

```
 1. Types definieren (Output-Modell)
 2. Agent als NarrareAgent implementieren (structured output via output_type=)
 3. Prompt als Mode 1 Governed Template in core/prompts/_bundled/
 4. Intent in core/prompts/route_table.py registrieren (mit allowed_context_modes)
 5. Template-Metadaten in Prompt Surface Manifest (manifest.yaml)
 6. Backend-Service mit PromptComposer Mode 1
 7. Contracts/Protocols definieren vor Service (RULE-03)
 8. Service + Router + DI schreiben (Backend)
 9. Adoption Registry Eintrag (scripts/adoption/)
10. Runtime Evidence integration (ADR-045)
11. Tests: Core (Agent), Backend (Service + Router), Frontend (Panel + Hook, falls zutreffend)
12. Prompt Governance Check bestanden
13. i18n in en/de/fr (bei UI / Frontend-Komponenten)
14. Doc-Gate: Feature-Dokumentation + CHANGELOG aktualisieren
```

---

## Schritt 1: Types definieren (Output-Modell)

**Datei:** `packages/core/narrare_core/agents/{name}_types.py`

```python
"""Output types for the {Name} agent."""

from __future__ import annotations

from pydantic import BaseModel, Field


class {Name}Output(BaseModel):
    """Structured output from {Name}Agent."""

    result: str = Field(description="Main result text")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
```

**Muster (bei komplexerem Output):** Siehe `character_voice_types.py`:
```python
class CharacterVoiceOutput(BaseModel):
    """Wrapper for one or more character-voice profiles."""
    characters: list[CharacterVoiceEntry] = []
```

**Regeln:**
- Output-Typ muss ein Pydantic `BaseModel` sein
- Jedes Feld braucht `description` für LLM-Verständnis
- Bei komplexen Outputs → separate Type-Datei (RULE-04)
- ADR-035: Agent-Output-Validierung im Agent selbst (Tool `output_validator`)
- Felder mit `ge=`/`le=` validieren automatisch Grenzen

---

## Schritt 2: Agent implementieren (NarrareAgent)

**Datei:** `packages/core/narrare_core/agents/{name}_agent.py`

Der Agent erbt von `NarrareAgent[DepsT, OutputT]` und nutzt:
- `output_type=[self._process_output, {Name}Output]` — Output Function Pattern (structured output)
- `system_prompt` — kommt vom From-PromptComposer (Mode 1), nicht inline
- `output_validator` — ADR-035 Qualitätssicherung
- Error-Klassifizierung via `agents/errors.py` / `agents/error_translator.py` (automatisch)

**Modernes Beispiel** (CharacterVoiceAgent, ANAL-008 — Stand 2026-06-29):

```python
"""{Name}Agent — NarrareAgent für [Domain]."""

from __future__ import annotations

from typing import Any, cast

from pydantic_ai import ModelRetry, RunContext

from narrare_core.agents.base import NarrareAgent
from narrare_core.agents.{name}_types import {Name}Deps, {Name}Output


class {Name}Agent(NarrareAgent[{Name}Deps, {Name}Output]):
    """{Name}Agent — [Kurzbeschreibung]."""

    def __init__(self, model: Any, system_prompt: str | None = None) -> None:
        super().__init__(
            model=model,
            deps_type={Name}Deps,
            output_type=[self._process_output, {Name}Output],
            system_prompt=system_prompt,  # Von PromptComposer Mode 1, nicht inline!
        )
        # ADR-035: Output-Validator direkt im Agent
        self._agent.output_validator(self._validate_output)

    async def _validate_output(
        self,
        ctx: RunContext[{Name}Deps],
        output: {Name}Output,
    ) -> {Name}Output:
        """Validate deterministic invariants (ADR-035).

        No side effects — deterministic validation only.
        """
        # Beispiel: Leere Ergebnisse filtern, Wertebereiche prüfen
        if not output.result.strip():
            raise ModelRetry("result must be non-empty")
        return output

    async def _process_output(
        self,
        ctx: RunContext[{Name}Deps],
        result: str | None = None,
    ) -> {Name}Output:
        """Output Function — strukturiert LLM-Response in {Name}Output.

        Bei Streaming (ctx.partial_output) → Minimal-Output.
        """
        if ctx.partial_output:
            return {Name}Output()
        return {Name}Output(result=result or "")

    async def run(
        self,
        prompt: str,
        deps: {Name}Deps,
        **kwargs: Any,
    ) -> {Name}Output:
        """Execute agent and return structured output."""
        result = await self._agent.run(prompt, deps=deps, **kwargs)
        return cast("{Name}Output", result.output)
```

**Wichtige Patterns:**
1. **Deps-Klasse** definieren (`{Name}Deps`) — einfache Dataclass/BaseModel für Kontext
2. **`system_prompt=None`** im Konstruktor — wird vom Service via PromptComposer befüllt
3. **`output_validator`** für ADR-035 Qualitäts-Gate (ModelRetry bei Invarianten-Verletzung)
4. **`_process_output`** wandelt LLM-Output-Funktion in Pydantic-Modell um
5. **Fehler** werden automatisch von `NarrareAgent.run()` über `classify_error` übersetzt

---

## Schritt 3: Prompt als Mode 1 Governed Template

**Datei:** `packages/core/narrare_core/prompts/_bundled/{category}/{lang}/{mode}/system.md`

Alte Agents nutzten `system_prompt` als inline String im Konstruktor. **Das ist seit ADR-054 VERBOTEN** — alle Feature-Prompts müssen als governed Template via `PromptComposer` (Mode 1) geladen werden.

**Template-Struktur:**
```
prompts/_bundled/
├── writing/
│   ├── en/new_chapter/system.md
│   └── de/new_chapter/system.md
├── kb/
│   ├── en/merge/system.md
│   └── de/merge/system.md
├── planning/
│   ├── en/character_arc/system.md
│   └── en/timeline_extraction/system.md
└── analysis/
    ├── en/coreference/system.md
    ├── en/character_voice/system.md
    └── de/character_voice/system.md
```

**Template-Format:**
```markdown
---
prompt_type: {category}
prompt_language: {lang}
prompt_version: "1.0.0"
---

## System Prompt

[System-Anweisungen. Variablen mit {{variable_name}} einbetten.]

### Context

- Projekt: {{project_title}}
- Sprache: {{writing_language}}
- Genre: {{genre}}

### Output Format

[JSON- oder Text-Output-Beschreibung]

## Do NOT

[Constraints und Negativ-Regeln]
```

**Regeln (RULE-02, RULE-02a, RULE-02b):**
- Template wird via `PromptComposer.build(intent, context)` geladen — keine direkten `importlib.resources` calls
- Variablen werden durch `VariableEngine` substituiert — keine f-Strings
- `system_prompt` des Agents ist der composed system prompt (Mode 1)
- Laufzeit-Input (Kapiteltext, Nutzeranfrage) fließt als user-channel `prompt=` im agent.run()
- Template-Metadaten (Frontmatter) sind Pflicht
- Template muss im Prompt Surface Manifest registriert sein (Schritt 5)

---

## Schritt 4: Intent in route_table.py registrieren

**Datei:** `packages/core/narrare_core/prompts/route_table.py`

Jeder Intent braucht:
- Eintrag in `INTENT_TO_CATEGORY` und `INTENT_TO_MODE`
- `PromptRouteConfig` mit `allowed_context_modes`

```python
# 1. Category mapping (für Promt-Template-Pfad)
INTENT_TO_CATEGORY: dict[LLMIntent, str] = {
    ...
    LLMIntent.{INTENT}: "{category}",
}

# 2. Default-Mode mapping
INTENT_TO_MODE: dict[LLMIntent, str] = {
    ...
    LLMIntent.{INTENT}: "{default_mode}",
}

# 3. Route-Config mit required/optional variables
ROUTE_CONFIGS: dict[LLMIntent, PromptRouteConfig] = {
    ...
    LLMIntent.{INTENT}: PromptRouteConfig(
        "{category}",
        "{default_mode}",
        required_variables=frozenset({"var1", "var2"}),
        optional_variables=_COMMON_OPTIONAL_VARIABLES | frozenset({"var3"}),
        allowed_context_modes=frozenset({"{default_mode}", "{extra_mode}"}),
    ),
}
```

**Wichtig:**
- `allowed_context_modes` muss den/die Modi deklarieren, die der Prompt unterstützt
- Optional-Variablen, die zum Template gehören, müssen deklariert werden (sonst CI-Fehler)
- Bei Multi-Mode-Intents (wie `ANALYSE` oder `PLAN`) alle Modes in `allowed_context_modes` auflisten

---

## Schritt 5: Template-Metadaten im Prompt Surface Manifest

**Datei:** `scripts/architecture/prompt-surface-manifest.yaml`

```yaml
{category}:
  {mode}:
    path: "{category}/{lang}/{mode}/system.md"
    context_modes: ["{context_mode}"]
    variables:
      required: ["var1", "var2"]
      optional: ["var3"]
    accept_extra_variables: false
```

Dieses Manifest wird von `scripts/prompt_governance_checks.py` validiert:
- Jeder Template-Pfad muss im Manifest auftauchen
- Alle deklarierten Variablen müssen im Template vorkommen
- context_modes müssen mit `route_table.py` übereinstimmen
- Ein Template ohne Manifest-Eintrag → CI-Fehler

**Siehe ADR-037 (Prompt Surface Contract) und ADR-049 (Identity + Path Contract).**

---

## Schritt 6: Backend-Service mit PromptComposer Mode 1

**Datei:** `apps/api/narrare/{domain}/{name}_service.py`

Der Service resolved den System-Prompt via `compose_invocation()` (Mode 1) und
übergibt ihn an den Agent-Konstruktor. Der Laufzeit-Input (z.B. Chapter-Text)
fließt als user-channel `prompt=` in `agent.run()`.

**Modernes Beispiel** (CoreferenceService, ANAL-005):

```python
"""{Name} service — ruft {Name}Agent via Mode 1 PromptComposer (ANAL-XXX)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from uuid import UUID

    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.llm.intents import ResolvedModelConfig
    from narrare_core.prompts.composer import PromptComposer
    from narrare_core.ai_invocation.pipeline import InvocationPipeline

logger = structlog.get_logger(__name__)


class {Name}Service:
    """Service for {name} analysis.

    Prompt resolution is Mode 1 (composer-driven) per ADR-054: resolves
    the system prompt via ``PromptComposer`` and passes to the agent
    constructor. No inline f-string feature prompt.
    """

    def __init__(
        self,
        model_registry: ModelRegistry,
        model_config: ResolvedModelConfig | None = None,
        composer: PromptComposer | None = None,
        *,
        invocation_pipeline: InvocationPipeline | None = None,
    ) -> None:
        self._registry = model_registry
        self._config = model_config
        self._composer = composer
        self._invocation_pipeline = invocation_pipeline

    async def analyze(self, ...) -> AsyncIterator[...]:
        """Run the {Name}Agent and stream results."""

        # 1. Daten laden und validieren
        ...

        # 2. Prompt via PromptComposer Mode 1 resolven
        from narrare_core.prompts.context import PromptContext
        from narrare_core.llm.intents import LLMIntent
        from narrare_core.ai_invocation import compose_invocation

        ctx = PromptContext(
            language=language,
            writing_language=language,
            project_title=novel.title,
            genre=novel.genre or "",
            mode="{context_mode}",
        )
        invocation = await compose_invocation(
            invocation_pipeline=self._invocation_pipeline,
            invocation_context=...,
            composer=self._composer,
            prompt_context=ctx,
            intent=LLMIntent.{INTENT},
        )
        composed_prompt = invocation.composed_prompt
        if composed_prompt is None:
            raise ConfigurationError(..., code="COMPOSITION_EMPTY")

        # 3. Modell holen + Agent instantiieren
        model = await self._registry.get_model(self._config)
        agent = {Name}Agent(model=model, system_prompt=composed_prompt.system)

        # 4. Agent ausführen
        deps = {Name}Deps(...)
        result = await agent.run(
            prompt=composed_prompt.user or chapter_text,
            deps=deps,
        )

        # 5. Ergebnis mappen und streamen
        yield ...
```

**Wichtig:**
- Kein `PromptRegistry.resolve()` direkt im Service (RULE-02b Verletzung)
- Kein `importlib.resources` für Prompt-Loading (RULE-02b Verletzung)
- Kein Inline-Fallback-String (RULE-02b)
- Bei Fehlern: loggen + re-raisen (RULE-11 — kein silent failure)

---

## Schritt 7: Contracts/Protocols definieren (RULE-03)

**Datei:** `apps/api/narrare/{domain}/contracts_{name}.py`

Bevor der Service geschrieben wird, muss das Protocol stehen:

```python
"""Contracts for {name} analysis."""

from __future__ import annotations

from typing import TYPE_CHECKING, AsyncIterator, Protocol
from uuid import UUID

if TYPE_CHECKING:
    from narrare.analysis.schemas_{name} import {Name}StreamEvent


class {Name}ServiceProtocol(Protocol):
    """Protocol for {Name}Service."""

    async def analyze(
        self,
        chapter_id: UUID,
        user_id: UUID,
    ) -> AsyncIterator[{Name}StreamEvent]:
        """Analyse and stream results."""
        ...
```

**Regeln:**
- `Protocol` (kein ABC) — RULE-03
- Vollständige Typannotationen (RULE-09)
- Async-Signaturen für I/O (RULE-13)
- Streaming + Non-Streaming teilen Interface (RULE-13)

---

## Schritt 8: Service + Router + DI schreiben (Backend)

### Router

**Datei:** `apps/api/narrare/{domain}/router_{name}.py`

```python
from fastapi import APIRouter, Depends

router = APIRouter(prefix="/analysis/{name}", tags=["analysis"])


@router.post("/{chapter_id}")
async def analyze_{name}(
    chapter_id: UUID,
    service: {Name}Service = Depends(get_{name}_service),
    ...
) -> StreamingResponse:
    ...
```

- Router delegiert SOFORT an Service (RULE-06)
- Keine Business-Logik im Router
- SSE-Streaming wenn backend SSE-kann (architectural-discipline.md §5.1)

### DI (Dependencies)

**Datei:** `apps/api/narrare/{domain}/dependencies_{name}.py`

```python
from fastapi import Depends
from narrare_core.llm.gateway import ModelRegistry
from narrare_core.prompts.composer import PromptComposer


def get_{name}_service(
    registry: ModelRegistry = Depends(get_model_registry),
    config: ResolvedModelConfig = Depends(resolve_model_config),
    composer: PromptComposer = Depends(get_prompt_composer),
    ...
) -> {Name}Service:
    return {Name}Service(
        model_registry=registry,
        model_config=config,
        composer=composer,
        ...
    )
```

---

## Schritt 9: Adoption Registry Eintrag

**Datei:** Neue Datei in `scripts/adoption/` oder Eintrag im bestehenden Registry-YAML.

Jeder Agent-Mode braucht einen Adoption Registry Eintrag (ADR-025):

```yaml
{feature_id}:
  mode: "{context_mode}"
  prompt_path_compliant: true
  requires_runtime_evidence: true
  status: governed_debt  # oder "adopted"
```

Der Eintrag wird von `scripts/check_adoption.py` validiert:
- Jeder routeable Intent muss einen Registry-Eintrag haben
- Jeder Mode muss `prompt_path_compliant` haben (ADR-046)
- Runtime Evidence muss für `requires_runtime_evidence: true` existieren

---

## Schritt 10: Runtime Evidence Integration (ADR-045)

Der Service muss Runtime Evidence erzeugen, damit die Adoption als "runtime verified" gilt:

```python
invocation_context = build_invocation_context(
    feature_id="{feature_id}",
    intent=LLMIntent.{INTENT},
    project_id=...,
    user_id=...,
    language=language,
)
invocation = await compose_invocation(
    invocation_pipeline=self._invocation_pipeline,
    invocation_context=invocation_context,
    composer=self._composer,
    prompt_context=ctx,
    intent=LLMIntent.{INTENT},
)
```

**Evidence-Arten (ADR-045):**
- `invocation_id` — eindeutige ID pro Aufruf
- `prepared_context_fingerprint` — Fingerabdruck des Prompt-Context
- `prompt_fingerprint` — Fingerabdruck des komponierten Prompts
- `budget_decision_fingerprint` — Budget-Entscheidungs-Fingerprint
- `model_call_marker` — Marker für den tatsächlichen Model-Call
- `streaming` — Ob gestreamt wurde

Status-Semantik: `PASS` / `GOVERNED_DEBT` / `STATIC_ONLY` / `FAIL`.
Ein neuer Agent (governed debt) startet als `governed_debt` und wird mit
CI/Integration-Tests zu `adopted` erhoben.

---

## Schritt 11: Tests schreiben

### Core-Level (Agent-Tests)

**Datei:** `tests/unit/core/agents/test_{name}_agent.py`

```python
from pydantic_ai.models.test import TestModel
from narrare_core.agents.{name}_agent import {Name}Agent, {Name}Deps


async def test_{name}_returns_output():
    model = TestModel(custom_output_text="Test result.")
    agent = {Name}Agent(model=model)
    deps = {Name}Deps(...)
    result = await agent.run(prompt="Test input.", deps=deps)
    assert result.result == "Test result."
```

### Backend-Level (Service-Tests)

**Datei:** `tests/unit/api/{domain}/test_{name}_service.py`

```python
async def test_{name}_service_success(
    self, service: {Name}Service
) -> None:
    result = await service.analyze(chapter_id, user_id)
    assert result is not None
```

### Frontend-Level (bei UI-Komponenten)

**Datei:** `packages/web/**/*.test.tsx`

- Component tests mit Vitest
- SSE-Client tests
- Hook tests (use{Name})

### Coverage-Ziele

| Layer | Minimum | Target |
|-------|---------|--------|
| Core | 90% | 95% |
| Backend | 80% | 90% |
| Frontend | 70% | 80% |

---

## Schritt 12: Prompt Governance Check

Vor dem Commit muss der Prompt alle Governance-Checks bestehen:

```bash
just check-prompts-structure   # Frontmatter, Variablen, Manifest
just check-adoption            # Registry-Eintrag vorhanden
just check-architecture        # RULE-XX Compliance
just check-streaming           # SSE Compliance (wenn zutreffend)
just check-governance          # Governance Health
```

**Was geprüft wird (ADR-037/046/049):**
1. Template hat valides Frontmatter (`prompt_type`, `prompt_language`, `prompt_version`)
2. Template ist im Prompt Surface Manifest registriert
3. Alle Template-Variablen sind im Manifest deklariert
4. Template-Pfad stimmt mit `route_table.py` überein (PROMPT-IDENTITY-Check)
5. Kein direkter Registry-Zugriff im Service (ADR-046)
6. context_modes sind in Manifest und route_table synchron
7. Template hat keine Orphan-Status (wird von einem Consumer geladen)
8. Kein Inline-Fallback-String im Service

---

## Schritt 13: i18n (bei Frontend-Komponenten)

Wenn der Agent eine UI-Komponente bekommt:

```
packages/i18n/messages/
├── en/{domain}.json   ← Englische Schlüssel
├── de/{domain}.json   ← Deutsche Übersetzung
└── fr/{domain}.json   ← Französische Übersetzung
```

**i18n-Schritte:**

1. Namespace in `request.ts` registrieren:
   ```typescript
   // packages/web/src/i18n/request.ts
   const namespaces = ["common", "{domain}", ...];
   ```

2. JSON-Dateien für alle 3 Locales anlegen
3. Im Code: `const t = useTranslations("{domain}");`
4. `studio.aiActions.*` nutzen für konsistente AI-Action-Beschriftungen
5. `studio.aiDiff.*` nutzen für Diff/Compare-Vocabulary

---

## Schritt 14: Doc-Gate

**Nach der Implementierung:**

1. **Feature Spec** erstellen/aktualisieren → `docs/features/{domain}/{feature-id}.md`
2. **CHANGELOG** aktualisieren → `docs/CHANGELOG.md`
3. **CURRENT_STATE.md** aktualisieren → neuen Eintrag im Phase-6-Abschnitt
4. **ADR-Status** prüfen → ggf. von `🔄 Proposed` zu `✅ Implemented`

---

## Vollständige Checkliste

### Pre-Implementation
- [ ] ADR existiert (bei neuer Architekturentscheidung) oder ist nicht nötig
- [ ] Feature Spec existiert (bei größerem Feature)
- [ ] Contract (Protocol) in `contracts.py` definiert (RULE-03)

### Core
- [ ] `*_types.py` — Output-Modell definiert
- [ ] `*_agent.py` — `NarrareAgent` implementiert mit `output_type` + `output_validator`
- [ ] `agents/__init__.py` — Exporte hinzugefügt
- [ ] `prompts/_bundled/{category}/{lang}/{mode}/system.md` — Template angelegt
- [ ] `route_table.py` — Intent, Category, Mode, Config registriert
- [ ] `manifest.yaml` — Template-Metadaten registriert
- [ ] Adoption Registry — Eintrag vorhanden

### Backend
- [ ] `contracts_{name}.py` — Protocol definiert (RULE-03)
- [ ] `schemas_{name}.py` — Request/Response/StreamEvent Schemas
- [ ] `{name}_service.py` — Service mit PromptComposer Mode 1
- [ ] `router_{name}.py` — SSE-Endpunkt (oder REST wenn begründete Ausnahme)
- [ ] `dependencies_{name}.py` — DI-Factory

### Frontend (falls UI)
- [ ] Panel-Komponente
- [ ] Hook (use{Name})
- [ ] SSE Client (connectSSE oder eigener)
- [ ] i18n Keys (en/de/fr)
- [ ] AI Operation Inventory registriert (`scripts/checks/ai_operation_inventory.yaml`)

### Quality
- [ ] Core-Agent-Tests (TestModel)
- [ ] Backend-Service-Tests
- [ ] Frontend-Tests (Vitest, falls UI)
- [ ] Governance Checks bestanden (`just check-prompts-structure`, `just check-adoption`)
- [ ] Architecture Checks bestanden (`just check-architecture`)
- [ ] Streaming Compliance bestanden (`just check-streaming`)
- [ ] Governance Health bestanden (`just check-governance`)

### Documentation
- [ ] Feature Spec aktualisiert
- [ ] CHANGELOG aktualisiert
- [ ] CURRENT_STATE.md aktualisiert
- [ ] ggf. ADR-Status aktualisiert

---

## Referenzen

| Thema | ADR / Spec | Datei |
|-------|-----------|-------|
| Agent Base Class | ADR-015, ADR-035 | `core/agents/base.py` |
| Structured Output | ADR-035 | `core/agents/*_types.py` |
| Mode 1 PromptComposer | ADR-054 | `core/prompts/composer.py` |
| Route Table | ADR-024, ADR-049 | `core/prompts/route_table.py` |
| Prompt Surface Manifest | ADR-037, ADR-049 | `scripts/architecture/prompt-surface-manifest.yaml` |
| Adoption Registry | ADR-025, ADR-045 | `scripts/adoption/` |
| Runtime Evidence | ADR-045 | `core/ai_invocation/` |
| i18n | ADR-013 | `packages/i18n/messages/` |
| Streaming Compliance | architectural-discipline.md §5.1 | `scripts/architecture/streaming_compliance.py` |
| Governance Checks | ADR-037, ADR-046, ADR-049 | `scripts/prompt_governance_checks.py` |
| AI Operation Inventory | CR-07 | `scripts/checks/ai_operation_inventory.yaml` |

---

> **Maintained by:** Architecture Specialist
> **Updates:** When the agent creation process changes (new ADRs, new tooling)
> **Source agents for reference:** CharacterVoiceAgent (ANAL-008), CoreferenceAgent (ANAL-005)
