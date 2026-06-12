# Content Review CR-01 – Default-Prompts Qualitätsaudit

> **Voraussetzung:** `_audit/results/content-review/cr-00-kontext.md` muss existieren und ausgefüllt sein.
> Sollte `_audit/results/content-review/cr-00-kontext.md` nicht existieren, erstelle sie
> zunächst auf Basis von `_audit/review-prompts/content-review-prompts/cr-00-kontext.md` neu.
>
> **Routing:** Führe diesen Prompt mit `NarrareCoreSpecialist` aus.
>
> **Schritt 0 – Prompt-Dateien lokalisieren (vor dem Review ausführen):**
> Nutze die Code-Review-Graph MCP Tools (z.B. `semantic_search_nodes` mit Keyword "prompt" oder `query_graph` mit `pattern="callers_of"`), um Prompts und deren Abhängigkeiten Token-sparend zu ermitteln, bevor du im Dateisystem suchst. Vermeide `grep` oder `find`.
>
> **Ausgabe:** `_audit/results/content-review/audit-prompts/cr-01-prompt-quality.md`
>
> **Fokus:** Sind die Prompts *inhaltlich effektiv*? Nicht nur: Sind sie syntaktisch korrekt?
> Bedenke: Ein Prompt kann technisch einwandfrei und inhaltlich wertlos sein.
>
> **Governance-Fokus seit CR-01-Remediation:** Prüfe nicht nur einzelne Prompttexte,
> sondern auch, ob der Befund durch bestehende Gates hätte verhindert werden müssen.
> Standards können existieren und trotzdem wirkungslos sein, wenn sie nicht auf
> ausführbare Checks, Manifestvalidierung, Evals oder Review-Checklisten gemappt sind.
>
> **Evidenz-Disziplin:** Verifiziere jeden Befund gegen den aktuellen Code- und
> Promptstand. Markiere alte Befunde ausdrücklich als `stale`, wenn aktuelle Evidenz
> sie nicht mehr stützt. Bewahre Audit-Historie, aber wiederhole keine erledigten
> Findings als aktuelle Risiken.
>
> **Wichtig:** Wenn du einen schwachen oder fehlenden Aspekt identifizierst
> (z.B. fehlende Negative-Beispiele, fehlender Reasoning-/Scratchpad-Mechanismus), schreibe nicht
> nur "fehlt" – sondern liefere direkt einen **konkreten Verbesserungs-Entwurf**
> als Markdown-Codeblock. Diese Entwürfe sind der eigentliche Wert dieses Reviews.

---

## 1. KB-Editor / Interview-Prompts

**Lies:** Alle Prompt-Dateien, die für KB-Interview und KB-Editor genutzt werden.

**Prüfe jeden Prompt auf:**

### 1.1 Klarheit der Aufgabe
- Ist dem Modell klar, *was* es tun soll?
- Gibt es eine explizite Rollenangabe? (z.B. "Du bist ein Literatur-Assistent...")
- Ist das erwartete Output-Format spezifiziert?

### 1.2 Kontextqualität
- Welche Informationen bekommt das Modell als Kontext?
- Fehlen wichtige Informationen, die das Modell für eine gute Antwort bräuchte?
  (Roman-Genre, Schreibstil, Zielgruppe, bisherige Charaktere, …)
- Werden irrelevante Informationen mitgeschickt, die den Kontext unnötig aufblähen?

### 1.3 Prompt-Engineering-Qualität
Bewerte nach diesen Kriterien (jeweils Ja/Nein + kurze Begründung):

| Kriterium | Status | Anmerkung |
|---|---|---|
| Klare Rollenangabe vorhanden | _[FILL]_ | _[FILL]_ |
| Output-Format spezifiziert | _[FILL]_ | _[FILL]_ |
| Negative Beispiele / Don'ts vorhanden | _[FILL]_ | _[FILL]_ |
| Reasoning-/Scratchpad-Mechanismus wo sinnvoll | _[FILL]_ | _[FILL]_ |
| Konsistenz-Anforderungen formuliert | _[FILL]_ | _[FILL]_ |
| Länge/Umfang des Outputs definiert | _[FILL]_ | _[FILL]_ |
| Kultureller/sprachlicher Kontext berücksichtigt | _[FILL]_ | _[FILL]_ |

**Für jedes "Nein" oder "⚠️ Teilweise": Liefere einen konkreten Verbesserungs-Entwurf.**

**Governance-Fragen für jeden Befund:**
- Hätte `check_prompt_structure.py --strict`, `scripts/prompt_governance_checks.py`,
  die ADR-037 Manifestvalidierung, ein Eval oder eine Review-Checkliste diesen Befund
  erkennen müssen?
