# Content Review CR-04 – Cross-Feature-Kohärenz

> **Audit-Datum:** 2026-07-11
> **Reviewer:** NarrareCoreSpecialist (Content Review Audit)
> **Methode:** `code-review-graph` MCP Tools (Graph ohne Embeddings → Keyword/Hybrid-
> Suche) + Read/Glob/Grep Fallback. Alle Einträge gegen echten Code verifiziert
> (Datei:Zeile), nicht aus Annahmen. ADR-050, RULE-22 als Norm herangezogen.
> **Kontext:** `_audit/results/content-review/cr-00-kontext.md` ✅ vorhanden
> **Vorherige Reviews:** cr-01 (Prompt-Qualität), cr-02 (System-Prompt-Architektur),
> cr-03 (Feature-Adoption) — Befunde werden hier für Cross-Feature-Relevanz integriert.
> **Fokus:** Können sich Informationen aus verschiedenen Systemteilen widersprechen?
> Sind KB, Storyboard, Templates und Frontmatter synchron?

---

## 1. KB-Context-Format-Standardisierung

### 1.1 Format-Analyse

> Verifiziert via Read von `_kb_envelope.py`, `_helpers.py`, `context_wiki.py`,
> `context.py` (`_format_kb_entries`), `_voice_profiles.py`,
> `proactive_service.py`, `_tier3_processor.py`. cr-00 §3 als Referenz.

Es gibt **sieben** Render-Pfade, die KB-bezogene Daten in Prompt-Variablen umwandeln.
Alle erfüllen das `KBContextEnvelope`-Protocol (ADR-050 P1-A), das provenance-
Erhaltung oder explizite Omission fordert. Die tatsächliche Wire-Format-Ausgabe
unterscheidet sich jedoch deutlich:

**Format A – Standard-Entity (Kompaktform):**
```
### Character: Aria Thorne
A skilled archer from the northern mountains. Twin sister of Malachai.

### Location: Ironhold Keep
A fortified stronghold overlooking the Shivering Strait.
```
- Erzeugt von: `writing/_helpers.py:format_entities()` (L74-100)
- Genutzt von: Tier-3 Referenced, Tier-4 Suggested, Tier-5 Pinned (via
  `WritingContextAssembler`); `PromptContext._format_kb_entries()`
  (`context.py:178-233`) — identisches Wire-Format
- Vorteile: Klar, token-effizient, LLM-freundliche `### Type: Name`-Header. Bewährt.
- Nachteile: **Null Provenance**. `preserved_fields=frozenset()` — weder `source`
  (manual vs auto-extracted), `confidence`, `review_status` noch `freshness` werden
  gerendert. ADR-050 P1-A macht die Omission *explizit* (`omitted_fields` mit
  `tier_does_not_require`), aber der Prompt-Text bleibt provenance-frei. Das LLM
  kann eine manuell kuratierte Tatsache nicht von einer 0.7-Confidence-
  Auto-Extraktion unterscheiden.

**Format B – Wiki-komprimiert:**
```
### Character: Aria Thorne
A determined archer driven by loyalty to her family.
Role: Protagonist
Attributes: skilled archer, loyal, impulsive
```
- Erzeugt von: `writing/context_wiki.py:format_entities_with_wiki()` (L32-101)
- Genutzt von: Tier-3 Processor (`_tier3_processor.py:95-99`) wenn frische
  WikiSummaries verfügbar sind (ADR-022)
- Vorteile: ~40% Token-Einsparung vs Format A (NarrativeSummary statt vollem Content).
  Angereichert um `role_in_story` und `key_attributes`.
- Nachteile: Nur verfügbar wenn WikiSummary `FRESH` ist — fällt sonst auf Format A
  zurück (`format_entities_with_wiki` L88-89: "Fall back to raw entity content").
  Ebenfalls `preserved_fields=frozenset()`. Das LLM sieht komprimierte Narrative,
  nicht die Originalfeld-Struktur — semantischer Informationsverlust bei der
  Feld-zu-Narrative-Kompression.

**Format C – Voice Profiles:**
```
**Aria Thorne**: Direct, terse sentences. Uses military vocabulary. Rarely asks questions.
**Malachai Thorne**: Formal, elaborate. Uses metaphors. Interrupts others.
```
- Erzeugt von: `writing/_voice_profiles.py:extract_voice_profiles()` (L39-89) /
  `profiles/_voice_extraction.py:build_character_voice_profile()`
- Genutzt von: `{{character_voice_profiles}}`-Variable in allen Writing-Prompts
  mit Dialog (ADR-055)
- Vorteile: Sehr kompakt, fokussiert auf Sprachmuster (Satzlänge, Diktion,
  Sprechstile).
- Nachteile: **Komplett anderes Format** als A/B — `**Name**: summary` statt
  `### Type: Name\nContent`. Stale-Warnung inline: `⚠️ last updated: 2026-01-15`.
  Die Frische-Information ist hier *sichtbar* (im Gegensatz zu A/B), aber nicht
  maschinell parsebar. Voice-Profile wird parallel zu Format A/B injiziert — das
  LLM erhält Character-Infos in zwei widersprüchlichen Formaten gleichzeitig.

**Format D – Proactive Suggestion:**
- Erzeugt von: `context/proactive_service.py:ProactiveContextService.suggest()`
  (L60-80) — 3-Stage-Pipeline (Name-Match → Embedding-Search → Hybrid-Scoring)
- Genutzt von: Tier-4 Suggested (unedorsed Kandidaten) → `{{kb_suggested}}`-
  Variable
- Vorteile: Hybrid-Scoring (semantisch + strukturell). Liefert `Suggestion`-
  Objekte mit `EntityMetadata` (`similarity_score`, `usage_count`,
  `last_referenced_at`).
- Nachteile: Die `kb_suggested`-Variable wird mit dem Standard-Boilerplate als
  "generated, unaccepted, lower-priority" gelabelt (erforderlich per
  `prompt-standards.md` §3). Aber die zugrunde liegenden Entity-Texte verwenden
  wieder Format A (`### Type: Name\nContent`). Die Scoring-Metadaten
  (`similarity_score`, `usage_count`) werden nicht in den Prompt gerendert — nur
  der Entity-Text.

**Format E – Timeline Event Envelope:**
- Erzeugt von: `analysis/timeline_envelope.py` (ADR-044)
- Genutzt von: Consistency-Pipeline (Stage-2 cross-referencing)
- Vorteile: Strukturierte `TimelineEventEnvelope`-Typen mit
  `character_refs`/`location_ref` als `{id, name}`-Hybrid. Id-basierte und
  name-basierte Referenzauflösung.
- Nachteile: Nur im Consistency-Pfad genutzt. Writing-Prompts sehen Timeline-Events
  nicht direkt (sie bekommen `{{kb_timelines}}` als Format A, nicht als
  strukturierte Envelopes).

**Format F – PromptContext-KB:**
- Erzeugt von: `prompts/context.py:PromptContext._format_kb_entries()` (L177-233)
- Genutzt von: Services die direkt `PromptContext` mit `kb_context_entries`
  füllen (KB-Services, einige Analysis-Pfade)
- Wire-Format: Identisch zu Format A (`### Type: Name\nContent`).
- Unterschied: Explizite ADR-050 P1-A Omission-Accounting mit 4 omitted_fields
  (`provenance`, `evidence`, `review_state`, `freshness`).

**Format G – KBContextEnvelope (Protocol, kein eigenes Wire-Format):**
- Definiert in: `context/_kb_envelope.py` (L78-145)
- Rolle: **Vertrag**, nicht Renderer. Definiert `render(entries, *, tier) ->
  RenderedKBContext`. Die obigen Formate A-F sind die Implementierungen.
- Wert: Erzwingt, dass jeder Render-Pfad `RenderedKBContext` mit
  `preserved_fields`/`omitted_fields` zurückgibt. Stiller Provenance-Verlust
  ist eine RULE-22-Verletzung.

### 1.2 Wann zu viel / zu wenig?

| Format | Zu viel wenn… | Zu wenig wenn… |
|---|---|---|
| A (Standard) | KB >50 Entities → Token-Explosion (Tier-5 Pinned bypassed Budget) | Provenance-Felder fehlen — LLM kann Quelle/Fehleranfälligkeit nicht bewerten |
| B (Wiki) | Role/Attributes redundant mit Content | NarrativeSummary verliert Feld-Struktur — Querying-spezifische Felder ("was ist ihre Waffe?") unklar |
| C (Voice) | >10 Characters mit Profilen → Token-Overhead für nicht-Dialog-Szenen | Nur Character-Voices — keine Location/Faction-Atmosphäre |
| D (Proactive) | Low-Similarity-Suggestions (>0.6 aber semantisch tangential) | Scoring-Metadiken nicht gerendert — LLM weiß nicht, warum vorgeschlagen |
| E (Timeline) | Sehr viele Timeline-Events → Consistency-Pipeline langsam | Nicht in Writing-Prompts sichtbar — LLM kann Timeline-Konflikte beim Schreiben nicht vermeiden |

### 1.3 Empfehlung: Einheitlicher Standard

**Empfehlung:** **Feature-spezifische Variation ist korrekt und sollte beibehalten
werden** — aber mit einer einheitlichen Provenance-Konvention.

**Begründung:**

1. **Wire-Format-Variation ist intentional.** Voice-Profiles brauchen ein anderes
   Format als Entity-Entries (Sprachmuster vs Fakten). Timeline-Envelopes brauchen
   strukturierte Refs (`{id, name}`) für Consistency-Checks. Ein Einheitsformat
   würde diese Feature-spezifischen Anforderungen nivellieren.

2. **Die `### Type: Name\nContent`-Konvention (A/B/F) ist bereits einheitlich.**
   Drei unabhängige Render-Pfade (_helpers, context_wiki, context.py) verwenden
   dasselbe Wire-Format — das ist gut. Format C (Voice) und E (Timeline) sind
   bewusst anders.

