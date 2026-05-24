---
id: CR-08-NTH
title: "Nice-to-Have Improvements (Cost, Retry, Model Registry)"
status: proposed
area: platform
mvp: false
---

# CR-08-NTH — Nice-to-Have Improvements

> **Spec for 3 low-priority improvements from CR-08 audit.**
> Review and approve before implementation begins.

---

## Overview

Three improvements from the CR-08 audit that are architecturally valuable
but not urgent. Each addresses a different area of technical debt:

| ID | Area | Current State | Target State | Risk if not done |
|----|------|--------------|--------------|------------------|
| NTH-01 | Cost Estimation | Blended $3/1M rate, single formula | Per-provider & per-model rates | Incorrect cost signals |
| NTH-02 | Retry Config | Hardcoded `RetryConfig` constants | Environment-variable override | Cannot tune without code change |
| NTH-03 | Model Registry | Manual model list in 4 provider files | Semi-automated or documented process | Registry drifts from reality |

---

## NTH-01: Per-Provider Cost Estimation via models.dev

### Current State

`TokenUsage.cost_estimate_usd` in `packages/core/narrare_core/llm/result.py`:
```python
@property
def cost_estimate_usd(self) -> float:
    return self.total_tokens * 0.000003  # $3 per 1M tokens blended
```

This is a blended approximation. Real costs differ by provider and model
by more than 10×:
- GPT-4o: ~$2.50/1M input + $10/1M output
- Claude Sonnet 4.5: ~$3/1M input + $15/1M output
- Ollama local: $0
- o3-mini: $1.10/1M input + $4.40/1M output

### Proposed Solution

