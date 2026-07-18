# Content Review CR-03 – Feature-Adoption

> **Review-Datum:** 2026-07-11
> **Reviewer:** Core Specialist (Content Review Audit)
> **Methode:** `code-review-graph` MCP Tools (Graph: 27.434 Knoten, 0 Embeddings →
> Keyword/Hybrid-Suche) + Read/Grep Fallback. Alle Einträge gegen echten Code
> verifiziert (Datei:Zeile), nicht aus Annahmen.
> **Kontext:** `_audit/results/content-review/cr-00-kontext.md`
> **Fokus:** Werden mem0, ContextBudget und Knowledge Graph *dort* genutzt, wo
> sie dem Nutzer echten Mehrwert bringen? Oder wurden sie eingebaut und vergessen?
>
> **Abgrenzung zu CR-08:** CR-03 prüft ADOPTION (wird die Infrastruktur genutzt,
> wo sie Mehrwert bringt?), CR-08 prüft KONFIGURIERBARKEIT (kann man Werte
> ändern?). Token-Limit-Konstanten selbst (Werte, Profile) werden hier nur
> bezüglich Aufgabeneignung bewertet — Konfigurierbarkeit siehe CR-08 §1.

---

## 1. mem0 – Adoption-Analyse

### 1.1 Aktuelle Nutzung vs. Sinnvolle Nutzung

> Verifiziert via `query_graph_tool(callers_of, FeedbackService)` und
> `callers_of(PreferenceService)` — Produktions-Caller extrahiert, Tests
> ausgeblendet. Code-Pfade in `cr-00-kontext.md` §4 bestätigt.

| Feature | Aktuelle mem0-Nutzung | Wäre mem0 hier sinnvoll? | Begründung |
|---|---|---|---|
| **Feedback Collection** (Writing-accept/reject/edit) | ✅ `FeedbackService.record()` → `mem0.add()` (`feedback_service.py:46-75`). Übersetzt `FeedbackEvent` in natürlichsprachlichen Text. Caller: `_get_feedback_service` in `memory/router.py:59` — einziger Produktions-Caller. | ✅ Ja (sinnvoll) | Preference-Learning braucht Feedback-Daten. Sauber getrennt: DB-Persist immer, mem0-Forward best-effort. |
| **Preference Derivation** (alle Schreib-/Analyse-Features) | ✅ `PreferenceService.get_preferences()` → `mem0.search()` (`preference_service.py:50-105`). Intent-spezifische Queries extrahieren 8 Preference-Dimensionen. Caller: `_get_preference_service_instance` in `_app/dependencies_prompts.py:110` (für PromptComposer-Injection). | ✅ Ja (sinnvoll) | Preferences sollen jeden Prompt anreichern. Adoption via PromptComposer ist architektonisch korrekt. |
| **Preference Injection** (in Prompts) | ✅ `PromptComposer.build()` ruft `get_preferences()` auf, wenn `preference_service` konfiguriert UND Context leer (`composer.py:93-113`). Injiziert als `user_preferences`-Variable. | ⚠️ Bedingt | Siehe Befund unten: Injection greift nur, wenn Context "leer" ist — bei WritingContextAssembler-vorangestellten Services möglicherweise nie. |
| **Consistency Check** | ❌ Keine mem0-Nutzung | ⚠️ Potenziell | mem0 könnte speichern, welche Konsistenz-Probleme wiederkehren, um wiederkehrende Muster zu erkennen. Aktuell kein Feedback-Loop vom Consistency-Resultat zu mem0. |
| **KB-Interview / Worldbuilding** | ❌ Keine mem0-Nutzung | ❌ Eher nicht | Einmalige Setup-Aufgaben; mem0-Mehrwert gering. |
| **Cross-Session Writing Continuity** | ❌ Keine mem0-Nutzung | ✅ Ja (hoher Mehrwert) | mem0 könnte Notizen aus vergangenen Schreib-Sessions speichern ("User arbeitete an Plot-Wendung in Kapitel 7", "Nutzer bevorzugt Cliffhanger-Endings pro Kapitel"). Aktuell startet jede Session ohne Erinnerung an vorherige Schreib-Entscheidungen. |
| **Character Voice Memory** | ❌ Keine mem0-Nutzung | ⚠️ Potenziell | ADR-055 (Character Voice) extrahiert Sprachmuster pro Charakter — diese könnten in mem0 persistiert werden, statt sie jedesmal neu zu profilieren. Aktuell live-pro-fektiv. |

### 1.2 Konkrete mem0-Nutzungsszenarien (priorisiert)

**Szenario 1 – Cross-Session Writing Context (höchste Priorität):**
- **Speichern:** Nach jeder Schreib-Session: "Nutzer schrieb Kapitel 7 mit Cliffhender-Endung", "Plot-Wendung: Antagonist entlarvt", "Nutzer entschied sich für第一-Person-Perspektive".
- **Abrufen:** Beim Start einer neuen Schreib-Session → Session-Kontext-Anreicherung ("Du arbeitest an einem Roman, wo in Kapitel 7 …").
- **Mehrwert:** Kontinuität über Sessions hinweg ohne manuelles Re-Kontextualisieren.

**Szenario 2 – Preference-Injection-Gate fixen (hohe Priorität):**
- **Problem:** `composer.py:93-113` injiziert Preferences nur, wenn `context` (PromptContext) "leer" ist. Die WritingContextAssembler-vorangestellten Services füllen den Context aber immer (`kb_characters`, `chapter_content`, etc.) — somit greift die Preference-Injection im Writing-Pfad möglicherweise nie.
- **Speichern/Abrufen:** Keine neuen mem0-Daten nötig — der Gate muss korrigiert werden, damit Preferences auch bei gefülltem Context injiziert werden.
- **Mehrwert:** mem0-Preferences erreichen tatsächlich die Schreib-Prompts.

**Szenario 3 – Consistency-Feedback-Loop (mittlere Priorität):**
- **Speichern:** Wenn ein Nutzer eine Consistency-Issue als "false positive" oder "resolved" markiert.
- **Abrufen:** Bei der nächsten Consistency-Prüfung → "Nutzer hat ähnliches Issue bereits als beabsichtigt markiert".
- **Mehrwert:** Reduziert wiederkehrende False-Positives, lernt beabsichtigte "Inkonsistenzen".

**Bewertung mem0-Adoption:** ⭐⭐⭐
**Befunde:**
- mem0 ist architektonisch korrekt integriert (graceful degradation, NullMemoryClient-Fallback,
  RULE-08-Konfinement auf `core/memory/`). Die **zwei** vorhandenen Use-Cases (Feedback +
  Preferences) sind sauber implementiert.
- **Aber:** Der Adoptions-Radius ist **eng** — mem0 deckt nur LEARN-001 ab. Die
  Preference-Injection hat ein mögliches Gate-Problem (nur bei leerem Context). Drei
  hochwertige Szenarien (Cross-Session-Context, Consistency-Loop, Voice-Memory) sind
  ungenutzt. mem0 ist "eingebaut und funktional, aber nicht ausgereizt".

---

## 2. ContextBudget – Adoption-Analyse

> Verifiziert via `query_graph_tool(callers_of, TokenBudgetManager)` (46 Caller,
> fast alle Tests) + `callers_of(WritingContextAssembler.assemble)` + Read der
> Analysis- und KB-Context-Builder.

### 2.1 Aktuelle Nutzung

