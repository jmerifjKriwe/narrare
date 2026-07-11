# Content Review CR-05 – Initiale Befunde

> **Datum:** 2026-07-11
> **Reviewer:** NarrareCoreSpecialist (Content Review Audit)
> **Methode:** Kompilation und Verifikation aller Befunde aus cr-00 bis cr-04,
> cr-07, cr-08. Jeder Befund verifiziert gegen echten Code (Datei:Zeile) in
> seinem Ursprungs-Review. Cross-Referenzen dedupliziert — jeder Befund hat
> genau eine FIND-Datei bei seinem Ursprungs-Review.
>
> **Ausgabe:** 21 FIND-Dateien unter `_audit/results/content-review/findings/`
> + `README.md` als Index.
>
> **Aufgabe:** Verifiziere und vertiefe die bereits bekannten Befunde.
> Füge Code-Referenzen, konkrete Auswirkungen und priorisierte
> Lösungsvorschläge hinzu.

---

## Zusammenfassung

Aus den sieben vorangegangenen Reviews (cr-00, cr-01, cr-02, cr-03, cr-04,
cr-07, cr-08) wurden **21 materialle Befunde** (P1/P2) zu FIND-Dateien
konsolidiert. Zusätzlich wurden 15 P3-Aufgaben und 3 Stale-Items im Index
erfasst.

Die Plattform hat eine **starke Architektur-Grundlage** (⭐⭐⭐⭐ in den meisten
Reviews): ADR-026 Capability-Injection, ADR-046 Prompt-Resolution-Path,
ADR-050 KB-Context-Envelope, 5-Tier-TokenBudget für Writing, systematische
AI-UX-State-Machine (17 Operationen, 11 Gates). Die materiallen Befunde sind
**Implementierungs- und Inhalts-Lücken**, keine Design-Fehler.

### Prioritäts-Verteilung

| Priorität | Anzahl | Charakteristik |
|---|---|---|
| 🔴 Hoch (P1) | 3 | Funktional eingeschränkte Features + Enforcement-Lücke |
| 🟡 Mittel (P2) | 18 | Inhalts-Defizite, Adoptions-Gaps, UX-Lücken, Enhancements |
| 🔴 Kritisch (P0) | 0 | Keine kritischen Befunde |

### Die drei P1-Befunde

1. **FIND-001 (cr-03):** Consistency-Check ohne KG-Relationships — die
   höchstwertige Cross-Feature-Konsistenz-Prüfung (beziehungsbasierte
   Widersprüche) ist strukturell blind. `ConsistencyDeps` hat kein
   `kb_relationships`-Feld.

2. **FIND-002 (cr-03):** Coreference ohne Charakter-Liste — funktionaler
   Adoptions-Fehler. Pronomen-Resolution braucht zwingend Charakter-Namen,
   bekommt aber `kb_characters=""`. Das Modell muss raten.

3. **FIND-014 (cr-08) `[configuration-effect]`:** RULE-18b-Enforcement-Toolchain
   entfernt — die gesamte P0-P5-Governance-Toolchain (Matrix, Checker,
   Review-Gate) wurde in Commit `f8abb42c` gelöscht, aber CONSTRAINTS.md
   referenziert sie weiterhin als "CI-validated". False Control auf Meta-Ebene.
   Architektur-Entscheidung erforderlich (bereinigen vs. wiederherstellen).

### Thematische Cluster

| Cluster | FINDs | Kernproblem |
|---|---|---|
| **Analysis/KB Adoptions-Flickenteppich** | FIND-001, -002, -003, -004, -006 | Writing nutzt Budget-System, Analysis/KB truncieren blind nach Zeichen |
| **Prompt-Inhalts-Defizite** | FIND-007, -008, -009, -010, -011 | Fehlende JSON-Schemata, Do-NOT-Items, Runtime-Contracts, style_profile |
| **Prompt-Sicherheit & Hygiene** | FIND-012, -013 | candidate_pairs nicht gewrappt, Injection Defense doppelt |
| **Cross-Feature-Kohärenz** | FIND-005, -016, -017 | Preference-Gate, Legacy-Templates, fehlende Provenance |
| **UX-Lücken** | FIND-018, -019, -020, -021 | ChatPanel-Fehlermeldung, Consistency-Dismiss, Sentiment-Arc, Demo-Projekt |
| **Konfigurierbarkeit** | FIND-014, -015 | Enforcement-Toolchain gelöscht, Rate-Limiter hart codiert |