**Data source: [models.dev](https://models.dev) | [GitHub](https://github.com/anomalyco/models.dev)**

models.dev ist eine community-gepflegte, open-source Datenbank aller relevanten
AI-Modelle. Sie enthält pro Modell:
- Exakte Preise (input, output, cache_read, cache_write, reasoning per 1M tokens)
- Limits (context, input, output tokens)
- Modalities, Capabilities
- Provider-Zuordnung

**API-Endpunkt:** `https://models.dev/api.json` (2MB JSON, ~3.851 Commits im GitHub-Repo)

Option A — **Models.dev Local Cache (empfohlen)**

1. `packages/core/narrare_core/llm/cost_rates.py` (NEU):
   - Lädt `models.dev/api.json` (oder lokalen Cache) als Preis-Quelle
   - Extrahiert per-model rates: `{model_id: {"input": float, "output": float, ...}}`
   - Fallback-Dict für Modelle die nicht in models.dev sind
   - Cache-Datei in `~/.narrare/cache/models_cache.json` mit TTL (24h)

2. `TokenUsage` erhält `provider: str` und `model: str` Felder.
   `cost_estimate_usd` wird zu:
   ```python
   @property
   def cost_estimate_usd(self) -> float:
       rates = get_rates_for_model(self.provider, self.model)
       if rates is None:
           return 0.0  # unbekanntes Modell → free (lokale Modelle)
       return (self.prompt_tokens * rates["input"] / 1_000_000
             + self.completion_tokens * rates["output"] / 1_000_000)
   ```

3. Die `gateway.py` propagiert `provider_name` und `model_id` an `TokenUsage`.

4. **Operator-Override**: `NARRARE_COST_RATES_JSON` (bereits in config.py)
   überschreibt models.dev-Werte (für Partnerrabatte, self-hosted).

Option B — **Nur Env-Var (ohne models.dev)**

`NARRARE_COST_RATES_JSON` als einzige Quelle. Operator muss Preise manuell pflegen.

**Empfehlung: A** — models.dev ist die perfekte Quelle. Aktuell, community-gepflegt,
deckt alle Provider ab. Die 24h-Cache-TTL verhindert übermässige API-Aufrufe.

### Files affected

- `packages/core/narrare_core/llm/cost_rates.py` — NEU: models.dev fetcher + cache
- `packages/core/narrare_core/llm/result.py` — TokenUsage: new fields, new calc
- `packages/core/narrare_core/llm/gateway.py` — Pass provider + model to TokenUsage
- `apps/api/narrare/_app/config.py` — NARRARE_COST_RATES_JSON bereits vorhanden
- Tests

### Definition of Done

- [ ] `cost_rates.py` lädt models.dev API + lokaler Cache + Fallback
- [ ] `TokenUsage` hat `provider: str` und `model: str` Felder
- [ ] `cost_estimate_usd` verwendet per-model Raten aus models.dev
- [ ] `gateway.py` propagiert provider + model
- [ ] `NARRARE_COST_RATES_JSON` überschreibt models.dev-Werte
- [ ] Tests: Cache-Treffer, Cache-Fehler, unbekanntes Modell, Env-Var-Override

---

## NTH-02: Retry Config als Env-Vars

### Current State

`retry.py:64-68`:
```python
DEFAULT_RETRY = RetryConfig(max_attempts=3, base_delay=1.0)
FAST_RETRY = RetryConfig(max_attempts=2, base_delay=0.5)
PATIENT_RETRY = RetryConfig(max_attempts=5, base_delay=2.0)
NO_RETRY = RetryConfig(max_attempts=1)
```

Nicht überschreibbar ohne Code-Änderung.

### Proposed Solution

Option A — **Core-seitige Env-Var-Override (empfohlen)**

`RetryConfig` erhält ein `@classmethod from_env()` das optional Env-Vars
liest — aber ohne `os.getenv` direkt im Core. Stattdessen über
ein einfaches `Settings`-Protokoll:

```python
from dataclasses import dataclass
from os import environ

@dataclass(frozen=True, slots=True)
class RetryConfig:
    max_attempts: int
    base_delay: float = 1.0
    max_delay: float = 60.0
    jitter: bool = True

    @classmethod
    def from_env(cls, prefix: str = "NARRARE_RETRY_") -> RetryConfig:
        """Create from env vars with fallback to defaults."""
        env = environ.get
        return cls(
            max_attempts=int(env(f"{prefix}MAX_ATTEMPTS", str(cls.max_attempts))),
            base_delay=float(env(f"{prefix}BASE_DELAY", str(cls.base_delay))),
            max_delay=float(env(f"{prefix}MAX_DELAY", str(cls.max_delay))),
            jitter=env(f"{prefix}JITTER", "true").lower() == "true",
        )
```

Die Modul-Konstanten `DEFAULT_RETRY` etc. bleiben als echte Constants,
werden aber nicht mehr direkt in `with_retry` verwendet (dort wird
per `from_env()` geladen).

Option B — **Nur in config.py abbilden**

`Settings` bekommt retry-Felder, `dependencies.py` injected sie.

**Empfehlung: A** — Minimaler Core-Change, funktioniert auch ohne FastAPI
(für MCP/CLI).

### Files affected

- `packages/core/narrare_core/llm/retry.py` — `from_env()` method
- Caller: `apps/api/narrare/writing/deps.py` (injects retry config)
- Caller: `packages/core/narrare_core/llm/gateway.py` (uses retry config)

### Definition of Done

- [ ] `RetryConfig.from_env()` Methode existiert
- [ ] Module-Level-Konstanten bleiben als echte Defaults
- [ ] `with_retry()` verwendet `from_env()` wenn kein explizites config übergeben
- [ ] Tests für env-var override
- [ ] Environment-Vars in `.env.example` dokumentiert

---

## NTH-03: Model Registry Validierung via models.dev

### Current State

4 `_providers/*.py` Dateien mit manuell gepflegten Modell-IDs:

| File | Models |
|------|--------|
| `_providers/openai.py` | gpt-4o, gpt-4o-mini, gpt-4-turbo, gpt-3.5-turbo, o1-preview, o1-mini, o3-mini, text-embedding-3-small |
| `_providers/anthropic.py` | claude-sonnet-4-5-20251020, claude-haiku-3-5-20241022, claude-opus-4-20250514 |
| `_providers/others.py` | gemini-2.0-flash, gemini-1.5-pro, gemini-1.5-flash, mixtral-8x7b-32768, llama-3.3-70b-versatile |
| `_providers/ollama.py` | ollama (dummy key) |

Diese Listen müssen manuell aktualisiert werden, wenn neue Modelle
erscheinen. Für Ollama ist das akzeptabel (User pullt eigene Modelle),
aber für OpenAI/Anthropic geraten die Listen schnell in Rückstand.

### Proposed Solution

**Data source: [models.dev](https://models.dev) — `https://models.dev/api.json`**

models.dev ist die ideale Quelle für die Modell-Validierung. Es listet alle
relevanten Modelle mit ihren IDs (die mit unseren `model_id` Werten übereinstimmen),
Provider-Zuordnung, Limits, und Preisen.

Option A — **CI-Validierung gegen models.dev (empfohlen)**

1. **CI-Job (`scripts/check_model_registry.py`)**:
   - Lädt `https://models.dev/api.json` (oder verwendet den NTH-01 Cache)
   - Extrahiert alle Model-IDs pro Provider (z.B. alle "openai/gpt-*" IDs)
   - Vergleicht mit den registrierten Modellen in `_providers/*.py`
   - **Warnung**: Wenn Modelle in models.dev existieren, die nicht in unserer Registry sind
   - **Warnung**: Wenn Modelle in unserer Registry deprecated sind (status="deprecated")
   - **Info**: Neue Modelle seit letztem Check (differenzbasiert)

2. **Ausgabeformat** (als CI-Annotation):
   ```
   ⚠️ MODELS.DEV: OpenAI hat 3 neue Modelle: gpt-5, gpt-4.1, o4-mini
   ⚠️ MODELS.DEV: Anthropic Claude 3 Haiku ist deprecated → ggf. aus Registry entfernen
   ```

3. **Häufigkeit**: Wöchentlich via `workflow_dispatch` oder scheduled CI.

4. **Synergie mit NTH-01**: Der models.dev Cache wird von beiden Features
   genutzt — einmal fetchen, zweimal nutzen (Preise + Registry-Validierung).

Option B — **Automatischer Registry-Import**

Erweiterte Version: CI-Job erstellt automatisch einen PR mit neuen Modell-IDs
die noch nicht in der Registry sind. Der Developer muss nur mergen.

**Empfehlung: A** — Niedrigerer Aufwand, keine automatischen PRs die manuell
geprüft werden müssen. Zusammen mit NTH-01 teilen sich beide den models.dev-Cache.

### Files affected

- `packages/core/narrare_core/llm/_providers/openai.py` — Header-Datum
- `packages/core/narrare_core/llm/_providers/anthropic.py` — Header-Datum
- `packages/core/narrare_core/llm/_providers/others.py` — Header-Datum
- `docs/maintenance/model-registry.md` — Neue Wartungs-Doku
- `scripts/check_model_registry_age.py` — CI-Prüfskript

### Definition of Done

- [ ] Jede Provider-Datei hat Header-Kommentar mit `# Last updated: YYYY-MM-DD`
- [ ] `docs/maintenance/model-registry.md` existiert mit Update-Anleitung
- [ ] CI-Warning bei >90 Tage alten Registrys
- [ ] Keine Änderung an der Registry-Logik

---

## Synergie-Effekt

NTH-01 und NTH-03 teilen sich die models.dev Integration:

```
models.dev/api.json
       ↓
  [Local Cache] ← 24h TTL / manuell via UI
       ↓
  ┌── NTH-01: cost_rates.py (Preise pro Modell)
  ├── NTH-03: models_validator.py (Registry-Vergleich)
  └── UI: "Refresh Model Data" Button
```

Ein Fetch, drei Consumer. Der Cache reduziert API-Aufrufe auf 1x/Tag
plus manuelle Refresh-Requests.

### Manueller Refresh via UI

In der Settings-Sektion (Settings → Model Configuration) wird ein Button
**"Refresh Model Data"** eingefügt:

- **Platzierung**: In der Model Configuration Tab (SET-003), unterhalb der
  Provider-Liste, oder separater Tab "Model Data"
- **Aktion**: POST `/api/v1/settings/models/refresh`
- **Backend**: Invalidiert den models.dev Cache und fetcht neu
- **Feedback**: Spinner während des Fetch, Erfolgsmeldung mit Diff
  ("3 neue Modelle, 2 deprecated")
- **Fehlerbehandlung**: Bei Netzwerkfehler → Meldung "Could not reach models.dev.
  Data from [Datum] still in use."
- **Cache-Age-Anzeige**: Kleines Label "Model data: updated 3 hours ago"
  neben dem Button, grau wenn aktuell, gelb wenn >7 Tage alt

## Implementation Order

```
NTH-02 (Retry Config) → NTH-01 + NTH-03 (models.dev Integration)
```

Begründung: NTH-02 ist der kleinste Change (ein `from_env()` in einer Datei).
NTH-01 und NTH-03 teilen sich die models.dev-Infrastruktur und sollten zusammen
implementiert werden — erst den Fetcher/Cache, dann Cost Estimation und
Registry-Validierung als zwei Consumer des gleichen Datensatzes.

---

## Status & History

- `2026-05-24` — Spec created from CR-08 audit findings
- `2026-05-24` — NTH-03 überarbeitet: models.dev als Datenquelle statt manuelle CI-Prüfung.
  Synergie mit NTH-01: geteilter Cache und API-Call.
