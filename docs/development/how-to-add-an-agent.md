# How to Add a New Agent

> Kurzanleitung: Von der Idee zum auslieferbaren Agent.
> Status: Gültig ab Phase 0 (Agents-First Foundation).

## Überblick

Ein neuer Narrare-Agent durchläuft diese Schritte:

1. **Types** definieren (`*_types.py`)
2. **Agent** implementieren (`*_agent.py`)
3. **Prompt** erstellen (optional, in `prompts/_bundled/`)
4. **Registry-Export** in `agents/__init__.py`
5. **Backend-Service** schreiben
6. **Router + DI** anbinden
7. **Tests** schreiben (Agent + Service)

---

## Schritt 1: Types definieren

Datei: `packages/core/narrare_core/agents/{name}_types.py`

```python
"""Output types for the {Name} agent."""

from __future__ import annotations

from pydantic import BaseModel, Field


class {Name}Output(BaseModel):
    """Structured output from {Name}Agent."""

    result: str = Field(description="Main result text")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
```

Bei einfachen Agents kann das Output-Modell auch direkt in der Agent-Datei stehen.
Für komplexe Outputs (mit `key_points`, `metadata`, etc.) → separate Type-Datei.

---

## Schritt 2: Agent implementieren

Datei: `packages/core/narrare_core/agents/{name}_agent.py`

```python
"""{Name}Agent — beschreibe hier was der Agent tut.

Usage:
    model = await registry.get_model(config)
    agent = {Name}Agent(model=model)
    deps = {Name}Deps(param1="value")
    result = await agent.run(prompt="Input...", deps=deps)
    print(result.result)
"""

from __future__ import annotations

from typing import Any

from pydantic_ai import RunContext

from narrare_core.agents.base import NarrareAgent
from narrare_core.agents.{name}_types import {Name}Output


class {Name}Deps:
    """Dependencies for {Name}Agent.

    Hier landen alle Kontext-Variablen, die der Agent braucht:
    Sprache, Genre, Projekt-ID, etc.
    """

    def __init__(
        self,
        param1: str = "",
        language: str = "en",
    ) -> None:
        self.param1 = param1
        self.language = language


class {Name}Agent(NarrareAgent[{Name}Deps, {Name}Output]):
    """{Name}Agent — [hier die Kurzbeschreibung]."""

    def __init__(self, model: Any) -> None:
        super().__init__(
            model=model,
            deps_type={Name}Deps,
            output_type=[self._process_output, {Name}Output],
            system_prompt=(
                "You are a helpful assistant. "
                "[Hier das System-Prompt]"
            ),
        )

    async def _process_output(
        self,
        ctx: RunContext[{Name}Deps],
        result: str = "",
        confidence: float = 1.0,
    ) -> {Name}Output:
        """Output Function — strukturiert die LLM-Response."""
        if ctx.partial_output:
            return {Name}Output()

        return {Name}Output(
            result=result,
            confidence=confidence,
        )

    async def run(
        self,
        prompt: str,
        deps: {Name}Deps,
        **kwargs: Any,
    ) -> {Name}Output:
        """Execute the agent and return structured output."""
        result = await self._agent.run(prompt, deps=deps, **kwargs)
        return result.output  # type: ignore[return-value]
```

**Pattern-Erklärung:**
- `NarrareAgent[DepsT, OutputT]` — generische Basisklasse
- `output_type=[self._process_output, {Name}Output]` — Output Function Pattern:
  - LLM ruft `_process_output` auf mit benannten Parametern
  - `_process_output` baut `{Name}Output` daraus
  - Bei Streaming (`ctx.partial_output`) → Minimal-Output
- `run()` delegiert an `self._agent.run()` und extrahiert `.output`

---

## Schritt 3: Prompt erstellen (optional)

Bei einfachen Agents reicht der `system_prompt`-String im Konstruktor.

Bei komplexen Anwendungsfällen → Prompt-Datei in `prompts/_bundled/`:

```
prompts/_bundled/{category}/{lang}/{mode}/system.md
```

Nutzung dann über `PromptComposer` (innerhalb des Agents).

---

## Schritt 4: Registry-Export

Datei: `packages/core/narrare_core/agents/__init__.py`

```python
from narrare_core.agents.{name}_agent import {Name}Agent, {Name}Deps
from narrare_core.agents.{name}_types import {Name}Output

__all__ = [
    ...
    "{Name}Agent",
    "{Name}Deps",
    "{Name}Output",
]
```

---

## Schritt 5: Backend-Service

Datei: `apps/api/narrare/{domain}/{name}_service.py`

```python
"""Service for {name} using {Name}Agent."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.llm.intents import ResolvedModelConfig

logger = structlog.get_logger(__name__)


class {Name}Service:
    def __init__(
        self,
        registry: ModelRegistry,
        config: ResolvedModelConfig,
    ) -> None:
        self._registry = registry
        self._config = config

    async def process(self, input_text: str) -> {Name}Output:
        model = await self._registry.get_model(self._config)
        agent = {Name}Agent(model=model)
        deps = {Name}Deps(language="en")

        try:
            result = await agent.run(prompt=input_text, deps=deps)
            return result
        except Exception as exc:
            logger.error("agent_failed", error=str(exc), exc_info=True)
            raise
```

Optional: `{name}_contracts.py` mit ServiceProtocol für Testbarkeit.

---

## Schritt 6: Router + DI

Datei: `apps/api/narrare/{domain}/{name}_router.py` + `{name}_deps.py`

Router (FastAPI):
```python
@router.post("/{name}/process")
async def process(
    request: {Name}Request,
    service: {Name}Service = Depends(get_{name}_service),
) -> {Name}Response:
    result = await service.process(request.input_text)
    return {Name}Response.model_validate(result)
```

DI:
```python
def get_{name}_service(
    registry: ModelRegistry = Depends(get_model_registry),
    config: ResolvedModelConfig = Depends(resolve_model_config),
    ...
) -> {Name}Service:
    return {Name}Service(registry=registry, config=config, ...)
```

---

## Schritt 7: Tests

### Agent-Level (unit/core/agents/)

```python
from pydantic_ai.models.test import TestModel
from narrare_core.agents.{name}_agent import {Name}Agent, {Name}Deps

async def test_{name}_returns_output():
    model = TestModel(custom_output_text="Test result.")
    agent = {Name}Agent(model=model)
    deps = {Name}Deps(language="en")
    result = await agent.run(prompt="Test input.", deps=deps)
    assert result.result == "Test result."
```

### Service-Level (unit/api/{domain}/)

```python
async def test_{name}_service_success(
    self, service: {Name}Service
) -> None:
    result = await service.process("Test input")
    assert result.result != ""
```

### Integration-Level

Über HTTP mit `TestModel` via DI override.

---

## Checkliste

- [ ] Type-Datei (`*_types.py`)
- [ ] Agent-Datei (`*_agent.py`)
- [ ] Prompt (optional)
- [ ] Registry-Export (`agents/__init__.py`)
- [ ] Service (Backend)
- [ ] Router + DI
- [ ] Contract (optional)
- [ ] Agent-Tests (TestModel)
- [ ] Service-Tests
- [ ] Integration-Tests
- [ ] i18n-Keys (bei UI)
- [ ] Doc-Gate: Feature-Dokumentation
