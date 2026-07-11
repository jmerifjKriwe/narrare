# Content Review — Findings Index

> **Stand:** 2026-07-11 (CR-05 Initial Findings, erster Lauf)
> **Quellen:** cr-00, cr-01, cr-02, cr-03, cr-04, cr-07, cr-08
> **Format:** Eine FIND-Datei pro materialem Befund (P0/P1/P2). P3-Aufgaben
> und Stale-Items unten zusammengefasst.

---

## Aktueller Stand

| Metrik | Wert |
|---|---|
| Materialle FINDs (P0/P1/P2) | 21 |
| davon 🔴 Hoch (P1) | 3 |
| davon 🟡 Mittel (P2) | 18 |
| davon 🔴 Kritisch (P0) | 0 |
| P3-Aufgaben (nicht als FIND) | 15 |
| configuration-effect-Befunde | 1 (FIND-014) |
| Enhancements (P2) | 2 (FIND-020, FIND-021) |

**Gesamt-Trend:** Die Plattform hat eine starke Architektur-Grundlage
(⭐⭐⭐⭐ in den meisten Reviews). Die materiallen Befunde sind
**Implementierungs- und Inhalts-Lücken**, keine Design-Fehler. Drei P1-Befunde
betreffen funktional eingeschränkte Features (Consistency ohne KG,
Coreference ohne Charaktere) und eine Enforcement-Lücke (RULE-18b Toolchain).

---

## Befund-Index (P0/P1/P2 — mit FIND-Datei)

### 🔴 Hoch (P1)

| FIND | Titel | Review | CR-AUFG | Status |
|---|---|---|---|---|
| [FIND-001](FIND-001-consistency-check-ohne-kg-relationships.md) | Consistency-Check ohne KG-Relationships | cr-03 | CR-AUFG-03-01 | Offen |
| [FIND-002](FIND-002-coreference-ohne-charakter-liste.md) | Coreference ohne Charakter-Liste | cr-03 | CR-AUFG-03-02 | Offen |
| [FIND-014](FIND-014-rule-18b-enforcement-toolchain-entfernt.md) | RULE-18b-Enforcement-Toolchain entfernt, CONSTRAINTS.md stale `[configuration-effect]` | cr-08 | CR-AUFG-08-15 | Offen |

### 🟡 Mittel (P2)

| FIND | Titel | Review | CR-AUFG | Status |
|---|---|---|---|---|
| [FIND-003](FIND-003-analysis-context-assembler-ohne-tokenbudget.md) | Analysis-ContextAssembler ohne TokenBudget-System | cr-03 | CR-AUFG-03-03 | Offen |
| [FIND-004](FIND-004-kbconsistencyanalyzer-body-truncation.md) | KBConsistencyAnalyzer Body-Truncation hardcoded | cr-03 | CR-AUFG-03-04 | Offen |
| [FIND-005](FIND-005-mem0-preference-injection-gate.md) | mem0-Preference-Injection-Gate verhindert Preferences im Writing-Prompt | cr-03 | CR-AUFG-03-05 | Offen |
| [FIND-006](FIND-006-adoption-scorer-token-budget.md) | Adoption-Scorer wertet token_budget als "adopted" ohne Code-Nachweis | cr-03 | CR-AUFG-03-07 | Offen |
| [FIND-007](FIND-007-worldbuilding-phase1-defizite.md) | Worldbuilding Phase 1 Prompt-Defizite (JSON-Schema + writing_language) | cr-01 | CR-AUFG-01-01, -02 | Offen |
| [FIND-008](FIND-008-worldbuilding-phase2-json-schema.md) | Worldbuilding Phase 2 — fehlendes formales JSON-Output-Schema | cr-01 | CR-AUFG-01-03 | Offen |
| [FIND-009](FIND-009-summarize-donot-json-format.md) | summarize-Prompt — Do-NOT <4 Items + fehlendes JSON-Format | cr-01 | CR-AUFG-01-04 | Offen |
| [FIND-010](FIND-010-kb-extract-runtime-input-contract.md) | kb/extract — fehlender Runtime-Input Contract | cr-01 | CR-AUFG-01-05 | Offen |
| [FIND-011](FIND-011-style-profile-fehlt-in-writing-prompts.md) | {{style_profile}} fehlt in 4 von 8 EN Writing-Prompts | cr-01 | CR-AUFG-01-06 | Offen |
| [FIND-012](FIND-012-candidate-pairs-wrapping.md) | {{candidate_pairs}} nicht XML-gewrappt trotz User-Content-Risiko | cr-01 | CR-AUFG-01-09 | Offen |
| [FIND-013](FIND-013-injection-defense-duplikat.md) | Injection Defense Duplikat zwischen NarrareMeta und NarrareUniversalRules | cr-02 | CR-AUFG-02-08 | Offen |
| [FIND-015](FIND-015-rate-limiter-hart-codiert.md) | Rate-Limiter hart codiert, nicht operator-konfigurierbar | cr-08 | CR-AUFG-08-16 | Offen |
| [FIND-016](FIND-016-writing-defr-legacy-templates.md) | Writing de/fr Legacy-Templates — ADR-026 Phase 5 Deviation | cr-02 | CR-AUFG-02-09 | Offen |
| [FIND-017](FIND-017-provenance-annotated-kb-rendering.md) | Kein Provenance-annotated KB-Rendering | cr-04 | CR-AUFG-04-01 | Offen |
| [FIND-018](FIND-018-chatpanel-generische-fehlermeldung.md) | ChatPanel zeigt generische Fehlermeldung statt strukturierte | cr-07 | CR-AUFG-07-25 | Offen |
| [FIND-019](FIND-019-consistency-ignorieren-markierung.md) | Consistency-Check — keine "Ignorieren"/"Resolved"-Markierung | cr-07 | CR-AUFG-07-26 | Offen |
| [FIND-020](FIND-020-emotionale-intensitaetskurve.md) | Emotionale Intensitätskurve (Sentiment-Arc) nicht visualisiert _(Enhancement)_ | cr-07 | CR-AUFG-07-28 | Offen |
| [FIND-021](FIND-021-demo-projekt-beispiel-kb.md) | Kein Demo-Projekt mit Beispiel-KB für Onboarding-Aha-Moment _(Enhancement)_ | cr-07 | CR-AUFG-07-29 | Offen |