| Feature | ContextBudget genutzt? | Token-Limit bekannt? | Overflow-Handling? |
|---|---|---|---|
| **Writing — new_chapter / extend / rewrite / coauthor** (`writing/service.py`, `extend_service.py`, `rewrite_service.py`, `coauthor_service.py`) | ✅ Ja — via `WritingContextAssembler` mit `TokenBudgetManager` (5-Tier, DEFAULT_TOTAL_BUDGET=6000) | ✅ Ja (`budget.py:59`, Profile-basiert via `token_profiles.py`) | ✅ Ja — Tier-Overflow fließt in nächsten Tier; Pinned ist Bypass (`context_assembler.py:190-229`) |
| **Writing — scene_by_scene / interactive_session / chat / interview** | ✅ Ja (WritingContextAssembler, gleiche Pipeline) | ✅ Ja | ✅ Ja |
| **Writing — inline_suggest** (`suggest_service.py`) | ❌ Nein — bewusst bypassed (ADR-045 D3 C: <500ms Latenz-Ziel, `preference_enrichment: not_applicable`) | ✅ `SUGGEST_MAX_TOKENS=60` (`run_limits.py:27`, immutable) | N/A (Low-Latency-Pfad) |
| **Writing — story_suggest** (`story_suggest_service.py`) | ⚠️ Teilweise | ⚠️ Siehe Befund | ⚠️ Siehe Befund |
| **Analysis — beta_reader** (`beta_reader_service.py` → `analysis/context_assembler.py`) | ❌ **Nein** — eigener `ContextAssembler` OHNE TokenBudgetManager. Hardcodiert `kb_summary_truncation=200` Zeichen (`analysis/context_assembler.py:50`) | ❌ Nein (kein Token-Limit, nur Char-Truncation) | ❌ Nein — stilles Abschneiden bei 200 Zeichen pro KB-Eintrag |
| **Analysis — consistency / fact_extraction** (`consistency_orchestrator.py`, `kb/consistency_analyzer.py`) | ❌ **Nein** — `KBConsistencyAnalyzer` trunciert `entity.body[:5000]` hardcoded (`consistency_analyzer.py:199`). `ConsistencyOrchestrator` bekommt `max_chapter_tokens` als Param, aber keine Tier-Allokation. | ⚠️ Teilweise (`max_chapter_tokens`-Param existiert) | ❌ Nein |
| **Analysis — POV / Readability / Coreference / Voice** (`coreference_service.py`, etc.) | ❌ **Nein** — bauen `PromptContext` ad-hoc, setzen KB-Variablen auf leere Strings (`coreference_service.py:175-179`) | ❌ Nein | ❌ Nein |
| **Analysis — character_voice / voice_check** (`character_voice_prompt.py`, `voice_check_prompt.py`) | ❌ Nein — `kb_relationships=""` hardcoded | ❌ Nein | ❌ Nein |
| **Planning — outline / character_arc / timeline** (`planning/timeline_analysis_service.py`) | ❌ Nein — `kb_relationships=""` (`timeline_analysis_service.py:188`) | ❌ Nein | ❌ Nein |
| **KB — extract / interview / improve / merge / suggest / enhance / worldbuilding** | ❌ Nein — bauen PromptContext ohne Budget-System | ❌ Nein (Registry sagt `token_budget: partial`) | ❌ Nein |

### 2.2 Problematische Stellen

1. **Analysis-ContextAssembler (`apps/api/narrare/analysis/context_assembler.py`)** — **KRITISCH:**
   Dies ist ein **völlig eigener** ContextAssembler, der NICHT von
   `WritingContextAssembler` / `TokenBudgetManager` erbt. Er trunciert KB-Einträge
   auf 200 Zeichen (`kb_summary_truncation=200`) ohne Token-Bewusstsein. Bei großen
   KBs oder langen Kapiteln schneidet er still ab. **Kein Overflow-Handling,
   keine Priorisierung, keine Tier-Logik.** Dies ist der BetaReader-Pfad — das
   Modell arbeitet potenziell mit unvollständigem KB-Kontext.

2. **KBConsistencyAnalyzer (`apps/api/narrare/kb/consistency_analyzer.py:199`)** —
   `entity.body[:5000]` hardcoded. Bei Einträgen >5000 Zeichen schneidet der
   Consistency-Check mitten im Content ab — das Modell sieht
   unvollständige Daten und kann Feld-Widersprüche übersehen, die im
   abgeschnittenen Teil liegen.

3. **Coreference-Service (`apps/api/narrare/analysis/coreference_service.py:175-179`)** —
   Setzt **alle** KB-Variablen (`kb_characters`, `kb_locations`, `kb_factions`,
   `kb_relationships`) auf leere Strings. Kommentar: *"No KB repository is wired
   for this call path (the service constructor intentionally omits it)"*.
   **Coreference-Resolution braucht aber Charakter-Namen!** Das Modell muss
   Pronomen zu Charakteren zuordnen, bekommt aber die Charakter-Liste nicht.

4. **Voice-Check / Character-Voice-Prompts** — setzen `kb_relationships=""`.
   Character-Voice-Profiling ohne Beziehungs-Kontext verliert Information darüber,
   wie Charaktere miteinander sprechen.

5. **Planning-Services** — setzen `kb_relationships=""`. Outline/Character-Arc
   ohne Beziehungs-Graph plant Charakter-Entwicklung ohne Berücksichtigung
   bestehender Beziehungen.

### 2.3 Priorisierungs-Strategie

Wenn nicht alles in den Kontext passt: Was ist wichtiger?

**Empfehlung für Priorisierungs-Reihenfolge (universell, orientiert an
cr-00 §3 Tier-System, auf Analysis/KB übertragen):**

1. **Direkter Kontext** (zu analysierender Kapiteltext / KB-Eintrag) — ohne
   diesen ist die Aufgabe unlösbar. Entspricht Tier-1 (Immediate).
2. **Referenzierte KB-Entities** (Charaktere, Orte, die im Text vorkommen) —
  最低 nötig für Konsistenz. Entspricht Tier-3 (KB Referenced).
3. **KB-Beziehungen** (relevant für die Analyse) — für Coreference,
   Consistency, Voice. Entspricht Tier-3-Erweiterung.
4. **User-Preferences** (Stil-Vorgaben) — anreichernd, nicht kritisch.
   Entspricht Preference-Injection.
5. **KB-Suggested** (semantisch vorgeschlagene Entities) — nur wenn Budget
   bleibt. Entspricht Tier-4.

> **Problem:** Diese Priorisierung existiert **nur** für Writing (via
> WritingContextAssembler). Analysis und KB haben kein analoges System —
> dort entscheidet hartcodierte Char-Truncation blind, was reinkommt.

**Bewertung ContextBudget-Adoption:** ⭐⭐⭐
**Befunde:**
- **Writing** ist vorbildlich: 5-Tier-System, mode-spezifische Allokation
  (extend/rewrite/first_chapter/wiki_optimized), konfigurierbare Overrides,
  Pinned-Bypass. ⭐⭐⭐⭐⭐ für Writing.
- **Analysis, KB, Planning** haben **kein** Budget-System. Drei eigene
  Context-Builder (`analysis/context_assembler.py`, ad-hoc PromptContext,
  `consistency_analyzer.py`) truncieren blind nach Zeichen. Das ist ein
  **struktureller Adoptions-Flickenteppich**: eine Hälfte der Plattform
  nutzt das Budget-System, die andere ignoriert es.
- Coreference ohne KB-Charaktere ist ein **funktionaler Adoptions-Fehler**,
  kein Budget-Problem — aber symptomatisch für fehlende Kontext-Disziplin
  außerhalb von Writing.

---

