# Adaptive Context + Dialogue Coach — Design Spec

**Date:** 2026-07-19
**Status:** Brainstorming-Output (awaiting Architecture-Specialist ADR)
**Owner:** Narrare Dev Coordinator
**Related Features:** LEARN-002 (recalibrated), ASSIST-004 (in-progress)
**Related ADRs:** TBD-XXX (pending — siehe §11)

---

## Table of Contents

- [1. Context](#1-context)
- [2. Approach Decision](#2-approach-decision)
- [3. Architektur-Überblick](#3-architektur-ueberblick)
- [4. IST-Stand Adaptivität](#4-ist-stand-adaptivitaet)
- [5. Adaptivitäts-Contract](#5-adaptivitaets-contract)
- [6. ASSIST-004 Dialogue Coach](#6-assist-004-dialogue-coach)
- [7. LEARN-002 Recalibration](#7-learn-002-recalibration)
- [8. Frontend / UX-Integration](#8-frontend--ux-integration)
- [9. Testing-Strategie](#9-testing-strategie)
- [10. Edge Cases](#10-edge-cases)
- [11. ADR-Strategie](#11-adr-strategie)
- [12. Implementation Order](#12-implementation-order)
- [13. Offene Architektur-Fragen für Architecture-Specialist](#13-offene-architektur-fragen-fuer-architecture-specialist)
- [14. Skills bei Umsetzung](#14-skills-bei-umsetzung)
- [15. Related ADRs](#15-related-adrs)
- [16. Glossary](#16-glossary)
- [17. Status & History](#17-status--history)

---

## 1. Context

### 1.1 Warum dieses Feature jetzt

Das Narrare-Roadmap hat viele spezifizierte, aber nicht realisierte Features. Der User hat in der Brainstorming-Session klar gestellt, dass er zwei Bereiche konkret angehen will: **Adaptivity** (die KI passt sich dem Schreibstil des Autors an) und **Analysis** (die KI hilft, Dialoge und Text gezielt zu analysieren und zu verbessern).

Aus der Sichtung der Roadmap ergab sich:

- `docs/features/learning/LEARN-002-style-adaptation.md` beschreibt eine statistische Voice-Pipeline (Satzlängen, Vokabular, Dialog-Ratio). Diese Spec ist **konzeptionell überholt** — sie konfligiert mit `ANAL-007` (Author Voice Profiling) und der existierenden `PreferenceProfile`-Infrastruktur aus `LEARN-001`.
- `docs/features/ai_assist/ASSIST-004-dialogue-coach.md` ist als Planned-Feature vorhanden, hat aber nur eine grobe Skizze (Analyse + Improve). Die technischen Details fehlen komplett.
- Die Adaptivitäts-Infrastruktur (PreferenceProfile, CharacterVoiceProfile, ProfileProvider, PromptContext-Felder) ist **bereits implementiert** — aber nie durch einen konkreten Consumer sichtbar gemacht worden.

Die Brainstorming-Session hat drei Ansätze evaluiert und sich für **Approach 3** entschieden (siehe §2).

### 1.2 Projekt-Status

Stand Juli 2026 (siehe `docs/_shared/CURRENT_STATE.md`):

- **Phase 6 — Post-MVP Features** ⏳ IN PROGRESS
- Backend: 20 Domain-Module, 20 AI-Agents (pydantic-ai), Alembic-Migrationen 0001–0030
- Frontend: Next.js 16 App Router, TipTap v3 Editor, TanStack Query + Zustand, 3 Lokales (en/de/fr)
- **Voice Vertical bereits komplett:**
  - `ANAL-008` Character Voice Profiling → `stable` (ADR-055)
  - `WRITE-010` Voice Consistency Checker → `stable` (ADR-057)
- **Adoptivitäts-Infrastruktur bereits vorhanden:**
  - `PreferenceProfile` (LEARN-001) → `stable`
  - `PreferenceContextEnricherImpl` (ADR-038) → `stable`
  - `ProjectWritingProfile` (ADR-040) → `stable`
  - `LLMIntent.VOICE` ist routeable (ADR-055)
- 71 Tasks aus vorherigen Phasen erledigt, `just check` 9/9 grün
- **AI Feature Freeze** aufgehoben seit 2026-06-03 (INFRA-011/ADR-027); neue AI-Features unter ratcheted Governance möglich

### 1.3 Warum ist das eine gute Gelegenheit?

Die Voice-Infrastruktur ist fertig, aber kein User-Feature zeigt ihren Wert. Mit **ASSIST-004 als Pilot-Consumer** der Adaptivität und **LEARN-002 als Visualisierung/Steuerung** ergibt sich ein kohärenter vertikaler Slice, der:

1. Den Wert der vorhandenen Infrastruktur sichtbar macht
2. Einen concrete pilot consumer für den neuen `AdaptiveContext`-Contract schafft
3. Die `LEARN-002`-Spec von einer unrealistischen statistischen Pipeline auf eine realistische Visualisierungs- und Steuerungs-Oberfläche umlenkt
4. Nebeneffekte hat: `style_constraints` und `avoidance_patterns` werden erstmals echt befüllt (derzeit immer leer)

---

## 2. Approach Decision

### 2.1 Drei Ansätze

| Ansatz | Beschreibung | Bewertung |
|--------|--------------|-----------|
| **Approach 1** | LEARN-002 full spec umsetzen (statistische Voice-Pipeline mit Satzlängen-Verteilung, Vokabular-Diversity, Few-Shot-Prompting) | ❌ Zu groß, konfligiert mit `ANAL-007` (Author Voice Profiling), eigentlicher User-Wert (Adaptivität spürbar machen) käme zu kurz |
| **Approach 2** | Nur Adaptivitäts-Contract bauen, ohne Pilot-Consumer — also nur Core-Erweiterung | ❌ Abstraktion ohne Consumer ist Spekulation; violates RULE-20 (no half-implementations). Wert bleibt unsichtbar |
| **Approach 3** (chosen) | Adaptivitäts-Contract + ASSIST-004 als Pilot-Consumer + LEARN-002 recalibrated als Visualisierung/Steuerung | ✅ Vollständiger Vertical Slice mit concrete consumer;每一 Komponente hat einen echten Zweck; jede Inkrement liefert echten User-Wert |

### 2.2 Approach 3 — "Writers Stimme, sauber getrennt"

Der Ansatz trennt drei Belange sauber:

```
┌─────────────────────────────────────────────────────────────────┐
│  (1) Adaptivity-Contract (Core)                                  │
│      — Definiert WAS adaptiv ist (AdaptiveContext)               │
│      — Definiert WIE es in Prompts injiziert wird (Enricher)     │
│      — Ist consumer-agnostic                                      │
└──────────────────────────┬──────────────────────────────────────┘
                           │ consumes
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  (2) ASSIST-004 — Dialogue Coach (Pilot Consumer)                │
│      — Erste konkrete AI-Operation, die Adaptivität nutzt        │
│      — Nutzt PreferenceProfile + CharacterVoiceProfile            │
│      — Liefert structured Feedback + Alternativen                │
└──────────────────────────┬──────────────────────────────────────┘
                           │ makes visible
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  (3) LEARN-002 recalibrated — Adaptive Dashboard                 │
│      — Macht Adaptivität sichtbar, steuerbar, transparent        │
│      — Settings-UI: Preferences ansehen, Weights einstellen      │
│      — Status-Indikator im Editor: "AI passt sich an"            │
└─────────────────────────────────────────────────────────────────┘
```

### 2.3 Was NICHT in diesem Design ist

Explizit ausgeschlossen:

- **ANAL-007 (Author Voice Profiling)** — bleibt `planned`; ist ein separates Feature mit anderem Scope (ganzer Roman vs. Per-Invocation).
- **ANAL-009 (Voice Drift Detection)** — bleibt `planned`; benötigt ANAL-007.
- **Neue SSOT für Style-Profile** — `PreferenceProfile` (LEARN-001) und `CharacterVoiceProfile` (ANAL-008) sind die beiden Quellen; es wird **keine** dritte Tabelle eingeführt.
- **Statistische Voice-Pipeline aus alter LEARN-002-Spec** — Satzlängenverteilung, Vokabular-Diversity, Few-Shot-Prompting etc. werden **nicht** gebaut. Die alte Spec wird recalibrated (siehe §7), nicht superseded.
- **Voice Metrics für Generation** — `voice_metrics` (ADR-057) bleiben **checking-path only**. Sie werden **nicht** in die Generation injiziert. Das ist eine harte Constraint aus ADR-057/055.
- **Eigenes Memory-Backend** — mem0 bleibt die Memory-Infrastruktur (ADR-033).

---

## 3. Architektur-Überblick

### 3.1 Drei Komponenten mit Dependency-Graph

```
                        ┌──────────────────────────────────────┐
                        │     Adaptivitäts-Contract (Core)      │
                        │  ───────────────────────────────────  │
                        │  • AdaptiveContext (dataclass)        │
                        │  • AdaptiveWeights (dataclass)        │
                        │  • AdaptiveContextProvider (Protocol) │
                        │  • AdaptiveContextEnricher            │
                        │  • AdaptiveSettings (dataclass)       │
                        │                                       │
                        │  Home: packages/core/narrare_core/    │
                        │        ai_invocation/                  │
                        └──────┬───────────────────┬────────────┘
                               │                   │
                               │ consumed by       │ visualized by
                               │                   │
                ┌──────────────▼─────┐    ┌────────▼──────────────────┐
                │  ASSIST-004        │    │  LEARN-002 (recalibrated) │
                │  Dialogue Coach    │    │  Adaptive Dashboard       │
                │  ─────────────     │    │  ─────────────────        │
                │  • DialogueCoach   │    │  • AdaptiveContextView    │
                │    Agent           │    │  • Weight Controls         │
                │  • ai_assist/      │    │  • Status Indikator        │
                │    domain          │    │  • Snapshot-History        │
                │  • SSE Streaming   │    │                            │
                │  • Editor UI       │    │  Home: apps/api/narrare/   │
                │                    │    │        adaptive/ +         │
                │  Home:             │    │        packages/web/       │
                │  apps/api/narrare/ │    │        settings/adaptive/  │
                │  ai_assist/        │    │                            │
                │  + core/agents/    │    │                            │
                │  + prompts/        │    │                            │
                └────────────────────┘    └───────────────────────────┘
```

### 3.2 Profile Sources (bereits existent — keine neue SSOT)

| Source | Typ | Owner | Wo | Wann befüllt |
|--------|-----|-------|----|--------------|
| `PreferenceProfile` | User-Präferenzen (Style, Content, Constraints) | LEARN-001 (Feedback-Loop) | `packages/core/narrare_core/memory/models.py` | Wenn User AI-Vorschläge annimmt/ablehnt/modifiziert (FeedbackEvent → PreferenceService) |
| `CharacterVoiceProfile` | Per-Character Voice (speech_summary, voice_metrics) | ANAL-008 + WRITE-010 | `packages/core/narrare_core/profiles/models.py` | Durch `LLMIntent.VOICE` (ANAL-008) und `voice_check` (WRITE-010) |
| `ProjectWritingProfile` | Konsolidierte Sicht (genre, tone, style, voices) | ADR-040 | `packages/core/narrare_core/profiles/models.py` | Wird at runtime assembliert (`profiles/assembly.py`) |

**Beide Quellen existieren bereits** — Adaptivität fügt keine neue SSOT hinzu, sondern **konsolidiert** sie zu einem `AdaptiveContext`.

### 3.3 Module Homes

| Komponente | Module Home | Begründung |
|-----------|-------------|------------|
| `AdaptiveContext` + `AdaptiveWeights` (dataclass) | `packages/core/narrare_core/ai_invocation/adaptive_context.py` | Gehört zur AI-Invocation-Infrastruktur (ADR-038) |
| `AdaptiveContextProvider` (Protocol) | `packages/core/narrare_core/ai_invocation/contracts.py` (erweitern) | ProfileProvider lebt auch hier (Zeile 140) |
| `AdaptiveContextEnricher` | `packages/core/narrare_core/ai_invocation/enrichers/adaptive.py` (neue Datei) | Gleiche Ebene wie `preferences.py`, `kb_suggested.py`, `consistency.py` |
| `AdaptiveSettings` (Core dataclass) | `packages/core/narrare_core/ai_invocation/adaptive_context.py` (gleiche Datei) | Immutables Value-Object, lebt nah an AdaptiveContext |
| `AdaptiveContextService` (Backend) | `apps/api/narrare/adaptive/` (neue Domain) | Neue Domain, weil eigene Endpunkte + Settings-Persistenz |
| `DialogueCoachAgent` | `packages/core/narrare_core/agents/dialogue_coach_agent.py` | Folgt Agent-Convention (`*_agent.py`) — ADR-015 |
| Dialogue Coach Service + Router | `apps/api/narrare/ai_assist/` (neue Domain) | Laut ASSIST-004-Spec domain `ai_assist/` |
| Dialogue Coach Prompts | `packages/core/narrare_core/prompts/_bundled/ai_assist/en/dialogue_coach/system.md` | Folgt ADR-002 Prompt-Cascade |
| Dialogue Coach Frontend | `packages/web/components/analysis/dialogue-coach/` | Erweitert vorhandene Analysis-Panel-Struktur |
| Adaptive Dashboard (LEARN-002) | `packages/web/components/studio/settings/AdaptiveDashboard.tsx` + `apps/api/narrare/adaptive/` | Settings-Bereich |

---

## 4. IST-Stand Adaptivität

### 4.1 Bereits implementiert (nutzbar)

| Komponente | Pfad | Status |
|-----------|------|--------|
| `PromptContext.user_preferences` | `packages/core/narrare_core/prompts/context.py:143` | ✅ Feld existiert, wird durch `as_variables()` als `{{user_preferences}}` im Template verfügbar |
| `PromptContext.style_constraints` | `packages/core/narrare_core/prompts/context.py:145` | ✅ Feld existiert; wird als `{{style_constraints}}` registriert |
| `PromptContext.avoidance_patterns` | `packages/core/narrare_core/prompts/context.py:144` | ✅ Feld existiert; wird als `{{avoidance_patterns}}` registriert |
| `PromptContext.character_voice_profiles` | `packages/core/narrare_core/prompts/context.py:140` | ✅ Feld existiert; wird als `{{character_voice_profiles}}` registriert |
| `PreferenceContextEnricherImpl` | `packages/core/narrare_core/ai_invocation/enrichers/preferences.py` | ✅ Implementiert (ADR-038); lädt `PreferenceProfile.to_prompt_text()` in `dynamic_inputs["user_preferences"]` |
| `PreferenceProfile.to_prompt_text()` | `packages/core/narrare_core/memory/models.py:66` | ✅ Implementiert; liefert formatierten Markdown-Block |
| `ProjectWritingProfile` (consolidated view) | `packages/core/narrare_core/profiles/models.py:35` | ✅ Implementiert (ADR-040); liefert `formatted_voice_profiles` |
| `ProfileProvider` Protocol | `packages/core/narrare_core/ai_invocation/contracts.py:140` | ✅ Implementiert; lädt ProjectWritingProfile per `project_id` |
| `formatted_voice_profiles` property | `packages/core/narrare_core/profiles/models.py:55` | ✅ Implementiert; formatiert Voice-Profile als Textblock |
| `voice_metrics` (ADR-057) | `packages/core/narrare_core/profiles/models.py:32` | ✅ Existiert; **checking-path only** — wird nicht in Generation injiziert |
| `{{user_preferences}}` Variable | `packages/core/narrare_core/prompts/variable_registry.py:94` | ✅ In `SYSTEM_VARS` registriert |
| `{{style_constraints}}` Variable | `packages/core/narrare_core/prompts/variable_registry.py:96` | ✅ In `SYSTEM_VARS` registriert |
| `{{avoidance_patterns}}` Variable | `packages/core/narrare_core/prompts/variable_registry.py:95` | ✅ In `SYSTEM_VARS` registriert |
| `{{character_voice_profiles}}` Variable | `packages/core/narrare_core/prompts/variable_registry.py:99` | ✅ In `SYSTEM_VARS` registriert |

### 4.2 Was NICHT da ist (Lücken, die dieses Design schließt)

| Lücke | Akteller Zustand | Wird gelöst durch |
|-------|------------------|-------------------|
| `style_constraints` und `avoidance_patterns` werden **nie** befüllt | Felder existieren, bleiben aber leer — kein Enricher schreibt hinein | `AdaptiveContextEnricher` leitet sie aus `PreferenceProfile.constraints` und `FeedbackEvent`-Modifier-Daten ab |
| Keine **strukturierte Sicht** auf alle Adaptivitäts-Signale | Man müsste aus `PreferenceProfile`, `CharacterVoiceProfile`, `ProjectWritingProfile` manuell aggregieren | `AdaptiveContext` als konsolidiertes Value-Object |
| Keine **Steuerungs-API** für User | User kann Weights (Preference vs. Voice) nicht einstellen | `AdaptiveContextService` mit `POST /api/v1/adaptive/weights` |
| Kein **AdaptiveContextProvider** Interface | ProfileProvider liefert ProjectWritingProfile, aber keine konsolidierte adaptive Sicht | Neues Protocol in `ai_invocation/contracts.py` |
| Keine **Sichtbarkeit im Editor** | User weiß nicht, ob/wie Adaptivität gerade aktiv ist | Status-Indikator (LEARN-002) |
| Keine **User-kontrollierbare Aktivierung** | Adaptivität ist implizit an oder aus | `AdaptiveSettings.enabled` (togglebar via API) |
| Kein **Pilot-Consumer**, der den Wert demonstriert | Adaptivität ist theoretisch da, aber kein Feature nutzt sie explizit | ASSIST-004 nutzt `AdaptiveContext` für Voice-Fidelity-Scoring |

### 4.3 Lessons aus der Voice-Vertical (ANAL-008, WRITE-010)

Aus der Voice-Vertical haben wir gelernt:

1. **Hybrid Deterministic + LLM** (ADR-021) funktioniert — für Voice-Check und Adaptivitäts-Scoring
2. **Self-contained dialogue attribution** ist besser als Coreference-Coupling
3. **voice_metrics dürfen NIE in Generation landen** — harte Constraint aus ADR-055/057
4. **Runtime-evidence-aware commit gate** (ADR-056) setzt durch, dass Features nicht nur spezifiziert sondern auch adopted sind

Dieses Design respektiert alle vier Lessons und baut auf ihnen auf.

---

## 5. Adaptivitäts-Contract

### 5.1 Neue Core-Datenmodelle

**Datei:** `packages/core/narrare_core/ai_invocation/adaptive_context.py` (neu)

```python
"""Adaptive Context — konsolidierte Sicht aller Adaptivitäts-Signale.

Definiert die Core-Datenmodelle für Adaptivität:
- ``AdaptiveWeights``: User-einstellbare Gewichtung der Signalquellen.
- ``AdaptiveContext``: Konsolidierter Snapshot aller adaptiven Daten
  für eine spezifische AI-Invocation.
- ``AdaptiveSettings``: Persistierte User-Settings (aktiviert, weights).

Siehe ADR-TBD (Adaptive Context + Dialogue Coach Vertical) und
CONSTRAINTS.md RULE-03 (Contracts first).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID


@dataclass(frozen=True, slots=True)
class AdaptiveWeights:
    """User-einstellbare Gewichtung der Adaptivitäts-Signale.

    Alle Werte sind Floats im Bereich [0.0, 1.0].
    Die exakte Semantik wird durch den AdaptiveContextEnricher bestimmt;
    typischerweise steuert ein höheres Weight, wie stark das jeweilige
    Signal in den Prompt injiziert wird (z.B. als explizite Instruktion
    oder als Kontext-Block).

    Attribute:
        preference: Gewicht für User-Präferenzen (PreferenceProfile).
            Default 0.7 — Präferenzen sind primär.
        voice_fidelity: Gewicht für Character-Voice-Fidelity (CharacterVoiceProfile).
            Default 0.9 — Voice-Fidelity ist kritisch für Dialogue Coach.
        style_constraints: Gewicht für harte Stil-Constraints.
            Default 1.0 — Constraints sind verbindlich.
        avoidance: Gewicht für Avoidance-Patterns (Dinge, die der User ablehnt).
            Default 1.0 — Avoidance ist verbindlich.
    """

    preference: float = 0.7
    voice_fidelity: float = 0.9
    style_constraints: float = 1.0
    avoidance: float = 1.0

    def validated(self) -> "AdaptiveWeights":
        """Gibt eine Kopie mit ge-clampten Werten [0.0, 1.0] zurück."""
        return AdaptiveWeights(
            preference=max(0.0, min(1.0, self.preference)),
            voice_fidelity=max(0.0, min(1.0, self.voice_fidelity)),
            style_constraints=max(0.0, min(1.0, self.style_constraints)),
            avoidance=max(0.0, min(1.0, self.avoidance)),
        )


@dataclass(frozen=True, slots=True)
class AdaptiveContext:
    """Konsolidierter Snapshot aller adaptiven Signale für eine Invocation.

    Wird vom ``AdaptiveContextProvider`` assembliert und vom
    ``AdaptiveContextEnricher`` in ``dynamic_inputs`` injiziert.
    Enthält keine Prompts — nur strukturierte Daten.

    Attribute:
        user_id: Die User-ID, für die der Kontext gilt.
        project_id: Die Project-ID, für die der Kontext gilt.
        preference_text: Formatierter Text aus PreferenceProfile (kann leer sein).
        voice_profiles_text: Formatierter Text aller CharacterVoiceProfiles (kann leer sein).
        style_constraints_text: Abgeleitete Stil-Constraints als Bullet-Liste.
        avoidance_patterns_text: Abgeleitete Avoidance-Patterns als Bullet-Liste.
        weights: Die zum Zeitpunkt der Invocation aktiven Weights.
        source_summary: Kurze, human-readable Zusammenfassung der Quellen
            (z.B. "3 character voices, 12 preference events"). Wird für
            Transparenz-UI und Logging verwendet.
    """

    user_id: UUID
    project_id: UUID
    preference_text: str = ""
    voice_profiles_text: str = ""
    style_constraints_text: str = ""
    avoidance_patterns_text: str = ""
    weights: AdaptiveWeights = field(default_factory=AdaptiveWeights)
    source_summary: str = ""

    @property
    def has_any_signal(self) -> bool:
        """True, wenn mindestens ein adaptives Signal vorhanden ist."""
        return bool(
            self.preference_text
            or self.voice_profiles_text
            or self.style_constraints_text
            or self.avoidance_patterns_text
        )


@dataclass(frozen=True, slots=True)
class AdaptiveSettings:
    """Persistierte User-Settings für Adaptivität.

    Diese Werte werden pro User (oder pro Project, siehe Q-A2) gespeichert
    und kontrollieren, ob und wie Adaptivität aktiv ist.

    Attribute:
        enabled: Master-Schalter. Wenn False, wird AdaptiveContext nicht
            assembliert und keine adaptiven Variablen werden injiziert.
        weights: Aktive Weight-Konfiguration.
    """

    enabled: bool = True
    weights: AdaptiveWeights = field(default_factory=AdaptiveWeights)
```

### 5.2 AdaptiveContextProvider Protocol

**Datei:** `packages/core/narrare_core/ai_invocation/contracts.py` (erweitern — anfügen)

```python
class AdaptiveContextProvider(Protocol):
    """Assembliert einen ``AdaptiveContext`` für eine AI-Invocation.

    Konsolidiert Daten aus:
    - ``PreferenceProfile`` (LEARN-001 / ADR-033 / mem0)
    - ``ProjectWritingProfile`` (ADR-040; enthält CharacterVoiceProfiles)
    - ``AdaptiveSettings`` (User-Settings)

    Der Provider ist **consumer-agnostic** — er weiß nicht, welche AI-Operation
    die Daten konsumiert. Consumer-spezifische Logik (z.B. Voice-Fidelity-
    Scoring für Dialogue Coach) gehört in den jeweiligen Service oder Agent.

    Implementierungen dürfen I/O machen (mem0, DB) und sollen graceful
    degradieren (D7 aus ADR-038): bei fehlenden Daten wird ein
    ``AdaptiveContext`` mit leeren Strings, aber korrekten IDs zurückgegeben.

    See:
        ADR-TBD (Adaptive Context + Dialogue Coach Vertical).
    """

    async def get_context(
        self,
        user_id: UUID,
        project_id: UUID,
    ) -> AdaptiveContext:
        """Liefere den konsolidierten AdaptiveContext für user+project.

        Args:
            user_id: Die User-ID.
            project_id: Die Project-ID.

        Returns:
            Einen AdaptiveContext. Auch wenn keine Preferences oder Voice-
            Profiles vorhanden sind, wird ein gültiges Objekt mit leeren
            Feldern zurückgegeben (graceful degradation).
        """
        ...

    async def get_settings(
        self,
        user_id: UUID,
        project_id: UUID,
    ) -> AdaptiveSettings:
        """Lade die persistierten AdaptiveSettings.

        Returns:
            Die gespeicherten Settings, oder Default-Settings falls keine
            gespeichert sind.
        """
        ...
```

### 5.3 AdaptiveContextEnricher

**Datei:** `packages/core/narrare_core/ai_invocation/enrichers/adaptive.py` (neu)

Dieser Enricher ist das Bindeglied zwischen Provider und Prompt-Variablen. Er ersetzt die bisher leeren `style_constraints` und `avoidance_patterns` durch echte Werte und sorgt dafür, dass die `AdaptiveContext`-Daten in `dynamic_inputs` landen.

Drei architektonische Optionen, wie er sich zu `PreferenceContextEnricherImpl` verhält (Architecture-Specialist entscheidet — siehe Q-A1):

#### Option α: Parallel (beide Enricher laufen)

```
PreferenceContextEnricherImpl  → dynamic_inputs["user_preferences"]
AdaptiveContextEnricher        → dynamic_inputs["style_constraints"]
                                 dynamic_inputs["avoidance_patterns"]
                                 dynamic_inputs["character_voice_profiles"]
                                 dynamic_inputs["__adaptive_source_summary"]
```

- Pro: Minimal-invasiv; berührt existierenden Enricher nicht
- Con: Zwei Enricher für eng verwandte Daten; Provider muss Daten mehrfach liefern
- Con: Risk of drift — die beiden Enricher könnten inkonsistente Sichten haben

#### Option β: AdaptiveContextEnricher ersetzt PreferenceContextEnricherImpl

```
AdaptiveContextEnricher  → dynamic_inputs["user_preferences"]
                          dynamic_inputs["style_constraints"]
                          dynamic_inputs["avoidance_patterns"]
                          dynamic_inputs["character_voice_profiles"]
                          dynamic_inputs["__adaptive_source_summary"]
```

- Pro: Single source of truth; konsistente Sicht
- Pro: Sauberere Architektur
- Con: Breaking change — `PreferenceContextEnricherImpl` muss deprecated werden
- Con: Bestehende Adoption-Tests müssen angepasst werden

#### Option γ: Refactor — PreferenceContextEnricherImpl delegiert intern an AdaptiveContextProvider

```
PreferenceContextEnricherImpl  → fragt AdaptiveContextProvider ab
                              → schreibt user_preferences, style_constraints,
                                 avoidance_patterns, character_voice_profiles
```

- Pro: Single source of truth ohne neuen Enricher
- Pro: Bestehende Tests und Contracts bleiben erhalten
- Con: Vermischt Verantwortlichkeiten — `PreferenceContextEnricherImpl` würde Character-Voice laden, was sein Name nicht andeutet
- Con: Refactor bestehenden Codes

**Empfehlung des Brainstormings:** Option β, aber final durch Architecture-Specialist zu entscheiden (Q-A1).

#### Enricher Sketch (für β oder γ)

```python
"""Adaptive Context Enricher — injiziert AdaptiveContext in dynamic_inputs.

Implementiert das ContextEnricher-Protocol aus
:mod:`narrare_core.ai_invocation.contracts`. Konsolidiert User-Präferenzen,
Character-Voice-Profile und Adaptive-Settings in ``dynamic_inputs`` für
die Prompt-Zusammensetzung.

This is a **parallel path** to PromptComposer's preference_service
auto-injection (siehe ADR-038).

Graceful degradation (D7): Wenn der Provider None ist oder keine Daten
liefert, wird der Kontext unverändert zurückgegeben.

See:
    ADR-TBD, ADR-038, CONSTRAINTS.md RULE-03/RULE-06/RULE-11.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from narrare_core.ai_invocation.contracts import AdaptiveContextProvider
    from narrare_core.ai_invocation.models import PromptInvocationContext

logger = structlog.get_logger(__name__)


class AdaptiveContextEnricher:
    """Injiziert AdaptiveContext-Daten in dynamic_inputs.

    Schreibt in die gut bekannten Variablen:
    - ``user_preferences`` (überschreibt evtl. vorhandenen Wert)
    - ``style_constraints``
    - ``avoidance_patterns``
    - ``character_voice_profiles``
    - ``__adaptive_source_summary`` (für Transparenz-UI; führende
      ``__`` kennzeichnet Internal-Only-Variable, wird von Prompt-
      Templates nicht referenziert)

    Wenn ``AdaptiveSettings.enabled == False``, wird der Kontext
    unverändert zurückgegeben (degradiert auf nicht-adaptive Generation).

    Args:
        provider: Eine AdaptiveContextProvider-Implementierung oder None.
    """

    def __init__(self, provider: AdaptiveContextProvider | None) -> None:
        self._provider = provider

    async def enrich(self, context: PromptInvocationContext) -> PromptInvocationContext:
        """Enrich context mit adaptiven Daten."""
        if self._provider is None:
            logger.debug("adaptive_enricher_noop", reason="no_provider")
            return context

        if context.user_id is None or context.project_id is None:
            logger.debug(
                "adaptive_enricher_missing_ids",
                feature_id=context.feature_id,
            )
            return context

        try:
            adaptive = await self._provider.get_context(
                user_id=context.user_id,
                project_id=context.project_id,
            )
            settings = await self._provider.get_settings(
                user_id=context.user_id,
                project_id=context.project_id,
            )
        except Exception:
            logger.warning(
                "adaptive_enricher_provider_failed",
                feature_id=context.feature_id,
                exc_info=True,
            )
            return context

        if not settings.enabled or not adaptive.has_any_signal:
            logger.debug(
                "adaptive_enricher_skipped",
                feature_id=context.feature_id,
                enabled=settings.enabled,
                has_signal=adaptive.has_any_signal,
            )
            return context

        logger.debug(
            "adaptive_enricher_success",
            feature_id=context.feature_id,
            source_summary=adaptive.source_summary,
        )

        return context.model_copy(
            update={
                "dynamic_inputs": {
                    **context.dynamic_inputs,
                    "user_preferences": adaptive.preference_text,
                    "style_constraints": adaptive.style_constraints_text,
                    "avoidance_patterns": adaptive.avoidance_patterns_text,
                    "character_voice_profiles": adaptive.voice_profiles_text,
                    "__adaptive_source_summary": adaptive.source_summary,
                    "__adaptive_weights": settings.weights.validated(),
                },
            },
        )
```

### 5.4 Backend-Service: AdaptiveContextService

**Datei:** `apps/api/narrare/adaptive/` (neue Domain)

```
apps/api/narrare/adaptive/
├── __init__.py
├── service.py              # AdaptiveContextService
├── contracts.py            # AdaptiveContextServiceProtocol
├── schemas.py              # Pydantic-API-Modelle
├── repository.py           # Persistenz (UserSettings-Tabelle)
├── models.py               # SQLAlchemy (falls eigene Tabelle; siehe Q-A2)
├── router.py               # 3 Endpoints
├── dependencies.py         # FastAPI-DI
└── adaptive_context_provider.py  # AdaptiveContextProvider-Impl
```

#### Endpunkte

```
GET    /api/v1/adaptive/context
  → 200 AdaptiveContextResponse
  → 401 unauthorized

POST   /api/v1/adaptive/toggle
  Body: { enabled: bool }
  → 200 AdaptiveSettingsResponse
  → 422 validation_error

POST   /api/v1/adaptive/weights
  Body: { preference: float, voice_fidelity: float,
          style_constraints: float, avoidance: float }
  → 200 AdaptiveSettingsResponse (mit ge-clampten Werten)
  → 422 validation_error
```

#### Service-Contract Sketch

```python
# apps/api/narrare/adaptive/contracts.py
class AdaptiveContextServiceProtocol(Protocol):
    """Service für Adaptivitäts-Sichtbarkeit und Steuerung.

    Implementiert den Backend-Teil von LEARN-002 (Adaptive Dashboard)
    und ist Consumer des Core-AdaptiveContextProvider.
    """

    async def get_context(
        self,
        user_id: UUID,
        project_id: UUID,
    ) -> AdaptiveContextResponse:
        """Liefere den konsolidierten AdaptiveContext für das Dashboard."""
        ...

    async def set_enabled(
        self,
        user_id: UUID,
        project_id: UUID,
        enabled: bool,
    ) -> AdaptiveSettingsResponse:
        """Aktiviere/deaktiviere Adaptivität."""
        ...

    async def set_weights(
        self,
        user_id: UUID,
        project_id: UUID,
        weights: AdaptiveWeightsInput,
    ) -> AdaptiveSettingsResponse:
        """Setze die Weight-Konfiguration (mit Clamping)."""
        ...
```

### 5.5 Adaptive Settings-Modell (Persistenz)

**Persistence Question (Q-A2):** Wo werden `AdaptiveSettings` gespeichert?

Zwei Optionen:

- **Option α — Eigene Tabelle** (`adaptive_settings`)
  - Pro: Sauberere Trennung; leichter zu migrieren
  - Con: Weitere Tabelle; Setting-Lifecycle-Komplexität

- **Option β — In existierende UserSettings/ProjectSettings integrieren**
  - Pro: Keine neue Tabelle; existierende Settings-Infrastruktur
  - Con: Schema muss erweitert werden (Alembic-Migration)

**Empfehlung:** Option β — Erweiterung von `UserSettings` (oder `UserAISettings`) um eine JSON-Spalte `adaptive_settings`. Architecture-Specialist entscheidet final (Q-A2).

### 5.6 Prompt-Variablen: schon registriert

Alle vier Variablen, die der `AdaptiveContextEnricher` schreibt, sind bereits in `SYSTEM_VARS` registriert (`packages/core/narrare_core/prompts/variable_registry.py:94-99`):

- `user_preferences` ✓
- `style_constraints` ✓
- `avoidance_patterns` ✓
- `character_voice_profiles` ✓

Die internen Variablen (`__adaptive_source_summary`, `__adaptive_weights`) **müssen nicht registriert werden**, weil sie von Prompt-Templates nicht referenziert werden. Sie werden nur in der Transparenz-UI und im Logging verwendet. Das führende `__` dokumentiert diese Internal-Only-Natur.

### 5.7 Was NICHT gebaut wird

Explizit ausgeschlossen (verhindert Scope-Creep):

1. **Keine neue PromptComposer-Stage** — Adaptivität läuft durch den existierenden Enricher-Mechanismus (ADR-038).
2. **Keine neuen Prompt-Variablen** — alle vier Variablen sind bereits registriert.
3. **Keine neuen Preference-Quellen** — `PreferenceProfile` und `CharacterVoiceProfile` bleiben die einzigen Quellen.
4. **Keine Voice Metrics in Generation** — `voice_metrics` (ADR-057) bleiben checking-path only. Die `formatted_voice_profiles`-Property von `ProjectWritingProfile` liest sie bewusst nicht (Kommentar in `profiles/models.py:30`).
5. **Kein Auto-Profiling** — Adaptivität reagiert nur auf existierende Daten; sie triggered keine neue Analyse. ANAL-008 und WRITE-010 bleiben separate User-Actions.
6. **Keine statistische Style-Analyse** — die alte LEARN-002-Idee (Satzlängen, Vokabular) wird nicht umgesetzt.

---

## 6. ASSIST-004 Dialogue Coach

### 6.1 User-Workflow

**Schritt-für-Schritt aus Usersicht:**

1. User selectiert im Editor einen Dialog-Abschnitt (1–4 sprechende Charaktere).
2. User öffnet **Dialogue Coach Panel** (rechte Seite oder Tab im Analysis-Panel — Q-D4).
3. User wählt einen Modus:
   - **Analyze**: Nur Feedback, keine Änderungen am Text
   - **Improve**: Feedback + vorgeschlagene Alternativen
4. User clickt **"Start"**.
5. AI läuft (SSE-Streaming zeigt Progress). Der Prompt enthält:
   - Der selektierte Text
   - CharacterVoiceProfile aller beteiligten Charaktere (aus KB)
   - PreferenceProfile (aus Feedback-Historie)
   - AdaptiveSettings (Weights)
6. AI liefert structured Output:
   - Liste von `DialogueIssue`s (jeweils: Typ, Schweregrad, Erklärung, Referenz)
   - Falls Improve-Modus: Liste von `DialogueAlternative`s (jeweils: Original, Rewrite, Erklärung)
7. User sieht Ergebnisse:
   - Issues kategorisiert nach Typ (subtext, exposition, redundancy, voice_mismatch, ...)
   - Bei Improve: Inline-Diff zwischen Original und Rewrite, mit Accept/Reject-Buttons
8. User acceptet einzelne Alternativen (werden in den Editor übernommen) oder dismisses sie.
9. Accept/Reject wird als `FeedbackEvent` gespeichert → speist PreferenceProfile (LEARN-001-Loop).

### 6.2 Architektur-Bestandteile

#### 6.2.1 Core

```
packages/core/narrare_core/
├── agents/
│   └── dialogue_coach_agent.py        # DialogueCoachAgent (NarrareAgent-Subclass)
├── ai_assist/                          # neue Subdomain (oder types in agents/)
│   └── dialogue_coach_types.py        # Output-Pydantic-Modelle (DialogueCoachOutput)
└── prompts/
    └── _bundled/
        └── ai_assist/
            └── en/
                └── dialogue_coach/
                    ├── system.md       # Mode 1 PromptComposer-Template (ADR-054)
                    └── system_improve.md  # Variante für Improve-Mode (oder Mode-Parameter)
```

##### DialogueCoachAgent

```python
# packages/core/narrare_core/agents/dialogue_coach_agent.py
"""Dialogue Coach Agent — analysiert und verbessert Dialog.

Nutzt AdaptiveContext für Preference- und Voice-Daten.
Folgt ADR-015 (Agents First-Class) und ADR-026 (Capability-Based Injection).
"""

from __future__ import annotations

from typing import Any

from pydantic_ai import RunContext
from pydantic_ai.agent import Agent

from narrare_core.agents.base import NarrareAgent
from narrare_core.ai_assist.dialogue_coach_types import (
    DialogueCoachDeps,
    DialogueCoachOutput,
)


class DialogueCoachAgent(NarrareAgent[DialogueCoachDeps, DialogueCoachOutput]):
    """AI-Agent für Dialog-Analyse und -Verbesserung.

    Output-Typ: ``DialogueCoachOutput`` (Pydantic-Modell).
    Intent: ``LLMIntent.DIALOGUE_COACH`` (routeable).
    Context-Mode: ``dialogue_coach`` (neu — siehe §6.4 Q-B4).
    """

    INTENT = "dialogue_coach"  # wird in LLMIntent registriert

    def __init__(self, model: Any) -> None:
        super().__init__(
            model=model,
            output_type=DialogueCoachOutput,
            deps_type=DialogueCoachDeps,
            system_prompt=None,  # wird via Capability + PromptComposer gebaut
        )

    async def run(
        self,
        prompt: str,
        *,
        deps: DialogueCoachDeps,
    ) -> DialogueCoachOutput:
        """Führt Dialogue-Coach-Analyse aus.

        Args:
            prompt: Der User-Prompt (modus-spezifische Instruktion).
            deps: Enthält adaptive_context, mode, characters, text.

        Returns:
            DialogueCoachOutput mit Issues und ggf. Alternativen.
        """
        ...
```

##### Output-Typen

```python
# packages/core/narrare_core/ai_assist/dialogue_coach_types.py
"""Pydantic-Output-Modelle für Dialogue Coach.

Diese Typen sind die verbindliche Schnittstelle zwischen Agent
und Backend-Service. Sie werden von RULE-17 (API-Frontend-Contract)
erfasst: das Backend-Schema muss exakt diesen Aufbau haben, und
das Frontend muss die gleichen Feldnamen lesen.
"""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from narrare_core.ai_invocation.adaptive_context import AdaptiveContext


class DialogueIssueType(StrEnum):
    """Klassifikation eines Dialog-Problems."""

    SUBTEXT_VIOLATION = "subtext_violation"
    """On-the-nose: Figuren sagen direkt, was sie denken/fühlen, statt es zu zeigen."""

    EXPOSITION_DUMP = "exposition_dump"
    """Info-Dumping: Dialog existiert nur, um dem Leser Weltwissen zu vermitteln."""

    REDUNDANCY = "redundancy"
    """Redundanz: Aussagen wiederholen das schon Bekannte."""

    VOICE_MISMATCH = "voice_mismatch"
    """Stimmen-Fehler: Der Dialog passt nicht zur etablierten Character-Voice."""

    UNDERSPECIFIED = "underspecified"
    """Zu vage: Aussagen sind nicht konkret genug."""

    OVERFORMAL = "overformal"
    """Zu steif: Die Sprache passt nicht zur emotiven Situation."""

    TAG_OVERUSE = "tag_overuse"
    """Tag-Überladung: Zu viele "sagte X", "antwortete Y" etc."""


class DialogueSeverity(StrEnum):
    """Schweregrad eines Issues."""

    INFO = "info"          # Hinweis, kein Problem
    MINOR = "minor"        # Kleines Problem
    MAJOR = "major"        # Signifikantes Problem
    CRITICAL = "critical"  # Blocker — Text funktioniert nicht


class DialogueIssue(BaseModel):
    """Ein einzelnes vom Coach identifiziertes Problem.

    Attributes:
        type: Klassifikation (DialogueIssueType).
        severity: Schweregrad (DialogueSeverity).
        speaker: Name der Figur, auf die sich das Issue bezieht (oder None für generisch).
        quote: Kurzes Zitat aus dem Original, das das Problem illustriert.
        explanation: 1-3 Sätze, warum das ein Problem ist.
        suggestion: Optionale kurze Verbesserungsempfehlung (kein Rewrite — dafür DialogueAlternative).
    """

    model_config = ConfigDict(frozen=True)

    type: DialogueIssueType
    severity: DialogueSeverity
    speaker: str | None = None
    quote: str = Field(..., min_length=1, max_length=500)
    explanation: str = Field(..., min_length=1, max_length=1000)
    suggestion: str | None = Field(default=None, max_length=500)


class DialogueAlternative(BaseModel):
    """Eine Verbesserungs-Alternative für einen Textabschnitt.

    Attributes:
        original_quote: Der zu verbessernde Originaltext.
        rewrite: Der neue Textvorschlag.
        rationale: Kurze Erklärung, warum der Rewrite besser ist.
        applies_to_issue_ids: Indizes der Issues, die dieser Rewrite addressiert.
        speakers: Liste der Figuren, die im Rewrite sprechen.
    """

    model_config = ConfigDict(frozen=True)

    original_quote: str = Field(..., min_length=1, max_length=1000)
    rewrite: str = Field(..., min_length=1, max_length=2000)
    rationale: str = Field(..., min_length=1, max_length=500)
    applies_to_issue_ids: list[int] = Field(default_factory=list)
    speakers: list[str] = Field(default_factory=list)


class DialogueCoachOutput(BaseModel):
    """Vollständiges Resultat eines Dialogue-Coach-Aufrufs.

    Attributes:
        mode: Der aktive Modus ("analyze" oder "improve").
        overall_assessment: 1-3 Sätze Zusammenfassung des Dialogs.
        issues: Liste der identifizierten Probleme.
        alternatives: Liste der Verbesserungs-Vorschläge (nur bei mode="improve").
        adaptive_summary: Human-readable Summary der genutzten Adaptivitäts-Signale
            (für Transparenz im UI).
    """

    model_config = ConfigDict(frozen=True)

    mode: str  # "analyze" | "improve"
    overall_assessment: str = Field(..., min_length=1, max_length=2000)
    issues: list[DialogueIssue] = Field(default_factory=list)
    alternatives: list[DialogueAlternative] = Field(default_factory=list)
    adaptive_summary: str = ""


class DialogueCoachDeps(BaseModel):
    """Runtime-Dependencies für den DialogueCoachAgent.

    Attributes:
        adaptive_context: Der AdaptiveContext (PreferenceProfile, VoiceProfiles, ...).
        mode: "analyze" oder "improve".
        text_to_analyze: Der selektierte Dialog-Text.
        characters: Namen der Figuren, die sprechen (für Voice-Matching).
        language: Output-Sprache (für deutsche vs. englische Hinweise).
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    adaptive_context: AdaptiveContext
    mode: str
    text_to_analyze: str
    characters: list[str] = Field(default_factory=list)
    language: str = "en"
```

##### Prompt-Template-Struktur

```markdown
---
prompt_type: ai_assist
prompt_language: en
prompt_version: "1.0.0"
intent: dialogue_coach
context_mode: dialogue_coach
---

## System

You are Narrare's Dialogue Coach — an AI editor specialized in dialogue.
Your job is to identify dialogue problems and, when asked, propose improved rewrites.

### Mode

{{mode}}

- `analyze`: Identify issues, provide suggestions, do NOT propose rewrites.
- `improve`: Identify issues AND propose `DialogueAlternative` rewrites.

### Adaptivity Signals

The following signals shape your analysis:

**Character Voice Profiles** (HIGH PRIORITY — voice fidelity is critical):
{{character_voice_profiles}}

**User Style Preferences** (weight: {{user_preferences}}):
{{user_preferences}}

**Style Constraints** (MANDATORY):
{{style_constraints}}

**Avoidance Patterns** (MANDATORY — never produce these):
{{avoidance_patterns}}

### Output Schema

Return JSON matching `DialogueCoachOutput`:

\`\`\`json
{
  "mode": "analyze|improve",
  "overall_assessment": "...",
  "issues": [
    {
      "type": "subtext_violation|exposition_dump|redundancy|voice_mismatch|underspecified|overformal|tag_overuse",
      "severity": "info|minor|major|critical",
      "speaker": "...|null",
      "quote": "...",
      "explanation": "...",
      "suggestion": "..."
    }
  ],
  "alternatives": [
    {
      "original_quote": "...",
      "rewrite": "...",
      "rationale": "...",
      "applies_to_issue_ids": [0, 1],
      "speakers": ["Aria"]
    }
  ]
}
\`\`\`

## First Message

Analyze the following dialogue and return JSON only.

### Characters

{{characters}}

### Text to Analyze

{{text_to_analyze}}
```

#### 6.2.2 Backend

```
apps/api/narrare/ai_assist/
├── __init__.py
├── router.py                       # POST /api/v1/ai-assist/dialogue-coach (SSE)
├── service.py                      # DialogueCoachService
├── contracts.py                    # DialogueCoachServiceProtocol
├── schemas.py                      # Pydantic Request/Response
├── dependencies.py                 # FastAPI-DI
├── dialogue_coach_agent_runner.py  # SSE-Streaming-Wrapper um Agent
├── dialogue_coach_prompt.py        # PromptComposer-Aufruf (Mode 1, ADR-054)
├── dialogue_coach_results.py       # Mapping Agent-Output → API-Response
├── dialogue_coach_runtime_content.py  # AdaptiveContext → Template-Variablen
└── speaker_attribution.py          # Light dialogue parsing für speaker-Zuordnung
```

##### Router Sketch

```python
# apps/api/narrare/ai_assist/router.py
"""Dialogue Coach Router.

Bietet einen SSE-Endpoint für Dialogue-Coach-Analyse. Folgt dem
Write/Analysis-SSE-Muster (z.B. voice_check).
"""

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from apps.api.narrare.ai_assist import schemas
from apps.api.narrare.ai_assist.contracts import DialogueCoachServiceProtocol
from apps.api.narrare.ai_assist.dependencies import get_dialogue_coach_service

router = APIRouter(prefix="/api/v1/ai-assist", tags=["ai-assist"])


@router.post("/dialogue-coach")
async def dialogue_coach(
    request: schemas.DialogueCoachRequest,
    service: DialogueCoachServiceProtocol = Depends(get_dialogue_coach_service),
) -> StreamingResponse:
    """Startet eine Dialogue-Coach-Analyse mit SSE-Streaming.

    Returns:
        StreamingResponse mit EventSource (data: json, error: ...).
    """
    return StreamingResponse(
        service.run_stream(request),
        media_type="text/event-stream",
    )
```

##### Service-Contract

```python
# apps/api/narrare/ai_assist/contracts.py
class DialogueCoachServiceProtocol(Protocol):
    """Service für Dialogue Coach.

    Assembliert AdaptiveContext, baut den Prompt via PromptComposer,
    ruft den DialogueCoachAgent auf und streamt SSE-Events.
    """

    async def run_stream(
        self,
        request: DialogueCoachRequest,
    ) -> AsyncIterator[bytes]:
        """Streamt SSE-Events für den Dialogue-Coach-Aufruf."""
        ...
```

#### 6.2.3 Frontend

```
packages/web/
├── components/
│   └── analysis/
│       └── dialogue-coach/
│           ├── DialogueCoachPanel.tsx       # Haupt-Panel
│           ├── DialogueModeSelector.tsx     # Analyze vs Improve
│           ├── DialogueIssueList.tsx        # Liste der Issues
│           ├── DialogueIssueCard.tsx        # Einzelnes Issue
│           ├── DialogueAlternativeList.tsx  # Liste der Rewrites (nur improve)
│           ├── DialogueAlternativeCard.tsx  # Einzelner Rewrite mit Accept/Reject
│           ├── DialogueInlineDiff.tsx       # Diff-View für Accept-Tracking
│           ├── DialogueCoachProgress.tsx    # SSE-Progress-Indikator
│           ├── DialogueCoachEmptyState.tsx  # No dialogue selected
│           └── __tests__/
│               ├── DialogueCoachPanel.test.tsx
│               ├── DialogueIssueCard.test.tsx
│               └── DialogueAlternativeCard.test.tsx
├── hooks/
│   └── dialogue-coach/
│       ├── useDialogueCoach.ts             # SSE-Connection + state
│       └── useDialogueCoachAccept.ts       # Accept-Tracking
├── lib/
│   └── api/
│       └── dialogue-coach.ts               # API-Client (SSE)
└── types/
    └── dialogue-coach.ts                    # TS-Typen (RULE-17 — match Backend)
```

##### TS-Typen (Regel 17 — Backend-match)

```typescript
// packages/web/types/dialogue-coach.ts
// MUST match backend Pydantic schemas field-by-field (RULE-17).

export type DialogueIssueType =
  | "subtext_violation"
  | "exposition_dump"
  | "redundancy"
  | "voice_mismatch"
  | "underspecified"
  | "overformal"
  | "tag_overuse";

export type DialogueSeverity = "info" | "minor" | "major" | "critical";

export interface DialogueIssue {
  readonly type: DialogueIssueType;
  readonly severity: DialogueSeverity;
  readonly speaker: string | null;
  readonly quote: string;
  readonly explanation: string;
  readonly suggestion: string | null;
}

export interface DialogueAlternative {
  readonly original_quote: string;
  readonly rewrite: string;
  readonly rationale: string;
  readonly applies_to_issue_ids: readonly number[];
  readonly speakers: readonly string[];
}

export interface DialogueCoachOutput {
  readonly mode: "analyze" | "improve";
  readonly overall_assessment: string;
  readonly issues: readonly DialogueIssue[];
  readonly alternatives: readonly DialogueAlternative[];
  readonly adaptive_summary: string;
}
```

### 6.3 Adaptivität als Pilot (Rückkopplung)

ASSIST-004 ist der **erste concrete Consumer** von `AdaptiveContext`. Die Rückkopplung funktioniert so:

```
                        ┌──────────────────────────────────┐
                        │  PreferenceProfile (LEARN-001)   │
                        │  (Feedback events accumulate)    │
                        └──────────────┬───────────────────┘
                                       │
                                       ▼
┌────────────────┐    reads    ┌──────────────────────┐   reads    ┌─────────────────────┐
│ CharacterVoice │ ◄────────── │ AdaptiveContext      │ ─────────► │ PreferenceProfile   │
│ Profile        │             │ Provider             │            │ (formatted text)    │
│ (ANAL-008)     │             │                      │            └─────────────────────┘
└────────────────┘             └──────────┬───────────┘
                                          │ provides AdaptiveContext
                                          ▼
                              ┌────────────────────────────┐
                              │ DialogueCoachAgent         │
                              │ uses voice + preferences   │
                              │ for Voice-Fidelity-Scoring │
                              └────────────┬───────────────┘
                                           │ produces
                                           ▼
                              ┌────────────────────────────┐
                              │ DialogueCoachOutput        │
                              │ with issues + alternatives │
                              └────────────┬───────────────┘
                                           │ user acts on
                                           ▼
                              ┌────────────────────────────┐
                              │ User Accepts/Rejects       │
                              │ → FeedbackEvent            │
                              │ → PreferenceProfile        │
                              │ (closes loop)              │
                              └────────────────────────────┘
```

Die `voice_fidelity`-Weight aus `AdaptiveWeights` kontrolliert, wie stark der Agent Voice-Mismatches priorisiert. Die `preference`-Weight kontrolliert, wie stark die allgemeinen Style-Preferences gewichtet werden. Diese Weights werden in den Prompt als Hinweis injiziert:

```text
**Voice Fidelity Priority**: 0.9 (high)
**Preference Priority**: 0.7 (medium)
```

### 6.4 Architektonische Fragen (ASSIST-004)

| ID | Frage | Entscheidung durch |
|----|-------|-------------------|
| Q-B1 | Ein Endpoint mit `mode`-Parameter vs zwei separate Endpoints (`/analyze`, `/improve`)? | Architecture-Specialist |
| Q-B2 | Soll Voice-Fidelity-Scoring die `voice_metrics` (ADR-057) nutzen, oder nur die `speech_summary`? Default: nur `speech_summary` — `voice_metrics` bleiben checking-path only. | Architecture-Specialist |
| Q-B3 | Auto-Inference der Sprecher (Light NLP) oder User muss sie manuell angeben? Confidence-Schwelle für Auto-Inference? | Architecture-Specialist + Core-Specialist |
| Q-B4 | Neuer routeable `context_mode = "dialogue_coach"` vs direkter Mode im Intent? Folgt ADR-055-Muster (context_mode) vs ADR-048 (non-writing adapter)? | Architecture-Specialist |
| Q-B5 | Modify-Tracking: detailliertes Inline-Diff (Char-Level) oder simpler Before/After-Block? Besteht Risiko von TipTap-Kompatibilitätsproblemen. | Frontend-Specialist + Architecture-Specialist |
| Q-B6 | Muss das neue `dialogue_coach`-Prompt in den §7 Stub-Variable-Detector (ADR-046) eingetragen werden? Vermutlich ja, weil neue routeable Surface. | Architecture-Specialist |

---

## 7. LEARN-002 Recalibration

### 7.1 Alt vs. Neu

| Aspekt | Alte LEARN-002-Spec | Neue LEARN-002 (recalibrated) |
|--------|---------------------|--------------------------------|
| **Fokus** | Statistische Voice-Pipeline (Satzlängen, Vokabular, Dialog-Ratio) | Adaptivitäts-Sichtbarkeit, Steuerung, Transparenz |
| **Datenquelle** | Eigene `StyleProfile`-Tabelle (neu zu bauen) | `PreferenceProfile` (LEARN-001) + `CharacterVoiceProfile` (ANAL-008) — beide bereits vorhanden |
| **Output** | Zahlen-Statistiken + Few-Shot-Beispiele für Generation | Adaptive Dashboard: Visible Signals, Weights, Status-Indikator |
| **Primary User Action** | "Analyze My Style" (30-60 Sekunden LLM-Aufruf) | "View Adaptive Context", "Toggle Adaptivity", "Adjust Weights" |
| **API-Endpoints** | `POST /api/v1/learning/style/analyze`, `POST /api/v1/learning/style/generate` | `GET /api/v1/adaptive/context`, `POST /api/v1/adaptive/toggle`, `POST /api/v1/adaptive/weights` |
| **Feature-ID** | LEARN-002 | LEARN-002 (bleibt — User-Entscheidung Q-C1) |
| **Status-Feld** | `planned` | `recalibrated` (neuer Wert, Q-C2) oder `in-progress` |
| **Abhängigkeiten** | WRITE-001, INFRA-001, INFRA-002 | LEARN-001 (PreferenceProfile), ANAL-008 (CharacterVoiceProfile), ADR-040 (ProjectWritingProfile), ASSIST-004 (pilot consumer) |

### 7.2 Was LEARN-002 konkret liefert

LEARN-002 (recalibrated) liefert drei konkrete Dinge:

#### (1) Backend — Adaptive Dashboard API

```
apps/api/narrare/adaptive/
├── service.py              # AdaptiveContextService
├── contracts.py            # Protocol
├── schemas.py              # API-Modelle
├── router.py               # 3 Endpoints
├── dependencies.py
└── adaptive_context_provider.py  # AdaptiveContextProvider-Impl
```

#### (2) Frontend — Adaptive Dashboard UI

```
packages/web/components/studio/settings/
├── AdaptiveDashboard.tsx             # Haupt-Panel
├── AdaptiveToggle.tsx                # Master-Schalter
├── AdaptiveWeightSlider.tsx          # Slider für eine Weight
├── AdaptiveWeightControls.tsx        # 4 Sliders (preference, voice_fidelity, ...)
├── AdaptiveSourceList.tsx            # Listet genutzte Quellen
├── AdaptiveSnapshotHistory.tsx       # Vergangene AI-Calls + genutzte Adaptivität
└── __tests__/
    ├── AdaptiveDashboard.test.tsx
    ├── AdaptiveToggle.test.tsx
    └── AdaptiveWeightControls.test.tsx
```

#### (3) Frontend — Status Indikator im Editor

```
packages/web/components/studio/editor/
├── AdaptiveStatusIndicator.tsx       # Kleines Icon in der Toolbar
└── __tests__/
    └── AdaptiveStatusIndicator.test.tsx
```

#### AdaptiveContextResponse-Schema

```python
# apps/api/narrare/adaptive/schemas.py
class AdaptiveSourceSummary(BaseModel):
    """Zusammenfassung einer adaptiven Quelle für UI-Anzeige."""

    source_type: str  # "preference_profile" | "character_voice" | "feedback_events"
    label: str        # "User Preferences" | "Aria Voice Profile" | ...
    detail: str       # "12 events, 0.85 confidence" | "Last updated 2 days ago"
    is_stale: bool = False


class AdaptiveContextResponse(BaseModel):
    """Response für GET /api/v1/adaptive/context."""

    enabled: bool
    weights: AdaptiveWeightsResponse
    sources: list[AdaptiveSourceSummary]
    has_any_signal: bool
    last_updated: datetime | None = None


class AdaptiveWeightsResponse(BaseModel):
    preference: float
    voice_fidelity: float
    style_constraints: float
    avoidance: float


class AdaptiveWeightsInput(BaseModel):
    """Input für POST /api/v1/adaptive/weights (alle optional)."""

    preference: float | None = Field(default=None, ge=0.0, le=1.0)
    voice_fidelity: float | None = Field(default=None, ge=0.0, le=1.0)
    style_constraints: float | None = Field(default=None, ge=0.0, le=1.0)
    avoidance: float | None = Field(default=None, ge=0.0, le=1.0)


class AdaptiveSettingsResponse(BaseModel):
    enabled: bool
    weights: AdaptiveWeightsResponse
```

### 7.3 User-Sicht (Adaptivitäts-Dashboard)

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Settings > Adaptivity                                                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─ Master Toggle ──────────────────────────────────────────────────┐  │
│  │  Adaptivity                                          [  ON  ]    │  │
│  │  Narrare passt AI-Vorschläge an Deine Vorlieben und Stimmen an    │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  ┌─ Active Signals ────────────────────────────────────────────────┐  │
│  │                                                                  │  │
│  │  ✓ User Preferences                                              │  │
│  │    12 feedback events, 0.85 confidence                            │  │
│  │    [View details]                                                 │  │
│  │                                                                  │  │
│  │  ✓ Character Voice: Aria                                         │  │
│  │    Formal, reserved; uses technical vocabulary                    │  │
│  │    Last updated 2 days ago                                        │  │
│  │                                                                  │  │
│  │  ✓ Character Voice: Toma                                         │  │
│  │    Casual, warm; uses metaphors                                   │  │
│  │    Last updated 5 days ago [⚠ stale]                              │  │
│  │                                                                  │  │
│  │  ✗ No style constraints derived yet                               │  │
│  │    [Run analysis to derive constraints]                           │  │
│  │                                                                  │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  ┌─ Weights ──────────────────────────────────────────────────────┐   │
│  │                                                                  │  │
│  │  Preference influence       ━━━━━━━━━━━━━━━━━━━○────  0.7       │  │
│  │  Voice fidelity priority    ━━━━━━━━━━━━━━━━━━━━━━○─  0.9       │  │
│  │  Style constraints          ━━━━━━━━━━━━━━━━━━━━━━━○  1.0       │  │
│  │  Avoidance enforcement      ━━━━━━━━━━━━━━━━━━━━━━━○  1.0       │  │
│  │                                                                  │  │
│  │  [Reset to defaults]                                              │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  ┌─ Recent Adaptive Activity ─────────────────────────────────────┐  │
│  │                                                                  │  │
│  │  Today                                                            │  │
│  │  • Dialogue Coach used 3 voices + 12 preferences    [View call]  │  │
│  │  • Rewrite (chapter 7, scene 2) — accepted          [View call]  │  │
│  │                                                                  │  │
│  │  Yesterday                                                       │  │
│  │  • Extend used 1 voice + 8 preferences              [View call]  │  │
│  │                                                                  │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 7.4 Adaptive Snapshot (optional)

**Frage Q-C3:** Wo werden die "Recent Adaptive Activity"-Einträge gespeichert?

#### Option α — Eigene Tabelle (`adaptive_snapshots`)

```sql
CREATE TABLE adaptive_snapshots (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id),
    project_id UUID NOT NULL REFERENCES projects(id),
    invocation_id UUID REFERENCES invocation_evidence(id),
    intent VARCHAR(50) NOT NULL,
    source_summary JSONB NOT NULL,
    weights JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

- Pro: Eigenes Schema, leicht zu queryn
- Pro: Kann ohne InvocationEvidence existieren (für nicht-LLM-Aktivitäten)
- Con: Weitere Tabelle; Synchronisation mit Evidence

#### Option β — Auf `invocation_evidence` (empfohlen)

Seit ADR-042 und ADR-045 existiert eine PostgreSQL-`invocation_evidence`-Tabelle. Diese enthält bereits `invocation_id`, `feature_id`, `prepared_context_fingerprint`, etc. Wir erweitern sie um eine optionale Spalte:

```sql
ALTER TABLE invocation_evidence
    ADD COLUMN adaptive_source_summary JSONB,
    ADD COLUMN adaptive_weights JSONB;
```

- Pro: Nutzt existierende Infrastruktur (ADR-041 / ADR-045)
- Pro: Korreliert automatisch mit Invocation-Evidence
- Pro: Keine neue Tabelle
- Con: Adaptivität wird an InvocationEvidence gekoppelt (was aber semantisch passt)

**Empfehlung:** Option β — verwendet ADR-041/ADR-045 File Evidence Sink. Architecture-Specialist entscheidet final (Q-C3).

### 7.5 Spec-Migration

Die LEARN-002-Feature-Datei (`docs/features/learning/LEARN-002-style-adaptation.md`) muss recalibriert werden:

#### Frontmatter (recalibrated)

```yaml
---
id: LEARN-002
title: "Adaptivity Dashboard"          # war: "Style Adaptation"
status: recalibrated                    # war: planned — Q-C2: ist "recalibrated" ein valider Status?
area: learning
mvp: false

ui_tooltip: "See and control how Narrare adapts to your writing voice."   # war: "AI learns your writing voice..."
ui_help_short: |
  View which signals Narrare uses to personalize AI suggestions,
  and adjust how strongly each one influences results.
ui_help_long: |
  ## Adaptivity Dashboard

  Adaptivity is Narrare's way of learning your preferences and respecting
  your characters' voices. The dashboard makes this transparent and adjustable.

  **Active Signals**
  - User preferences (from your accept/reject history)
  - Character voice profiles (from ANAL-008 analysis)
  - Derived style constraints
  - Avoidance patterns

  **Adjustable Weights**
  - Preference influence
  - Voice fidelity priority
  - Style constraints enforcement
  - Avoidance enforcement

  **Per-call transparency**
  Each AI call records which signals influenced the result. Click any
  recent call to see exactly what was used.

  **Note:** Adaptivity uses your existing data — it never runs new long-running
  analyses in the background. To update a character voice, run ANAL-008 again.
ui_available_in: [settings, editor]

service: adaptive/service.py
contract: adaptive/contracts.py#AdaptiveContextServiceProtocol
router: adaptive/router.py
prompt: ""  # adaptivity is not a prompt surface; it injects into other prompts
requires: [LEARN-001, ANAL-008, ASSIST-004]
---
```

#### Neue Sections

- "What it does" — ersetzen durch Adaptivity-Dashboard-Beschreibung
- "How it works (User)" — neuer Workflow (View → Toggle → Adjust → See activity)
- "How it works (Technical)" — `AdaptiveContextService`, `AdaptiveContextProvider`, `AdaptiveContextEnricher`
- "Constraints & Edge Cases" — neue Edge Cases aus §10
- "Related Features" — updated Cross-References
- "Status & History" — Eintrag "2026-07-19: Recalibrated from statistical pipeline to adaptive dashboard"

#### Changelog-Eintrag (verpflichtend)

```markdown
### Changed

- **LEARN-002 recalibrated:** The Style Adaptation spec has been reinterpreted
  as an Adaptivity Dashboard. The previous concept (statistical voice pipeline
  with sentence-length distribution and few-shot prompting) is no longer
  pursued. The new scope is visualization, control, and transparency of
  existing adaptive signals (PreferenceProfile + CharacterVoiceProfile).
  See `docs/superpowers/specs/2026-07-19-adaptive-context-dialogue-coach-design.md`.
```

### 7.6 Was LEARN-002 nicht ist

Explizit ausgeschlossen, um Scope-Creep zu verhindern:

1. **Kein Author-Voice-Profiler** — das ist `ANAL-007` (bleibt `planned`). LEARN-002 visualisiert vorhandene Stimmdaten, erstellt aber keine neuen.
2. **Keine eigene Style-SSOT** — `PreferenceProfile` (LEARN-001) und `CharacterVoiceProfile` (ANAL-008) sind die einzigen Quellen.
3. **Keine neue Long-Running-Analyse** — "Analyze My Style" (alte Spec, 30-60 Sekunden) entfällt. Adaptivität ist rein reaktiv.
4. **Keine Few-Shot-Prompting-Engine** — alte Spec wollte Example-Sentences in Prompts injizieren. Das ist nicht Teil von Adaptivität.
5. **Keine Statistics-Charts** — Satzlängen-Verteilung, Vokabular-Diversity etc. entfallen. Stattdessen: Quellen-Übersicht + Weights + Activity.
6. **Keine CLI-Commands** — alte Spec erwähnt `narrare style analyze` / `narrare style generate`. Diese entfallen.
7. **Kein Separater Style-Profile-Export** — `PreferenceProfile` hat bereits einen Export-Mechanismus (LEARN-001).

### 7.7 Architektonische Fragen (LEARN-002)

| ID | Frage | User-Entscheidung / Entscheidung durch |
|----|-------|----------------------------------------|
| Q-C1 | Feature-ID `LEARN-002` beibehalten oder neu vergeben? | **User: LEARN-002 bleibt** — Recalibration, kein neues Feature |
| Q-C2 | Ist `status: recalibrated` ein valider Feature-Status, oder nutzen wir `in-progress`? | Architecture-Specialist (mit Docs-Specialist) — klärt Status-Semantik |
| Q-C3 | Adaptive Snapshot: eigene Tabelle oder `invocation_evidence`-Erweiterung? | **User: was architektonisch sauberer ist** — Empfehlung ist Option β (Erweiterung) |
| Q-C4 | Trennung `AdaptiveContextProvider` (Core) vs `AdaptiveContextService` (Backend) — nötig oder Overengineering? | Architecture-Specialist |

---

## 8. Frontend / UX-Integration

### 8.1 Integration-Matrix

| Komponente | Wo gelebt |消费者 | Datenquelle |
|-----------|-----------|---------|--------------|
| `AdaptiveStatusIndicator` | Editor Toolbar (rechts oben) | User während des Schreibens | `useAdaptiveStatus`-Hook → `GET /api/v1/adaptive/context` (kurz) |
| `DialogueCoachPanel` | Tab in Analysis Panel ODER eigenes Panel (Q-D4) | User bei Dialog-Auswahl | SSE `/api/v1/ai-assist/dialogue-coach` |
| `AdaptiveDashboard` | Settings → Adaptivity | User in Settings | `useAdaptiveContext`-Hook → REST `/api/v1/adaptive/*` |
| `AdaptiveSnapshotHistory` | Inside `AdaptiveDashboard` | User will vergangene Nutzung sehen | `GET /api/v1/adaptive/snapshots` (paginated) |
| Weights Controls | Inside `AdaptiveDashboard` | User adjusts influence | `POST /api/v1/adaptive/weights` mit TanStack Mutation |
| Master Toggle | Inside `AdaptiveDashboard` + Quick-Action in Editor-Menu | User toggles adaptivity | `POST /api/v1/adaptive/toggle` |

### 8.2 Editor-Integration (ASSIST-004)

```
┌────────────────────────────────────────────────────────────────────────┐
│  Narrare Editor                                                        │
│  ┌──────────────────────────────────────────┐  ┌─────────────────────┐ │
│  │ Chapter 7 — The Council                  │  │ Analysis            │ │
│  │                                          │  │ ┌─────────────────┐ │ │
│  │  ┌─ Aria ────────────────────────────┐   │  │ │ Dialogue Coach  │ │ │
│  │  │ "We have to act now," she said,   │   │  │ │ ▼               │ │ │
│  │  │  glancing at Toma.                │   │  │ └─────────────────┘ │ │
│  │  └───────────────────────────────────┘   │  │                     │ │
│  │                                          │  │  Selected: Aria+Toma │ │
│  │  ┌─ Toma ────────────────────────────┐   │  │  dialogue (3 lines) │ │
│  │  │ "I know. But we need more info    │   │  │                     │ │
│  │  │  first," Toma replied             │   │  │  Mode: ● Analyze    │ │
│  │  │  carefully.                       │   │  │         ○ Improve   │ │
│  │  └───────────────────────────────────┘   │  │                     │ │
│  │                                          │  │  [ Start Analysis ] │ │
│  │                                          │  │                     │ │
│  └──────────────────────────────────────────┘  └─────────────────────┘ │
│  [✨ Adaptivity: ON, 2 voices active]                                   │
└────────────────────────────────────────────────────────────────────────┘
```

#### Interaktions-Flow

1. User wählt Text im Editor aus (TipTap-Selection)
2. `DialogueCoachPanel` wird enabled (sobald gültige Selection)
3. User wählt Mode (Analyze / Improve)
4. User clickt **Start Analysis**
5. `useDialogueCoach`-Hook:
   - Baut Request mit selection + chapter_id + mode
   - Öffnet SSE-Connection zu `/api/v1/ai-assist/dialogue-coach`
   - Streamt Progress-Events → zeigt `DialogueCoachProgress`
   - Bei `data`-Event → parst JSON, setState
   - Bei `error`-Event → zeigt Fehlermeldung
6. Bei mode=analyze: `DialogueIssueList` rendert Issues
7. Bei mode=improve: `DialogueAlternativeList` rendert Rewrites + Accept/Reject-Buttons
8. Bei Accept: `useDialogueCoachAccept`:
   - Wendet Rewrite in TipTap-Editor an (Inline-Diff via `DialogueInlineDiff`)
   - Speichert `FeedbackEvent(action=ACCEPT)`
9. Bei Reject: Speichert `FeedbackEvent(action=REJECT)`

### 8.3 Adaptivitäts-Sichtbarkeit im Editor (Status-Indikator)

Drei Zustände für `AdaptiveStatusIndicator`:

```
┌──────────────────────────────────────────────────────┐
│ Status         │ Icon   │ Tooltip                    │
├──────────────────────────────────────────────────────┤
│ ✨ Aktiv        │  ✨     │ "Adaptivity: ON — 2 voice  │
│                │         │  profiles + 12 preferences │
│                │         │  active"                   │
├──────────────────────────────────────────────────────┤
│ ⚪ Pausiert     │  ⚪     │ "Adaptivity: PAUSED —     │
│                │         │  Click to re-enable"       │
├──────────────────────────────────────────────────────┤
│ 🔘 Keine Daten  │  🔘     │ "Adaptivity: No signals   │
│                │         │  yet — accept or reject AI │
│                │         │  suggestions to build it"  │
└──────────────────────────────────────────────────────┘
```

#### Behaviour

- **Klick** öffnet das Adaptive Dashboard (in Settings) ODER einen Quick-Popover (Q-D2)
- **Hover** zeigt Source-Summary
- Pollt `/api/v1/adaptive/context` alle 60 Sekunden (oder via TanStack refetchOnWindowFocus)
- Ist ein轻薄 Indicator — nimmt kaum Platz weg

### 8.4 Settings-Integration (LEARN-002 Adaptive Dashboard)

```
Settings Sidebar
├── General
├── AI
│   ├── Providers
│   ├── Default Models
│   ├── Token Limits
│   └── Context Budget
├── Writing
│   ├── Goals
│   └── Tone Library
├── Learning
│   ├── Feedback Profile (LEARN-001)
│   └── Adaptivity Dashboard (LEARN-002 — NEW)
└── About
```

#### Adaptive Dashboard Subtree

```
Settings > Learning > Adaptivity Dashboard
├── Master Toggle
├── Active Signals (collapsible)
│   ├── User Preferences (12 events)
│   ├── Character Voices
│   │   ├── Aria (formal, reserved) ✓
│   │   └── Toma (casual, warm) ✓
│   └── Style Constraints (none yet)
├── Weights (4 sliders)
│   ├── Preference: 0.7
│   ├── Voice Fidelity: 0.9
│   ├── Style Constraints: 1.0
│   └── Avoidance: 1.0
├── Recent Adaptive Activity (paginated list)
└── Learn More (link to docs)
```

### 8.5 Cross-Component-Interaktion

Wenn User im Adaptive Dashboard Weights ändert, müssen alle Komponenten, die Adaptivität anzeigen, updaten:

```
AdaptiveDashboard
  └─ POST /api/v1/adaptive/weights
       └─ TanStack Query mutation
            └─ onSuccess: queryClient.invalidateQueries({
                  queryKey: ['adaptive-context']
                })
                  ↓
                  ├─ AdaptiveStatusIndicator (refetches)
                  ├─ DialogueCoachPanel (refetches context for next call)
                  └─ AdaptiveSnapshotHistory (refetches)
```

Dies entspricht dem ADR-043 (useAIOperation) Muster. Architecture-Specialist muss entscheiden, ob dieses Cache-Invalidation-Muster ADR-043-konform ist (Q-D3).

### 8.6 i18n-Integration

Drei neue i18n-Namespaces (alle in `packages/i18n/messages/{en,de,fr}/` registriert — RULE-16):

#### Namespace 1: `studio.dialogueCoach`

```json
{
  "title": "Dialogue Coach",
  "mode": {
    "analyze": "Analyze",
    "improve": "Improve"
  },
  "start": "Start Analysis",
  "noSelection": "Select dialogue in the editor to begin",
  "issues": {
    "title": "Issues Found",
    "empty": "No issues found — this dialogue looks good!"
  },
  "alternatives": {
    "title": "Suggested Rewrites",
    "accept": "Accept",
    "reject": "Reject",
    "rationale": "Why this is better"
  },
  "severity": {
    "info": "Info",
    "minor": "Minor",
    "major": "Major",
    "critical": "Critical"
  },
  "issueType": {
    "subtext_violation": "On the nose",
    "exposition_dump": "Exposition dump",
    "redundancy": "Redundancy",
    "voice_mismatch": "Voice mismatch",
    "underspecified": "Too vague",
    "overformal": "Too formal",
    "tag_overuse": "Too many tags"
  },
  "progress": {
    "loading": "Analyzing dialogue...",
    "complete": "Analysis complete",
    "error": "Analysis failed"
  }
}
```

#### Namespace 2: `settings.adaptive`

```json
{
  "title": "Adaptivity",
  "subtitle": "Control how Narrare adapts to your writing",
  "masterToggle": {
    "label": "Adaptivity",
    "description": "Narrare passt AI-Vorschläge an Deine Vorlieben und Stimmen an",
    "on": "ON",
    "off": "OFF"
  },
  "sources": {
    "title": "Active Signals",
    "empty": "Noch keine adaptiven Signale — Accept oder Reject AI-Vorschläge, um welche zu sammeln",
    "preferenceProfile": "User Preferences",
    "characterVoice": "Character Voice: {{name}}",
    "styleConstraints": "Style Constraints",
    "avoidancePatterns": "Avoidance Patterns",
    "viewDetails": "View details"
  },
  "weights": {
    "title": "Weights",
    "preference": "Preference influence",
    "voiceFidelity": "Voice fidelity priority",
    "styleConstraints": "Style constraints",
    "avoidance": "Avoidance enforcement",
    "reset": "Reset to defaults"
  },
  "activity": {
    "title": "Recent Adaptive Activity",
    "empty": "Keine Aktivität in den letzten 7 Tagen",
    "viewCall": "View call details"
  }
}
```

#### Namespace 3: `editor.adaptiveIndicator`

```json
{
  "active": "Adaptivity: ON",
  "paused": "Adaptivity: PAUSED",
  "noData": "Adaptivity: No signals yet",
  "activeDetail": "{{voiceCount}} voice profile(s) + {{prefCount}} preference(s) active",
  "enableNow": "Enable"
}
```

#### Namespace-Registrierung (RULE-16)

In `packages/web/lib/i18n/request.ts` muss das `namespaces`-Array erweitert werden:

```typescript
export const namespaces = [
  "common",
  // ... existing
  "studio.dialogueCoach",
  "settings.adaptive",
  "editor.adaptiveIndicator",
] as const;
```

Und in `packages/i18n/messages/{en,de,fr}/` müssen die drei JSON-Dateien in **allen drei Locales** angelegt werden (gleichzeitiger Commit — RULE-16).

Validiert durch `packages/web/__tests__/i18n-namespace-registry.test.ts`.

### 8.7 Accessibility & UX-Quality-Gates

**Skill: `web-design-guidelines` (mandatory für Frontend-Specialist)**

| Kriterium | Anforderung |
|-----------|-------------|
| Tastatur-Navigation | Alle Controls (Toggle, Sliders, Accept/Reject-Buttons) per Tab erreichbar; sichtbarer Focus-Ring |
| ARIA | `role="slider"` für Weight-Sliders mit `aria-valuemin=0`, `aria-valuemax=1`, `aria-valuenow`; `aria-busy` auf Panel während SSE läuft |
| Kontrast | Status-Indikator (✨ ⚪ 🔘) braucht Text-Label nicht nur Icon — mindestens 4.5:1 Kontrast |
| Screenreader | SSE-Progress muss `aria-live="polite"` haben, damit SR-User Updates hört |
| Reduced Motion | `DialogueInlineDiff` muss `prefers-reduced-motion` respektieren (keine slide-Animationen) |
| Error-States | Network-Fehler → klare Meldung mit Retry-Button, kein stiller Zustand |
| Empty-States | Wenn kein Dialog selektiert: klare Handlungsaufforderung |
| Loading-States | Skeleton-UI für Adaptive Dashboard, Progress-Bar für Dialogue Coach |
| Mobile-Responsiveness | Settings-Seite muss auf Tablet funktionieren; Dialogue Coach Panel collapsable |
| Internationalisierung | Keine hardcoded Strings — alle via `useTranslations()` (RULE-16) |

### 8.8 Architektonische Fragen (Frontend)

| ID | Frage | User-Entscheidung / Entscheidung durch |
|----|-------|----------------------------------------|
| Q-D1 | Soll der Adaptiv-Indikator wirklich in die Editor-Toolbar? | **User: ja** —.Visibility ist wichtiger Teil des Value-Props |
| Q-D2 | Indikator in **allen** AI-Panels (Analysis, Generation) oder nur im Editor? | Frontend-Specialist + Architecture-Specialist — Empfehlung: erstmal nur Editor, später ausrollen |
| Q-D3 | Cross-Component-Update via TanStack Query Cache Invalidation — ADR-043-konform? | Architecture-Specialist |
| Q-D4 | Dialogue Coach als Tab in Analysis-Panel ODER eigenständiges Panel (z.B. rechts)? | **User: Architect/Frontend-Specialist entscheidet** — mit `frontend-design` und `vercel-composition-patterns` Skills |

---

## 9. Testing-Strategie

### 9.1 Layer-Matrix

| Layer | Test-Typ | Tool | Coverage-Ziel | Was wird getestet |
|-------|---------|------|--------------|-------------------|
| **Core — Dataclass** | Unit | pytest | 100% | `AdaptiveWeights.validated()` clamping; `AdaptiveContext.has_any_signal`; `AdaptiveSettings` Defaults |
| **Core — Enricher** | Unit | pytest + Fake | 95% | `AdaptiveContextEnricher.enrich`: Provider None, IDs fehlen, Provider failed, enabled=False, has_any_signal=False, Success-Path |
| **Core — Provider Protocol** | Contract | pytest + Fake | 100% | `AdaptiveContextProvider` Protocol-Konformität; fake provider implementiert |
| **Core — DialogueCoachAgent** | Unit | pytest + TestModel | 95% | Agent akzeptiert AdaptiveContext in Deps; Output-Type korrekt; Voice-Profile tauchen in dynamic_inputs auf |
| **Core — PromptComposer** | Integration | pytest + real Composer | 95% | Variablen werden ersetzt; alle 4 adaptiven Variablen resolve korrekt |
| **Backend — Service** | Unit | pytest + Fake | 90% | `AdaptiveContextService.get_context`, `.set_enabled`, `.set_weights`; Clamping in `set_weights` |
| **Backend — Service** | Integration | pytest + real Service | 85% | Service mit real Provider, real DB (sqlite/postgres), persistierte Settings |
| **Backend — Router** | Integration | pytest + httpx | 85% | 3 Endpoints; 401/422/200-Responses; Auth-Enforcement |
| **Backend — DialogueCoachService** | Unit | pytest + Fake Agent | 90% | Service.run_stream: baut Request, ruft Agent auf, streamt korrekte SSE-Events |
| **Backend — DialogueCoachService** | Integration | pytest + TestModel | 80% | End-to-End mit TestModel — Issues und Alternativen kommen durch |
| **Backend — Speaker Attribution** | Unit | pytest | 90% | `speaker_attribution.py`: einfache Heuristik für "said X", "X replied", etc. |
| **Frontend — Hooks** | Unit | Vitest + MSW | 90% | `useDialogueCoach`: SSE-Mock, State-Transitions; `useAdaptiveContext`: REST-Mock |
| **Frontend — Components** | Unit | Vitest + Testing Library | 85% | Alle Panel-Komponenten rendern korrekt in allen States (empty/loading/error/loaded) |
| **Frontend — Components** | Visual Regression | Playwright `toHaveScreenshot()` (ADR-059) | smoke | Status-Indikator in 3 Zuständen; Adaptive Dashboard |
| **Frontend — A11y** | Integration | axe-core via Vitest | 100% | Keine A11y-Violations in neuen Komponenten |
| **Frontend — i18n** | Unit | `i18n-namespace-registry.test.ts` | 100% | Alle 3 Namespaces registriert; alle Locales vorhanden |
| **E2E** | Pydantic Evals | `evals/` (ADR-032) | smoke | Adaptivität hat messbaren Effekt (siehe §9.3) |

### 9.2 Adaptivität testen — synthetische Feedback-Sequenz

Dieser Test verifiziert, dass Adaptivität einen **echten Effekt** hat (RULE-18b — Configuration Effect Integrity):

```python
# tests/integration/test_adaptive_effect.py
"""Verifiziert, dass AdaptiveContext einen messbaren Effekt auf den Prompt hat.

Stellt sicher, dass eine synthetische Feedback-Sequenz zu anderen AI-Vorschlägen
führt als ohne Feedback. Schließt die Lücke zwischen "Setting existiert" und
"Setting hat Effekt" (RULE-18b).
"""

import pytest
from narrare_core.ai_invocation.adaptive_context import (
    AdaptiveContext,
    AdaptiveWeights,
)
from narrare_core.ai_invocation.enrichers.adaptive import AdaptiveContextEnricher
from narrare_core.ai_invocation.models import PromptInvocationContext
from tests.fakes import FakeAdaptiveContextProvider


@pytest.mark.asyncio
async def test_adaptive_context_changes_prompt_variables() -> None:
    """AdaptiveContext-Enricher schreibt in dynamic_inputs."""
    provider = FakeAdaptiveContextProvider(
        context=AdaptiveContext(
            user_id=UUID("..."),
            project_id=UUID("..."),
            preference_text="User prefers short sentences",
            style_constraints_text="- Avoid passive voice",
            source_summary="1 preference",
        ),
    )
    enricher = AdaptiveContextEnricher(provider=provider)

    context = PromptInvocationContext(
        feature_id="test",
        user_id=UUID("..."),
        project_id=UUID("..."),
        dynamic_inputs={},
    )

    result = await enricher.enrich(context)

    assert result.dynamic_inputs["user_preferences"] == "User prefers short sentences"
    assert result.dynamic_inputs["style_constraints"] == "- Avoid passive voice"
    assert result.dynamic_inputs["__adaptive_source_summary"] == "1 preference"


@pytest.mark.asyncio
async def test_adaptive_disabled_skips_enrichment() -> None:
    """Wenn AdaptiveSettings.enabled=False, wird NICHT angereichert."""
    provider = FakeAdaptiveContextProvider(enabled=False)
    enricher = AdaptiveContextEnricher(provider=provider)

    context = PromptInvocationContext(
        feature_id="test",
        user_id=UUID("..."),
        project_id=UUID("..."),
        dynamic_inputs={"user_preferences": "existing"},
    )

    result = await enricher.enrich(context)

    assert result.dynamic_inputs["user_preferences"] == "existing"
    assert "style_constraints" not in result.dynamic_inputs


def test_adaptive_weights_clamping() -> None:
    """AdaptiveWeights.validated() clampt auf [0.0, 1.0]."""
    weights = AdaptiveWeights(
        preference=1.5,
        voice_fidelity=-0.3,
        style_constraints=0.5,
        avoidance=0.8,
    )
    clamped = weights.validated()
    assert clamped.preference == 1.0
    assert clamped.voice_fidelity == 0.0
    assert clamped.style_constraints == 0.5
    assert clamped.avoidance == 0.8


@pytest.mark.asyncio
async def test_synthetic_feedback_sequence_changes_dialogue_coach_output() -> None:
    """End-to-End: Synthetische Feedback-Sequenz ändert DialogueCoachOutput.

    1. Setup: Project ohne Preferences.
    2. Run Dialogue Coach → capture baseline output.
    3. Seed PreferenceProfile mit "user dislikes passive voice".
    4. Run Dialogue Coach again → capture new output.
    5. Assert: outputs unterscheiden sich (Preferences werden berücksichtigt).
    """
    # This test requires real LLM call (TestModel won't show adaptivity effect).
    # Marked as slow / eval test.
    pytest.skip("Requires real LLM — see evals/test_dialogue_coach_adaptive.py")


class FakeAdaptiveContextProvider:
    """Fake für Unit-Tests — implementiert AdaptiveContextProvider Protocol."""

    def __init__(
        self,
        context: AdaptiveContext | None = None,
        enabled: bool = True,
    ) -> None:
        self._context = context or AdaptiveContext(
            user_id=UUID("00000000-0000-0000-0000-000000000000"),
            project_id=UUID("00000000-0000-0000-0000-000000000000"),
        )
        from narrare_core.ai_invocation.adaptive_context import AdaptiveSettings
        self._settings = AdaptiveSettings(enabled=enabled)

    async def get_context(self, user_id, project_id):
        return self._context

    async def get_settings(self, user_id, project_id):
        return self._settings
```

### 9.3 Pydantic Evals

Per ADR-032 sind Pydantic Evals die SSOT für Prompt-Qualität. Für Dialogue Coach und Adaptivität müssen folgende Evals entstehen:

```
evals/
├── dialogue_coach/
│   ├── test_analyze_basic.py            # Basic analyze-mode cases
│   ├── test_improve_basic.py            # Basic improve-mode cases
│   ├── test_voice_fidelity_high_weight.py  # voice_fidelity=1.0 → mehr voice-mismatches detected
│   ├── test_voice_fidelity_low_weight.py   # voice_fidelity=0.1 → weniger voice-mismatches
│   ├── test_preferences_respected.py    # User-Präferenzen tauchen im Output auf
│   └── test_avoidance_enforced.py       # Avoidance-Patterns werden vom Rewrite gemieden
└── adaptive_context/
    ├── test_with_and_without_preferences.py
    └── test_with_and_without_voices.py
```

**Wichtigster Eval:** `test_voice_fidelity_high_weight.py` vs `test_voice_fidelity_low_weight.py` — diese beiden müssen **unterschiedliche Outputs** produzieren, wenn die Weight geändert wird. Das ist der **effect-integrity-Beweis** (RULE-18b) dafür, dass Adaptivität nicht nur exists, sondern einen echten Effekt hat.

Eval-Beispiel (vereinfacht):

```python
# evals/dialogue_coach/test_voice_fidelity_weight_effect.py
"""Eval: Voice-Fidelity-Weight hat messbaren Effekt auf Issues.

RULE-18b — Configuration Effect Integrity: Eine konfigurierbare Weight
muss nachweislich das Runtime-Verhalten ändern.
"""

import pytest
from pydantic_evals import Case, Dataset
from narrare_core.agents.dialogue_coach_agent import DialogueCoachAgent
from narrare_core.ai_invocation.adaptive_context import AdaptiveContext, AdaptiveWeights


DATASET = Dataset(
    cases=[
        Case(
            name="voice_mismatch_dialogue",
            inputs={
                "text": "'Sup, dude?' Aria said, adjusting her monocle.",
                "characters": ["Aria"],
                "voice_summary": "Aria is formal, reserved, uses technical vocabulary.",
            },
            expected_output=None,  # No exact match — we check signal
        ),
    ],
)


@pytest.mark.eval
@pytest.mark.asyncio
async def test_high_voice_weight_detects_more_voice_mismatches(agent_with_model):
    """voice_fidelity=1.0 sollte voice_mismatch-Issues finden."""
    agent = agent_with_model(
        weights=AdaptiveWeights(voice_fidelity=1.0),
    )
    result = await agent.run(...)
    voice_mismatches = [i for i in result.issues if i.type == "voice_mismatch"]
    assert len(voice_mismatches) > 0


@pytest.mark.eval
@pytest.mark.asyncio
async def test_low_voice_weight_fewer_voice_mismatches(agent_with_model):
    """voice_fidelity=0.1 sollte deutlich weniger oder keine voice_mismatch-Issues finden."""
    agent = agent_with_model(
        weights=AdaptiveWeights(voice_fidelity=0.1),
    )
    result = await agent.run(...)
    voice_mismatches = [i for i in result.issues if i.type == "voice_mismatch"]
    # Signifikant weniger als bei high weight
    assert len(voice_mismatches) == 0  # oder deutlich weniger
```

---

## 10. Edge Cases

Vollständige Liste der Edge Cases, die alle Layer berücksichtigen müssen:

| # | Edge Case | Treatment |
|---|-----------|-----------|
| E1 | User hat keine Preferences (neuer User, 0 Feedback-Events) | `AdaptiveContext.has_any_signal=False`; Enricher überspringt; Status-Indikator zeigt "Keine Daten" |
| E2 | User hat Preferences, aber deaktiviert Adaptivität (`enabled=False`) | Enricher überspringt; Status-Indikator zeigt "Pausiert"; AI läuft ohne Adaptivität (degradiert nicht) |
| E3 | PreferenceProfile-Provider ist offline (mem0 down) | Enricher fängt Exception ab, logt Warning, degradiert graceful (ADR-038 D7) |
| E4 | CharacterVoiceProfile ist stale (>7 Tage) | Voice-Text wird injiziert, aber `is_fresh=False` markiert; UI zeigt ⚠; Service-Schicht logt Info |
| E5 | CharacterVoiceProfile fehlt für genannten Sprecher | Voice-Check überspringt diesen Sprecher; Issue wird als `voice_mismatch` mit `speaker=unknown` markiert oder nicht als voice_mismatch |
| E6 | Sprecher kann nicht zugeordnet werden (Auto-Inference-Q-C3) | Service fragt User via UI (manual override); alternativ: Issue ohne speaker |
| E7 | Selection ist zu kurz (<50 Zeichen) | Frontend blockiert "Start Analysis" mit Hinweis "Wähle einen längeren Dialog-Abschnitt" |
| E8 | Selection ist zu lang (>5000 Zeichen) | Frontend blockiert mit Hinweis "Wähle einen kürzeren Abschnitt (max 5000 Zeichen)"; oder Service splittet in mehrere Calls |
| E9 | Selection enthält keine Dialog-Tags | Service läuft, Issues enthalten `tag_overuse=0`; Alternativen ggf. mit hinzugefügten Tags |
| E10 | Selection enthält >4 sprechende Charaktere | Service blockiert mit 422; Frontend zeigt Hinweis "Max 4 speakers — split the scene" |
| E11 | Alle Weights auf 0.0 | Adaptivität ist faktisch aus; Service logt Info; UI zeigt Warning "All weights are zero — adaptivity is effectively disabled" |
| E12 | Alle Weights auf 1.0 | Adaptivität ist max; AI-Prompt wird sehr groß; Service logt Info; ggf. Token-Limit-Warnung |
| E13 | AdaptiveSettings-JSON in DB ist malformed | Service lädt Defaults + logt Error; UI zeigt Warnhinweis "Settings reset to defaults due to corruption" |
| E14 | LLM liefert kein valides JSON (Output-Validation-Failed) | ADR-035 greift; Retry mit Schema-Hint; bei erneutem Fehlschlag: SSE-error-Event |
| E15 | Network-Disconnect während SSE | ADR-052 Session-Recovery greift; User kann Resume clicken; Frontend zeigt Reconnect-Banner |

---

## 11. ADR-Strategie

### 11.1 Haupt-ADR

**ADR-TBD: Adaptive Context + Dialogue Coach Vertical**

Vollständiges Outline:

```markdown
# ADR-TBD: Adaptive Context + Dialogue Coach Vertical

**Date:** 2026-07-XX (nach Brainstorming-Approval)
**Status:** 🔄 Proposed → ✅ Accepted
**Affects:**
- `packages/core/narrare_core/ai_invocation/` (new: adaptive_context.py, adaptive.py enricher)
- `packages/core/narrare_core/ai_invocation/contracts.py` (extend)
- `packages/core/narrare_core/agents/dialogue_coach_agent.py` (new)
- `packages/core/narrare_core/ai_assist/dialogue_coach_types.py` (new)
- `packages/core/narrare_core/prompts/_bundled/ai_assist/en/dialogue_coach/` (new)
- `apps/api/narrare/ai_assist/` (new domain)
- `apps/api/narrare/adaptive/` (new domain)
- `packages/web/components/analysis/dialogue-coach/` (new)
- `packages/web/components/studio/settings/AdaptiveDashboard.tsx` (new)
- `packages/web/components/studio/editor/AdaptiveStatusIndicator.tsx` (new)

## Context

(Brainstorming-Summary — siehe docs/superpowers/specs/2026-07-19-adaptive-context-dialogue-coach-design.md §1-3)

## Decision

Wir bauen einen vertikalen Slice bestehend aus:
1. **AdaptiveContext** (Core) — konsolidiert PreferenceProfile + CharacterVoiceProfile.
2. **ASSIST-004 Dialogue Coach** (Pilot Consumer) — erste AI-Operation, die Adaptivität explizit nutzt.
3. **LEARN-002 recalibrated** — Adaptivitäts-Dashboard zur Sichtbarkeit und Steuerung.

## Alternatives Considered

(Siehe §2.1: Approach 1 = full statistical pipeline; Approach 2 = contract-only.)

## Consequences

### Positive
- Adaptivität wird sicht- und steuerbar (bisher: implizit undurchsichtig)
- Erste concrete Demonstration des Wertes der Voice-Vertical
- LEARN-002 bekommt realistischen Scope (statt unrealistischer Statistik-Pipeline)
- Schließt die Feedback-Loop (accept/reject → preference → next AI call)

### Negative
- Neue Domain `apps/api/narrare/ai_assist/` (Betriebs-Komplexität)
- Erweiterung von `invocation_evidence`-Schema (Migration nötig)
- Erste Injizierung in `style_constraints` und `avoidance_patterns` — bestehende Templates müssen diese Variablen nutzen (sonst hat Enricher keinen Effekt)

### Neutral
- Feature-ID LEARN-002 bleibt (Recalibration, nicht Superseding)

## Decisions (zählt alle Q-A*, Q-B*, Q-C*, Q-D* Antworten)

( werden hier vom Architecture-Specialist beantwortet )

## Open Questions (für Folge-ADRs oder Sub-ADRs)

( siehe §13 )

## Compliance

- RULE-03: Contracts first — AdaptiveContextProvider Protocol vor Implementation
- RULE-04: File sizes — keine File >400 LOC; Service evtl. splitten
- RULE-06: One responsibility — adaptive_context.py (data) vs enricher (I/O) vs provider (Protocol)
- RULE-13: Two methods run/stream — DialogueCoachService.run_stream (und implizit run für non-streaming MCP)
- RULE-17: API-Frontend-Contract — DialogueCoachOutput TS-Typen matchen Pydantic-Schema
- RULE-18b: Configuration Effect Integrity — Weights haben messbaren Effekt (Eval, siehe §9.3)
- RULE-20: No half-implementations — alle drei Komponenten werden voll gebaut
- RULE-22: Cross-Feature Coherence — AdaptiveContext verarbeitet Daten aus LEARN-001, ANAL-008, WRITE-010

## References

- `docs/superpowers/specs/2026-07-19-adaptive-context-dialogue-coach-design.md` (dieses Doc)
- ADR-038 (AI Invocation Adoption Contract)
- ADR-040 (KG SSOT — ProjectWritingProfile)
- ADR-041 (Typed Manifests / Persistent Evidence)
- ADR-045 (Runtime Adoption Enforcement)
- ADR-055 (Character Voice Contract)
- ADR-057 (Voice Check Checking-Path Contract)
```

### 11.2 Sub-ADRs (optional)

Falls der Haupt-ADR zu groß wird, können diese Sub-ADRs abgespalten werden:

| Sub-ADR | Titel | Trigger |
|---------|-------|---------|
| Sub-ADR-TBD-a | AdaptiveContextEnricher vs PreferenceContextEnricher (Q-A1) | Wenn Option α/β/γ nicht offensichtlich ist |
| Sub-ADR-TBD-b | Adaptive Snapshot Persistence (Q-C3) | Falls komplexere Schema-Entscheidung nötig |
| Sub-ADR-TBD-c | Dialogue Coach Tab vs Panel (Q-D4) | Falls Frontend-Entscheidung ADR-würdig |

### 11.3 Spec-Files to Update

Nach ADR-Approval müssen folgende Spec-Files aktualisiert werden:

| Datei | Aktion |
|-------|--------|
| `docs/features/learning/LEARN-002-style-adaptation.md` | Recalibrate — Frontmatter, Title, alle Sections neu |
| `docs/features/ai_assist/ASSIST-004-dialogue-coach.md` | Detail — Implementation-Pfade, Technical Section ausfüllen |
| `docs/superpowers/specs/2026-07-19-adaptive-context-dialogue-coach-design.md` | Mark as approved (Status ändern) |
| `docs/architecture/decisions/ADR-TBD-*.md` | Neu anlegen |
| `docs/architecture/decisions/INDEX.md` | Neue ADR-Zeile(n) eintragen |
| `docs/_shared/CURRENT_STATE.md` | Update mit Feature-Status (sobald implementiert) |
| `docs/features/INDEX.md` | LEARN-002 / ASSIST-004 Status-Symbole updaten |

### 11.4 Governance-Update

Die folgenden Governance-Artefakte müssen gepflegt werden:

| Artefakt | Aktion |
|----------|--------|
| `docs/architecture/decisions/INDEX.md` | Neue ADR-Zeile eintragen mit Status |
| `docs/_shared/CURRENT_STATE.md` | Update nach jeder Implementation-Phase |
| **AI Operation Inventory** (falls geführt) | Neue Intent `dialogue_coach` eintragen; Adaptivität als Cross-Cutting Concern dokumentieren |
| **Adoption Registry** (siehe ADR-045) | Neue AI-Operation `dialogue_coach` muss Adoption-Status erreichen (static/runtime/adopted) |
| **§7 Stub-Variable-Detector** (siehe ADR-046) | Falls `dialogue_coach` neue routeable Surface ist: in §7 eintragen (Q-B6) |
| `pyproject.toml [tool.narrare.architecture.exceptions]` | Falls neue Architecture-Exceptions nötig (z.B. für Pydantic AI Capability mit Dynamic Instructions) |

---

## 12. Implementation Order

Geschätzte Dauer: **4–6 Sessions** (jede Session ~3-5 Stunden Fokus-Arbeit).

### Layer-Ordering-Prinzip

```
Core (Contracts + Data) → Backend (Service + API) → Frontend (UI) → Testing (continuously)
                                                              ↓
                                                          Docs (Doc Gate)
```

### Phase 1 — Core Contracts & Data (1 Session)

**Verantwortlich:** NarrareCoreSpecialist

```
Phase 1
├── 1.1 Erstelle packages/core/narrare_core/ai_invocation/adaptive_context.py
│       (AdaptiveWeights, AdaptiveContext, AdaptiveSettings)
├── 1.2 Erweitere contracts.py um AdaptiveContextProvider Protocol
├── 1.3 Schreibe tests/unit/core/ai_invocation/test_adaptive_context.py
│       (Dataclass-Tests, Clamping, Defaults)
├── 1.4 Schreibe tests/unit/core/ai_invocation/test_adaptive_provider_protocol.py
│       (Protocol-Contract-Test mit Fake)
└── 1.5 Prüfe check_architecture.py — keine neuen Violations
```

**DoD:** Core-Datenmodelle sind implementiert und getestet. Alle Tests grün.

### Phase 2 — Enricher + Provider Impl (1 Session)

**Verantwortlich:** NarrareCoreSpecialist

```
Phase 2
├── 2.1 Implementiere packages/core/narrare_core/ai_invocation/enrichers/adaptive.py
│       (AdaptiveContextEnricher)
├── 2.2 Schreibe tests/unit/core/ai_invocation/test_adaptive_enricher.py
│       (Edge Cases: None provider, missing IDs, failed provider, disabled,
│        no signals, success path)
├── 2.3 Wire enricher in apps/api/narrare/_app/dependencies_prompts.py ein
├── 2.4 Implementiere Backend-Impl von AdaptiveContextProvider
│       (apps/api/narrare/adaptive/adaptive_context_provider.py)
└── 2.5 Prüfe existing PreferenceContextEnricherImpl-Tests noch grün
```

**DoD:** Enricher läuft im Stack, ist aber noch nicht durch User-Feature sichtbar.

### Phase 3 — Backend: ASSIST-004 + Adaptive API (1-2 Sessions)

**Verantwortlich:** NarrareBackendSpecialist

```
Phase 3
├── 3.1 Erstelle apps/api/narrare/ai_assist/ Domain
│       ├── contracts.py (DialogueCoachServiceProtocol)
│       ├── schemas.py (Request/Response)
│       ├── service.py (DialogueCoachService)
│       ├── router.py (SSE Endpoint)
│       ├── dialogue_coach_agent_runner.py
│       ├── dialogue_coach_prompt.py
│       ├── speaker_attribution.py
│       └── dependencies.py
├── 3.2 Erstelle Core: packages/core/narrare_core/agents/dialogue_coach_agent.py
├── 3.3 Erstelle Core: packages/core/narrare_core/ai_assist/dialogue_coach_types.py
├── 3.4 Erstelle Prompt: packages/core/narrare_core/prompts/_bundled/ai_assist/en/dialogue_coach/system.md
├── 3.5 Registriere LLMIntent.DIALOGUE_COACH (falls neuer Intent nötig)
├── 3.6 Erstelle apps/api/narrare/adaptive/ Domain
│       ├── contracts.py (AdaptiveContextServiceProtocol)
│       ├── schemas.py (AdaptiveContextResponse, etc.)
│       ├── service.py (AdaptiveContextService)
│       ├── router.py (3 Endpoints)
│       └── dependencies.py
├── 3.7 Alembic Migration für AdaptiveSettings-Spalte (Q-A2)
├── 3.8 Backend-Tests: Unit + Integration für beide Domains
└── 3.9 just check-adoption: dialogue_coach erreicht static + runtime + adopted
```

**DoD:** Alle Backend-Endpoints funktionieren; Adoption-Status erreicht.

### Phase 4 — Frontend: ASSIST-004 + Adaptive Dashboard (1-2 Sessions)

**Verantwortlich:** NarrareFrontendSpecialist (mit `frontend-design` + `web-design-guidelines` Skills)

```
Phase 4
├── 4.1 TS-Typen: packages/web/types/dialogue-coach.ts + adaptive.ts (RULE-17)
├── 4.2 API-Clients: lib/api/dialogue-coach.ts (SSE), lib/api/adaptive.ts (REST)
├── 4.3 Hooks: useDialogueCoach.ts, useAdaptiveContext.ts
├── 4.4 Dialogue Coach Components (components/analysis/dialogue-coach/)
│       ├── DialogueCoachPanel.tsx
│       ├── DialogueModeSelector.tsx
│       ├── DialogueIssueList.tsx, DialogueIssueCard.tsx
│       ├── DialogueAlternativeList.tsx, DialogueAlternativeCard.tsx
│       └── DialogueInlineDiff.tsx
├── 4.5 Adaptive Dashboard (components/studio/settings/)
│       ├── AdaptiveDashboard.tsx
│       ├── AdaptiveToggle.tsx
│       ├── AdaptiveWeightControls.tsx, AdaptiveWeightSlider.tsx
│       └── AdaptiveSourceList.tsx
├── 4.6 Status Indicator (components/studio/editor/AdaptiveStatusIndicator.tsx)
├── 4.7 i18n: 3 Namespaces × 3 Locales = 9 JSON-Dateien
├── 4.8 Frontend-Tests: Unit (Vitest), Visual Regression (Playwright/ADR-059)
└── 4.9 A11y-Validierung (axe-core)
```

**DoD:** Alle UI-Komponenten funktionieren; Tests grün; A11y-Validiert.

### Phase 5 — Pydantic Evals (1 Session)

**Verantwortlich:** NarrareCoreSpecialist + NarrarePlatformSpecialist

```
Phase 5
├── 5.1 evals/dialogue_coach/test_analyze_basic.py
├── 5.2 evals/dialogue_coach/test_improve_basic.py
├── 5.3 evals/dialogue_coach/test_voice_fidelity_weight_effect.py (RULE-18b)
├── 5.4 evals/dialogue_coach/test_preferences_respected.py
├── 5.5 evals/adaptive_context/test_with_and_without_preferences.py
└── 5.6 evals in CI einbinden
```

**DoD:** Adaptivität hat **messbaren Effekt** (Eval zeigt: Weight-Änderung → Output-Änderung).

### Phase 6 — Documentation & Governance (0.5 Session)

**Verantwortlich:** NarrareDocsSpecialist

```
Phase 6
├── 6.1 Recalibrate docs/features/learning/LEARN-002-style-adaptation.md
├── 6.2 Update docs/features/ai_assist/ASSIST-004-dialogue-coach.md
├── 6.3 ADR-TBD finalisieren (Status: ✅ Implemented)
├── 6.4 docs/architecture/decisions/INDEX.md updaten
├── 6.5 docs/_shared/CURRENT_STATE.md updaten
├── 6.6 docs/features/INDEX.md updaten (Status-Symbole)
├── 6.7 CHANGELOG.md Eintrag
├── 6.8 Doc Gate (14-Punkte-Checklist) für beide Features
└── 6.9 §7 Stub-Variable-Detector-Eintrag falls nötig (Q-B6)
```

**DoD:** Doc Gate passed; CHANGELOG aktuell; alle Cross-References korrekt.

---

## 13. Offene Architektur-Fragen für Architecture-Specialist

Alle offenen Fragen als Referenz-Tabelle. User-Entscheidungen sind markiert; die restlichen Fragen müssen vom Architecture-Specialist beantwortet werden.

### Adaptivitäts-Contract (Q-A1 — Q-A5)

| ID | Frage | Status |
|----|-------|--------|
| Q-A1 | `AdaptiveContextEnricher` ersetzt (`β`) / parallel (`α`) / delegiert (`γ`) zu `PreferenceContextEnricherImpl`? | offen — Brainstorming empfiehlt β |
| Q-A2 | Adaptive-Persistenz: eigene Tabelle `adaptive_settings` vs Erweiterung von `UserSettings`/`ProjectSettings` (JSON-Spalte)? | offen — Brainstorming empfiehlt Erweiterung |
| Q-A3 | `ProfileProvider` bleibt die Voice-Schnittstelle, oder brauchen wir eine neue `VoiceProfileConsumer`-Variante für Generation vs Checking? | offen |
| Q-A4 | Ist `AdaptiveContext` die **einzige** Preference-Injection-Quelle (konsolidiert), oder behalten wir parallele Injektionspfade? | offen — hängt mit Q-A1 zusammen |
| Q-A5 | Welche Intents/Routen **müssen** Adaptivität nutzen (Governance)? Vorschlag: alle AI-Operations, die Text generieren oder analysieren. | offen |

### ASSIST-004 (Q-B1 — Q-B6)

| ID | Frage | Status |
|----|-------|--------|
| Q-B1 | Ein Endpoint mit `mode`-Parameter vs zwei separate Endpoints (`/analyze`, `/improve`)? | offen |
| Q-B2 | Voice-Fidelity mit `voice_metrics` (ADR-057) ja/nein? Default: nein — `voice_metrics` bleiben checking-path only. | offen — Empfehlung: nein |
| Q-B3 | Auto-Inference der Sprecher (Light NLP) — Confidence-Schwelle? | offen — Core-Specialist mit |
| Q-B4 | Routeable `context_mode = "dialogue_coach"` vs direkter Mode im Intent? | offen — Architecture-Specialist |
| Q-B5 | Modify-Tracking: detailliertes Inline-Diff vs simpler Before/After-Block? | offen — Frontend-Specialist mit |
| Q-B6 | §7 Stub-Variable-Detector-Eintrag nötig (für neue routeable Surface)? | offen — Architecture-Specialist |

### LEARN-002 (Q-C1 — Q-C4)

| ID | Frage | Status |
|----|-------|--------|
| Q-C1 | Feature-ID `LEARN-002` bleibt? | **User: ja** ✅ |
| Q-C2 | Status-Wert `recalibrated` — valides Feature-Status-Feld? | offen — Docs-Specialist mit |
| Q-C3 | Adaptive Snapshot: eigene Tabelle vs `invocation_evidence`-Erweiterung? | **User: was architektonisch sauberer ist** — Empfehlung: β (Erweiterung) |
| Q-C4 | `AdaptiveContextProvider` (Core Protocol) vs `AdaptiveContextService` (Backend Service) — ist diese Trennung nötig oder Overengineering? | offen |

### Frontend (Q-D1 — Q-D4)

| ID | Frage | Status |
|----|-------|--------|
| Q-D1 | Adaptiv-Indikator im Toolbar? | **User: ja** ✅ |
| Q-D2 | Indikator in allen AI-Panels oder nur Editor? | offen — Empfehlung: erstmal Editor, später ausrollen |
| Q-D3 | Cross-Component-Update via TanStack Cache Invalidation ADR-043-konform? | offen — Architecture-Specialist |
| Q-D4 | Dialogue Coach als Tab in AnalysisTab oder eigenständiges Panel? | **User: Architect/Frontend-Specialist entscheidet** — mit `frontend-design` + `vercel-composition-patterns` Skills |

---

## 14. Skills bei Umsetzung

Pflicht-Skills für die Umsetzung der einzelnen Komponenten:

| Specialist | Skill | Wann | Zweck |
|-----------|-------|------|-------|
| NarrareFrontendSpecialist | `frontend-design` | Alle Dialogue Coach UI-Komponenten, Adaptive Dashboard, Status-Indikator | Distinkte, polierte UI; vermeidet generische AI-Optik |
| NarrareFrontendSpecialist | `vercel-composition-patterns` | Dialogue Coach Panel-Architektur (Tab vs Panel, Accept/Reject-Tracking-State) | Skalierbare Komponenten-Composition; Vermeidung boolean-prop-proliferation |
| NarrareFrontendSpecialist | `web-design-guidelines` | Vor Finalisierung jeder Frontend-Komponente; A11y-Review | Kontrast, Tastatur-Nav, ARIA, Reduced Motion; Pflicht für §8.7 |
| NarrareFrontendSpecialist | `tailwind-design-system` | Sliders, Toggle, Status-Indikator, Inline-Diff | Konsistente Design-Tokens; Wiederverwendung existierender Tailwind-Patterns |
| NarrareFrontendSpecialist | `vercel-react-best-practices` | SSE-Handling in `useDialogueCoach`, Cache Invalidation | Performance bei streaming; korrekte useEffect-Cleanup |
| NarrareCoreSpecialist | `building-pydantic-ai-agents` | `DialogueCoachAgent`-Implementation | Tools, Capabilities, Structured Output, Deps-Pattern |
| NarrareCoreSpecialist | `mem0` | Integration von `PreferenceProfile` in `AdaptiveContextProvider` | mem0-Client korrekt nutzen; graceful degradation |
| NarrareBackendSpecialist | `test-driven-development` | Alle Backend-Services (Contracts zuerst, dann Fakes, dann Impl) | RULE-03 (Contract-first) + RULE-10 (Tests not optional) |
| NarrarePlatformSpecialist | `test-driven-development` | Alle Core-Module | Same as above |
| All | `verification-before-completion` | Vor jedem "Done"-Claim | Run tests, check output, then claim |
| All | `requesting-code-review` | Vor Merge | Strukturierte Review-Anforderung |
| Coordinator | `writing-plans` | Nach ADR-Approval — schreibt detaillierten Implementation-Plan | Ersetzt dieses Spec durch task-by-task Plan |

---

## 15. Related ADRs

Liste aller relevanten ADRs, auf denen dieses Design aufbaut oder die es betrifft:

| ADR | Titel | Beziehung |
|-----|-------|-----------|
| [ADR-002](../../architecture/decisions/ADR-002-prompt-system.md) | Unified Prompt System | Prompt-Templates leben in `_bundled/ai_assist/`; PromptComposer baut Dialogue-Coach-Prompt |
| [ADR-015](../../architecture/decisions/ADR-015-agents-first-class.md) | Pydantic-AI Agents as First-Class Citizens | DialogueCoachAgent ist ein NarrareAgent; Modell via ModelRegistry |
| [ADR-021](../../architecture/decisions/ADR-021-deterministic-analysis-strategy.md) | Deterministic Analysis Strategy | Speaker-Attribution und Voice-Fidelity-Scoring nutzen Light NLP |
| [ADR-026](../../architecture/decisions/ADR-026-capability-prompt-injection.md) | Capability-Based Prompt Injection | Adaptive-Daten sind "Dynamic per-invocation content" (Kategorie 3); Capability `NarrareAdaptive` möglich |
| [ADR-032](../../architecture/decisions/ADR-032-pydantic-evals-ssot.md) | Pydantic Evals as Evaluation SSOT | Adaptivity-Effect-Evals (§9.3) |
| [ADR-033](../../architecture/decisions/ADR-033-mem0-v3-oss-memory-architecture.md) | mem0 2.0.x OSS Memory Architecture | PreferenceProfile wird via mem0 gespeichert/geladen |
| [ADR-038](../../architecture/decisions/ADR-038-ai-invocation-adoption-contract.md) | AI Invocation Adoption Contract | Adaptivitäts-Enricher folgt dem Pattern von PreferenceContextEnricherImpl |
| [ADR-040](../../architecture/decisions/ADR-040-kg-ssot-audit-lifecycle.md) | KG SSOT / Voice Profile SSOT | `ProjectWritingProfile` ist die SSOT für konsolidierte Voice-Sicht |
| [ADR-041](../../architecture/decisions/ADR-041-typed-manifests-drift-metrics.md) | Typed Manifests / Persistent Evidence | Option β für Adaptive Snapshot nutzt `invocation_evidence`-Tabelle |
| [ADR-043](../../architecture/decisions/ADR-043-ai-interaction-primitives.md) | Shared AI Interaction Primitives (`useAIOperation`) | Frontend-Integration von SSE; TanStack Query Invalidation Pattern |
| [ADR-045](../../architecture/decisions/ADR-045-runtime-adoption-enforcement.md) | Runtime Adoption Enforcement | `dialogue_coach` muss Adoption-Status erreichen (static/runtime/adopted) |
| [ADR-046](../../architecture/decisions/ADR-046-prompt-path-compliance.md) | Prompt-Path-Compliance | Neue routeable Surface muss §7-Checker berücksichtigen (Q-B6) |
| [ADR-052](../../architecture/decisions/ADR-052-session-stop-recovery.md) | Session Stop and WebSocket Recovery | SSE-Recovery bei Network-Disconnect (Edge Case E15) |
| [ADR-053](../../architecture/decisions/ADR-053-ai-session-lifecycle.md) | AI Session Lifecycle Pattern (WebSocket) | Falls Dialogue Coach in WebSocket-Session läuft (sonst SSE) |
| [ADR-054](../../architecture/decisions/ADR-054-inline-feature-prompt-debt-migration.md) | Inline Feature-Prompt Debt Migration | Dialogue-Coach-Prompt wird von Anfang an Mode 1 (PromptComposer) — kein Inline-f-string |
| [ADR-055](../../architecture/decisions/ADR-055-character-voice-contract.md) | Character Voice Storage Contract | `CharacterVoiceProfile` ist die SSOT für Voice-Daten |
| [ADR-056](../../architecture/decisions/ADR-056-runtime-aware-commit-gate-true-debt-baseline.md) | Runtime-Evidence-Aware Commit Gate | Adoption-Status für `dialogue_coach` muss runtime-verified sein |
| [ADR-057](../../architecture/decisions/ADR-057-voice-check-checking-path-contract.md) | Voice-Check Checking-Path Contract | `voice_metrics` bleiben checking-path only — Adaptivität injiziert nur `speech_summary` |
| [ADR-059](../../architecture/decisions/ADR-059-vrt-and-design-system-strategy.md) | Visual Regression Testing & Design System | Playwright `toHaveScreenshot()` für Status-Indikator und Adaptive Dashboard |
| [ADR-065](../../architecture/decisions/ADR-065-rule-13-two-method-run-stream-contract.md) | RULE-13 Two-Method run/stream Contract | DialogueCoachService braucht sowohl `run()` (für MCP/A2A) als auch `stream()` (für SSE) |
| [ADR-067](../../architecture/decisions/ADR-067-reusable-kb-context-provider.md) | Reusable KB-Context Provider | Muster für Provider-Design; `AdaptiveContextProvider` folgt ähnlichem Ansatz |

---

## 16. Glossary

| Term | Definition |
|------|------------|
| **AdaptiveContext** | Structured Core-Data-Model, das alle adaptiven Signale (Preferences, Voices, Constraints, Avoidance) für eine AI-Invocation konsolidiert. Definiert in `packages/core/narrare_core/ai_invocation/adaptive_context.py`. |
| **AdaptiveWeights** | User-einstellbare Floats (0.0–1.0), die kontrollieren, wie stark jedes adaptive Signal gewichtet wird. Bestandteil von AdaptiveContext. |
| **AdaptiveSettings** | Persistierte User-Settings: `enabled` (bool) + `weights`. Leben in UserSettings (oder eigener Tabelle — siehe Q-A2). |
| **Adaptivity Contract** | Die Core-Abstraktionsschicht (Provider + Enricher + Dataclasses), die PreferenceProfile und CharacterVoiceProfile konsolidiert. Nicht zu verwechseln mit dem AI Invocation Adoption Contract (ADR-038). |
| **Pilot Consumer** | Die erste konkrete AI-Operation, die den Adaptivity Contract explizit nutzt. In diesem Design: ASSIST-004 Dialogue Coach. |
| **Recalibration** | Die Neu-Interpretation einer bestehenden Feature-Spec mit anderem Scope. KEIN Superseding (Feature-ID bleibt); KEINE neue Spec. LEARN-002 wird recalibrated, nicht superseded. |
| **Adaptive Snapshot** | Ein Datensatz, der pro AI-Call protokolliert, welche adaptiven Signale den Prompt beeinflusst haben. Option β (empfohlen) speichert dies in `invocation_evidence`. |
| **Voice Fidelity** | Grad der Übereinstimmung zwischen generiertem Dialog und der etablierten Character-Voice. Wird im Dialogue Coach als Issue-Typ `voice_mismatch` und als Weight `voice_fidelity` berücksichtigt. |
| **§7 Stub-Variable-Detector** | CI-Check (ADR-046), der sicherstellt, dass neue routeable Prompt-Surfaces ihre Variablen im Manifest deklarieren. Mögliche relevant für `dialogue_coach` (Q-B6). |
| **Mode 1 (ADR-054)** | Inline-Feature-Prompt-Migration-Muster: PromptComposer baut den Prompt aus Intent + Context-Mode + gebündeltem Template. Dialogue Coach nutzt Mode 1 von Anfang an (kein Inline-f-string). |
| **Checking Path** | Ein Prompt-Pfad, der `voice_metrics` lesen darf (z.B. Voice-Check in WRITE-010). Adaptivität ist NICHT checking path — sie liest nur `speech_summary`. |
| **Effect Integrity (RULE-18b)** | Das Prinzip, dass eine konfigurierbare Einstellung nachweislich einen Effekt auf das Runtime-Verhalten haben muss. Für Weights durch Eval bewiesen (§9.3). |

---

## 17. Status & History

- **2026-07-19**: Initial design created via brainstorming session. User approved all 6 Abschnitte. Pending Architecture-Specialist ADR + user spec review.

### Abschnitte der Brainstorming

1. ~~Architektur-Überblick & Profile Sources~~ ✅ approved
2. ~~Adaptivitäts-Contract (Core)~~ ✅ approved
3. ~~ASSIST-004 Dialogue Coach~~ ✅ approved
4. ~~LEARN-002 Recalibration~~ ✅ approved
5. ~~Frontend / UX-Integration~~ ✅ approved
6. ~~Testing + ADR + Implementation Order~~ ✅ approved

### Nächste Schritte

1. **Architecture-Specialist** erstellt ADR-TBD auf Basis dieses Specs; beantwortet alle offenen Fragen aus §13.
2. **Coordinator** führt self-review dieses Dokuments durch.
3. **User** reviewt dieses Spec-Dokument + ADR.
4. **Coordinator** invokierte `writing-plans` Skill für detaillierten Implementation-Plan (task-by-task).
5. Implementation folgt in 6 Phasen (siehe §12).

---

> This design document is a brainstorming output. Implementation requires:
> 1. **Architecture-Specialist ADR** (resolves Q-A1..Q-D4 aus §13)
> 2. **User spec review** dieses Dokuments
> 3. **`writing-plans` skill invocation** für detaillierten Implementation-Plan
>
> Bis diese drei Schritte abgeschlossen sind, ist dieses Spec **nicht** als Architektur-Entscheidung verbindlich. Implementierung ohne abgeschlossenes ADR wäre ein RULE-21-Verstoß (Architecture review invalidated by material plan changes).
