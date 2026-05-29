# DISC-001: LLM Wiki — Die Diskussion dahinter

> **Was das ist:** Ein informeller Diskussions-Nachklapp zu ADR-022. Hier steht nicht die Entscheidung (die ist im ADR), sondern der Weg dorthin: Welche Gedanken wurden durchgespielt, welche Sackgassen erkundet, welche Geistesblitze kamen zwischendrin.
>
> **Zielgruppe:** Zukünftige Agents und Entwickler, die verstehen wollen, *warum* wir diesen spezifischen Weg gewählt haben — und warum die naheliegenden Alternativen es nicht geworden sind.
>
> **Datum:** 2026-05-29
> **Sprache:** Deutsch (die Diskussion war auf Deutsch)
> **Format:** Freie Erzählung

---

## Die Ausgangsfrage

> *„Würde es Sinn machen, den KB Bereich um ein LLM Wiki zu ergänzen?"*

So fing es an. Eine vage Idee, ein Buzzword fast — "LLM Wiki". Der Hype darum war gerade überall präsent. Claude AI hatte sein "Projects"-Wiki, Gemini AI arbeitete an etwas Comparablem. Die Idee: Ein Wiki, das nicht von Menschen befüllt wird, sondern von der AI selbst — automatisch generiert aus den Rohdaten, die ohnehin im System liegen.

Aber war das wirklich etwas, das Narrare brauchte? Oder war das einfach nur ein "shiny object"?

Die Antwort lag nicht auf der Hand. Also fingen wir an, systematisch hinzuschauen.

---

## Phase 1: Bestandsaufnahme — Was haben wir eigentlich schon?

Bevor wir über ein neues Feature nachdenken, wollten wir wissen: Was macht das bestehende Knowledge-Base-(KB)-System eigentlich schon?

Der Blick auf die Feature-Liste war ernüchternd — im positiven Sinne. Das KB-System ist bereits gewaltig:

- **KB-001 bis KB-008**: Acht Entity-Typen — Charaktere, Orte, Gegenstände, Ereignisse, Fraktionen, Konzepte, Timeline-Einträge, Notizen
- **KB-Templates (KB-003)**: Strukturierte Vorlagen pro Entity-Typ
- **Relationships (KB-004)**: Semantische Beziehungen zwischen Entitäten
- **AI-Assisted Creation (KB-005)**: KI-gestützte Entity-Erstellung
- **Worldbuilding (KB-006)**: Automatische Welt-Vorschläge
- **Extraction (KB-007)**: Entity-Extraktion aus Text
- **Consistency Checker (CONS-001)**: Logik-Prüfung über Entity-Grenzen hinweg
- **Knowledge Graph (KB-008)**: Visuelle Graph-Visualisierung (geplant)

Dazu kommt **INFRA-004** (Text-/Embedding-Suche), die bereits semantische Suche über alle Entities ermöglicht.

**Die ehrliche Erkenntnis nach dieser Bestandsaufnahme:** Das KB-System hat wenig *Lücken*. Es fehlt kaum etwas Funktionelles. Die Frage war also nicht "Was fehlt?", sondern: "Nutzen wir das, was wir haben, optimal?"

---

## Phase 2: Konzept-Schärfung — Vom UI-Feature zur systemischen Optimierung

Der zweite Schritt war: Was meinen wir eigentlich mit "LLM Wiki"?

Die Diskussion um LLM Wikis im Allgemeinen dreht sich um ein Kernversprechen: **LLMs sollen schneller relevante Daten finden können.** Ein Wiki, das von der AI selbst kuratiert wird, liefert kurze, prägnante Zusammenfassungen statt roher Datenberge.

Aber hier kam der entscheidende Perspektivwechsel:

User (sinngemäß): *"Es geht doch gar nicht um ein weiteres UI-Feature. Es geht darum, dass das LLM beim Schreiben besseren Kontext bekommt. Das ist eine Context-Optimierung, kein UI-Feature."*

**Das war der Durchbruch.** Wir hatten die ganze Zeit gedacht: "Bauen wir ein Wiki für Autoren?" Aber die eigentliche Frage war: "Bauen wir einen Precomputed Context Layer für das LLM?"

Der Unterschied ist fundamental:
- Ein **UI-Feature** muss schön aussehen, Suchfunktion haben, verlinkt sein
- Ein **Context Layer** muss schnell sein, deterministisch, token-effizient — und das UI ist ein willkommener Nebeneffekt

### Der ChapterSummary-Clou

Und dann fiel der Groschen, der alles veränderte:

> **Die ChapterSummaries (WRITE-012) existieren bereits.**