---

## Cross-Referenzen (keine Duplikate)

Die folgenden Befunde werden in mehreren Reviews erwähnt, sind aber nur einmal
als FIND angelegt (bei ihrem Ursprungs-Review). cr-04 hat mehrere Cross-Refs
auf cr-01/cr-02/cr-03-Befunde — diese werden hier **nicht** dupliziert:

| FIND | Ursprung | Auch erwähnt in |
|---|---|---|
| FIND-001 (Consistency ohne KG) | cr-03 | cr-04 §3.2, §4.1 |
| FIND-002 (Coreference ohne Charaktere) | cr-03 | cr-04 §2.2, §4.1 |
| FIND-003 (Analysis ohne TokenBudget) | cr-03 | cr-04 §4.1 |
| FIND-005 (Preference-Injection-Gate) | cr-03 | cr-04 §4.1, §4.2.1 |
| FIND-007 (Worldbuilding phase1 writing_language) | cr-01 | cr-04 §5.4 |
| FIND-011 (style_profile in Writing) | cr-01 | cr-04 §4.2.3 |
| FIND-013 (Injection Defense Duplikat) | cr-02 | cr-04 §5.2 |
| FIND-016 (Writing de/fr Legacy) | cr-02 | cr-00 §6, cr-04 §5.5 |

---

## P3-Aufgaben (🟢 Niedrig — keine eigene FIND-Datei)

Diese Aufgaben sind dokumentiert, haben aber zu niedrige Priorität für eine
eigene FIND-Datei. Sie sind in ihren Ursprungs-Reviews vollständig beschrieben.

### cr-01 (Gates/Registry/Dokumentation)

| CR-AUFG | Titel | Typ | Review-Datei |
|---|---|---|---|
| CR-AUFG-01-07 | Do-NOT-Item-Count-Checker implementieren (≥4 Items) | gate/check | cr-01 §Aufgaben |
| CR-AUFG-01-08 | JSON-Output-Schema-Vorhandensein-Checker implementieren | gate/check | cr-01 §Aufgaben |
| CR-AUFG-01-10 | `{{style_profile}}` zu SHOULD_VARS für writing hinzufügen | manifest/registry | cr-01 §Aufgaben |
| CR-AUFG-01-11 | prompt-content-standards.md phase2-Bewertung aktualisieren | documentation | cr-01 §Aufgaben |
| CR-AUFG-01-12 | prompt-standards.md Appendix A chat-Pfad korrigieren | documentation | cr-01 §Aufgaben |

### cr-02 (Content-Hygiene/Dead-Code)

