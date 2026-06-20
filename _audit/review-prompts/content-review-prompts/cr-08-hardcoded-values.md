# Content Review CR-08 – Hardcodierte Werte & Konfigurierbarkeit

> **Voraussetzung:** `_audit/results/content-review/cr-00-kontext.md` muss existieren und ausgefüllt sein.
> Sollte `_audit/results/content-review/cr-00-kontext.md` nicht existieren, erstelle sie
> zunächst auf Basis von `_audit/review-prompts/content-review-prompts/cr-00-kontext.md` neu.
>
> **Ausgabe:** `_audit/results/content-review/cr-08-hardcoded-values.md`
>
> **Rhythmus:** Quartalsweise (Major Review) + bei jeder neuen Modell-Generation
>
> **Fokus:** Welche Werte sind im Code fest verdrahtet, obwohl sie sich ändern
> (Modell-Releases, Nutzerbedürfnisse, Projektgröße) oder vom Nutzer/Operator
> sinnvollerweise angepasst werden sollten?
>
> **Methodik:** Durchsuche den gesamten Code systematisch nach Konstanten,
> Magic Numbers und fest verdrahteten Strings. Bewerte jeden Fund nach:
> - Änderungswahrscheinlichkeit (hoch/mittel/niedrig)
> - Wer sollte es ändern können? (Entwickler / Operator / Nutzer)
> - Schaden bei falschem Wert (kritisch / spürbar / kosmetisch)
>
> Nutze zuerst die Code-Review-Graph MCP Tools (`semantic_search_nodes`, `query_graph`,
> `traverse_graph`) für TokenBudget, ModelRegistry, Settings, Router Factories,
> Streaming und Provider-Konfiguration. Nutze `Grep` nur gezielt als Fallback für
> reine Literal-Suchen, wenn der Graph die Kandidaten nicht vollständig erfasst.
>
> **CR-AUFG-08-14 Strukturpflicht:** Jeder materielle P0/P1-Befund zur Kategorie
> Konfiguration↔Runtime-Effekt MUSS maschinenlesbar markiert werden:
> `[P0|P1] [category: configuration-effect] FIND-... / CR-AUFG-...`.
> Für jeden solchen Wert muss im selben Review/PR eine Klassifikation in
> `docs/architecture/governance/configuration-adoption-matrix.yaml` existieren
> oder ergänzt werden. Unklassifizierte strukturierte P0/P1-Befunde blockieren
> `scripts/check_configuration_matrix.py`.

---

## 1. Token- und Kontext-Limits

> Referenz: FIND-005, FIND-006 — dieser Abschnitt prüft den aktuellen Stand
> und ob Fixes umgesetzt wurden.

**Suche nach:** Alle numerischen Konstanten und Dateien, die Token-Zahlen direkt im Code definieren (nicht importieren). Beginne mit Code-Graph-Suchen nach `TokenBudget`, `max_tokens`, `budget`, `reserve`, `model_limits`, `ContextAssembler` und `PromptContext`. Nutze gezielte Literal-Suche nur als Fallback.

### 1.1 Gefundene Token-Konstanten

| Konstante | Wert | Datei:Zeile | Feature-Scope | Konfigurierbar? | Sinnvoll kalibriert? |
|---|---|---|---|---|---|
| _[FILL]_ | _[FILL]_ | _[FILL]_ | Global/Feature | Ja/Nein | Ja/Nein/Unklar |

### 1.2 Feature-Output-Limits: Aufgaben-Check

Für jede Funktion mit Output-Limit: Kann das Modell die Aufgabe mit diesem Limit
vollständig erfüllen? Orientierung: ~700 Wörter ≈ 1.000 Tokens.

| Funktion | Limit (Tokens) | Max sinnvoller Output | Ausreichend? | Handlungsbedarf |
|---|---|---|---|---|
| _[FILL]_ | _[FILL]_ | _[FILL]_ | Ja/Nein/Knapp | _[FILL]_ |

### 1.3 Quartals-Modell-Abgleich