Sie werden vom `ChapterSummaryAgent` generiert — reduzieren 1500+ Tokens Kapiteltext auf ~80 Tokens prägnante Zusammenfassung. Aber sie werden *nirgends* für den Writing-Context genutzt. Sie werden nur für den Storyboard-Sync verwendet, eine relativ randständige Funktion.

Das war der Moment, in dem aus einer "vielleicht netten Idee" ein "das müssen wir bauen" wurde. Wir hatten die halbe Lösung bereits im System — und nutzten sie nicht. **RULE-20** (keine Half-Implementations) traf uns hier direkt: Das ChapterSummary war eine Half-Implementation, weil sein primärer Use-Case (Writing-Context-Optimierung) nie realisiert wurde.

---

## Phase 3: Design-Entscheidungen — Die vier großen Fragen

Nachdem klar war, *was* wir bauen wollen, ging es an die konkrete Ausgestaltung. Vier Entscheidungen wurden gemeinsam erarbeitet:

### 1. Sichtbarkeit — Nur Context oder auch UI?

Die naive erste Idee: "Das ist nur ein interner Layer, der Autor merkt nichts davon."

Der User argumentierte dagegen — und zwar überzeugend:

> *"Der Autor sieht, wie die AI seine Welt versteht. Wenn die WikiSummary einen Charakter falsch beschreibt, merkt der Autor: 'Ah, die Daten sind unvollständig.' Das ist Feedback. Das ist Kontrolle."*

**Entscheidung: Beides.** Interner Context-Layer *und* Wiki-UI für Autoren. Die WikiSummaries sind der primäre Zweck — aber die Einsicht in diese Summaries ist ein Feature eigener Klasse.

### 2. Granularität — Wie tief gehen wir?

Je detaillierter die Summaries, desto besser der Context — aber desto teurer die Generierung und desto größer der Speicher.

Der Konsens: **So viel wie sinnvoll, nicht so viel wie möglich.**

- Entity-Summaries (~40 Tokens): Kurze narrative Beschreibung jeder KB-Entity
- Chapter-Summaries (~60 Tokens): Erweiterte Kapitel-Zusammenfassung (baut auf WRITE-012 auf)
- Relationship-Summaries: Kurzer Kontext zu jeder Beziehung
- Character-Arcs: Entwicklungspfad eines Charakters über mehrere Kapitel (später)

Der Trick: Inkrenmentelle Einführung. Entity-Summaries zuerst, Chapter-Summaries als Erweiterung, Character-Arcs und Plot-Summaries später.

### 3. Refresh-Strategie — Wann wird neu generiert?

Drei Optionen standen im Raum:

- **Periodisch** (alle N Stunden): Einfach, aber teuer — viele unveränderte Entities werden neu generiert
- **On-Change** (bei Entity-Änderung): Präzise, aber Trigger müssen sauber sein
- **On-Demand** (beim Write-Call): Lazy — aber dann hat der Write-Call die Latenz

Der User wies zu Recht auf die Token-Kosten hin:

> *"Wenn wir periodisch alle 6 Stunden alles neu generieren, sind das hunderte LLM-Calls pro Tag für Daten, die sich vielleicht gar nicht geändert haben."*

**Entscheidung: On-Change + On-Demand.** Bei Entity-Änderung wird sofort neu generiert (Background-Task, kein Blocking). Zusätzlich kann der Autor manuell refreshen. Kein periodischer Refresh.

### 4. Prompt-Responsivität — Der wichtigste Punkt

Der letzte Design-Punkt kam vom User und war der vielleicht wichtigste:

> *"Was passiert, wenn der Autor den Wiki-Generation-Prompt ändert? Wenn er sagt: 'Beschreibe Charaktere emotionaler' — dann müssen doch alle Charakter-Summaries neu?"*

Ja. Absolut.

Aber das ist **kein Cache**. Ein Cache wird durch Zeit oder Content-Änderung invalid. Hier wird die Invalidierung durch eine *Prompt-Änderung* ausgelöst — eine vollkommen andere Kategorie.

**Entscheidung: Prompt-Version-Tracking.** Jeder Wiki-Generation-Prompt hat eine Version (semantisch: `1.2.3`). Jedes WikiSummary speichert, mit welcher Prompt-Version es generiert wurde. Bei Prompt-Änderung:

1. `wiki.prompt.changed`-Event wird gepublisht
2. Alle abhängigen Summaries werden `stale`
3. Beim nächsten Zugriff: Lazy Refresh im Background
4. Fallback: Rohdaten, während der Refresh läuft

Der User prägte den Begriff: **"Prompt-sensitiver Materialized View."** Nicht einfach nur Cache — ein View, der von seiner Query-Definition (dem Prompt) abhängt.

---

## Phase 4: Architektur — Die technische Tiefe