| CR-AUFG | Titel | Typ | Review-Datei |
|---|---|---|---|
| CR-AUFG-02-10 | MetaPromptLoader vollständig entfernen (Dead-Code) | dead-code | cr-02 §Aufgaben |
| CR-AUFG-02-11 | Chat-Template Redundanz reduzieren (Content-Polish) | content-quality | cr-02 §Aufgaben |

### cr-03 (Erweiterung/Enforcement)

| CR-AUFG | Titel | Typ | Review-Datei |
|---|---|---|---|
| CR-AUFG-03-06 | mem0 Cross-Session Writing Context evaluieren | Erweiterung | cr-03 §Aufgaben |
| CR-AUFG-03-08 | Runtime-Gate: leere KB-Variablen-Werte erkennen | enforcement | cr-03 §Aufgaben |
| CR-AUFG-03-09 | Voice/Planning-Services: kb_relationships füllen (nicht ="") | adoption | cr-03 §Aufgaben |

### cr-04 (Evaluierung/Dokumentation)

| CR-AUFG | Titel | Typ | Review-Datei |
|---|---|---|---|
| CR-AUFG-04-02 | Storyboard↔KB Inhalts-Konsistenz-Prüfung evaluieren | Evaluierung | cr-04 §Aufgaben |
| CR-AUFG-04-03 | Frontmatter-Schema-Validierung einführen | gate/check | cr-04 §Aufgaben |
| CR-AUFG-04-04 | Tier-3 Entity-Typ-Klassifikation erweiterbar machen | Core-Refactoring | cr-04 §Aufgaben |
| CR-AUFG-04-05 | Konsistenz Voice-Profile-Format und Entity-Format dokumentieren | documentation | cr-04 §Aufgaben |

### cr-07 (i18n)

| CR-AUFG | Titel | Typ | Review-Datei |
|---|---|---|---|
| CR-AUFG-07-27 | Legacy-i18n-Block: unverdeutschte Strings im deutschen studio.json entfernen | i18n | cr-07 §Aufgaben |

---

## Stale / Dokumentations-Schuld (aus cr-00, nicht als CR-AUFG erfasst)

Diese Items wurden in cr-00 als bekannte Probleme dokumentiert, haben aber
keine eigene CR-AUFG-Nummer. Sie sind hier zur Vollständigkeit erfasst.

| Item | Beschreibung | Status | Quelle |
|---|---|---|---|
| **prompt-inventory.yaml Drift** | Inventory (Stand 2026-06-01) weicht massiv von Realität ab: Phantom de/fr-Dateien für analysis/kb/planning/wiki; fehlende Modi (character_voice, coreference, voice_check, etc.); verschobene chat-Kategorie; unvollständige writing de/fr. | Offen (Dokumentations-Dienst) | cr-00 §1, §6 |
| **ADR-039 Lücke** | INDEX springt ADR-038 → ADR-040 (kein ADR-039 vorhanden). | Offen (Dokumentations-Lücke) | cr-00 §6 |
| **Worldbuilding Phase 2 stale Bewertung** | `prompt-content-standards.md` L224 bewertet phase2 als ⭐⭐⭐ ("Missing: formal output schema, Do-NOT, CoT, confidence"). Teilweise veraltet: Do-NOT/CoT/Confidence wurden hinzugefügt. Nur JSON-Schema fehlt (FIND-008). | Wird mit FIND-008 + CR-AUFG-01-11 behoben | cr-01 §1.3 stale finding |

---

## Quell-Review-Dateien

| Review | Pfad | Fokus |
|---|---|---|
| cr-00 | `../cr-00-kontext.md` | Projekt-Kontext, Prompt-Inventar, Vorbelastung |
| cr-01 | `../audit-prompts/cr-01-prompt-quality.md` | Default-Prompts Qualitätsaudit |
| cr-02 | `../coherence/cr-02-system-prompt.md` | Prompt-Architektur & KI-Persona |
| cr-03 | `../adoption/cr-03-feature-adoption.md` | Feature-Adoption (mem0, ContextBudget, KG) |
| cr-04 | `../coherence/cr-04-cross-feature.md` | Cross-Feature-Kohärenz |
| cr-07 | `../cr-07-ux.md` | UI/UX & AI-Interaktionsqualität |
| cr-08 | `../cr-08-hardcoded-values.md` | Hardcodierte Werte & Konfigurierbarkeit |
| cr-05 | `../cr-05-initial-findings.md` | Dieser Index (Initial Findings Kompilation) |