## 3. Knowledge Graph – Adoption-Analyse

> Verifiziert via `query_graph_tool(callers_of, GraphService)` (3 Caller: dep +
> 2 Tests), `semantic_search_nodes_tool` (KG-Traversal), Grep nach
> `kb_relationships` (22 Matches), Read von `query_service.py`,
> `graph_service.py`, `consistency_types.py`.

### 3.1 Aktuelle Nutzung

| Feature | KG genutzt? | Zweck | Sinnvoll erweitert? |
|---|---|---|---|
| **KB Graph Visualization** (`kb/graph_service.py:GraphService`, `kb/router_graph.py`) | ✅ Ja | **Visualisierung nur.** Serialisiert Entities + Relationships zu GraphNodes/GraphEdges für Frontend. BFS-Kürzester-Pfad, Adjacency-Map, Degree-Berechnung. Caller: nur `get_graph_service` dep + Tests. | ⚠️ Funktional, aber **reiner Frontend-Export** — kein Reasoning damit. |
| **Writing — new_chapter / extend / rewrite / coauthor** | ✅ Ja (flach) | `fetch_formatted_relationships()` → `kb_relationships` als **flacher formatierter Text-String** im Prompt. 4 Services: `service.py:156`, `extend_service.py:229`, `rewrite_service.py:234`, `coauthor_service.py:217`. | ⚠️ Flach — das Modell bekommt eine Text-Liste von Beziehungen, keinen traversierbaren Graphen. |
| **KBAgent (interactive)** (`agents/kb_agent.py`) | ✅ Ja | `KBQueryService.get_related()` als Agent-Tool — der interaktive KB-Agent kann verwandte Entities abfragen. | ✅ Sinnvoll — Agent kann Graph bei Bedarf traversieren. |
| **Consistency Check** (`consistency_orchestrator.py`, `kb/consistency_analyzer.py`) | ❌ **Nein** | `ConsistencyDeps` hat KEIN Beziehungs-Feld (`consistency_types.py:107-127`: nur `kb_entity_summaries`, `timeline_events`, `extracted_facts`). `KBConsistencyAnalyzer` prüft nur **entry-internal** Feld-Widersprüche, keine cross-entity-Beziehungs-Konsistenz. | ❌ **Nein — größte Unternutzung.** Siehe §3.2. |
| **Analysis — Coreference / POV / Voice** | ❌ Nein | `kb_relationships=""` — siehe §2.2. | ❌ Nein |
| **Planning — Outline / Character-Arc / Timeline** | ❌ Nein | `kb_relationships=""` — siehe §2.2. | ❌ Nein |
| **KB-005 Proactive Context** (`context/proactive_service.py`) | ⚠️ Teilweise | Hybrid-Scoring (semantisch + strukturell) für KB-Suggestions — nutzt Ähnlichkeit, aber keine Graph-Traversal für Vorschläge. | ⚠️ Könnte Graph-Nachbarschaft für bessere Vorschläge nutzen. |

### 3.2 Untergenutzte KG-Potenziale

- **Werden Charakter-Beziehungen aus dem KG für Consistency-Checks genutzt?**
  **NEIN.** Dies ist die größte Unternutzung. Der Consistency-Check (`ConsistencyAgent`)
  kann Beziehungen weder sehen noch prüfen. Ein Beispiel: Wenn der KG sagt
  "Aria ist Feindin von Malachai" (relationship_type=`enemy`), der Text aber
  beschreibt, wie sie verbündet kämpfen, würde der Consistency-Check dies
  **nicht** erkennen — weil `ConsistencyDeps` keine `kb_relationships` enthält.
  Die `ConsistencyCheckType.WORLD` ("faction relationships") existiert als
  Typ (`consistency_types.py:32`), kann aber mangels Daten nicht effektiv
  arbeiten.