- Wenn ja: Warum wurde er nicht erkannt? Fehlte die Regel, fehlte Registry-/Manifestdaten,
  war der Check zu eng, oder war die Doku/der Audit-Prompt veraltet?
- Welche Remediation ist nötig: Prompt-Template-Fix, Gate/Test-Erweiterung,
  Manifest-/Registry-Fix, Dokumentationsupdate, oder alle zusammen?

Beispiel-Format:
```markdown
**Fehlendes Negative-Beispiel für KB-Interview-Prompt – Entwurf:**
Do NOT:
- Ask multiple questions at once
- Use generic placeholders like "Character A" instead of the actual name
- Generate content that contradicts existing KB entries
```

_[FILL – Entwürfe für alle schwachen Kriterien]_

### 1.4 Effektivitäts-Einschätzung
Führt dieser Prompt zu konsistenten, hochwertigen KB-Einträgen?
Begründe auf Basis des Prompt-Inhalts – ohne Test-Daten.

**ADR-026-Abgrenzung:** Bewerte, ob der Prompt nur anpassbare Feature-Instruktionen enthält. Garantierte Regeln (Universal Rules, Meta-Persona, Injection Defense) sollen über Capabilities kommen und nicht in jedem Feature-Prompt dupliziert werden.

**Bewertung KB-Prompts:** ⭐⭐⭐⭐⭐ `[FILL]`
**Befunde:** _[FILL]_

---

## 2. Writing-Prompts (Continue, Rewrite, Extend, Suggest)

**Lies:** Alle Writing-Prompt-Dateien.

### 2.1 Continue-Prompt
- Bekommt das Modell genug Kontext über den bisherigen Text und Stil?
- Wird der Schreibstil des Autors berücksichtigt? Woher kommt diese Information?
- Gibt es klare Anweisungen für Länge, Ton, Perspektive?

**Bewertung:** ⭐⭐⭐⭐⭐ `[FILL]`
**Befunde:** _[FILL]_

### 2.2 Rewrite-Prompt
- Ist klar, *was* umgeschrieben werden soll und *warum*?
- Wird der Original-Stil bewahrt oder darf er sich verändern?
- Gibt es Anweisungen für den Umgang mit Charakterstimmen?

**Bewertung:** ⭐⭐⭐⭐⭐ `[FILL]`
**Befunde:** _[FILL]_

### 2.3 Suggest-Prompt (inline in ...)
- Gibt es klare Anweisungen, welche Art von Vorschlägen erwartet werden? (Plot, Charakter, Stil)
- Werden die Vorschläge auf den bestehenden Text und die KB-Informationen abgestimmt?
- Liegen alle anpassbaren Prompt-Instruktionen in `core/prompts/` bzw. in gebündelten
  Promptdateien/PromptComposer-Cascade, statt in Routern oder Services?
- Falls mehrere Suggest-Promptvarianten existieren: Welche ist die kanonische Quelle,
  welche sind Fallback-/Testpfade, und sind nicht-kanonische Pfade dokumentiert oder blockiert?
- Was sollte die konsolidierte Promptquelle enthalten?

**Bewertung:** ⭐⭐⭐⭐⭐ `[FILL]`
**Befunde:** _[FILL]_

---

## 3. Analysis-Prompts (Consistency Check, Voice Check, …)

**Lies:** Alle Prompts für Analyse-Funktionen.

### 3.1 Consistency Check
- Prüft der Prompt die richtigen Aspekte? (Fakten, Zeitlinie, Charakterkonsistenz, …)
- Gibt es klare Anweisungen, wie Inkonsistenzen zu identifizieren und zu benennen sind?
- Ist das Output-Format für den Nutzer verständlich?
- Werden falsch-positive Ergebnisse durch präzise Anweisungen minimiert?

**Bewertung:** ⭐⭐⭐⭐⭐ `[FILL]`
**Befunde:** _[FILL]_

---

## 4. Grundlegende Roman-Informationen als Prompt-Kontext

> **Kernfrage:** Gibt es einen Ort, wo der Nutzer einmalig grundlegende Roman-Informationen
> hinterlegen kann (Schreibstil, Erzählperspektive, Genre, Zielgruppe, Ton), die dann
> *automatisch* für fast alle KI-Anfragen genutzt werden?

**Analyse:**
- Gibt es ein "Writing Profile" oder "Project Settings" für globale Stil-Informationen?
- Wenn ja: Wird es konsistent in alle relevanten Prompts injiziert?
- Wenn nein: Welche Prompts würden davon am stärksten profitieren?

**Empfehlung:** _[FILL – konkrete Umsetzungsidee]_