Nach den Design-Entscheidungen wurde es technisch. Der User fragte:

> *"Wie wird aktuell der Prompt für ein neues Kapitel zusammengesetzt?"*

Das war der Moment, die gesamte Pipeline von Anfang bis Ende durchzugehen.

### Die aktuelle Pipeline

1. **WritingContextAssembler** (`core/writing/context_assembler.py`): Lädt Rohdaten (Entities, Chapters) und formatiert sie 1:1 — keine Vorverarbeitung, keine Optimierung. **RULE-02**-konform, aber roh.

2. **PromptComposer** (`core/prompts/composer.py`): Nimmt die formatierten Daten und substituiert sie in Prompt-Templates: `{{kb_characters}}`, `{{recent_chapters}}`, etc.

3. **Prompt-Templates** (`core/prompts/_bundled/writing/en/new_chapter/system.md`): Definiere, was genau im Kontext landet und wie es strukturiert ist.

Die Pipeline ist sauber — aber ineffizient. Stell dir vor, du schickst einem Autor die gesamte Rohfassung eines Buches, jedes Mal wenn er ein neues Kapitel schreibt. Das ist im Kern, was hier passiert.

### Wo die WikiSummaries andocken

Wir analysierten das 5-Tier-Modell des WritingContextAssemblers:

| Tier | Inhalt | Bisher | Mit Wiki |
|------|--------|--------|----------|
| 1 | Immediate (aktuelle Session) | Rohdaten | Rohdaten (unverändert) |
| 2 | Recent Chapters | Rohdaten (~1500 Tokens/Kapitel) | WikiChapterSummary (~60 Tokens) |
| 3 | KB Referenced | Entity-Rohdaten (~200 Tokens/Entity) | WikiSummary (~40 Tokens) |
| 4 | KB Suggested | Embedding-Suche (~300ms) | Entfällt — Wiki hat alle relevanten Entities |
| 5 | User Notes | Rohdaten | Rohdaten (unverändert) |

**Der Clou:** Tier 4 (Embedding-Suche) wird komplett überflüssig. Statt bei jedem Write-Call eine Vektor-Suche zu fahren, werden die relevanten Entities bereits beim Schreiben des vorherigen Kapitels identifiziert und ihre Summaries vorberechnet. Der Write-Call macht nur noch einen Key-Lookup.

Das bedeutet:
- **Token-Reduktion**: ~85% weniger Tokens für Entity-Kontext (200 → 40 Tokens/Entity)
- **Latenz**: Embedding-Suche (300ms) vom kritischen Pfad entfernt
- **Determinismus**: Gleicher Input → gleicher Wiki-Context → gleicher Write-Output

### Prompt-Abhängigkeitsmodell — das Herzstück

Die technisch interessanteste Frage war: Wie stellen wir sicher, dass WikiSummaries immer mit dem aktuellen Prompt generiert werden?

```
Wiki Generation Prompt (wiki/en/entity_summary/system.md)
    ↓ prompt_version: "1.2.3"
    ↓
WikiSummary.depends_on.wiki_prompt_version == "1.2.3"
    ↓ Bei Änderung ≠ current
WikiSummary.status = stale
    ↓ Beim nächsten Write-Call
Lazy Refresh im Background (Fallback auf Rohdaten bis fertig)
```

Die Versionierung ist semantisch:
- **Patch** (1.2.3 → 1.2.4): Typo-Fix → kein Refresh zwingend
- **Minor** (1.2.3 → 1.3.0): Prompt-Verbesserung → alle Summaries stale
- **Major** (1.0.0 → 2.0.0): Breaking Change → alle Summaries stale + force refresh

---

## Phase 5: Alternativen — Was wir verworfen haben

Nicht jeder Weg, den wir diskutiert haben, wurde auch gegangen. Zwei Alternativen wurden intensiv beleuchtet und dann verworfen:

### Option B: Live-Context-Assembly optimieren

Die Idee: Statt eines neuen Systems könnten wir einfach den bestehenden WritingContextAssembler optimieren. Embedding-Search schneller machen (bessere Indizes, Caching). Rohdaten komprimieren (kürzere Template-Formate).

**Warum wir es verworfen haben:**

- Es optimiert das falsche Problem. Die Latenz der Embedding-Suche (~300ms) ist ärgerlich, aber das eigentliche Problem sind die ~6000 Tokens Rohdaten pro Write-Call. Token-Kosten skalieren mit Nutzung, nicht mit Optimierung.
- Die ChapterSummary (WRITE-012) bleibt ungenutzt. Das wäre eine RULE-20-Verletzung: etwas bauen, aber nicht für seinen eigentlichen Zweck nutzen.
- Kein UI-Gewinn. Der Autor bekommt keine Einsicht in das, was die AI "denkt".
- Kein Determinismus. Embedding-Suche bleibt auf dem kritischen Pfad.