3. **Das echte Problem ist Provenance-Transparenz, nicht Wire-Format-Vielfalt.**
   ADR-050 P1-A hat die Omission *explizit* gemacht — aber das LLM sieht
   weiterhin keine Provenance. Das `KBContextEnvelope`-Protocol sollte eine
   Option für "Provenance-annotated rendering" bieten, bei der kritische Felder
   (`source`, `confidence`) bei niedrigen Werten oder bei `review_status="pending"`
   inline in den Text gerendert werden:
   ```
   ### Character: Aria Thorne [auto-extracted, confidence: 0.72]
   ```
   Dies würde es dem LLM ermöglichen, unsichere Fakten zurückhaltender zu
   behandeln. Aktuell behandelt das LLM alle KB-Entries als gleichwertig.

**Bewertung KB-Format-Konsistenz:** ⭐⭐⭐⭐ `[4/5]`

**Befunde:**
- ✅ 3 von 4 Text-Render-Pfaden (A/B/F) verwenden dasselbe `### Type: Name`-
  Wire-Format — gut konsistent.
- ✅ ADR-050 P1-A `KBContextEnvelope`-Protocol macht Provenance-Omission explizit
  (kein stiller Verlust mehr).
- ✅ `{{kb_suggested}}` korrekt als "generated/unaccepted/lower-priority" gelabelt.
- ✅ Format C (Voice) und E (Timeline) sind bewusst anders — Feature-spezifische
  Variation ist gerechtfertigt.
- ⚠️ Kein Render-Pfad gibt Provenance (`source`, `confidence`, `review_status`)
  in den Prompt-Text aus — das LLM kann manuelle Fakten nicht von unsicheren
  Auto-Extraktionen unterscheiden (ALLE `preserved_fields=frozenset()`).
- ⚠️ Format C (Voice) injiziert Frische-Information inline (`⚠️ last updated`),
  aber Format A/B tun dies nicht — inkonsistente Frische-Transparenz.

---

## 2. Storyboard ↔ Knowledge Base – Konsistenzprüfung

**Kernfrage:** Kann ein Storyboard-Eintrag (Plot-Point, Zeitlinie) mit einem
KB-Eintrag (Charakter, Ort, Ereignis) in Konflikt geraten?

### 2.1 Architektureller Ist-Stand

> Verifiziert via Read von `_kb_lifecycle.py`, `_planning_consumer.py`,
> `planning/models.py`, `universal/en/system.md`. ADR-050 P1-B als Referenz.

Narrare hat eine **architektonisch durchdachte Cross-Feature-Sync-Architektur**
(ADR-050 P1-B), aber die Implementierungen leben in Backend — Core definiert nur
die Protokolle.

**Drei-Schicht-Modell der KB↔Consumer-Synchronisation:**

| Schicht | Contract | Implementierungsort | Status |
|---|---|---|---|
| Write-Side | `KBEntityLifecycleObserver` Protocol (`_kb_lifecycle.py:66-145`) | Backend-Services (`apps/api/narrare/{planning,chapters,storyboard}/`) | Protocol definiert ✅; Backend-Implementierungen nicht in diesem Review verifiziert |
| Read-Side | `CrossFeatureRefIndex` Protocol (`_kb_lifecycle.py:148-203`) | Backend-Service (z.B. `apps/api/narrare/consistency/`) | Protocol definiert ✅; `enrich_timeline_envelopes` (ADR-044) ist partielle Timeline-Implementation |
| Policy | `ContradictionPromotionPolicy` (`_kb_lifecycle.py:206-249`) | Backend (aus Project-Settings konstruiert) | Default-Policy definiert ✅ |

**Consumer-Spezialisierungen (Protokolle in Core):**

| Consumer | Ref-Art | On Rename | On Deprecate | On Delete |
|---|---|---|---|---|
| **Timeline** (`TimelineRefConsumer`, `_planning_consumer.py:24-51`) | Hybrid JSON `{id, name}` in `timeline_events` | Update `{id, name}` wo `id` match UND `name==old_name`. Issue wenn Rename Story-Bead kreuzt. | Mark als `"status": "deprecated"`. Kein Rewrite. | Issue `deleted_ref_without_tombstone` pro Event |
| **Storyboard** (`StoryboardRefConsumer`, `_planning_consumer.py:54-85`) | Name-basierter Freitext in `outline_notes` / `planned_beats` | **Kein Rewrite** (RULE-22 §7). Scan nach `old_name`, Issue `stale_name_ref`. | Issue `deprecated_ref_in_active_context`. | Issue `deleted_ref_without_tombstone`. |
| **Chapter Frontmatter** (`_helpers.py:extract_frontmatter_references()`) | Entity-IDs in `pov_character`, `characters`, `location`, etc. | Nicht in Core behandelt — Backend-Consumer | — | — |

### 2.2 Welche Informationen liegen sowohl im Storyboard als auch in der KB vor?

| Information | Im Storyboard? | In der KB? | Konfliktmöglichkeit |
|---|---|---|---|
| Charakter-Existenz | Ja (via `planned_beats`-Freitext, `outline_notes`) | Ja (KB-Entity vom Typ `character`) | **Ja** — Charakter im Storyboard erwähnt aber in KB gelöscht; oder umgekehrt |
| Charakter-Name | Ja (Freitext in Beats) | Ja (Entity.name) | **Ja** — Rename in KB → Stale-Name im Storyboard (nur Warning, kein Auto-Rewrite) |
| Charakter-Attribute (Alter, Aussehen, etc.) | Nein (Storyboard = Struktur, nicht Detail) | Ja (Entity-Content) | Nein — orthogonal |
| Ort-Beschreibung | Ja (vage, in `outline_notes`) | Ja (Entity-Content) | **Ja** — "Die Burg im Norden" (Storyboard) vs "Ironhold Keep" (KB) |
| Timeline-Ereignisse | Teilweise (`planned_beats` als Plot-Punkte) | Ja (Entity vom Typ `timeline`) | **Ja** — Beat sagt "Charakter stirbt in Akt 2"; KB hat den Charakter noch als lebend |
| Beziehungen | Indirekt (Beats können Beziehungen implizieren) | Ja (`kb_relationships`, RelationshipType-Vokabular) | **Ja** — Beat impliziert Allianz, aber KB sagt Feindschaft |

### 2.3 Konfliktlösungs-Präzedenz

> Verifiziert via `universal/en/system.md` (L13-15) und
> `prompt-standards.md` §3 "Cross-Feature Context Precedence" (L480-499).

**Die Präzedenz-Ordnung ist architektonisch garantiert** durch
`NarrareUniversalRules` Capability (nicht übersteuerbar):

```
1. Current author instruction (höchste)
2. Explicit project writing profile / manual override
3. Current scene / storyboard / timeline plan
4. Curated KB (accepted facts)
5. Learned memory / mem0 preferences
6. Generated suggestions / inferred extraction (niedrigste)
```

`universal/en/system.md:13`: *"When the outline contradicts the Knowledge Base,
follow the outline. The outline represents the author's current intent."*

**Das bedeutet konkret:** Im Konfliktfall "gewinnt" das Storyboard (Präzedenz 3)
über die KB (Präzedenz 4). Die KB wird nicht ignoriert, aber das LLM folgt dem
Outline bei Widersprüchen.

### 2.4 Test-Szenarien

| Szenario | Datenquelle 1 | Datenquelle 2 | Möglicher Konflikt | Handling |
|---|---|---|---|---|
| Charakter stirbt in Kapitel 5 (Storyboard-Beat) aber existiert noch als lebend in KB | Storyboard (`planned_beats`: "Aria sacrifices herself") | KB (Entity: Aria, content: "alive, active") | LLM bekommt widersprüchliche Infos: Beat sagt tot, KB sagt lebendig. Bei Generierung von Kapitel 5: folgt Outline → Charakter stirbt. Bei Generierung von Kapitel 6+: KB injiziert Aria als lebend → LLM könnte sie versehentlich wieder auferstehen lassen | **Keine automatische KB-Aktualisierung nach Storyboard-Beat.** Das KB-Entry bleibt unverändert. Der `CrossFeatureRefIndex` prüft Refs, nicht Inhalts-Konsistenz. Konsistenz-Check (CONS-001) könnte dies erkennen — aber nur wenn der Chapter-Text geschrieben wurde, nicht präventiv beim Planen. |
| Ort hat in KB andere Beschreibung als in Storyboard | KB (Entity: "Ironhold Keep", content: "Eine Festung aus schwarzem Stein") | Storyboard (`outline_notes`: "Das hölzerne Dorf Ironhold") | LLM erhält beide: KB als `{{kb_locations}}` (Format A), Storyboard als `{{author_instructions}}` oder Chapter-Outline (Tier-1). Präzedenz: Tier-1/Author > Tier-3/KB → Outline gewinnt | Universal Rules: "follow the outline". KB-Info wird im Prompt angezeigt, aber Outline hat Präzedenz. **Aber:** Es gibt keinen automatischen Konsistenz-Check zwischen Storyboard-Text und KB-Content (nur Ref-Integrität wird geprüft, nicht semantische Konsistenz). |
| KB-Charakter wird umbenannt (Rename) | KB (Entity.name: "Aria" → "Arya") | Storyboard (Freitext in Beats: "Aria enters the room") | Storyboard hat stale Namen. `StoryboardRefConsumer.on_kb_entity_renamed` scannt Beats nach `old_name`, emitiert `RefIntegrityIssue` (`stale_name_ref`) — **aber kein Auto-Rewrite** (RULE-22 §7: "explicit/manual sources are not auto-rewritten") | Warning wird angezeigt. Prompt-Kontext: LLM erhält KB-Entity mit neuem Namen (Format A) + Storyboard-Beat mit altem Namen. Kann zu Verwirrung führen wenn LLM zwei Versionen desselben Charakters "sieht". Default-Policy: `stale_name_ref → warning`. |
| Charakter-Beziehung im KG sagt "Feinde" aber Storyboard-Beat beschreibt Allianz | KB (`kb_relationships`: Aria ↔ Malachai: `enemy`) | Storyboard (`planned_beats`: "Aria und Malachai kämpfen Seite an Seite") | **Beziehungs-Konflikt.** CR-03 §3.2 Befund: Consistency-Check hat KEINE `kb_relationships` in `ConsistencyDeps` → kann Beziehungs-Konflikt strukturell nicht erkennen. Beim Schreiben: LLM erhält Beziehung aus KB (Präzedenz 4) und Beat aus Storyboard (Präzedenz 3) → folgt Storyboard (Allianz). | **Keine automatische Erkennung beim Schreiben.** Consistency-Check kann es nicht prüfen (CR-AUFG-03-01). Der Konflikt wird nur sichtbar wenn der Autor manuell aufpasst. |
| Charakter in Chapter-Frontmatter referenziert aber in KB gelöscht | Chapter-Frontmatter (`pov_character: "uuid-of-aria"`) | KB (Entity gelöscht — `on_kb_entity_deleted`) | Frontmatter-Ref ist dangling. `_helpers.py:extract_frontmatter_references()` extrahiert die ID. Tier-3 versucht den Entity zu laden → Lookup-Miss → Entity fehlt im Kontext. | **Stiller Kontext-Verlust.** Kein Warning, kein Error im Prompt. Der `ChapterFrontmatterConsumer` (Backend) sollte `RefIntegrityIssue` mit `deleted_ref_without_tombstone` emitiern. Ob der Autor das sieht hängt von Backend-Implementation ab. |