**Bewertung:** ⭐⭐⭐⭐⭐ `[FILL]`
**Befunde:** _[FILL]_

---

## 5. Mehrstufige Prompt-Strategie

> **Kernfrage:** Macht es für bestimmte Funktionen Sinn, erst eine einfache, günstige
> AI-Anfrage zu stellen (Diskussion, Entwurf), und erst am Ende einen reichhaltigen
> Kontext-Prompt für das finale Ergebnis zu verwenden?
> Oder führt das zu schlechterer Qualität?

**Analysiere für jede Hauptfunktion:**

| Funktion | Aktuell | Mehrstufig sinnvoll? | Erwartete Qualitäts-Auswirkung | Token-Ersparnis |
|---|---|---|---|---|
| KB-Interview | _[FILL]_ | Ja/Nein | _[FILL]_ | _[FILL]_ |
| Continue | _[FILL]_ | Ja/Nein | _[FILL]_ | _[FILL]_ |
| Rewrite | _[FILL]_ | Ja/Nein | _[FILL]_ | _[FILL]_ |
| Consistency Check | _[FILL]_ | Ja/Nein | _[FILL]_ | _[FILL]_ |
| Suggest | _[FILL]_ | Ja/Nein | _[FILL]_ | _[FILL]_ |

**Empfehlung:** _[FILL – generelle Strategie-Empfehlung]_

---

## 6. Prompt Security & Injection Prevention

**Analysiere:**
- Wie wehrhaft sind die Prompts gegen böswilligen User-Input ("Ignore all previous instructions")?
- Werden User-Eingaben (z.B. KB-Texte, Roman-Entwürfe) sicher abgekapselt (z.B. in `<user_input>` XML-Tags)?
- Gibt es eine klare Trennung zwischen System-Anweisungen und User-Daten?
- Was passiert, wenn ein Nutzer schädliche Anweisungen in einen Charakter-Namen schreibt?
- Werden user-content Variablen gegen `variable_registry.USER_CONTENT_VARS` geprüft?
- Nutzen Templates nur die freigegebene Wrapper-Vocabulary
  (`<user_provided_text>`, `<user_provided_data>`, `<user_instructions>`)?
- Ist klar dokumentiert, dass Runtime-Manuskript/User-Content Daten sind und keine
  auszuführenden Instruktionen?
- Wird `{{kb_suggested}}` als generiert, unaccepted, lower-priority und no-override
  gekennzeichnet?
- Verwenden gebündelte System-Prompts `{{writing_language}}` statt des deprecated
  Alias `{{language}}`?

**Bewertung Security:** ⭐⭐⭐⭐⭐ `[FILL]`
**Befunde:** _[FILL]_

---

## Gesamtbewertung Prompt-Qualität

**Bewertung:** ⭐⭐⭐⭐⭐ `[FILL]`
**Vorherige Bewertung:** _[Sterne des letzten Audits eintragen]_ | **Trend:** _[↗️ Besser | ➡️ Gleich | ↘️ Schlechter]_
**Zusammenfassung:** _[FILL – 3–5 Sätze]_

## Governance / Root-Cause / Doc-Drift Addendum

Beantworte nach der inhaltlichen Bewertung:

1. **Root Cause:** Sind Probleme Template-Text-Fehler, Registry-/Manifest-Lücken,
   fehlende Checks, fehlende Evals, oder Dokumentationsdrift?
2. **Checker Coverage:** Für jeden aktuellen Befund: hätte er von bestehenden Checks
   erkannt werden müssen? Wenn ja, warum nicht?
3. **Doc Drift:** Stimmen `docs/development/prompt-standards.md`,
   `docs/development/prompt-content-standards.md` und die `.opencode/context/`-Ableitungen
   mit dem aktuellen Implementierungsmodell überein?
4. **Stale Findings:** Welche früheren Befunde sind durch aktuelle Evidenz erledigt?
5. **Remediation-Aufteilung:** Formuliere Aufgaben getrennt für:
   - Prompt-Templates
   - Gates/Checker/Tests/Evals
   - Manifest/Variable Registry
   - Dokumentation/Audit-Prompts

---

## Aufgaben

<!-- Nummerierung: CR-AUFG-01-01, CR-AUFG-01-02, … -->

Für jede Aufgabe angeben:

```markdown
- **CR-AUFG-01-XX:** [Titel]
  - Typ: prompt-template | gate/check/test/eval | manifest/registry | documentation | mixed
  - Evidenz: [aktuelle Dateien/Zeilen oder stale-Hinweis]
  - Remediation: [konkrete Änderung]
  - Gate-Frage: [hätte ein bestehender Check das fangen müssen? warum/warum nicht?]
```