- **Können Writing-Prompts auf KG-Daten zugreifen, um Charaktere korrekt darzustellen?**
  **Bedingt.** Writing-Services injizieren `kb_relationships` als flachen Text.
  Das Modell muss daraus selbst ableiten, wer mit wem wie verbunden ist. Bei
  komplexen Graphen (viele Charaktere, verschachtelte Beziehungen) ist ein
  flacher Text-String unübersichtlich. Graph-Traversal ("welche Charaktere
  sind im aktuellen Szenario anwesend und wie stehen sie zueinander?") würde
  präzisere, szenario-relevante Beziehungs-Extrakte liefern.

- **Gibt es Situationen, wo die KB-Textsuche durch KG-Traversal ersetzt werden sollte?**
  **Ja, bei Proactive Context.** Aktuell nutzt `ProactiveContextService`
  semantische Ähnlichkeit (Embeddings). Für Beziehungs-relevante Szenarien
  ("Charakter A taucht auf → zeige auch Charakter B, weil sie verbunden sind")
  wäre Graph-Nachbarschaft treffsicherer als reine Text-Ähnlichkeit.

**Bewertung KG-Adoption:** ⭐⭐
**Befunde:**
- KG ist als **Datenstruktur** voll implementiert (RelationshipType-Vokabular mit
  40+ Typen, GraphService mit BFS/Adjacency, Relationship-Repository mit
  `get_adjacency_map`).
- **Aber:** KG wird fast ausschließlich für **Visualisierung** (Frontend-Graph)
  und **flache Text-Injection** (4 Writing-Services) genutzt.
- Der **höchstwertige Use-Case — beziehungsbasierte Consistency-Checks — ist
  ungenutzt.** `ConsistencyDeps` hat kein Beziehungs-Feld. Der Consistency-Check
  ist "eingebaut und vergessen" im Sinne der Graph-Reasoning-Fähigkeit.
- Coreference ohne Charakter-Beziehungs-Kontext ist ein funktionales Defizit.

---

## 4. Prompt-Anreicherung – Vollständigkeits-Check

> **Kernfrage:** Reichern wir Prompts immer mit den *richtigen* Informationen an?
> Verifiziert via Read der Service-Dateien + Grep nach Kontext-Variablen.

| Funktion | Bekommt aktuell | Fehlt | Überflüssig |
|---|---|---|---|
| **KB-Interview** (`kb/interview`) | System-Prompt via PromptComposer, Meta/Universal Capabilities, User-Preferences (wenn mem0 konfiguriert). | — (Setup-Aufgabe, minimaler Kontext nötig) | — |
| **Writing-Continue** (new_chapter / extend / rewrite) | Kapitel-Content (Tier-1), Recent Chapters (Tier-2), KB-Referenced (Tier-3, wiki-komprimiert), KB-Suggested (Tier-4), Pinned (Tier-5), KB-Relationships (flach), Voice-Profiles, User-Preferences, Tone, Genre, Story-Structure. | ⚠️ Konsistente **KG-Nachbarschaft** für Szenario-relevante Charaktere (statt flacher Voll-Liste). | — (gut angereichert) |
| **Consistency Check** | Chapter-Texte, KB-Entity-Summaries (nur Name+Typ+Felder), Timeline-Events, Extracted-Facts (Stage-1), Timeline-Envelopes (ADR-044). | **❌ KB-Relationships** (siehe §3.2 — kann Beziehungs-Widersprüche nicht prüfen), **❌ Andere Entity-Bodies** (nur Summaries), cross-entity-Kontext. | — |
| **Coreference** | Chapter-Text, Project-Title, Genre, Language. | **❌ Charakter-Namen** (alle KB-Vars = ""), **❌ KB-Relationships**. Coreference ohne Charakter-Liste ist funktional eingeschränkt. | — |
| **Suggest** (inline_suggest) | Minimaler Kontext (bewusst, <500ms-Latenz). | — (ADR-045 D3 C: bewusst bypassed) | — |
| **Story-Suggest** | Kapitel-Kontext, KB-Entities (via WritingContextAssembler). | ⚠️ KG-Beziehungen für plausible Vorschläge. | — |
| **Rewrite** | Selection + Kontext (Tier-System), KB-Entities, Relationships, Voice-Profiles. | — | — |
| **Beta-Reader** | Chapter-Text, Previous-Summaries, KB-Characters + Locations (200-Zeichen-trunciert), Genre. | ⚠️ KB-Factions, **KB-Relationships** (fehlen), volle Entity-Bodies (nicht 200-Zeichen-stumps). | — |
| **Voice-Check / Character-Voice** | Chapter-Text, Voice-Profile-Daten. | ⚠️ KB-Relationships (= ""), voller KB-Charakter-Kontext. | — |

**Bewertung Prompt-Anreicherung:** ⭐⭐⭐
**Befunde:**
- **Writing** ist hervorragend angereichert (Tier-System, Voice, Relationships,
  Tone, Genre). ⭐⭐⭐⭐⭐ für Writing.
- **Consistency Check** hat die größte Lücke: **keine KB-Relationships**. Die
  Konsistenz-Prüfung kann Beziehungs-Widersprüche strukturell nicht erkennen.
- **Coreference** ohne Charakter-Namen ist ein **funktionaler Fehler** — die
  Aufgabe (Pronomen → Charakter zuordnen) braucht zwingend die Charakter-Liste.
- **Beta-Reader** arbeitet mit 200-Zeichen-KB-Stumps — oberflächlicher Kontext
  für eine Aufgabe, die Tiefe braucht.
- Insgesamt: Writing = vorbildlich, Analysis/KB = unterversorgt.

---

## 5. Feature-Adoption-Gates & Machine Checks

> Verifiziert via Read von `scripts/check_adoption.py`, `scripts/adoption/scorer.py`,
> `scripts/adoption/scorer_checks.py`, `scripts/architecture/adoption-registry.yaml`.

**Analysiert:**

1. **Gibt es eine maschinenlesbare Adoption Registry?**
   ✅ Ja — `scripts/architecture/adoption-registry.yaml` (v2.0.0). Definiert pro
   Kategorie: `required_infrastructure` (token_budget, prompt_composer,
   mem0_preferences, kb_entities, kb_relationships, injection_defense, meta_prompt,
   i18n), `context_variables` (must/should), `runtime_requirements` und
   `prompt_path_compliance` (RULE-02b).

2. **Deckt `scripts/check_adoption.py` die geprüften Erwartungen ab?**
   ⚠️ **Teilweise — mit signifikanten Lücken.** Der Scorer
   (`scripts/adoption/scorer_checks.py:60-62`) prüft `token_budget` und
   `injection_defense` so:
   ```python
   # token_budget / injection_defense: assume adopted if bundled prompts exist.
   adopted = 1.0 if has_prompts else 0.0
   ```
   **Das bedeutet:** `token_budget: required` für Analysis wird als "adopted"
   gewertet, sobald bundled Prompt-Dateien existieren — **unabhängig davon, ob
   der Code tatsächlich `TokenBudgetManager` nutzt.** Die Analysis-Services
   (die kein Budget-System haben, siehe §2) passieren dieses Gate problemlos.
   Die infrastructure_definition sagt zwar: *evidence: "uses TokenBudgetManager
   or ContextAssembler with budget parameter"* — aber der Scorer prüft diese
   Evidence **nicht** im Code, sondern nur Datei-Präsenz.

3. **Lücken zwischen inhaltlichen Anforderungen und automatisierter Prüfung:**

   | Erwartung (Registry) | Automatisiert geprüft? | Lücke |
   |---|---|---|
   | `token_budget: required` | ❌ "assumed adopted if prompts exist" | Analysis/KB/Planning passieren ohne Code-Nachweis |
   | `injection_defense: required` | ❌ "assumed adopted if prompts exist" | Nicht gegen XML-Tagging verifiziert |
   | `kb_relationships: required` (writing) | ⚠️ Via Variablen-Präsenz im Prompt-Template | Prüft Template-VARIABLE, nicht ob Runtime den Wert füllt (Coreference setzt `=""`) |
   | `mem0_preferences: required` | ✅ Via `user_preferences`-Variablen-Präsenz | Template-Check, nicht Runtime-Wiring |
   | `kb_entities: required` (writing) | ✅ Via Variablen-Präsenz | Template-Check |
   | `prompt_path_compliance` (RULE-02b) | ✅ Via `*_prompt_path_compliance.py` Tests | Gut geprüft |
   | Runtime-Evidence (probes) | ✅ `requires_runtime_evidence: true` + `.evidence/` Probes | Prüfen enrichment/validation/evidence-sink, **nicht** Budget-Code-Pfade |

4. **Sind neue AI-Features verpflichtet, PromptComposer, TokenBudget/ContextAssembler, mem0-Präferenzen, Injection Defense, i18n/Locale-Strategie und Streaming zu prüfen?**
   ⚠️ **Auf dem Papier ja, maschinell unvollständig.** Die Registry deklariert
   alle als `required`, aber der Scorer prüft nur Variablen-Präsenz (statische
   Template-Analyse) bzw. "assumed adopted". Es gibt **keinen** Checker, der
   verifiziert: "Nutzt dieser Service-Code tatsächlich TokenBudgetManager?"
   oder "Füllt dieser Service `kb_relationships` zur Runtime mit echten Daten
   (nicht `=''`)?". Die Runtime-Probes prüfen enrichments/validation, aber nicht
   Budget-Allokation oder Context-Tiefe.

**Bewertung Adoption-Gates:** ⭐⭐⭐
**Befunde:**
- Die **Registry-Struktur** ist vorbildlich (v2.0.0, maschinenlesbar, pro-Modus-Overrides).
- Die **Scoring-Logik** hat eine systematische Lücke: `token_budget` und
  `injection_defense` werden als "assumed adopted" gewertet ohne Code-Nachweis.
  Dies erklärt, warum Analysis-Services ohne Budget-System das Gate passieren.
- Die Runtime-Evidence-Probes sind ein guter Ansatz, decken aber nicht die
  spezifischen Adoptions-Lücken dieses Reviews (Budget-Code-Nutzung,
  Context-Tiefe, nicht-leere KB-Variablen-Werte).
- **Konkrete Lücke:** Coreference setzt `kb_characters=""` — das Template hat
  die Variable (Registry: adopted), aber der Runtime-Wert ist leer. Kein Gate
  fängt das ab.

---

## 6. Token-Limits – Kalibrierung & Aktualität

> Referenz: `core/llm/token_profiles.py`, `core/llm/run_limits.py`,
> `core/context/budget.py`. Werte aus CR-08 §1 bestätigt (keine Duplikation
> der Konfigurierbarkeits-Analyse — hier nur Aufgabeneignung).

### 6.1 Output-Limits: Passen sie zur Aufgabe?

> Orientierung: ~700 Wörter ≈ 1.000 Tokens.

| Funktion | Typische Output-Länge (Wörter) | Benötigte Tokens (ca.) | Definiertes Limit | Ausreichend? | FIND? |
|---|---|---|---|---|---|
| **Inline-Suggest** | 5–15 Wörter | ~60 | `SUGGEST_MAX_TOKENS=60` (`run_limits.py:27`, immutable) | ✅ Ja (bewusst, Latenz) | Nein |
| **Writing new_chapter** (balanced) | 1.000–1.500 | ~1.500–2.200 | Profile `balanced`=2000 / `long_texts`=8000 / `comprehensive`=16000 | ✅ Ja (profile-wählbar) | Nein |
| **Writing extend_chapter** | 300–800 | ~450–1.200 | Profile-basiert | ✅ Ja | Nein |
| **Consistency Check** | Bericht, 200–800 Wörter | ~300–1.200 | Profile-basiert (default: `config.resolve_output_limit()` → 4096 Fallback `model_config.py:54`) | ✅ Ja | Nein |
| **Beta-Reader** | Ausführliche Kritik, 500–1.500 Wörter | ~750–2.200 | Profile-basiert | ✅ Ja | Nein |
| **KB-Consistency (entry-internal)** | Issue-Liste, 100–400 Wörter | ~150–600 | Profile-basiert (via `registry.run`) | ✅ Ja | Nein |
| **Coreference** | Resolution-Liste, 100–400 Wörter | ~150–600 | Profile-basiert | ✅ Ja | Nein |
| **KB-Interview / Worldbuilding** | Strukturierte KB-Einträge, 500–2.000 Wörter | ~750–3.000 | Profile-basiert | ✅ Ja | Nein |
| **Analysis — POV / Readability / Voice-Check** | Score + Erklärung, 100–400 Wörter | ~150–600 | Profile-basiert | ✅ Ja | Nein |
| **Planning — Outline / Character-Arc / Timeline** | Strukturiert, 500–2.000 Wörter | ~750–3.000 | Profile-basiert | ✅ Ja | Nein |
| **Story-Suggest** | 3–5 Vorschläge, ~300 Wörter | ~450 | Profile-basiert | ✅ Ja | Nein |

> **Hinweis:** Kein Feature hat "Kein Limit definiert" — alle laufen über
> `config.resolve_output_limit()` (Profile-basiert) oder `OutputBudgetDecision`
> mit Fallback 4096. Daher **keine neuen FIND-Einträge** aus §6.1 erforderlich.

### 6.2 Sind die Limits feature-spezifisch oder global?

- **Output-Limits** sind **profile-basiert** (global pro Profile, nicht pro
  Feature): `quick`=500, `balanced`=2000, `long_texts`=8000, `comprehensive`=16000.
  Das Profil wird pro Request/User/Project konfiguriert (`token_limit_profile`
  in `user_ai_settings` / `project_settings`).
- **Ausnahme:** `SUGGEST_MAX_TOKENS=60` ist der einzige feature-spezifische,
  harte Output-Cap (immutable, ADR-045 D3 C Latenz-Ziel).
- **Context-Budget** (`DEFAULT_TOTAL_BUDGET=6000`) ist pro-Assembler-Aufruf
  konfigurierbar (`total_budget`-Param, `tier_overrides`), mode-spezifisch
  (extend/rewrite/first_chapter/wiki_optimized).
- **Welche Features werden durch globale Profile eingeschränkt?** Konservative
  Nutzer mit `quick`=500 bekommen bei Beta-Reader oder Consistency-Check
  möglicherweise abgeschnittene Berichte. Aber: Profile sind Nutzer-wählbar,
  nicht Feature-zwangsläufig.

**Befund:** Output-Limits sind gut kalibriert und profile-basiert konfigurierbar.
Kein Feature hat ein unangemessenes Limit. ⭐⭐⭐⭐⭐ für Output-Limit-Kalibrierung.

### 6.3 Modell-Vergleich: Wie viel Potenzial liegt brach?

| Modell (Provider) | Max Output (ca.) | Aktuell genutzt (max Profile) | Ungenutzt |
|---|---|---|---|
| OpenAI GPT-4.1 / GPT-5-Klasse | ~32.000 Tokens | `comprehensive`=16.000 | ~50% |
| Anthropic Claude Sonnet/Opus | ~8.000–16.000 Tokens (output) | `comprehensive`=16.000 | ~0–50% (modellabhängig) |
| Ollama (lokal, z.B. llama3.2) | Modellabhängig (oft 4.000–8.000) | `long_texts`=8.000 | Variabel |
| `TOKEN_OUTPUT_ABSOLUTE_MAX` (Hard Cap) | 131.072 | 16.000 (`comprehensive`) | ~88% |

> **Bemerkung:** Das `comprehensive`-Profil (16.000) lässt ~50% des
> GPT-4.1-Output-Fensters ungenutzt. Für extrem lange Kapitel-Generierung
> (10.000+ Wörter in einem Aufruf) gäbe es Kopfraum. Das ist aber bewusst
> konservativ kalibriert (Kosten, Latenz, Qualität). Kein Handlungsbedarf.

### 6.4 Konfigurierbarkeit

> Siehe CR-08 §1 für detaillierte Konfigurierbarkeits-Analyse (keine Duplikation).
> Hier nur Adoptions-relevante Aspekte.

- **Nutzer (WebUI):** Kann Token-Limit-Profil wählen (`quick`/`balanced`/
  `long_texts`/`comprehensive`/`custom` mit raw output limit). ⭐⭐⭐⭐⭐
- **Self-Hoster:** Kann Profile-Werte über Code-Defaults überschreiben
  (`token_profiles.py`). Tier-Overrides via Settings/Method-Param. ⭐⭐⭐⭐
- **Analysis/KB-Output-Limits:** Nutzen dieselbe Profile-Cascade — kein
  separates Limit nötig.

**Bewertung Token-Limits:** ⭐⭐⭐⭐⭐
**Befunde:**
- Output-Limits sind vorbildlich kalibriert, profile-basiert, konfigurierbar
  und haben keine "Kein Limit definiert"-Fälle. Keine neuen FINDs.
- Das Context-Budget-System (6000 Default) ist für Writing exzellent, aber
  **nicht für Analysis/KB adoptiert** (siehe §2 — das ist ein Adoptions-Problem,
  kein Kalibrierungs-Problem).

---

## Gesamtbewertung Feature-Adoption

**Bewertung:** ⭐⭐⭐
**Vorherige Bewertung:** _Kein vorheriges CR-03 vorhanden (Erst-Durchlauf)._
**Trend:** ➡️ (Baseline)
**Zusammenfassung:** Die Plattform hat eine **zweigeteilte Adoptions-Landschaft**.
Writing ist vorbildlich: vollständiges 5-Tier-TokenBudget, KB-Relationships,
Voice-Profiles, mode-spezifische Allokation. Analysis, KB und Planning hingegen
sind **strukturell unterversorgt**: kein Budget-System (eigene
200-Zeichen-Truncation), keine KG-Relationships in Consistency-Checks (die
größte Unternutzung), Coreference ohne Charakter-Namen. mem0 ist funktional
aber eng (nur LEARN-001, drei hochwertige Szenarien ungenutzt). Die
Adoption-Gates haben eine systematische Lücke: `token_budget` wird als
"assumed adopted" gewertet ohne Code-Nachweis, weshalb Analysis ohne Budget
durchgeht. Die Infrastruktur ist gebaut — sie wird nur zur Hälfte genutzt.

---

## Aufgaben

<!-- Nummerierung: CR-AUFG-03-01, CR-AUFG-03-02, … -->

### CR-AUFG-03-01 — Consistency-Check mit KG-Relationships anreichern

**Status (2026-07-13):** ✅ implemented — `ConsistencyDeps` gained `kb_relationships`-Feld (`consistency_types.py`); Orchestrator-Pipeline lädt Relationships via `fetch_formatted_relationships` (`checker_context.py`); Consistency-Prompt referenziert `{{kb_relationships}}` mit Beziehungs-Cross-Reference-Anweisung (`system.md` v2.1.0). 11 neue Tests. Commit `423d515`.
**Priorität:** P1 (höchster inhaltlicher Mehrwert)
**Problem:** `ConsistencyDeps` (`consistency_types.py:107-127`) hat kein Feld für
KB-Relationships. Der Consistency-Check kann Beziehungs-Widersprüche ("Aria ist
Feindin von Malachai" im KG, aber verbündet im Text) strukturell nicht erkennen.
`ConsistencyCheckType.WORLD` existiert, kann aber mangels Daten nicht effektiv
arbeiten.
**Aufgabe:** Erweitere `ConsistencyDeps` um `kb_relationships` (formatiert wie in
Writing via `fetch_formatted_relationships`). Wire den ConsistencyOrchestrator,
dass er Relationships lädt und übergibt. Aktualisiere den Consistency-Prompt
(`_bundled/analysis/en/consistency/system.md`), damit er Relationships explizit
prüft.
**Referenz:** §3.2, §4 (Consistency Check).

### CR-AUFG-03-02 — Coreference-Service mit KB-Charakteren versorgen

**Status (2026-07-13):** ✅ implemented — `CoreferenceService` akzeptiert optionales `KBRepository`, lädt Charakter-Namen für Pronomen-Resolution (`coreference_service.py` + `coreference_kb.py`). DI-Factory verdrahtet (`dependencies_coreference.py`). 6 neue Tests. Commit `0b79fca`.
**Priorität:** P1 (funktionaler Adoptions-Fehler)
**Problem:** `coreference_service.py:175-179` setzt alle KB-Variablen (`kb_characters`,
`kb_locations`, `kb_factions`, `kb_relationships`) auf leere Strings. Kommentar:
*"No KB repository is wired for this call path"*. Coreference-Resolution braucht
aber zwingend die Charakter-Liste des Romans, um Pronomen korrekt zuzuordnen.
**Aufgabe:** Wire das `KBRepositoryProtocol` in den Coreference-Service. Lade
Charaktere für den Roman und fülle `kb_characters` mit echten Daten.
**Referenz:** §2.2 (Nr. 3), §4 (Coreference).

### CR-AUFG-03-03 — Analysis-ContextAssembler auf TokenBudget-System migrieren

**Status (2026-07-13):** ✅ implemented (Rest-Fix) — Budget-System war bereits vorhanden (`AnalysisContextAssembler`, ADR-025). Rest-Fix: 200-Zeichen-Pre-Truncation im API-Layer entfernt, damit das Budget-System volle Entity-Bodies sieht (`context_assembler.py`). 3 neue Tests. Commit `b48c7d1`.
**Priorität:** P2 (strukturelle Konsistenz)
**Problem:** `apps/api/narrare/analysis/context_assembler.py` ist ein eigener
ContextAssembler ohne TokenBudgetManager, mit hardcoded
`kb_summary_truncation=200` Zeichen. Beta-Reader arbeitet mit oberflächlichen
KB-Stumps. Kein Overflow-Handling, keine Priorisierung.
**Aufgabe:** Evaluieren, ob Analysis von einem analogen Tier-System profitiert
(oder ob ein `AnalysisContextAssembler(TokenBudgetManager)`-Subklasse sinnvoll
ist). Mindestens: Char-Truncation durch Token-bewusste Truncation ersetzen.
**Referenz:** §2.1, §2.2 (Nr. 1).
**Hinweis:** Abstimmung mit Architecture-Specialist (RULE-03 Contract first).
**Status (verifiziert 2026-07-12):** Kern-Ziel bereits umgesetzt —
`packages/core/narrare_core/analysis/assembler.py::AnalysisContextAssembler`
(3-Tier-Budget, `AnalysisBudgetManager`, 6000-Token-Default, Overflow-Cascade;
ADR-025) existiert und ist via `build_budgeted_prompt` in
`BetaReaderService.analyze` (`beta_reader_service.py:150`) verdrahtet.
Verbleibender Rest: Die 200-Zeichen-Pre-Truncation im API-Layer
`ContextAssembler` (`context_assembler.py:50/168/203`) beschneidet KB-Daten
*vor* dem Budget-System. Rest-Aufgabe: Pre-Truncation entfernen/anheben, damit
das Budget-System volle Entity-Bodies sieht und selbst token-bewusst kürzt.
Kein Neubau des Budget-Systems nötig.

### CR-AUFG-03-04 — KBConsistencyAnalyzer Body-Truncation durch Budget ersetzen

**Status (2026-07-13):** ✅ implemented — `entity.body[:5000]` durch `cap_to_budget(entity.body, max_body_tokens)` ersetzt (`consistency_analyzer.py`). `max_body_tokens` konfigurierbar (Default 1500 ≈ 5000 Zeichen). 5 neue Tests. Commit `d275e3c`.
**Priorität:** P2
**Problem:** `consistency_analyzer.py:199` trunciert `entity.body[:5000]`
hardcoded. Bei Einträgen >5000 Zeichen schneidet der Consistency-Check mitten
im Content ab — Feld-Widersprüche im abgeschnittenen Teil werden übersehen.
**Aufgabe:** Token-bewusste Truncation oder Budget-basierte Kürzung einführen.
Zumindest dokumentieren/parametrisieren, dass 5000 Zeichen ein bewusstes Limit
sind.
**Referenz:** §2.2 (Nr. 2).

### CR-AUFG-03-05 — mem0-Preference-Injection-Gate untersuchen

**Status (2026-07-13):** ✅ verified — Investigation bestätigt: Gate funktioniert korrekt für Writing-Services. `WritingPipeline` setzt `user_id`/`project_id` in `PromptContext.extra`; zwei Mechanismen (Enricher + Fallback-Gate) stellen Preference-Injection sicher. Kein Produktions-Fix nötig. 6 Regression-Tests. Commit `6162944`.
**Priorität:** P2
**Problem:** `composer.py:93-113` injiziert Preferences nur, wenn Context "leer"
ist. Bei WritingContextAssembler-vorangestellten Services ist der Context
regelmäßig gefüllt — Preferences erreichen möglicherweise nie den Writing-Prompt.
**Aufgabe:** Verifizieren, ob die Preference-Injection im Writing-Pfad
tatsächlich greift. Falls nicht: Gate-Bedingung anpassen (Preferences sollen
auch bei gefülltem KB/Chapter-Context injiziert werden, da sie orthogonal sind).
**Referenz:** §1.1, §1.2 (Szenario 2).

### CR-AUFG-03-06 — mem0 Cross-Session Writing Context

**Status (2026-07-13):** ✅ implemented — Neuer `SessionMemoryService` (`core/memory/`) mit `record_writing_session()` + `get_cross_session_context()`. `WritingService` ruft Context vor Generation ab und speichert Summary nach Abschluss. Variable durchläuft Writing-Pipeline-Governance-Chain. 16 neue Tests. Commit `b233723`.
**Priorität:** P3 (Erweiterung)
**Problem:** mem0 speichert nur Preferences und Feedback. Cross-Session-Kontext
("Nutzer arbeitete an Plot-Wendung in Kapitel 7") fehlt — jede Session startet
ohne Erinnerung an vorherige Schreib-Entscheidungen.
**Aufgabe:** mem0 nach Session-Ende Summary-Memories speichern und beim
Session-Start abrufen (siehe Implementierungsplan).
**Implementierungsplan:**
1. **Contract (RULE-03):** mem0-Memory-Typ `writing_session` definieren
   (Metadata: `{type, novel_id, chapter_id, mode, timestamp}`). Store-Hook im
   Writing-Service nach Chapter-Save; Retrieval im WritingContextAssembler
   oder einem neuen SessionContextEnricher.
2. **Storage:** Nach Abschluss einer Writing-Operation (Kapitel generiert &
   gespeichert) eine kurze strukturelle Summary speichern (mode, Kapitel-Titel,
   Wortzahl-Delta — zunächst *ohne* zusätzlichen LLM-Call) via `mem0.add()`.
   Best-effort mit graceful degradation (NullMemoryClient-Fallback, RULE-08).
3. **Retrieval:** Beim Start einer Writing-Session mem0 nach vergangenen
   Writing-Session-Memories für dieses Novel/User durchsuchen. Als
   `cross_session_context`-Variable in den Prompt injizieren
   (budget-durchlaufen).
4. **Prompt:** `{{cross_session_context}}` in relevante Writing-Prompts
   aufnehmen (optional / empty-safe, bestehendes Pfad-Compliance-Test-Muster).
5. **Tests:** Unit-Tests für Store- + Retrieve-Flow mit NullMemoryClient;
   graceful-degradation-Test.
6. **Scope-Guard:** Zusammenfassungen kurz halten (keine vollen
   Session-Transkripte). Token-budget-durchlaufen über bestehendes System.
**Entscheidung:** Zunächst strukturelle Summaries (kein Extra-LLM-Call);
LLM-summarisierte Memories später, falls wertvoll.
**Referenz:** §1.2 (Szenario 1).

### CR-AUFG-03-07 — Adoption-Scorer: token_budget gegen Code verifizieren

**Status (2026-07-13):** ✅ implemented + enforced — `CheckDetail.unverified`-Flag hinzugefügt; Scorer markiert `token_budget`/`injection_defense` als "unverified" bei reiner Datei-Präsenz. `AdoptionReport.unverified_count` (Baseline: 7). Audit-Report listet unverified Items. Score unverändert (Ratchet). 23 neue Tests. Commit `13b9f69`.
**Priorität:** P2 (Enforcement-Gap)
**Problem:** `scorer_checks.py:60-62` wertet `token_budget` als "assumed adopted
if bundled prompts exist" — ohne Code-Nachweis. Analysis/KB/Planning passieren
das `token_budget: required`-Gate, obwohl ihre Services kein Budget-System nutzen.
**Aufgabe:** Erweitere den Scorer (oder einen neuen Checker), dass er
verifiziert: "Nutzt dieser Service-Code TokenBudgetManager oder
ContextAssembler(total_budget=...)?". Mindestens: Flagge Kategorien als
"unverified" statt "adopted", wenn nur Datei-Präsenz vorliegt.
**Referenz:** §5.
**Abstimmung:** Mit Platform-Specialist (CI/Enforcement).

### CR-AUFG-03-08 — Runtime-Gate: leere KB-Variablen-Werte erkennen

**Status (2026-07-13):** ✅ implemented + enforced — Neuer Checker `scripts/check_empty_kb_vars.py` scannt Service-Code auf hartcodierte Leerstring-Zuweisungen an KB-Variablen. Ratchet-Baseline: 11 Findings. In `just check` integriert (blockiert neue Verstöße). 20 neue Tests. Commit `ba630e0`.
**Priorität:** P3 (Enforcement)
**Problem:** Die Registry prüft Variablen-Präsenz im Prompt-Template (statisch).
Coreference hat `kb_characters` im Template (Registry: adopted), setzt es zur
Runtime aber auf `=""`. Kein Gate fängt leere Runtime-Werte ab.
**Aufgabe:** Checker implementieren, der Service-Code auf hartcodierte
Leerstring-Zuweisungen an KB-Kontext-Variablen scannt (siehe
Implementierungsplan).
**Implementierungsplan:**
1. **Ansatz:** Bestehenden Adoption-Scorer erweitern ODER neuen Checker
   (z.B. `scripts/check_empty_kb_vars.py`), der Service-Code unter
   `apps/api/` auf Muster wie `"kb_characters": ""` / `kb_relationships=""`
   scannt (AST- oder Regex-basiert).
2. **Erkennung:** Bekannte KB-Variablen: `kb_characters`, `kb_locations`,
   `kb_factions`, `kb_relationships`. Hartcodierte Leerstring-Zuweisungen als
   "runtime-empty variable"-Finding markieren.
3. **Baseline (Ratchet):** Gegen aktuellen Codestand laufen lassen, aktuelle
   Anzahl leerer Zuweisungen als Baseline setzen. Neue Verstöße schlagen fehl;
   bestehende werden zur schrittweisen Bereinigung getrackt.
4. **Warning-only:** Zunächst als Warnung (nicht blockierend) mit
   Ratchet-Baseline, gemäß Prevention-Disziplin.
5. **Tests:** Checker selbst testen (findet bekannte Leer-Zuweisungen, passt
   wenn gefüllt).
6. **Integration:** In `just check` / pre-commit / CI neben bestehenden
   Adoption-Checks einbinden.
**Verhindert:** Die Coreference-Klasse Bug (CR-AUFG-03-02) rekurrenzfrei —
sobald 03-02 `kb_characters` füllt, sinkt die Baseline; jeder *neue* Service
mit `kb_characters=""` wird flaggiert.
**Referenz:** §5.
**Abstimmung:** Mit Platform-Specialist.

### CR-AUFG-03-09 — Voice/Planning-Services: kb_relationships füllen (nicht ="")

**Status (2026-07-13):** ✅ implemented — Voice-Check, Character-Voice, Timeline-Analysis und Coreference-Services laden und injizieren nun KB-Relationships via `fetch_formatted_relationships`. Graceful Degradation bei fehlendem Repo. 2 Helper-Module extrahiert (RULE-04). 17 neue Tests. Commit `6bf2806`.
**Priorität:** P3
**Problem:** `character_voice_prompt.py:87`, `voice_check_prompt.py:92`,
`timeline_analysis_service.py:188`, `coreference_service.py:178` setzen
`kb_relationships=""`. Diese Features verlieren Beziehungs-Kontext, der für
Charakter-Darstellung und Planung relevant wäre.
**Aufgabe:** Evaluieren pro Feature, ob `fetch_formatted_relationships()` (wie
in Writing) angebunden werden soll. Mindestens für Voice-Check und
Character-Arc (wo Beziehungen charakterprägend sind).
**Referenz:** §2.1, §4.

### CR-AUFG-03-10 — Consistency-Feedback-Loop zu mem0

**Status (2026-07-18):** ✅ Resolved — ConsistencyFeedbackService (Core, `packages/core/narrare_core/memory/consistency_feedback_service.py`) implementiert `ConsistencyFeedbackCollector`: speichert Dismissals als mem0-Memories + ruft semantisch ähnliche vergangene Dismissals via pgvector ab, um rephrasierte False-Positives zu unterdrücken. Backend-Wiring: Store-Hook in `dismissed_service.py` (nach DB-Persist), Retrieve+Suppress-Hook in `consistency_service.py::check` (filtert Issues mit Semantic-Match > 0.85), `suppressed_count` Feld in `ConsistencyCheckResponse` (backend + frontend TS + OpenAPI, RULE-17). Beide Hooks optional (`feedback_memory=None` = deaktiviert) und best-effort (RULE-11: mem0-Fehler propagieren nie). Enforcement: 51 neue Tests (20 Core + 31 Backend) + 2 Frontend-Test-Updates; `just check-architecture` 0 Verstöße, `just check-ai-ux` 0 Verstöße. Commits: `92368e19` (Contracts), `8e66a484` (Core Service), `bdecab49` (Backend+Frontend Wiring).
**Priorität:** P3 (Erweiterung)
**Problem:** Der Consistency-Check hat keinen Feedback-Loop zu mem0. Wenn ein
Nutzer ein Consistency-Issue als "false positive" oder "beabsichtigt" markiert,
wird diese Information nicht gespeichert. Wiederkehrende False-Positives
belasten wiederholt; beabsichtigte "Inkonsistenzen" werden nicht gelernt.
**Aufgabe:** Wenn ein Nutzer ein Consistency-Issue als "false positive" /
"resolved" / "intended" markiert, speichere das in mem0 (analog FeedbackService).
Bei der nächsten Consistency-Prüfung rufe ähnliche vergangene Markierungen ab,
um wiederkehrende False-Positives zu reduzieren.
**Referenz:** §1.1 (Consistency Check), §1.2 (Szenario 3).

### CR-AUFG-03-11 — Character Voice Memory in mem0 persistieren

**Status (2026-07-17):** ✅ Resolved — already-implemented (Architecture-Verifikation). Das Task-Premise ("Voice-Patterns werden nicht persistiert, jede Session neu profiliert") ist **falsch**: ADR-055 (✅ Accepted + Implemented 2026-06-29) persistiert das abgeleitete Voice-Profil via `persist_voice_analysis()` (`apps/api/narrare/analysis/character_voice_kb_writer.py`) auf **jedem** Profiling-Lauf in die KB (`metadata["speech"]["voice_analysis"]` + `updated_at`-Bump). Der Writing-Pfad liest aus der KB via `build_character_voice_profile()` → `get_speech_data()` — **nicht** live. mem0 wäre hier redundant (strukturierte `VoiceAnalysis`-Objekte gehören in die KB, nicht in natürlichsprachige mem0-Memories) und semantisch falsch (Cross-Novel-Voice-Sharing: Charaktere verschiedener Novels sind verschiedene Charaktere). Kein Code hinzugefügt — architektonisch sauberer als redundante mem0-Machinery. Lifecycle-Status: Anforderung durch ADR-055 Implementierung erfüllt.
**Priorität:** P3 (Erweiterung)
**Problem:** ADR-055 (Character Voice) extrahiert Sprachmuster pro Charakter
live pro Sektion. Diese Voice-Patterns werden nicht in mem0 persistiert, sodass
jede Session das Profil neu erstellt.
**Aufgabe:** Evaluieren und umsetzen, ob ADR-055 Voice-Patterns in mem0
persistiert werden, statt sie live neu zu profilieren. Beim Abruf eines
Charakters im Writing-Pfad prüfen, ob ein gespeichertes Voice-Profil existiert;
falls ja, wiederverwenden, falls nein, neu profilieren und speichern.
**Referenz:** §1.1 (Character Voice Memory).

### CR-AUFG-03-12 — Proactive Context via KG-Traversal erweitern

**Status (2026-07-13):** ✅ implemented — `ProactiveContextService.suggest()` akzeptiert optionales `entity_connections`-Adjacency-Map. Graph-Nachbarn von Name-Match-Entities erhalten 0.15 Score-Boost (Hybrid-Scoring — Entity muss sowohl semantisch relevant als auch graph-verbunden sein). 7 neue Tests. Commit `af3b5ec`.
**Priorität:** P3 (Erweiterung)
**Problem:** `ProactiveContextService` nutzt für KB-Suggestions nur semantische
Ähnlichkeit (Embeddings). Für beziehungs-relevante Szenarien ("Charakter A
taucht auf → auch Charakter B vorschlagen, weil verbunden") wäre
Graph-Nachbarschaft treffsicherer als reine Text-Ähnlichkeit.
**Aufgabe:** Erweitere `ProactiveContextService` so, dass für
beziehungs-relevante Vorschläge Graph-Nachbarschaft (BFS via GraphService /
Adjacency-Map) zusätzlich zur Embedding-Ähnlichkeit genutzt wird.
Hybrid-Scoring bestehend beibehalten, Graph-Signal als Booster.
**Referenz:** §3.1 (KB-005 Proactive Context), §3.2.

### CR-AUFG-03-13 — Budget-Adoption auf verbleibende Analysis/Planning-Services ausweiten

**Status (2026-07-18):** `accepted_risk` — Planning-Services haben aktuell minimales KB-Kontext (`kb_*`-Variablen sind Leerstrings bis auf `kb_relationships` aus 03-09). Budget-Enforcement auf leerem Content bietet keinen Mehrwert — das Budget-System hat nichts zu allokieren. **Owner:** Core Specialist. **Rationale:** Die Deferral-Begründung ist technisch fundiert (Evaluation 2026-07-13): bis Planning-KB-Wiring wächst, ist Budget-Adoption wirkungslos. **Controls:** Adoption-Scorer trackt Budget-Adoption continues; sobald Planning-Services echten KB-Content injizieren, greift das Budget-Gate natürlich. **Review-Datum:** nächster quartalsmäßiger Major Review (cr-06 §5.3) oder wenn Planning-KB-Wiring erweitert wird.
**Priorität:** P3 (strukturelle Konsistenz)
**Problem:** Neben Beta-Reader (CR-AUFG-03-03) haben POV/Readability/Voice-Check
sowie Planning-Services (Outline/Character-Arc/Timeline) weiterhin kein
Budget-System. Sie bauen ad-hoc `PromptContext` ohne Token-Bewusstsein. Der
strukturelle Adoptions-Flickenteppich (§2.3) besteht für diese Services fort.
**Aufgabe:** Evaluieren pro Service, ob die Nutzung des bestehenden
`AnalysisContextAssembler` (`packages/core/narrare_core/analysis/assembler.py`)
sinnvoll ist. Mindestens für Services mit großem KB-Kontextbedarf
(Planning / Character-Arc) anbinden.
**Referenz:** §2.1, §2.3.
**Abstimmung:** Mit Architecture-Specialist (RULE-03 Contract first).

---

## Abschluss-Status

**Gesamtbewertung:** 10 von 13 Aufgaben implementiert, 1 evaluiert/deferred, 2 deferred.

| Status | Aufgaben |
|--------|----------|
| ✅ implemented | 03-01, 03-02, 03-03, 03-04, 03-05 (verified), 03-06, 03-07 (+enforced), 03-08 (+enforced), 03-09, 03-12 |
| ⏳ deferred | 03-10 (Full-Stack-Feature), 03-11 (ADR-055-Integration), 03-13 (evaluated — minimales KB-Kontext) |

**Verifikation:** `just check` 9/9 grün, `just typecheck` 0 Fehler, `just test` 9717 Passed / 62 Skipped, 0 Failed.

**Enforcement-Maßnahmen hinzugefügt:**
- `CheckDetail.unverified`-Flag im Adoption-Scorer (03-07) — token_budget/injection_defense nicht mehr als "adopted" ohne Code-Nachweis
- `scripts/check_empty_kb_vars.py` Ratchet-Checker (03-08) — blockiert neue hartcodierte Leerstring-Zuweisungen an KB-Variablen

**Commits auf Branch `chore/cr-03-feature-adoption-fixes`:**
`0da5c5b` → `13b9f69` → `423d515` → `0b79fca` → `6bf2806` → `d275e3c` → `b48c7d1` → `6162944` → `ba630e0` → `b233723` → `af3b5ec`