**Fazit:** Eine Optimierung des bestehenden Systems wäre ein Schritt in die richtige Richtung, aber nicht der große Wurf.

### Option C: KB-008 Knowledge Graph erweitern

Die Idee: KB-008 (der geplante Knowledge Graph) bekommt narrative Beschreibungen für jeden Knoten. Eine Graph-DB (Neo4j) dient als primärer Context-Layer.

**Warum wir es verworfen haben:**

- KB-008 ist selbst noch "planned" — auf ein nicht implementiertes Feature aufzusetzen ist hochriskant. Wieder RULE-20: Man baut nicht auf halben Sachen auf.
- Eine Graph-DB (Neo4j) wäre eine neue Infrastruktur-Dependency. Das bedeutet ADR, Evaluierung, Betriebskosten — für ein Feature, das noch nicht mal spezifiziert ist.
- Embedding-Suche in einem Graph ist komplexer als einfacher Key-Lookup. Der Graph ist gut für Traversierung, schlecht für semantische Suche.
- KB-008 ist primär ein *Visualisierungs*-Feature. Es hat keinen Service-Layer für Context-Lookup. Der Umbau wäre aufwändiger als ein neues Modul.

**Fazit:** KB-008 als Fundament zu nehmen wäre ein Architektur-Fehler gewesen. Das Wiki steht orthogonal zum Graph — der Graph visualisiert Beziehungen, das Wiki liefert Kontext.

---

## Das Ergebnis

Nach alledem stand:

- **ADR-022**: LLM Wiki als Precomputed Context Layer ✅ (Proposed)
- **WIKI-001**: Feature Spec ✅ (Planned)
- **Ein neues Modul**: `core/wiki/` mit Service, Agent, Repository, Contracts
- **Token-Reduktion**: ~85% für Entity-Context
- **Latenz**: Embedding-Suche vom kritischen Pfad entfernt
- **Determinismus**: Key-Lookup statt Vektor-Suche
- **Prompt-Responsivität**: Prompt-Version-Tracking + Stale-Mechanismus
- **Nebenprodukt**: Wiki-UI für Autoren (Einsicht in Context-Qualität)

### Die zentralen Erkenntnisse dieser Diskussion

1. **Das naheliegende Feature war nicht das richtige.** "LLM Wiki" klingt nach UI, aber der wahre Wert liegt im Context Layer.
2. **Das halbe System war schon da.** ChapterSummary (WRITE-012) wartete bereits darauf, für seinen eigentlichen Zweck genutzt zu werden.
3. **Die wichtigste Frage kam vom User.** Prompt-Responsivität war nicht auf dem Radar — und ist jetzt einer der Kernmechanismen.
4. **Inkrementelle Einführung ist der Schlüssel.** Wir starten klein (Entities + Chapters) und erweitern später (Arcs, Plots, Locations).
5. **Graceful Degradation ist nicht verhandelbar.** Das Wiki ist ein Optimierungs-Layer. Kein Write-Call wird jemals blockiert, weil ein WikiSummary stale ist.

---

## Reflexion — Was diese Diskussion über unsere Arbeitsweise sagt

Rückblickend war diese Diskussion ein gutes Beispiel dafür, wie wir bei Narrare arbeiten wollen:

- **Problem zuerst, Lösung später.** Wir haben nicht mit "Bauen wir ein LLM Wiki" angefangen, sondern mit "Was ist eigentlich das Problem?"
- **Das System verstehen, bevor man es erweitert.** Die Bestandsaufnahme des KB-Systems war frustrierend (es ist riesig!) — aber sie hat die ChapterSummary-Lücke erst sichtbar gemacht.
- **Der User bringt die entscheidenden Perspektiven.** Der Prompt-Responsivität-Mechanismus kam nicht aus der Architektur-Überlegung, sondern aus der Frage: "Was macht der Autor damit?"
- **Alternativen ernsthaft prüfen, nicht nur pro forma.** Option B und C wurden nicht nur genannt, sondern technisch durchdacht und aus guten Gründen verworfen.

---

## Anhänge

- **ADR-022**: Die formale Entscheidung — `docs/architecture/decisions/ADR-022-llm-wiki.md`
- **WIKI-001**: Die Feature-Spec — `docs/features/WIKI-001-llm-wiki.md`
- **WRITE-012**: Die bestehende ChapterSummary — `docs/features/WRITE-012-chapter-summary.md`
- **KB-008**: Der geplante Knowledge Graph — `docs/features/KB-008-knowledge-graph.md`