**Weiteres Szenario (zusätzlich generiert):**

| Szenario | Datenquelle 1 | Datenquelle 2 | Möglicher Konflikt | Handling |
|---|---|---|---|---|
| KB-Auto-Extraktion erstellt Character-Entry, aber Autor hat im Storyboard einen anderen Namen etabliert | KB (`source: "auto_extraction"`, `confidence: 0.72`, Name: "The Archer") | Storyboard (`planned_beats`: "Aria, known as the Archer") | Auto-Extraktion erstellt einen separaten Entity "The Archer" statt Aria zuzuordnen. Wenn akzeptiert → zwei KB-Entities für denselben Charakter. | KB-Merge (`kb/merge`) kann Duplicates erkennen. Aber: das Prompt zeigt beide Entities (Format A) ohne Provenance — LLM sieht zwei "verschiedene" Charaktere. `source` und `confidence` werden nicht gerendert (Format A: `preserved_fields=frozenset()`). |

### 2.5 Bewertung

**Bewertung:** ⭐⭐⭐⭐ `[4/5]`

**Befunde:**
- ✅ **Architektonisch exzellentes Sync-Contract-System** (ADR-050 P1-B):
  `KBEntityLifecycleObserver` + `CrossFeatureRefIndex` +
  `ContradictionPromotionPolicy` definieren Ref-Integrität über Feature-Grenzen
  hinweg. Core definiert die Protokolle; Backend implementiert.
- ✅ **Konfliktlösungs-Präzedenz ist garantiert**: `NarrareUniversalRules`
  ("outline > KB") gilt universell und ist nicht übersteuerbar.
- ✅ **Auto-Rewrite-Verbot** für Storyboard-Beats (RULE-22 §7) ist korrekt —
  nutzerautorisierte Inhalte werden nicht automatisch geändert, nur gewarnt.
- ⚠️ **Ref-Integrität ≠ Inhalts-Konsistenz**: Die Sync-Contracts prüfen, ob
  *Referenzen* gültig sind (Rename/Delete/Deprecate), aber nicht, ob der *Inhalt*
  semantisch konsistent ist (z.B. Charakter-Attribut "Alter: 25" im KB vs
  "30-jährige Frau" im Storyboard-Text). Es gibt keine automatische
  Storyboard↔KB-Inhalts-Konsistenz-Prüfung.
- ⚠️ **Backend-Implementierungen nicht verifiziert**: Die Protokolle sind in Core
  definiert, aber ob `apps/api/narrare/{planning,chapters,storyboard}/` sie
  tatsächlich implementieren (und registrieren), wurde in diesem Core-fokussierten
  Review nicht verifiziert. "Dokumentiert ≠ implementiert" (CR-04-Lektion).
- ✅ **Re-Check 2026-07-14 — VERIFIZIERT:** Backend-Adoption nachträglich verifiziert.
  `KBEntityLifecycleObserver` implementiert via `KBLifecycleDispatcher`
  (`apps/api/narrare/kb/lifecycle_dispatcher.py`); `TimelineRefConsumerImpl` /
  `StoryboardRefConsumerImpl` (`apps/api/narrare/planning/kb_lifecycle_consumer.py`);
  `CrossFeatureRefIndexImpl` gewired in `apps/api/narrare/consistency/deps.py:101-109`
  (`get_cross_feature_ref_index`); `ContradictionPromotionPolicy` mit Defaults.
  Alle mit Unit-Tests abgedeckt (`tests/unit/api/{kb,consistency,chapters}/`,
  `tests/unit/planning/`). Kein Dokumentations-vs-Implementation-Gap mehr.
- ⚠️ **Beziehungs-Konsistenz** (KG vs Storyboard) ist strukturell nicht prüfbar:
  `ConsistencyDeps` hat kein `kb_relationships`-Feld (CR-03 §3.2,
  CR-AUFG-03-01). Die höchstwertige Cross-Feature-Konsistenz-Prüfung
  (beziehungsbasierte Widersprüche) ist ungenutzt.