---

## Befund-Index

> Vollständiger Index mit allen FIND-Dateien, P3-Aufgaben und Stale-Items:
> [`findings/README.md`](findings/README.md)

### P1 (🔴 Hoch)

| FIND | Titel | Review |
|---|---|---|
| [FIND-001](findings/FIND-001-consistency-check-ohne-kg-relationships.md) | Consistency-Check ohne KG-Relationships | cr-03 |
| [FIND-002](findings/FIND-002-coreference-ohne-charakter-liste.md) | Coreference ohne Charakter-Liste | cr-03 |
| [FIND-014](findings/FIND-014-rule-18b-enforcement-toolchain-entfernt.md) | RULE-18b-Enforcement-Toolchain entfernt `[configuration-effect]` | cr-08 |

### P2 (🟡 Mittel)

| FIND | Titel | Review |
|---|---|---|
| [FIND-003](findings/FIND-003-analysis-context-assembler-ohne-tokenbudget.md) | Analysis-ContextAssembler ohne TokenBudget | cr-03 |
| [FIND-004](findings/FIND-004-kbconsistencyanalyzer-body-truncation.md) | KBConsistencyAnalyzer Body-Truncation hardcoded | cr-03 |
| [FIND-005](findings/FIND-005-mem0-preference-injection-gate.md) | mem0-Preference-Injection-Gate | cr-03 |
| [FIND-006](findings/FIND-006-adoption-scorer-token-budget.md) | Adoption-Scorer token_budget ohne Code-Nachweis | cr-03 |
| [FIND-007](findings/FIND-007-worldbuilding-phase1-defizite.md) | Worldbuilding Phase 1 Defizite | cr-01 |
| [FIND-008](findings/FIND-008-worldbuilding-phase2-json-schema.md) | Worldbuilding Phase 2 JSON-Schema | cr-01 |
| [FIND-009](findings/FIND-009-summarize-donot-json-format.md) | summarize Do-NOT + JSON-Format | cr-01 |
| [FIND-010](findings/FIND-010-kb-extract-runtime-input-contract.md) | kb/extract Runtime-Input Contract | cr-01 |
| [FIND-011](findings/FIND-011-style-profile-fehlt-in-writing-prompts.md) | style_profile in Writing-Prompts | cr-01 |
| [FIND-012](findings/FIND-012-candidate-pairs-wrapping.md) | candidate_pairs Wrapping | cr-01 |
| [FIND-013](findings/FIND-013-injection-defense-duplikat.md) | Injection Defense Duplikat | cr-02 |
| [FIND-015](findings/FIND-015-rate-limiter-hart-codiert.md) | Rate-Limiter hart codiert | cr-08 |
| [FIND-016](findings/FIND-016-writing-defr-legacy-templates.md) | Writing de/fr Legacy-Templates | cr-02 |
| [FIND-017](findings/FIND-017-provenance-annotated-kb-rendering.md) | Provenance-annotated KB-Rendering | cr-04 |
| [FIND-018](findings/FIND-018-chatpanel-generische-fehlermeldung.md) | ChatPanel generische Fehlermeldung | cr-07 |
| [FIND-019](findings/FIND-019-consistency-ignorieren-markierung.md) | Consistency Ignorieren-Markierung | cr-07 |
| [FIND-020](findings/FIND-020-emotionale-intensitaetskurve.md) | Emotionale Intensitätskurve _(Enhancement)_ | cr-07 |
| [FIND-021](findings/FIND-021-demo-projekt-beispiel-kb.md) | Demo-Projekt Beispiel-KB _(Enhancement)_ | cr-07 |

---

## Deduplizierungs-Protokoll

Folgende Cross-Referenzen wurden **nicht** als eigene FINDs angelegt, um
Duplikate zu vermeiden (jeder Befund lebt bei seinem Ursprungs-Review):