Sind die definierten Output-Limits noch zeitgemäß angesichts aktuell verfügbarer Modelle?

| Modell | Max Output (aktuell) | Im Code bekannt? | Ungenutzes Potenzial |
|---|---|---|---|
| _[FILL – alle Modelle aus settings/config]_ | _[FILL]_ | Ja/Nein | _[FILL Tokens]_ |

**Neue Modelle seit letztem Review (manuell ergänzen):** _[FILL]_

**Bewertung:** ⭐⭐⭐⭐⭐ `[FILL]`
**Befunde:** _[FILL]_

---

## 2. Modell-Konfiguration

**Suche nach:** Hardcodierten Modell-Namen, Modell-IDs, Provider-Strings. Beginne mit Code-Graph-Suchen nach `ModelRegistry`, `provider`, `model_id`, `DEFAULT_LLM_MODEL`, `anthropic`, `openai`, `ollama`, `gemini`, `mistral`, `llama`. Prüfe besonders Router, Dependency Factories und Settings-Resolver (RULE-18).

### 2.1 Hardcodierte Modell-Referenzen

| Fundstelle | Modell-String | Zweck | Sollte konfigurierbar sein? |
|---|---|---|---|
| _[FILL]_ | _[FILL]_ | _[FILL]_ | Ja/Nein/Bereits |

### 2.2 Default-Modelle pro Feature

Sind die Default-Modelle pro Feature sinnvoll gewählt?
(Teures Modell für einfache Aufgaben = unnötige Kosten; günstiges Modell für
komplexe Aufgaben = schlechtere Qualität)

| Feature | Default-Modell | Aufgaben-Komplexität | Modell passt? | Bessere Alternative? |
|---|---|---|---|---|
| Suggest | _[FILL]_ | Niedrig | _[FILL]_ | _[FILL]_ |
| Continue | _[FILL]_ | Mittel | _[FILL]_ | _[FILL]_ |
| Extend (Kapitel) | _[FILL]_ | Hoch | _[FILL]_ | _[FILL]_ |
| KB-Interview | _[FILL]_ | Mittel | _[FILL]_ | _[FILL]_ |
| Consistency Check | _[FILL]_ | Hoch | _[FILL]_ | _[FILL]_ |
| Freier Assistent | _[FILL]_ | Variabel | _[FILL]_ | _[FILL]_ |

**Bewertung:** ⭐⭐⭐⭐⭐ `[FILL]`
**Befunde:** _[FILL]_

---

## 3. Weitere Magic Numbers & Strings

**Suche nach weiteren hardcodierten Werten, die sich ändern können:** `max_entries`, `max_results`, `max_tokens`, `timeout`, `retry`, `backoff`, `batch_size`, `limit`, `threshold`, Feature Flags und Provider-Defaults. Beginne mit Code-Graph-Suchen und nutze gezielte Literal-Suche nur als Fallback.

### 3.1 Gefundene Kandidaten

> **Eskalationsregel:** Jeder hardcodierte Wert mit Änderungsrisiko "Hoch" und
> "Konfigurierbar machen: Ja" wird automatisch als FIND angelegt, falls noch keines
> existiert. Trage die FIND-Nummer in die letzte Spalte ein oder erstelle die Datei.
> Wenn der Wert P0/P1 und `configuration-effect` ist, nutze zusätzlich exakt den
> Strukturmarker `[P0|P1] [category: configuration-effect] FIND-... / CR-AUFG-...`
> und klassifiziere den Wert in der Configuration Adoption Matrix.

| Konstante/Wert | Datei:Zeile | Beschreibung | Änderungsrisiko | Konfigurierbar machen? | FIND |
|---|---|---|---|---|---|
| `max_entries=20` (Suggest) | router.py:80 | KB-Einträge im Suggest | Hoch | ✅ Budget-basiert | FIND-005 |
| _[FILL – weitere Funde]_ | _[FILL]_ | _[FILL]_ | Hoch/Mittel/Niedrig | Ja/Nein/Bereits | _[FILL]_ |