- ⚠️ **Stiller Kontext-Verlust bei dangling Frontmatter-Refs**: Wenn ein
  referenzierter KB-Entity gelöscht wird, verschwindet er still aus dem
  Tier-3-Kontext. Es gibt keine Prompt-Level-Warnung ("⚠️ pov_character
  referenced in frontmatter not found in KB").

---

## 3. Templates ↔ Frontmatter – Schema-Konsistenz

> Verifiziert via Read von `shared/frontmatter.py`,
> `prompts/variable_engine.py`, `prompts/variable_registry.py`,
> `prompts/context.py`. `prompt-standards.md` §1 Frontmatter-Schema als Referenz.

**Prüfung:**

### 3.1 Frontmatter-Schema

Das Frontmatter-Schema ist in `prompt-standards.md` §1 definiert als:

```yaml
---
prompt_type: <category>         # writing | kb | analysis | planning | meta | generation | wiki | universal
prompt_language: <locale>       # en | de | fr
prompt_version: "<MAJOR>.<MINOR>.<PATCH>"
---
```

Der Parser (`shared/frontmatter.py:parse_frontmatter()`, L52-77) ist **generisch**
— er parst beliebiges YAML ohne Schema-Validierung. Unbekannte Felder werden
akzeptiert und in `metadata` gespeichert. Es gibt **keine** Schema-Enforcement-
Logik, die unbekannte Felder ablehnt oder fehlende Pflichtfelder erzwingt —
außer in der `ParsedFrontmatter.require()`-Methode (L45-49), die manuell für
spezifische Keys aufgerufen werden muss.

### 3.2 Template-Variablen vs Frontmatter

Template-Variablen (`{{variable}}`) und Frontmatter-Felder sind **orthogonal**:

- **Frontmatter** beschreibt Metadaten über die Prompt-Datei (Typ, Sprache,
  Version). 3 Felder, alle vom Code erwartet und genutzt.
- **Template-Variablen** beschreiben Laufzeit-Daten, die in den Prompt-Body
  substituiert werden. 80+ registrierte Variablen in `variable_registry.py`.

Es gibt **keine** 1:1-Beziehung zwischen Frontmatter-Feldern und
Template-Variablen — sie dienen unterschiedlichen Zwecken.

### 3.3 Code-Erwartung vs Frontmatter-Realität

| Feld | In Frontmatter-Schema | In Code erwartet | Konsistent? | Evidenz |
|---|---|---|---|---|
| `prompt_type` | ✅ Ja (required) | ✅ Ja — `PromptRegistry` nutzt es für Kategorisierung, Cascade-Auflösung (`registry.py`) | ✅ Ja | Alle 58 `system.md`-Dateien haben `prompt_type` |
| `prompt_language` | ✅ Ja (required) | ✅ Ja — `PromptRegistry` nutzt es für Sprach-Cascade (`registry.py`), Capabilities laden sprachspezifisch | ✅ Ja | Alle 58 `system.md`-Dateien haben `prompt_language` |
| `prompt_version` | ✅ Ja (required) | ✅ Ja — Version-Tracking, `check_prompt_structure.py` validiert Format | ✅ Ja | Alle 58 `system.md`-Dateien haben `prompt_version` |
| Genre-spezifische `system_{genre}.md` | Nicht im Frontmatter | ✅ Ja — `PromptRegistry` prüft `system_{genre}.md` VOR `system.md` pro Cascade-Level | ✅ Ja | File-basiert, kein Frontmatter-Feld nötig |
| `prompt_mode` (sub-mode) | Nicht im Schema | Nicht direkt — Mode kommt aus dem Verzeichnisnamen (`{category}/{lang}/{mode}/system.md`) | ✅ Ja | Pfad-basiert, kein Frontmatter nötig |

### 3.4 Template-Variablen ohne Frontmatter-Äquivalent

Template-Variablen haben **kein** Frontmatter-Äquivalent und brauchen auch keins.
Die Variable Engine (`variable_engine.py:prepare_variables_for_template()`,
L145-170) validiert zur Build-Zeit:

1. Jede `{{variable}}` im Template MUSS im Taxonomy registriert sein
   (`variable_registry.py`) — sonst `PromptVariableError` (L163-164)
2. Jede required Variable MUSS im Variablen-Dict vorhanden sein — sonst
   `PromptVariableError` (L170)
3. Optionale Variablen bekommen leere String-Defaults (L167-168)

**Schema-Gap-Analyse (Variablen-Registry vs Template-Verwendung):**

| Variable | In Registry | In Templates verwendet | Im Context verfügbar | Konsistent? | Evidenz |
|---|---|---|---|---|---|
| `{{style_profile}}` | ✅ `SYSTEM_VARS` (L87) | ✅ 4 von 8 EN Writing-Prompts | ✅ `PromptContext.style_profile` (L106) | ⚠️ **Inkonsistent** — CR-01 §4: fehlt in scene_by_scene, interactive_session, story_suggest, inline_suggest, chat | cr-01 Befund |
| `{{kb_characters}}` | ✅ `SYSTEM_VARS` (L65) | ✅ In Templates | ⚠️ Runtime: Coreference setzt `=""` | ❌ **Runtime-Gap** — CR-03 §2.2: Coreference-Service hat kein KB-Repository wired | cr-03 Befund |
| `{{kb_relationships}}` | ✅ `SYSTEM_VARS` (L68) | ✅ In Templates | ⚠️ Runtime: Coreference, Voice, Planning setzen `=""` | ❌ **Runtime-Gap** — CR-03 §2.2: mehrere Services ignorieren Relationships | cr-03 Befund |
| `{{user_preferences}}` | ✅ `SYSTEM_VARS` (L84) | ✅ In Templates | ⚠️ Runtime: nur wenn Context "leer" | ❌ **Injection-Gate-Gap** — CR-03 §1.2: `composer.py:93-113` injiziert nur bei leerem Context | cr-03 Befund |
| `{{candidate_pairs}}` | ✅ `FEATURE_DYNAMIC_VARS` (L147) | ✅ kb/merge | ✅ Via Extra-Dict | ⚠️ Nicht XML-gewrappt trotz User-Content-Risiko | cr-01 §6.6 |
| `{{kb_pinned}}` | ✅ `SYSTEM_VARS` (L76) | ✅ In Templates | ✅ Via `WritingContext.to_prompt_variables()` | ✅ Ja | ADR-050 P1-D: nachträglich registriert |
| `{{writing_language}}` | ✅ `SYSTEM_VARS` (L106) | ✅ Alle EN Writing-Prompts | ✅ `PromptContext.writing_language` | ⚠️ Fehlt in worldbuilding/phase1 | cr-01 §1.3 |

### 3.5 Automatische Template-Aktualisierung bei KB-Strukturänderung

**Nein** — Templates werden nicht automatisch aktualisiert, wenn sich die
KB-Struktur ändert. Die Beziehung ist:

```
KB-Entity-Typen (character, location, faction, system, timeline)
  ↓
Tier-3 Processor (`_tier3_processor.py:89-93`) klassifiziert hart:
  chars = [e for e in entities if e.entity_type == "character"]
  locs  = [e for e in entities if e.entity_type == "location"]
  ...
  ↓
Template-Variablen: {{kb_characters}}, {{kb_locations}}, {{kb_factions}},
  {{kb_systems}}, {{kb_timelines}}, {{kb_relationships}}
```

Wenn ein neuer Entity-Typ hinzugefügt wird (z.B. "object" oder "concept"),
wird er vom Tier-3 Processor **nicht** erfasst (er klassifiziert nur die 5
bekannten Typen). Das Template hat keine Variable dafür. Der Entity
verschwindet aus dem Kontext.

**Bewertung:** ⭐⭐⭐⭐ `[4/5]`

**Befunde:**
- ✅ Frontmatter-Schema (3 Felder) ist mit Code-Erwartung voll konsistent — alle
  Felder werden vom Registry/Cascade-System genutzt.
- ✅ Variable Engine validiert strikt: unregistrierte → Error, fehlende required →
  Error, optionale → leerer Default. Sauber.
- ✅ `parse_frontmatter()` ist generisch und robust (YAML-safe_load, graceful
  fallback bei Parse-Fehlern).
- ⚠️ Keine Schema-Validierung für Frontmatter: unbekannte Felder werden akzeptiert
  ohne Warning. Ein Tippfehler (`prompt_typ:` statt `prompt_type:`) würde still
  ignoriert werden — das `require()` muss manuell pro Feld aufgerufen werden.
- ⚠️ Template-Variablen haben mehrere **Runtime-Gaps** (nicht Schema-Gaps): Die
  Variablen sind im Template vorhanden und registriert, aber der Runtime-Service
  füllt sie nicht oder mit `=""` (siehe cr-03 Befunde: Coreference ohne
  `kb_characters`, Voice/Planning ohne `kb_relationships`, Preference-Injection-
  Gate). Diese Gaps werden von keinem maschinellen Gate erkannt (CR-AUFG-03-08).
- ⚠️ Tier-3 Processor klassifiziert hart 5 Entity-Typen — neue Typen werden
  still ignoriert. Keine dynamische Erweiterung.

---

## 4. Funktionen, die sich gegensätzlich verhalten

**Kernfrage:** Kann ein Nutzer durch Nutzung von Feature A in einen Zustand
geraten, den Feature B nicht korrekt verarbeitet?

> Befunde aus cr-01, cr-03 integriert; zusätzlich verifiziert via Read von
> `universal/en/system.md`, `prompt-standards.md` §3, `profiles/assembly.py`,
> `prompts/context.py`, `_voice_profiles.py`.

### 4.1 Widerspruchs-Matrix

| Feature A | Feature B | Potenzieller Widerspruch | Schwere | Empfehlung |
|---|---|---|---|---|
| **Writing-Style-Learning** (mem0 PreferenceService → `user_preferences`) | **Manual-Style-Override** (`style_profile`, `tone_instructions`, `author_instructions`) | **Präzedenz ist klar geregelt** (Universal Rules: "author instructions > preferences"; prompt-standards.md §3: Manual-Override = Präzedenz 2, Learned Memory = Präzedenz 5). **ABER:** CR-AUFG-03-05 fand, dass `composer.py:93-113` Preferences nur injiziert wenn Context "leer" ist. Writing-Context ist immer gefüllt → **mem0-Preferences erreichen den Writing-Prompt möglicherweise nie.** Der Widerspruch entsteht nicht durch Konflikt, sondern durch Abwesenheit: Preferences werden still geschluckt, statt mit Manual-Override zu konkurrieren. | 🟡 Mittel | CR-AUFG-03-05: Preference-Injection-Gate korrigieren. Gate-Bedingung soll Preferences auch bei gefülltem KB/Chapter-Context injizieren (sie sind orthogonal). |
| **KB-Auto-Extraktion** (kb/extract → Entity mit `source: "auto_extraction"`, `confidence: 0.72`) | **Manuelle KB-Einträge** (`source: "manual"`, `confidence: 1.0`) | **Divergenz möglich:** Auto-Extraktion kann fehlerhafte oder widersprüchliche Entities erstellen. Wenn akzeptiert (vom Autor endorsed), werden sie zu normalen KB-Entities. Beim Rendering (Format A) werden **alle** Entities identisch dargestellt — `source` und `confidence` werden nicht gerendert (`preserved_fields=frozenset()`). Das LLM kann eine fehlerhafte Auto-Extraktion nicht von einem kuratierten manuellen Eintrag unterscheiden. KB-Merge (`kb/merge`) kann Duplikate erkennen, aber nicht semantische Fehler in akzeptierten Extraktionen. | 🟡 Mittel | Provenance-annotated Rendering einführen (siehe §1.3): bei niedriger Confidence oder `review_status="pending"` Provenance inline in den Prompt rendern. |
| **Voice-Checker** (`analysis/voice_check`, `analysis/character_voice`) | **Writing-Continue** (`scene_by_scene`, `interactive_session`, `story_suggest`) | **Stil-Definition kann divergieren.** Voice-Checker misst Voice-Consistency gegen `{{character_voice_profiles}}`. Writing-Continue generiert Prosa. **ABER:** CR-01 §4: `{{style_profile}}` fehlt in 4 von 8 Writing-Prompts (scene_by_scene, interactive_session, story_suggest, inline_suggest). Wenn Continue ohne Style-Profile generiert, kann der Output vom profilierbaren Stil abweichen — und Voice-Checker meldet Inkonsistenz, die Continue "nicht wissen konnte". | 🟡 Mittel | CR-AUFG-01-06: `{{style_profile}}` zu allen 8 EN Writing-Prompts hinzufügen. |
| **Storyboard-Timeline** (`planning/models.py:StoryboardView`, `SyncStatus`) | **Chapter-Timestamps** (Chapter Frontmatter `pov_character`, `characters`, etc.) | **Einseitige Synchronisation.** KB-Lifecycle-Changes → Consumer (Timeline, Storyboard, Frontmatter). Aber: **keine umgekehrte Synchronisation.** Wenn ein Charakter im Storyboard-Beat stirbt, wird das KB-Entry nicht aktualisiert. Wenn ein Chapter geschrieben wird, das vom Outline abweicht (`SyncStatus.DEVIATED`), wird die KB nicht automatisch angepasst. Die Sync-Status (`on_track`, `deviated`) sind reine Status-Marker — sie lösen keine KB-Updates aus. | 🟡 Mittel | Keine automatische Lösung empfohlen (bidirektionale Sync ist extrem komplex). **Aber:** Konsistenz-Check sollte Deviation als Konsistenz-Flag berücksichtigen. |
| **KB-Consistency-Check** (analysis/consistency, `ConsistencyDeps`) | **Knowledge Graph** (`kb_relationships`, RelationshipType) | **Beziehungs-Konsistenz ist strukturell nicht prüfbar.** CR-03 §3.2: `ConsistencyDeps` hat kein `kb_relationships`-Feld. Consistency-Check kann Beziehungs-Widersprüche ("Aria ist Feindin im KG, aber verbündet im Text") nicht erkennen. `ConsistencyCheckType.WORLD` existiert, ist aber mangels Daten funktionslos. | 🔴 Hoch | CR-AUFG-03-01: `ConsistencyDeps` um `kb_relationships` erweitern. |
| **Coreference-Resolution** (`analysis/coreference`) | **KB-Charaktere** (`kb_characters`) | **Funktionaler Adoptions-Fehler.** CR-03 §2.2 Nr.3: Coreference-Service setzt alle KB-Variablen auf `=""`. Coreference-Resolution MUSS Pronomen zu Charakteren zuordnen, bekommt aber die Charakter-Liste nicht. Das Modell muss raten. | 🔴 Hoch | CR-AUFG-03-02: KB-Repository in Coreference-Service wiren. |
| **Tier-5 Pinned (Budget-Bypass)** | **Token-Budget-Manager** (`TokenBudgetManager`) | **Bypass-Overhead.** Tier-5 (Pinned) wird immer inkludiert, selbst wenn vorherige Tiers das Budget überschreiten (`context_assembler.py:190-229`). Bei vielen angepinnten Entities kann das Context-Fenster überlaufen → Output-Kürzung oder Modell-Fehler. Es gibt keinen "Hart-Cap" für Pinned. | 🟢 Niedrig | Bewusstes Design (Autor will Pinned immer sehen). Aber: Warning/Metrik bei Pinned-Overflow wäre hilfreich. |
| **Beta-Reader** (`analysis/beta_reader`) | **KB-Context** (`kb_characters`, `kb_locations`) | **Oberflächlicher Kontext.** CR-03 §2.2 Nr.1: Analysis-ContextAssembler trunciert KB-Entries auf 200 Zeichen (`kb_summary_truncation=200`). Beta-Reader arbeitet mit KB-Stumps statt vollen Entries. Feld-Widersprüche, die im abgeschnittenen Teil liegen, werden übersehen. | 🟡 Mittel | CR-AUFG-03-03: Analysis-ContextAssembler auf TokenBudget migrieren. |

### 4.2 Detaillierte Analyse der 4 Kern-Widersprüche

#### 4.2.1 Writing-Style-Learning vs. Manual-Style-Override

**Wer gewinnt?** Architektonisch: **Manual-Override** (Präzedenz 2 > mem0
Präzedenz 5). `NarrareUniversalRules`: "When author instructions contradict user
preferences, always follow the author instructions."

**Realität:** Der Widerspruch entsteht selten, weil **mem0-Preferences oft gar
nicht im Prompt ankommen** (CR-AUFG-03-05: Injection-Gate). Wenn Preferences
ankommen, werden sie als `{{user_preferences}}` in Section 7 gerendert — klar
als "preferences" gelabelt, nicht als Instructions. Das LLM kann sie korrekt
als niedrigere Präzedenz behandeln.

**Restrisiko:** mem0-Preferences könnten **komplementär** sein (nicht
widersprüchlich), aber dennoch ignoriert werden. Beispiel: Autor schreibt nie
Dialoge → mem0 lernt "präferiert Beschreibungen" → aber Writing-Continue injiziert
diese Preference nie → Modell generiert Dialoge. Das ist kein Widerspruch, sondern
ein **Adoptions-Verlust**.

#### 4.2.2 KB-Auto-Extraktion vs. manuelle KB-Einträge

**Können sie divergieren?** **Ja.** KB-Extract (`kb/en/extract/system.md`)
extrahiert Entities mit Confidence ≥0.7. Wenn akzeptiert, werden sie zu normalen
KB-Entities. Es gibt keinen Mechanismus, der auto-extrahierte Entities als
"sekundär" markiert — `review_status` geht auf `"endorsed"` beim Accept.

**Konkreter Konfliktfall:** Auto-Extraktion erstellt Character "The Archer"
(confidence 0.72). Manuell existiert bereits "Aria" (confidence 1.0). Beide
werden im Prompt identisch gerendert (Format A: `### Character: The Archer` /
`### Character: Aria`). LLM sieht zwei Charaktere. KB-Merge kann sie später
zusammenführen — aber beim **Schreiben** sieht das Modell Duplikate ohne
Provenance-Indikator.

**KB-Extract-Prompt-Defense:** Der Extract-Prompt hat strenge Confidence-Thresholds
(≥0.7 endorse, 0.4-0.7 uncertain, <0.3 never) und `source_text`-Evidence-Felder.
Aber sobald der Entity akzeptiert und in die KB geschrieben ist, geht diese
Provenance verloren — `source`-Feld existiert auf `KBContextEntry`, wird aber
nicht gerendert.

#### 4.2.3 Voice-Checker vs. Writing-Continue

**Verschiedene "richtige" Stile?** **Möglich.** Voice-Checker
(`analysis/voice_check/system.md`, ⭐⭐⭐⭐⭐ per cr-01) misst
Voice-Consistency-Metriken (Satzlänge, Vokabular, etc.) gegen
`{{character_voice_profiles}}`. Writing-Continue generiert Prosa.

**Divergenz-Mechanismus:**

1. **Fehlendes `{{style_profile}}`** in 4 von 8 Writing-Prompts (cr-01 §4):
   `scene_by_scene`, `interactive_session`, `story_suggest`, `inline_suggest`
   generieren ohne Style-Profile. Voice-Checker misst gegen Profile. Continue
   wusste nicht, welches Profil gilt → Checker meldet Inkonsistenz.

2. **Stale Voice-Profile** (`_voice_profiles.py:74`): Voice-Profile >30 Tage alt
   werden mit `⚠️ last updated` markiert. Aber Writing-Continue generiert
   weiterhin gegen das stale Profil. Voice-Checker (separat aufgerufen) misst
   gegen dasselbe stale Profil → beide sind "falsch" auf dieselbe Weise.

3. **Voice-Checker ohne Beziehungs-Kontext** (CR-03 §4): `voice_check_prompt.py`
   setzt `kb_relationships=""`. Voice-Checker weiß nicht, wie Charaktere
   miteinander sprechen. Writing-Continue hat `kb_relationships` → kann
   Beziehungs-Ton treffen. Checker meldet fälschlich Inkonsistenz, weil er den
   Beziehungs-Kontext nicht hatte.

#### 4.2.4 Storyboard-Timeline vs. Chapter-Timestamps

**Sind sie synchron?** **Einseitig.** KB → Consumer (Timeline, Storyboard,
Frontmatter) ist über Protokolle geregelt. Consumer → KB gibt es nicht.

**Konkreter Sync-Bruch:**

1. Autor plant im Storyboard: "Kapitel 5: Aria stirbt" (`planned_beats`).
2. Autor schreibt Kapitel 5 → Aria stirbt.
3. KB-Entry "Aria" bleibt unverändert (`content: "alive, active"`).
4. Autor schreibt Kapitel 6 → `WritingContextAssembler` injiziert Tier-3
   `kb_characters` → Aria als "alive, active".
5. **LLM sieht:** Outline (Präzedenz 3) + KB (Präzedenz 4). Outline sagt nicht,
   was in Kapitel 6 passiert. KB sagt Aria ist lebendig.
6. **Möglicher Output:** LLM lässt Aria auferstehen, weil KB sie als lebendig
   deklariert und das Outline für Kapitel 6 nichts sagt.

**Keine automatische Lösung:** Bidirektionale Sync wäre extrem komplex
(Story-Events → KB-Lifecycle-Changes). Konsistenz-Check (CONS-001) sollte dies
erkennen — aber nur nachträglich (nachdem der Text geschrieben wurde), nicht
präventiv beim Generieren.

**Bewertung:** ⭐⭐⭐ `[3/5]`

**Befunde:**
- ✅ Konfliktlösungs-Präzedenz ist architektonisch garantiert (Universal Rules).
- ✅ KB→Consumer Sync-Protokolle sind durchdacht (ADR-050 P1-B).
- 🔴 **Consistency-Check ohne KG-Relationships** = hochwertigster
  Cross-Feature-Konsistenz-Check strukturell blind (CR-AUFG-03-01).
- 🔴 **Coreference ohne Charakter-Liste** = funktionaler Adoptions-Fehler
  (CR-AUFG-03-02).
- 🟡 **Provenance-Verlust** bei KB-Rendering: LLM kann manuelle von
  Auto-Extraktion nicht unterscheiden → keine konfliktbewusste Generierung.
- 🟡 **Style-Profile-Lücke** in 4/8 Writing-Prompts → Voice-Checker vs Continue
  Divergenz (CR-AUFG-01-06).
- 🟡 **Preference-Injection-Gate** → mem0-Preferences erreichen Writing-Prompts
  möglicherweise nie (CR-AUFG-03-05).
- 🟡 **Einseitige Storyboard↔KB-Synchronisation** → Story-Events aktualisieren
  KB nicht → stale KB beim nachfolgenden Schreiben.
- 🟢 **Tier-5 Pinned Bypass** — bewusstes Design, kein Bug, aber Overflow-Risiko.

**Accepted Risk (2026-07-14) — Tier-5 Pinned Budget-Bypass:** Tier-5 (Pinned) wird
immer inkludiert, selbst bei Budget-Überschreitung — bewusstes Design (Autor will
angepinnte Entities immer sehen). Ein Overflow-Warning/Metrik wurde als mögliche
Erweiterung identifiziert (§4.1 🟢, §4.2 Bewertung), aber nicht als Aufgabe
registriert, da kein aktuelles Fehlverhalten vorliegt und der Bypass als Feature gilt.
*Reason:* conscious design decision, no current violation. Reassess falls
Pinned-Overflow zu Output-Kürzungen oder Modell-Fehlern führt.

---

## 5. i18n-Konsistenz in Prompts

> Verifiziert via cr-00 §5 (Locale-Strategie), cr-02 §2.2 (de/fr Legacy),
> `prompt-standards.md` §5 (Versioning Rules), `prompt-content-standards.md` §8
> (Formality Register), `variable_registry.py` (VARIABLE_ALIASES).

**Wichtig:** Prüfung unter Berücksichtigung der EN-only-Strategie (ADR-026
Phase 5). Fehlende DE/FR-Templates werden **nicht** als Fehler gewertet, wenn
EN-only bewusst ist.

### 5.1 Aktuelle Locale-Strategie

| Prompt-Familie | Sprachen | Strategie | Konsistent? |
|---|---|---|---|
| `meta` | en, de, fr | **Deklarierte lokalisierte Familie** — v3.0.0 in allen 3 Locales, Versions-Parität ✅ | ✅ Ja |
| `universal` | en, de, fr | **Deklarierte lokalisierte Familie** — v1.0.0 in allen 3 Locales, Versions-Parität ✅ | ✅ Ja |
| `writing` (EN) | en | **EN-only per Phase 5** — 10 Modi, Output-Sprache via `{{writing_language}}` | ✅ Ja |
| `writing` (DE/FR Legacy) | de, fr | **Legacy-Lokalisierung** — 6 Modi (chat, co_author, inline_suggest, interview, new_chapter, rewrite_selection) | ⚠️ **Phase 5 Deviation** — cr-02 AUFG-02-09 |
| `kb` | en | EN-only per Standard | ✅ Ja |
| `analysis` | en | EN-only per Standard | ✅ Ja |
| `planning` | en | EN-only per Standard | ✅ Ja |
| `generation` | en | EN-only per Standard | ✅ Ja |
| `wiki` | en | EN-only per Standard | ✅ Ja |

### 5.2 Werden `{{writing_language}}`, Meta/Universal Rules und UI-i18n korrekt gesteuert?

**`{{writing_language}}`-Steuerung:**

- ✅ Alle EN Writing-Prompts verwenden `{{writing_language}}` in Constraints
  (verifiziert in cr-01). Kein bundled System-Prompt verwendet deprecated
  `{{language}}` (`check_deprecated_language_variable` enforced).
- ✅ `PromptContext.as_variables()` (L171-173): `writing_language` defaultet zu
  `language` wenn nicht gesetzt — sicherer Fallback.
- ⚠️ **worldbuilding/phase1** hat kein `{{writing_language}}` (cr-01 §1.3,
  CR-AUFG-01-02). Das Modell weiß nicht, in welcher Sprache es antworten soll.
- ⚠️ **kb/enhance**, **kb/extract** haben kein `{{writing_language}}` in
  Constraints (cr-01 §1.3). Enhance generiert Entity-Felder in der Projektsprache
  — ohne Sprachanweisung.

**Meta/Universal Rules — Mehrsprachigkeit:**

- ✅ Meta v3.0.0 in en/de/fr — strukturelle Parität: Identity, Approach, Role
  Flexibility, Conversation Guardrails (7 Bulletpoints), Avoidance-Patterns.
- ✅ Universal v1.0.0 in en/de/fr — strukturelle Parität: Fiction Guidelines,
  Conflict Resolution (2 Regeln), Injection Defense.
- ✅ Register: DE = Du, FR = tu (per `prompt-content-standards.md` §8, Q-013
  gelöst). Keine gemischten Du/Sie oder tu/vous.
- ⚠️ Injection Defense Duplikat zwischen Meta und Universal (cr-02 AUFG-02-08) —
  ~30 Token Overhead, Drift-Risiko bei zukünftigen Aktualisierungen.

**UI-i18n:**

- Nicht in Scope dieses Core-Reviews (UI-i18n lebt in `packages/web/messages/`
  bzw. `packages/i18n/`). Die Prompt-Seite ist korrekt: Capabilities laden
  sprachspezifisch via `for_run(ctx)` mit EN-Fallback.

### 5.3 Sind Meta/Universal Rules in den erforderlichen Sprachen vorhanden und strukturell konsistent?

✅ **Ja.** Beide Capability-Familien sind vollständig in en/de/fr vorhanden mit
Versions-Parität. Strukturelle Parität verifiziert (gleiche Sektionen, gleiche
Reihenfolge). Dies ist vorbildlich.

### 5.4 Sind Feature-Templates (EN-only) strukturell so gebaut, dass die Ausgabe-Sprache zuverlässig gesteuert wird?

⚠️ **Überwiegend ja, mit Lücken.** Die meisten EN Writing-Prompts haben
`Write in {{writing_language}}` in Constraints. **Aber:**

- `worldbuilding/phase1`: Kein `{{writing_language}}`, keine Constraints-Sektion
  (CR-AUFG-01-02).
- `kb/enhance`: Kein `{{writing_language}}` in Constraints (CR-AUFG-01-02 implizit).
- `kb/extract`: Kein `{{writing_language}}` (CR-AUFG-01-02 implizit).

Diese Features können Output in der falschen Sprache produzieren, wenn das Modell
defaultet (EN bei fehlender Sprachanweisung).

### 5.5 Writing de/fr Legacy-Inkonsistenz (cr-00 Befund)

⚠️ **Bestehendes Problem.** 6 writing-Modi existieren in de/fr
(chat, co_author, inline_suggest, interview, new_chapter, rewrite_selection),
obwohl ADR-026 Phase 5 EN-only vorschreibt.

**Risiko:** Diese Templates haben eigene Rollenbeschreibungen ("Du bist ein
versierter Assistent für kreatives Schreiben") und Anweisungen, die vom
EN-Standard abweichen könnten. Sie sind weder vollständig (4 EN-Modi fehlen)
noch in regelmäßigen Review-Zyklen. Content-Drift zwischen EN und de/fr ist
möglich.

**cr-02 AUFG-02-09** empfiehlt: Entfernen der de/fr-Templates. Output-Sprache
wird zuverlässig über `{{writing_language}}` gesteuert (EN-Instructions + DE-Output
funktioniert). Die de/fr Meta/Universal-Capabilities bleiben mehrsprachig.

### 5.6 Bewertung

**Bewertung i18n-Qualität in Prompts:** ⭐⭐⭐⭐ `[4/5]`

**Befunde:**
- ✅ EN-only-Strategie für Feature-Prompts ist sound und konsequent umgesetzt
  (5 von 6 Kategorien rein EN-only).
- ✅ Meta/Universal als deklarierte lokalisierte Familien: vollständige
  Versions-Parität, strukturelle Konsistenz, korrektes Register (Du/tu).
- ✅ `{{writing_language}}` als kanonische Output-Sprach-Variable konsequent
  genutzt. `{{language}}` deprecated und in keinem bundled Template.
- ✅ `variable_registry.VARIABLE_ALIASES` löst Legacy-`{{language}}` automatisch
  auf → Abwärtskompatibilität ohne Bruch.
- ⚠️ Writing de/fr Legacy (6 Modi) — Phase 5 Deviation (CR-AUFG-02-09).
- ⚠️ Drei EN-Templates ohne `{{writing_language}}`: worldbuilding/phase1,
  kb/enhance, kb/extract — können Output in falscher Sprache produzieren
  (CR-AUFG-01-02).
- ⚠️ Injection Defense Duplikat Meta↔Universal (CR-AUFG-02-08) — Redundanz mit
  Drift-Risiko.

---

## Gesamtbewertung Cross-Feature-Kohärenz

**Bewertung:** ⭐⭐⭐⭐ `[4/5]`

**Zusammenfassung:** Narrare besitzt eine architektonisch ausgereifte
Cross-Feature-Kohärenz-Infrastruktur. Die KB↔Consumer-Synchronisation (ADR-050
P1-B) mit `KBEntityLifecycleObserver`-, `CrossFeatureRefIndex`- und
`ContradictionPromotionPolicy`-Protokollen ist durchdacht und folgt dem
Contract-First-Prinzip (RULE-03). Die Konfliktlösungs-Präzedenz
(Outline > KB > Preferences > Suggestions) ist über `NarrareUniversalRules`
architektonisch garantiert und nicht übersteuerbar. KB-Context-Rendering ist über
das `KBContextEnvelope`-Protocol (ADR-050 P1-A) provenance-aware — stiller
Metadaten-Verlust ist eine RULE-22-Verletzung. Die i18n-Strategie (EN-only
Feature-Prompts + trilinguale Capabilities + `{{writing_language}}`-Variable)
ist konsistent umgesetzt. Verbleibende Schwachpunkte sind: (1) **kein
Render-Pfad gibt Provenance in den Prompt-Text aus** — das LLM kann manuelle von
Auto-Extraktion nicht unterscheiden; (2) **Ref-Integrität ≠ Inhalts-Konsistenz**
— Storyboard↔KB semantische Widersprüche werden nicht präventiv geprüft; (3)
**funktionaler Adoptions-Fehler bei Coreference** (keine Charakter-Liste) und
**Consistency-Check** (keine KG-Relationships) aus cr-03; (4) **Style-Profile-
Lücke** in 4/8 Writing-Prompts aus cr-01, die Voice-Checker vs Continue-Divergenz
verursacht; (5) **Preference-Injection-Gate** aus cr-03, das mem0-Preferences
möglicherweise nie den Writing-Prompt erreicht. Diese Punkte sind behebbar ohne
Architekturänderungen — sie sind Implementierungs- und Inhalts-Lücken, keine
Design-Fehler.

---

## Aufgaben

<!-- Nummerierung: CR-AUFG-04-01, CR-AUFG-04-02, … -->

### CR-AUFG-04-01 — Provenance-annotated KB-Rendering einführen

**Re-Check 2026-07-14:** **ERLEDIGT 2026-07-14** — `RenderOptions`-Contract (`context/_render_options.py`) + Annotation-Engine (`context/_provenance_annotation.py`) implementiert; 4 Render-Pfade erweitert (`writing/_helpers.py`, `writing/context_wiki.py`, `prompts/context.py`, `writing/_tier3_processor.py`); ADR-050 §Decision 1 Amendment-Note ergänzt. Trigger #4 aktiv (nicht-manuelle Sources <0.9 Confidence annotiert). Default-off = byte-identisch zum bisherigen Output (Regression-Test).

**Priorität:** P2 (Kohärenz — LLM kann Quelle/Fehleranfälligkeit nicht bewerten)
**Typ:** Core-Implementierung (KBContextEnvelope-Protocol)
**Referenz:** §1.1, §1.3, §4.2.2

**Problem:** Alle 4 Text-Render-Pfade (Format A/B/D/F) haben
`preserved_fields=frozenset()` — kein Provenance-Feld wird in den Prompt-Text
gerendert. `KBContextEntry` trägt `source` (manual/auto_extraction/imported),
`confidence` (0.0-1.0), `review_status` (pending/endorsed/rejected), `freshness`
(fresh/stale/pending) — aber das LLM sieht keine dieser Informationen. Es kann
eine manuell kuratierte Tatsache nicht von einer 0.72-Confidence-Auto-Extraktion
unterscheiden. ADR-050 P1-A macht die Omission *explizit* (kein stiller Verlust),
aber die Information kommt nicht beim Konsumenten (LLM) an.

**Aufgabe:** Erweitere das `KBContextEnvelope`-Protocol um eine
Provenance-Rendering-Option. Bei niedriger Confidence (<0.7), bei
`review_status="pending"`, bei `freshness="stale"`, oder bei `source="auto_extraction"` mit niedriger
Confidence soll die Provenance inline in den Prompt-Text gerendert werden:

```
### Character: Aria Thorne [auto-extracted, confidence: 0.72, pending review]
```

Bei `source="manual"` oder `confidence>=0.9` und `review_status="endorsed"`:
keine Annotation (wie bisher). Dies ermöglicht dem LLM, unsichere Fakten
zurückhaltender zu behandeln.

**Abstimmung:** Architecture-Specialist (RULE-03 Contract-Erweiterung).
**Akzeptanzkriterien:**
- [x] `KBContextEnvelope.render()` hat eine Option für Provenance-Rendering
- [x] Render-Pfade (_helpers, context_wiki, context.py) implementieren die Option
- [x] Niedrige Confidence / pending Status → inline Annotation im Prompt-Text
- [x] Hohe Confidence / endorsed → keine Annotation (wie bisher)
- [x] Stale Freshness → inline Annotation (konsistent mit Voice-Profile-Format C)
- [x] Tests verifizieren Provenance-Rendering bei Schwellwerten

**Exit evidence:**
- Commit `34851f10` (`feat(core): add opt-in provenance annotation to KB context rendering`)
- Implementation: `_render_options.py`, `_provenance_annotation.py`, 4 Render-Pfade, ADR-050 Amendment
- Enforcement: 90+ Unit-Tests (`test_provenance_annotation.py`, `test_provenance_rendering.py`, `test_render_options.py`) — Schwellwert-Tests (0.69/0.70-Source-aware), RULE-22 Accounting, Default-off-Regression. Pyright 0 Errors, volle Unit-Suite 9191 passed.
- Freshness in Rendering-Bedingung integriert (§1.3 ⚠️ geschlossen).

---

### CR-AUFG-04-02 — Storyboard↔KB Inhalts-Konsistenz-Prüfung evaluieren

**Status (2026-07-18):** `accepted_risk` — Architektur-Evaluation hat den Ansatz als **falsche Schicht** abgelehnt: `WritingContextAssembler` ist reine Daten-Transformation (kein Agent); heuristische Erkennung semantischer Widersprüche zwischen Planned-Beats und KB-Entities wäre zu fehleranfällig (False Positives überdecken echten Mehrwert). **Owner:** Architecture Specialist. **Rationale:** Post-hoc CONS-001 Consistency-Check bleibt das gewählte Safety-Net — fängt Cross-Feature-Widersprüche nach Generation ab, ohne die Assembler-Schicht zu überlasten. Optionaler Follow-up: `SyncStatus.DEVIATED` Prompt-Hint (nicht erforderlich, nur bei konkretem UX-Bedarf). **Controls:** CONS-001 existiert und funktioniert. **Review-Datum:** bei konkretem UX-Problem (Stale-KB-Detection-Bedarf) oder nächster quartalsmäßiger Major Review.

**Priorität:** P3 (Erweiterung — Ref-Integrität existiert, Inhalts-Konsistenz fehlt)
**Typ:** Evaluierung / Brainstorming
**Referenz:** §2.4, §4.2.4

**Problem:** Die Sync-Contracts (ADR-050 P1-B) prüfen Ref-Integrität (Rename,
Delete, Deprecate), aber nicht semantische Inhalts-Konsistenz. Beispiel:
Charakter stirbt im Storyboard-Beat → KB-Entry bleibt "alive, active" → bei
Generierung von Kapitel 6+ sieht das LLM den Charakter als lebendig. Es gibt
keine präventive Warnung beim Schreiben, nur nachträgliche Konsistenz-Checks.

**Aufgabe:** Evaluieren, ob eine "Stale-KB-Detection" beim
`WritingContextAssembler` sinnvoll ist: Vergleiche `planned_beats`-Text
(Storyboard) mit injizierten KB-Entities. Wenn ein Beat "X stirbt" enthält aber
der KB-Entity X noch "alive" ist → Warning. Brainstorming mit Orchestrator
(Thinking-Partner-Pattern), da dies komplexe NLP-Mustererkennung erfordert.

**Abstimmung:** Orchestrator (Thinking-Partner). Architecture-Specialist bei
Architektur-Entscheidung.
**Akzeptanzkriterien:**
- [x] Evaluierung dokumentiert: Machbarkeit, Aufwand, Mehrwert
- [ ] Falls Ja: Contract (RULE-03) definiert, dann Implementierung
  - Anmerkung (2026-07-18): Bewusst offen — die Evaluierung entschied "Nein" (falsche Schicht, siehe Status `accepted_risk` oben), daher wurde der "falls Ja"-Zweig nicht ausgelöst und dieses Kriterium bleibt absichtlich unangehakt.

**Exit evidence:**
- Evaluierung dokumentiert (Architektur-Brief, 2026-07-14)
- Empfehlung: DEFER — falsche Schicht für NLP-Detection; CONS-001 post-hoc bleibt Safety-Net
- Optionaler Follow-up (separate Aufgabe bei Bedarf): SyncStatus.DEVIATED als einzeiliger Prompt-Hint

---

### CR-AUFG-04-03 — Frontmatter-Schema-Validierung einführen

**Re-Check 2026-07-14:** **ERLEDIGT 2026-07-14** — `scripts/check_frontmatter_schema.py` Checker implementiert (nutzt shared `parse_frontmatter()`); validiert Required-Fields, unbekannte Felder (Tippfehler-Erkennung), Enum-Werte, Semver. Warning-only + Clean-Baseline-Ratchet (Baseline: 0 — alle 46 `system.md` clean). Gewired in `.pre-commit-config.yaml`, `justfile check-architecture`, `scripts/run_checks.py`.

**Priorität:** P3 (Enforcement — Tippfehler in Frontmatter werden still ignoriert)
**Typ:** Gate/Checker
**Referenz:** §3.1, §3.5

**Problem:** `parse_frontmatter()` (`shared/frontmatter.py:52-77`) ist generisch
— sie parst beliebiges YAML ohne Schema-Validierung. Ein Tippfehler
(`prompt_typ:` statt `prompt_type:`) wird still akzeptiert. `require()` muss
manuell pro Feld aufgerufen werden.

**Aufgabe:** Führe eine Schema-Validierung ein, die bekannte Frontmatter-Felder
(`prompt_type`, `prompt_language`, `prompt_version`) prüft und bei unbekannten
Feldern oder Tippfehlern eine Warning oder CI-Block ausgibt. Kann im
`check_prompt_structure.py`-Checker integriert werden.

**Abstimmung:** Platform-Specialist (CI/Checker).
**Akzeptanzkriterien:**
- [x] Frontmatter-Schema-Validator prüft required Fields und warnt bei unknowns
- [x] Integration in `check_prompt_structure.py` oder eigenständiger Checker
- [x] CI blockt Tippfehler in Frontmatter-Keys

**Exit evidence:**
- Commit `09f1d8e8` (`feat(scripts): add frontmatter schema validation with warning-only ratchet`)
- Implementation: `scripts/check_frontmatter_schema.py` (209 Zeilen), gewired in pre-commit + justfile + run_checks
- Enforcement: Der Checker selbst (warning-only Ratchet, Baseline 0, Wachstum → CI-Fail) + 19 Unit-Tests (`test_check_frontmatter_schema.py`). Structural cause (SSOT in prompt-standards.md war unenforced) → existierender Checker-Mechanismus erweitert.

---

### CR-AUFG-04-04 — Tier-3 Entity-Typ-Klassifikation erweiterbar machen

**Re-Check 2026-07-14:** **ERLEDIGT 2026-07-14** — `ENTITY_TYPE_TO_BUCKET`-Registry + `kb_other`-Catch-All-Bucket in `_tier3_processor.py`; `WritingContext.kb_other` + `to_prompt_variables()`; `SYSTEM_VARS`-Registrierung; 10 Writing-Templates mit `{{kb_other}}`. structlog `tier3_unclassified_entity_type`-Warning. Vollständige Chain gewired (kein Producer-only-Gap).

**Priorität:** P3 (Architektur — neue Entity-Typen werden still ignoriert)
**Typ:** Core-Refactoring
**Referenz:** §3.5

**Problem:** `_tier3_processor.py:89-93` klassifiziert hart 5 Entity-Typen
(character, location, faction, system, timeline). Wenn ein neuer Entity-Typ
hinzugefügt wird (z.B. "object" oder "concept"), wird er still ignoriert — der
Entity verschwindet aus dem Kontext, ohne Warning.

**Aufgabe:** Mach die Entity-Typ-Klassifikation erweiterbar: entweder über eine
Registry der bekannten Typen oder durch ein Catch-All-Bucket für unbekannte
Typen (mit Warning). Mindestens: Log/Metrik wenn ein Entity-Typ nicht
klassifiziert wurde.

**Abstimmung:** Architecture-Specialist (RULE-03 bei neuer Contract-Definition).
**Akzeptanzkriterien:**
- [x] Neue Entity-Typen werden nicht still ignoriert
- [x] Catch-All-Bucket oder Warning für unbekannte Typen
- [x] Log/Metrik für nicht-klassifizierte Entities

**Exit evidence:**
- Commit `ba9fb218` (`feat(core): route unclassified KB entity types to a kb_other bucket instead of dropping them`)
- Implementation: `_tier3_processor.py` (Registry + Catch-All + Truncation-Priority), `writing/models.py`, `prompts/variable_registry.py`, 10 Templates
- Enforcement: 21 Unit-Tests (`test_tier3_other_bucket.py`) + structlog-Warning + Prompt Surface Contract Gate + Empty-KB-Var-Gate (no growth)

---

### CR-AUFG-04-05 — Konsistenz zwischen Voice-Profile-Format und Entity-Format dokumentieren

**Re-Check 2026-07-14:** **ERLEDIGT 2026-07-14** — `docs/development/prompt-standards.md` §KB Context Wire Formats (Intentional Variation): dokumentiert Format C (Voice = Sprachmuster) vs Format A/B (Entity = Fakten), parallele Injection-Begründung, Freshness/Provenance-Konvention.

**Priorität:** Niedrig (Dokumentation — Format-Variation ist intentional)
**Typ:** Dokumentation
**Referenz:** §1.1, §1.3

**Problem:** Voice-Profile (Format C: `**Name**: speech_summary`) und Entity-
Entries (Format A: `### Type: Name\nContent`) verwenden unterschiedliche
Wire-Formate für dieselbe Entität (Charakter). Das LLM erhält
Charakter-Informationen in zwei Formaten parallel. Dies ist intentional (Voice
= Sprachmuster, Entity = Fakten), aber nicht dokumentiert als bewusste Design-
Entscheidung.

**Aufgabe:** Dokumentiere in `prompt-content-standards.md` oder ADR, dass die
Format-Variation zwischen Voice-Profiles und Entity-Entries bewusst ist und
welche Information wo zu finden ist.

**Akzeptanzkriterien:**
- [x] Design-Entscheidung dokumentiert
- [x] Template-Autoren wissen, welches Format welche Information liefert

**Exit evidence:**
- Commit `cc6fa6e4` (`docs(prompts): document intentional voice-profile vs entity wire-format variation`)
- Implementation: `docs/development/prompt-standards.md` neuer Subsection
- Enforcement: Documentation-Drift-Gate green

---

### CR-AUFG-04-06 — Prompt-Level-Warnung bei fehlgeschlagener Tier-3-Entity-Auflösung

**Re-Check 2026-07-14:** **ERLEDIGT 2026-07-14** — `WritingContext.kb_context_warnings` + Population in `context_assembler.py` (join `orphan_reference_warnings`, `⚠️ Context warning:`-Prefix); `SYSTEM_VARS`-Registrierung; 10 Writing-Templates. Detection existierte bereits (`check_orphan_references`); nur Prompt-Surface-Hop fehlte. End-to-End-Test bestätigt Warning erreicht den komponierten Prompt.

**Priorität:** P2 (Kohärenz — dangling Frontmatter-Refs verschwinden still aus dem Kontext)
**Typ:** Core-Implementierung (Context Assembly)
**Referenz:** §2.4, §2.5

**Problem:** Wenn ein in Chapter-Frontmatter referenzierter KB-Entity (`pov_character`,
`characters`, `location`) gelöscht wird, verschwindet er still aus dem Tier-3-Kontext.
Die Backend-Seite erkennt dies bereits — `ChapterFrontmatterRefConsumer` emitiert
`RefIntegrityIssue` mit `deleted_ref_without_tombstone` (verifiziert:
`apps/api/narrare/kb/lifecycle_dispatcher.py`, `tests/unit/api/chapters/test_kb_lifecycle_consumer.py`).
Aber beim Assemblieren des Tier-3-Kontexts (`_tier3_processor.py`) führt ein Lookup-Miss
zu stiller Abwesenheit — es gibt keine Warnung im erzeugten Prompt. Das LLM erfährt nicht,
dass ein erwarteter Kontextbestandteil fehlt.

**Aufgabe:** Wenn Tier-3 Entities anhand referenzierter IDs lädt und eine ID nicht
aufgelöst werden kann, soll eine sichtbare Warnung in den Kontext-Text eingefügt werden
(z. B. `⚠️ Referenced entity not found: pov_character "uuid"`). Damit wird der stille
Kontext-Verlust für das LLM sichtbar.

**Abstimmung:** Core-Specialist (Implementierung). Architecture-Specialist bei Contract-Berührung.
**Akzeptanzkriterien:**
- [x] Tier-3 Lookup-Miss erzeugt eine sichtbare Warnung im Kontext-Text
- [x] Warnung nennt die fehlgeschlagene Referenz (ID und/oder Feld)
- [x] Tests verifizieren Warnung bei gelöschter/fehlender Entity
- [x] Kein stiller Kontext-Verlust mehr bei dangling Frontmatter-Refs

**Exit evidence:**
- Commit `335baf79` (`feat(core): surface dangling KB reference warnings into the writing prompt`)
- Implementation: `writing/models.py`, `writing/context_assembler.py`, `prompts/variable_registry.py`, 10 Templates
- Enforcement: 9 Unit-Tests (`test_context_warnings_cr04_06.py`) inkl. End-to-End (Warning im komponierten `new_chapter`-Prompt verifiziert) + Empty-KB-Var-Gate (no growth)
- Cross-Feature-Integration verifiziert: Commit `138e831f` (`fix(prompts): mark kb_other and kb_context_warnings as optional for writing routes`) — Routes ohne volle KB-Assembly (REWRITE/EXTEND) erhalten leere Defaults statt Crash; Integration-Suite green.

---

### Verweise auf bestehende Aufgaben aus anderen Reviews (Cross-Feature-relevant)

Die folgenden Aufgaben aus cr-01, cr-02, cr-03 sind direkt relevant für
Cross-Feature-Kohärenz und werden hier nicht dupliziert, sondern referenziert:

| Aufgabe | Review | Cross-Feature-Relevanz | Schwere |
|---|---|---|---|
| CR-AUFG-03-01 | cr-03 | Consistency-Check ohne KG-Relationships → Beziehungs-Widersprüche nicht prüfbar (§4.1) | 🔴 Hoch |
| CR-AUFG-03-02 | cr-03 | Coreference ohne Charakter-Liste → funktionaler Adoptions-Fehler (§4.1) | 🔴 Hoch |
| CR-AUFG-03-05 | cr-03 | Preference-Injection-Gate → mem0-Preferences erreichen Writing-Prompts nicht (§4.2.1) | 🟡 Mittel |
| CR-AUFG-01-06 | cr-01 | `{{style_profile}}` fehlt in 4/8 Writing-Prompts → Voice-Checker vs Continue Divergenz (§4.2.3) | 🟡 Mittel |
| CR-AUFG-01-02 | cr-01 | `{{writing_language}}` fehlt in worldbuilding/phase1 → i18n-Lücke (§5.4) | 🟡 Mittel |
| CR-AUFG-02-08 | cr-02 | Injection Defense Duplikat Meta↔Universal → Drift-Risiko (§5.2) | 🟡 Mittel |
| CR-AUFG-02-09 | cr-02 | Writing de/fr Legacy Templates → Phase 5 Deviation (§5.5) | 🟡 Mittel |
| CR-AUFG-03-03 | cr-03 | Analysis-ContextAssembler ohne TokenBudget → 200-Zeichen-Truncation (§4.1) | 🟡 Mittel |
| CR-AUFG-03-08 | cr-03 | Runtime-Gate für leere KB-Variablen-Werte → Template hat Variable, Runtime setzt `=""` (§3.4) | 🟡 Mittel |

---

## Abschluss-Status

**Stand:** 2026-07-14 (Re-Check nach Cross-Feature-Fixes auf Branch `chore/review-04-cross-feature-fixes`)

**Aufgaben-Abschluss:**
- **5 von 5 ursprünglichen Aufgaben** gelöst/evaluiert:
  - CR-AUFG-04-01 — ✅ Resolved (`34851f10`)
  - CR-AUFG-04-02 — ✅ Evaluiert → DEFER (`accepted`, Empfehlung dokumentiert)
  - CR-AUFG-04-03 — ✅ Resolved (`09f1d8e8`)
  - CR-AUFG-04-04 — ✅ Resolved (`ba9fb218`)
  - CR-AUFG-04-05 — ✅ Resolved (`cc6fa6e4`)
- **1 neue Aufgabe aus Gap-Analyse** gelöst:
  - CR-AUFG-04-06 — ✅ Resolved (`335baf79`)

**Zusätzliche Verifizierungen (ohne Code-Änderung gelöst):**
- B2 Backend-Adoption der KB-Lifecycle-Protokolle nachträglich verifiziert (siehe
  §2.5 Re-Check 2026-07-14): `KBLifecycleDispatcher`, `TimelineRefConsumerImpl` /
  `StoryboardRefConsumerImpl`, `CrossFeatureRefIndexImpl` implementiert + Unit-Tests.
  Kein Dokumentations-vs-Implementation-Gap mehr.

**Accepted Risks:**
- B4 Tier-5 Pinned Budget-Bypass (§4.2 Bewertung): bewusstes Design, kein aktuelles
  Fehlverhalten. Reassess falls Pinned-Overflow zu Output-Kürzungen oder
  Modell-Fehlern führt.

**Cross-Feature-Integration-Gap (während Verifikation gefunden & behoben):**
- `kb_other`- und `kb_context_warnings`-Variablen waren anfangs required für alle
  Writing-Routes. Routes ohne volle KB-Assembly (REWRITE/EXTEND) crash-ten.
  Fix: Commit `138e831f` — beide Variablen als optional für Writing-Routes markiert,
  leere Defaults statt Crash. Integration-Suite green.

**Review-Status:** Abgeschlossen. Alle CR-04-Aufgaben resolved/evaluiert. Kein offener
Implementierungs-Schulden mehr in diesem Review.