| cr-04 Cross-Ref | → FIND bei Ursprung |
|---|---|
| §3.2, §4.1 Consistency ohne KG | → FIND-001 (cr-03) |
| §2.2, §4.1 Coreference ohne Charaktere | → FIND-002 (cr-03) |
| §4.1 Analysis ohne TokenBudget | → FIND-003 (cr-03) |
| §4.1, §4.2.1 Preference-Injection-Gate | → FIND-005 (cr-03) |
| §5.4 worldbuilding phase1 writing_language | → FIND-007 (cr-01) |
| §4.2.3 style_profile in Writing | → FIND-011 (cr-01) |
| §5.2 Injection Defense Duplikat | → FIND-013 (cr-02) |
| §5.5 Writing de/fr Legacy | → FIND-016 (cr-02) |

**FIND-014 und FIND-015** behalten ihre aus cr-08 etablierten Nummern
(konsistent mit der Quell-Review, die diese IDs bereits vergab).

---

## Stale / Dokumentations-Schuld

Aus cr-00 dokumentiert (keine CR-AUFG-Nummer, hier zur Vollständigkeit):

1. **prompt-inventory.yaml Drift:** Inventory (2026-06-01) weicht massiv von
   Realität ab — Phantom de/fr-Dateien, fehlende Modi, verschobene chat-Kategorie.
   Aktion: Inventory regenerieren oder als deprecated markieren.

2. **ADR-039 Lücke:** INDEX springt ADR-038 → ADR-040 (kein ADR-039 vorhanden).

3. **Worldbuilding Phase 2 stale Bewertung:** Wird mit FIND-008 (JSON-Schema)
   und P3-Aufgabe CR-AUFG-01-11 (Bewertung aktualisieren) behoben.

---

## Neue Befunde (während dieses Reviews entdeckt)

Keine weiteren Befunde in diesem Review.

Die Kompilation hat keine neuen Befunde zutage gefördert, die in den
Einzelpreviews nicht bereits erfasst waren. Die Cross-Feature-Perspektive
(cr-04) hat die bestehenden Befunde bestätigt und thematisch verknüpft, aber
keine zusätzlichen materiallen Probleme identifiziert.

> Ein potentieller neuer Befund — **Voice-Checker ohne Beziehungs-Kontext**
> (`voice_check_prompt.py:92` setzt `kb_relationships=""`) — ist bereits als
> P3-Aufgabe CR-AUFG-03-09 in cr-03 erfasst und im Index dokumentiert. Keine
> Hochpriorisierung erforderlich, da Voice-Check auch ohne Beziehungs-Kontext
> funktional arbeitet (eingeschränkte, aber nicht fehlerhafte Qualität).

---

## Empfohlene Remediations-Reihenfolge

Basierend auf Priorität und Abhängigkeiten:

1. **FIND-014** (P1, configuration-effect) — Architektur-Entscheidung zuerst
   (blockiert CR-AUFG-08-14 Strukturpflicht für alle künftigen Reviews).
2. **FIND-001 + FIND-002** (P1) — Funktional eingeschränkte Features.
   Consistency ohne KG und Coreference ohne Charaktere sind die höchstwertigen
   funktionalen Lücken.
3. **FIND-005** (P2) — Preference-Injection-Gate. Wenn behoben, entfaltet
   mem0-Preference-Learning endlich Wirkung im Writing-Pfad.
4. **FIND-011** (P2) — style_profile in Writing-Prompts. Voraussetzung für
   Voice-Checker-Konsistenz (reduziert false-positive Inkonsistenz-Meldungen).
5. **FIND-007 bis FIND-010** (P2) — Prompt-Inhalts-Defizite. Schnelle Wins
   (Template-Updates, keine Architekturänderung).
6. **FIND-003, FIND-004, FIND-006** (P2) — Analysis/KB Adoptions-Flickenteppich.
   Größerer Scope, Koordination mit Architecture-Specialist (Contract first).
7. **FIND-017** (P2) — Provenance-Rendering. Contract-Erweiterung (RULE-03).
8. **FIND-018 bis FIND-021** (P2) — UX-Lücken und Enhancements.
9. **FIND-012, FIND-013, FIND-015, FIND-016** (P2) — Hygiene und
   Konfigurierbarkeit.

P3-Aufgaben nach opportunistischer Gelegenheit (wenn ohnehin am Code).

---

*End of CR-05 Initial Findings. Alle Befunde gegen echten Code verifiziert
(Datum: 2026-07-11). Siehe `findings/README.md` für den vollständigen Index.*