### 3.2 Timeouts & Retry-Logik

| Wert | Aktuell | Sinnvoll? | Konfigurierbar? |
|---|---|---|---|
| API-Request-Timeout | _[FILL]_ | _[FILL]_ | Ja/Nein |
| Retry-Anzahl | _[FILL]_ | _[FILL]_ | Ja/Nein |
| Retry-Backoff | _[FILL]_ | _[FILL]_ | Ja/Nein |
| Streaming-Timeout | _[FILL]_ | _[FILL]_ | Ja/Nein |

### 3.3 Feature-Flags & Kill-Switches

Gibt es Features, die per Flag ein-/ausgeschaltet werden können?
Sind sie konfigurierbar oder hardcodiert?

| Feature | Aktuell aktiv? | Flag vorhanden? | Konfigurierbar? |
|---|---|---|---|
| _[FILL]_ | Ja/Nein | Ja/Nein | Ja/Nein |

**Bewertung:** ⭐⭐⭐⭐⭐ `[FILL]`
**Befunde:** _[FILL]_

---

## 4. Konfigurierbarkeits-Matrix

> Zusammenfassung: Was sollte auf welcher Ebene konfigurierbar sein?

| Wert | Aktuell | Sollte konfigurierbar sein für | Priorität |
|---|---|---|---|
| Output-Token-Limit pro Feature | Hardcodiert | Nutzer (einfach) + Operator (Rohwert) | 🔴 Hoch |
| Default-Modell pro Feature | _[FILL]_ | Nutzer | _[FILL]_ |
| max_entries KB-Suggest | Hardcodiert (20) | Nutzer / Auto (Budget-basiert) | 🔴 Hoch |
| API-Timeout | _[FILL]_ | Operator | _[FILL]_ |
| _[FILL weitere Funde]_ | _[FILL]_ | _[FILL]_ | _[FILL]_ |

---

## 5. Empfehlung: Konfigurationsschichten

Nicht alles muss in die WebUI – aber alles sollte *irgendwo* ohne Code-Änderung
anpassbar sein. Empfohlene Schichten:

| Schicht | Zielgruppe | Ort | Beispiele |
|---|---|---|---|
| **Nutzer-UI** | Endnutzer | WebUI Einstellungen | Output-Länge (kurz/mittel/lang), Default-Modell |
| **Projekt-Config** | Power-User | `project.json` / `.narrare/config` | Feature-spezifische Modelle, KB-Budget |
| **Operator-Config** | Self-Hoster | `settings.json` / Env-Vars | Token-Rohwerte, Timeouts, API-Keys |
| **Code-Defaults** | Entwickler | `model_limits.py` | Fallback-Werte wenn nichts konfiguriert |

---

## Gesamtbewertung Konfigurierbarkeit

**Bewertung:** ⭐⭐⭐⭐⭐ `[FILL]`
**Zusammenfassung:** _[FILL – 3–5 Sätze]_

---

## Aufgaben

<!-- Nummerierung: CR-AUFG-08-01, CR-AUFG-08-02, … -->

Für materielle Konfigurations-/Effekt-Aufgaben mit P0/P1-Priorität gilt das
maschinenlesbare Format:

```markdown
- [P1] [category: configuration-effect] FIND-099 / CR-AUFG-08-99: Kurzer Titel —
  warum der konfigurierte Wert am Runtime-Effekt vorbeiläuft oder unklassifiziert ist.
```

Pflichtfelder:
- Priorität: `[P0]` oder `[P1]`
- Kategorie: `[category: configuration-effect]`
- Stabiler Lifecycle-Verweis: `FIND-...` oder `CR-AUFG-...`
- Matrix-Klassifikation: `setting_id`, `classification`, `lifecycle`,
  `runtime_consumer`/`enforcement_evidence` oder expliziter `formal_finding`-Status
  in `docs/architecture/governance/configuration-adoption-matrix.yaml`

_[FILL]_
