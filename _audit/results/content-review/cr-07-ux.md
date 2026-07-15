# Content Review CR-07 – UI/UX & AI-Interaktionsqualität

> **Voraussetzung:** `_audit/results/content-review/cr-00-kontext.md` muss existieren und ausgefüllt sein.
> Sollte `_audit/results/content-review/cr-00-kontext.md` nicht existieren, erstelle sie
> zunächst auf Basis von `_audit/review-prompts/content-review-prompts/cr-00-kontext.md` neu.
>
> **Schritt 1 – Frontend-Code lokalisieren (vor dem Review ausführen):**
> Nutze zuerst die Code-Review-Graph MCP Tools:
> - `semantic_search_nodes` für `AI`, `streaming`, `connectSSE`, `suggest`, `continue`, `rewrite`, `extend`, `interview`, `loading`, `AbortController`
> - `query_graph` mit `imports_of`/`importers_of` für `connectSSE`, API-Clients, AI-Komponenten und Stores
> - `traverse_graph` für die wichtigsten AI-UI-Flows
>
> Nutze `Glob`/`Grep` nur gezielt als Fallback, wenn der Graph einzelne TSX/JSX-Dateien nicht erfasst.
>
> **Lies dann:**
> - Alle gefundenen AI-relevanten React-Komponenten
> - `docs/development/ui-principles.md`, insbesondere §16 AI-Interaction Standards
> - Relevante API-/Streaming-Clients und Stores, die aus dem Graph hervorgehen
>
> **Ausgabe:** `_audit/results/content-review/cr-07-ux.md`
>
> **Methodik:** Da du die WebUI nicht live bedienen kannst, leitest du UX-Qualität
> aus dem Code ab. Das ist möglich und ausreichend – aber nur wenn du den
> Frontend-Code tatsächlich gelesen hast. Führe die Code-Graph-Abfragen oben aus,
> bevor du irgendeine Tabelle ausfüllst. Ein "Unklar" oder "Vermutlich" ist
> **kein akzeptables Ergebnis** – wenn du es nicht im Code findest, schreibe
> explizit: "Nicht implementiert" oder "Komponente nicht gefunden unter [Pfad]".
>
> Konkret statt vage: Nicht "Loading-Indikator vermutlich vorhanden" –
> sondern "Spinner in `WritingPanel.tsx:142` via `isLoading`-State" oder
> "Kein Loading-State in Suggest-Komponente gefunden".

---

> **Review-Methode:** `code-review-graph` MCP (Semantic Search lieferte 0 TSX/JS-Knoten —
> der Graph ist Python-only, 27.390 Knoten decken das Backend ab, nicht das Frontend).
> Fallback auf Glob/Grep/Read für TSX/TS. Alle 8 Abschnitte sind gegen **gelesenen
> Code** verifiziert, nicht aus Annahmen. Zentrale Quellen:
> - `packages/web/lib/hooks/use-ai-operation.ts` (+ 3 Sub-Module) — AI-Lifecycle-State-Machine
> - `packages/web/lib/api/streaming.ts` — `connectSSE` SSE-Transport
> - `packages/web/lib/api/ai-error-mapping.ts` — `mapSSEError` Fehler-Mapping
> - `scripts/checks/ai_operation_inventory.yaml` — 17 AI-Operationen, maschinengeprüft
> - `docs/development/ui-principles.md` §16 — AI-Interaction Standards (11 Gates)
> - `docs/architecture/governance/ai-ux-compliance-v2.md` — Governance-Vertrag

---

## 1. AI-Wartezeiten & Feedback

> KI-Anfragen dauern typischerweise 2–30 Sekunden. Was sieht der Nutzer in dieser Zeit?

**Analysiere für jede AI-Funktion:**

| Funktion | Loading-Indikator vorhanden? | Art des Indikators | Streaming? | Abbruch möglich? |
|---|---|---|---|---|
| Writing-Continue | Ja | `Loader2`-Spinner + "Stoppen"-Label im Button (`ContinueButton.tsx:62-64`, wechselt zu `t("aiActions.stop")`); AI-generierter Text wird mit `.ai-generated-pending`-Highlight inline markiert (`editor.css:177`); `isLoading`/`isStreaming` via `useContinueStream.ts:52` | Ja (SSE via `streamExtend` → `connectSSE`, `useContinueStream.ts:72-117`, Token-für-Token `onChunk` mit `insertAIContent`/`appendToPendingMark`) | Ja (`handleStop` → `cancel()` in `useContinueStream.ts:138-140`, Button zeigt "Stoppen" während Streaming) |
| Rewrite | Ja | `Loader2`-Spinner + `t("aiActions.generating")` ("Generiere...") im Modal (`RewriteSuggestionModal.tsx:107-112`); `isRewriteStreaming` via `useRewriteFlow.ts:137-138` | Ja (SSE via `streamRewrite` → `connectSSE`, `useRewriteOperation` sub-hook; Alternativen streamen in Suggestion-Cards) | Ja (`handleRewriteCancel` → `rewriteAiOp.cancel()` + `handleVariantCancel` in `useRewriteFlow.ts:143`; Escape während Streaming im Modal `RewriteSuggestionModal.tsx:60-63`) |
| Suggest (Ghost-Text) | Ja | `.ghost-text-fetching`-Puls-Animation (italic, muted) während Request in-flight (`GhostText.ts:210-228`, `editor.css:139-154`); lokalisierter Status-Text via Extension-Options (`fetchingStatusText`), niemals hardcoded English | Ja (SSE via `createSseSuggestionFetcher` in `suggest.ts`; Ghost-Text erscheint zeichenweise via `_streamTimer`) | Ja (AbortController im Extension-Storage `_abortController`; Tab/Escape/ArowRight; `GhostText.ts:147-156`, `ghost-text-helpers.ts`. Governed Exception für non-React-Extension per ADR-043) |
| KB-Interview | Ja | `Loader2`-Spinner (w-8 h-8) + `t("aiActions.aiThinking")` ("KI denkt nach...") (`KBInterviewView.tsx:138-141`); `interviewOp.isLoading`/`isStreaming` via `useAIOperation` (`KBInterviewView.tsx:50-61`) | Ja (SSE via `requestInterview` → `connectSSE`, `KBInterviewView.tsx:51`) | Ja (Stop-Button mit `OctagonX`-Icon `KBInterviewView.tsx:142-149` → `interviewOp.cancel()`; Escape `KBInterviewView.tsx:110-115`) |
| Consistency Check | Ja | `ConsistencyLoading`-Komponente mit Cancel-Button (`ConsistencyCheckPanel.tsx:176`); `isLoading` via `useAIOperation` (`ConsistencyCheckPanel.tsx:47-55`) | Nein (REST via `consistencyApi.checkConsistency`, nicht SSE — `ConsistencyCheckPanel.tsx:52`. justified: Backend bietet keinen SSE-Endpoint für Consistency, RETURN-based `ConsistencyCheckResponse`) | Ja (Cancel-Button in `ConsistencyLoading` → `cancelOp()` `ConsistencyCheckPanel.tsx:71-73, 176`; Cleanup bei Unmount `:86-88`) |
| Freier Assistent | Ja | Streaming-Indikator: `Loader2`-Spinner + `Bot`-Icon + `t("chatPanel.streaming")` ("Denke nach...") (`ChatPanel.tsx:122-134`); grüner Verbindungs-Punkt im Header (`ChatPanel.tsx:86`); `isStreaming` via `useChat.ts:121` | Ja (SSE via `chatApi.streamChat` → `connectSSE`, `useChat.ts:41-61`, Token-für-Token `onToken`) | Ja (`cancelStream` → `aiOp.cancel()` `useChat.ts:114-117`; Escape `ChatPanel.tsx:66-76`) |

**Goldstandard für AI-UX:**
- Streaming-Output (Token für Token) wo möglich – Nutzer sieht sofort Fortschritt
- Abbruch-Button immer sichtbar während KI-Anfrage läuft
- Bei Nicht-Streaming: Skeleton oder animierter Platzhalter, kein leerer Bereich
- Fehler klar benennen: "KI-Anfrage fehlgeschlagen – Modell nicht erreichbar" statt "Error"
- AI-Output wird nicht ohne Nutzerbestätigung angewendet; Accept/Reject/Retry/Stop nutzen die kanonischen `studio.aiActions.*`-Labels.

**Bewertung:** ⭐⭐⭐⭐ `4/5`
**Befunde:**

Die AI-Wartezeit-Behandlung ist **architektonisch vorbildlich** und systematisch durchgesetzt.
Alle 17 AI-Operationen (`ai_operation_inventory.yaml`) nutzen die gemeinsame
`useAIOperation`-State-Machine (`use-ai-operation.ts`), die den vollständigen
Lifecycle verwaltet: `idle → loading → streaming → complete | error | connection_lost`
(`use-ai-operation.types.ts:18-24`). Die State-Machine erzwingt:

1. **Sofortiges Loading-Feedback (<200ms, §16.3):** `start()` setzt sofort `status: "loading"`
   (`ai-operation-lifecycle.ts:90-102`) — noch bevor der asynchrone `execute`-Aufruf
   überhaupt läuft. Jede Komponente kann `isLoading` sofort rendern.
2. **Streaming (§16.1):** `notifyData()` wechselt `loading → streaming`
   (`ai-operation-lifecycle.ts:168-182`) — wird bei erstem Chunk aufgerufen.
   connectSSE propagiert den `signal`-Abort bis zum `fetch()`-Aufruf (`streaming.ts:146-152`).
3. **Abbruch (§16.2):** `cancel()` ruft `abortRef.current?.abort()` auf
   (`ai-operation-lifecycle.ts:115-127`). Check 7 (`ai-ux-compliance-v2.md`)
   stellt maschinell sicher, dass `execute` das Signal propagiert — nicht nur
   lokaler UI-State.
4. **Connection-Loss (§16.7):** Watchdog-Timer (15s default,
   `ai-operation-execute.ts:18`), bei Timeout → `connection_lost`-State +
   Auto-Retry-Konfiguration (`ai-operation-lifecycle.ts:56-86`). Partial Output
   bleibt erhalten (z.B. `useChat.ts:80-87` sichert partiellen Content).
5. **Fehler-Mapping (§16.5):** `mapSSEError` (`ai-error-mapping.ts`) mappt
   HTTP-Statuscodes auf strukturierte `AIErrorResponse` mit i18n-Keys und
   Handlungsempfehlungen (siehe §4).

**Governed Exceptions** (3, maschinell verfolgt via `.ai_interaction_exclude`):
- `editor.ghost_text` — non-React TipTap-Extension (ADR-043 non-react-extension category)
- `writing.session` — WebSocket (ADR-052/053, server-side Task.cancel)
- `extraction.timeline` — callback-basiertes SSE (ADR-043 non-react-transport category)

**Goldstandard-Erfüllung:**

| Goldstandard | Status | Evidence |
|---|---|---|
| Streaming-Output | ✅ Erfüllt | Alle SSE-Operationen streamen Token-für-Token; `onChunk` in `connectSSE` (`streaming.ts:102-115`) |
| Abbruch-Button sichtbar | ✅ Erfüllt | Jede AI-Komponente zeigt Stop/Cancel während `isStreaming` (ContinueButton, RewriteModal, KBInterviewView, ConsistencyCheckPanel, ChatPanel) |
| Skeleton/Platzhalter bei Nicht-Streaming | ✅ Erfüllt | ConsistencyCheck (REST) nutzt `ConsistencyLoading`-Komponente mit Spinner |
| Klar benannte Fehler | ⚠️ Teilweise | `mapSSEError` liefert actionable Messages, aber ChatPanel.tsx:136 ignoriert diese und zeigt generisches `chatPanel.errorConnecting` ("Verbindungsfehler") — siehe CR-AUFG-07-25 |
| Accept/Reject-Bestätigung | ✅ Erfüllt | Alle Writing-Outputs nutzen Accept/Reject (RewriteModal, ContinueButton AIAnnotation accept/reject, GenerationPanel, Co-Author, KB-Enhance). Labels aus `studio.aiActions.*` |

**Ein Stern Abzug** für die ChatPanel-Fehlerlücke (CR-AUFG-07-25): Die
handlungsableitbare Fehlermeldung wird vom Hook berechnet (`useChat.ts:88`:
`setError(errResponse.userMessage)`), aber von der Komponente verworfen und
durch eine generische ersetzt. Das ist ein isolierter Befund, kein systematisches Problem.

---

## 2. AI-Output-Präsentation

> Wie wird das KI-Ergebnis präsentiert? Kann der Nutzer es sinnvoll nutzen?

### 2.1 Writing-Output (Continue, Rewrite, Extend)

**Analysiere:**
- Wird der generierte Text direkt in den Editor eingefügt oder erst in einer Preview?
- Kann der Nutzer zwischen Original und Vorschlag wechseln (Diff-Ansicht)?
- Gibt es Undo für AI-Aktionen?
- Kann der Nutzer Teile des Vorschlags übernehmen (nicht nur alles-oder-nichts)?

**Bewertung:** ⭐⭐⭐⭐ `4/5`
**Befunde:**

**Continue (Extend) — Direkt-Insert mit AIAnnotation-Mark:**
- Generierter Text wird **direkt in den Editor** eingefügt, aber mit dem
  `aiGenerated`-Mark (`AIAnnotation.ts:30-59`) markiert. Die Mark trägt
  Attribute: `request_id`, `source`, `original_text`, `status`, `created_at`.
- Während Streaming: `.ai-generated-pending`-Highlight (subtile primärfarbige
  Hintergrund, `editor.css:177-185`) — Nutzer sieht sofort, was KI ist.
- Floating-Actions (accept/reject) erscheinen an der Insert-Position via
  ProseMirror Decoration (Tracker-Plugin, `AIAnnotation.ts`).
- **Partial Accept:** Nicht explizit für Continue implementiert — Accept wendet
  den gesamten pending-Mark an, Reject verwirft ihn. Modify-Detection
  (`getPendingModification`) erkennt, ob der Nutzer den AI-Text verändert hat,
  bevor er acceptet (`AIAnnotation.ts:67-77`).
- **Undo:** Über die Mark-Accept/Reject-Logik (`acceptMark`/`rejectMark` in
  `aiAnnotationApi.ts`). Nach Accept wird der Text Teil des Dokuments
  (normaler Undo via TipTap History).

**Rewrite — Modal mit Preview + Diff + Stil-Varianten:**
- Rewrite öffnet ein **Modal** (`RewriteSuggestionModal.tsx`) — KEIN Direkt-Insert.
  Original-Text wird im Modal-Header angezeigt (`:82-86`:
  `t("aiActions.original")` + `t("aiActions.quotedOriginal", {text})`).
- **Mehrere Alternativen:** `RewriteSuggestionList` zeigt mehrere Vorschläge als
  auswählbare Karten (selected/unselected Styling). Nutzer wählt eine aus.
- **Diff-Ansicht (CR-AUFG-07-18):** `AIDiffView` (`shared/ai-diff/AIDiffView.tsx`)
  ist die shared, accessible Diff-Oberfläche. Text-Modus: Inline-Diff via
  `AIDiffSegmentList` (added/removed Segmente). Field-Modus: Before/After-Spalten.
  Adapter in `lib/ai-diff/adapters/rewrite.ts`. SR-Summary für Screenreader
  (`aiDiff.srSummary`).
- **Partial Accept:** "Insert as New" (`insertAsNew`) fügt den Vorschlag als
  neuen Text ein, ohne das Original zu ersetzen — eine Form von Partial-Accept.
  Voll-accept ersetzt die Selection (`useRewriteActions.ts`).
- **Stil-Varianten (CR-AUFG-07-22):** `StyleVariantPicker` im Modal erlaubt
  Regeneration mit anderer Stil-Variante (6-value `StyleVariant` enum), ohne
  das Modal zu verlassen. Löst ein klassisches AI-UX-Problem (Regenerate).
- **Reject mit Begründung:** Optionales Reject-Reason-Textarea
  (`RewriteSuggestionModal.tsx:136-150`), verwendet für Preference-Learning.
- **Keyboard:** Ctrl/Cmd+Enter = Accept, Escape = Reject/Retry
  (`RewriteSuggestionModal.tsx:53-71`, standardisiert via `ai-action-shortcuts.ts`).

**Extend (Generation Panel) — Review-Phase mit Accept/Reject:**
- `GenerationPanel.tsx` hat drei Phasen: `config → streaming → review`.
- In der Review-Phase wird der Draft in `GenerationDraft` angezeigt (nicht direkt
  im Editor). Accept (`acceptDraft`) wendet den Text an (`onDraftAccepted`),
  Reject schließt das Panel.
- **Rating:** Nach Accept/Reject erscheint `RatingPrompt` (Stern-Rating) für
  Preference-Learning (`GenerationPanel.tsx:12`).

**Lücken:**
- Continue hat **keine Diff-Ansicht** (nur Highlight + floating accept/reject).
  Für Continue ist Diff weniger relevant (Append, kein Replace), aber ein
  visuell klarerer "vorher/nachher"-Kontrast fehlt im Vergleich zu Rewrite.
- **Teilweises Übernehmen** (z.B. nur 2 von 3 generierten Sätzen bei Continue)
  ist nicht als explizite UX-Action implementiert — der Nutzer muss manuell
  editieren, was er behalten will (modify-detection respektiert das).

### 2.2 Suggest-Output (Inline-Vorschläge)

**Analysiere:**
- Wie werden Vorschläge im Editor angezeigt? (Inline Ghost-Text, Popup, Sidebar?)
- Wie akzeptiert/ablehnt der Nutzer Vorschläge? (Tab, Klick, Tastenkürzel?)
- Gibt es visuellen Kontrast zwischen eigenem Text und KI-Vorschlag?
- Werden mehrere Vorschläge zur Auswahl angeboten?

Referenz: `docs/development/ui-principles.md` und die im Code-Graph gefundenen Inline-Suggestion-Komponenten/Extensions.

**Bewertung:** ⭐⭐⭐⭐⭐ `5/5`
**Befunde:**

**Ghost-Text Inline-Suggest (GitHub-Copilot-Stil) — vollständig implementiert:**
- **Darstellung:** Inline Ghost-Text direkt an der Cursor-Position via ProseMirror
  `Decoration.widget(side: 1)` (`GhostText.ts:284-293`). Styling:
  `.ghost-text-suggestion` = italic, muted-foreground, opacity 0.6, nicht
  selektierbar (`editor.css:116-122`). Klaren visueller Kontrast zum echten Text.
- **Akzeptieren:** `Tab` = gesamten Vorschlag übernehmen
  (`GhostText.ts:147`, `ghost-text-helpers.ts:acceptSuggestion`).
- **Wortweise:** `ArrowRight` = erstes Wort übernehmen
  (`GhostText.ts:155`, `acceptFirstWord`) — enables partial accept, sehr elegant.
- **Ablehnen:** `Escape` = verwerfen (`GhostText.ts:148-154`).
- **Typing-Mismatch-Detection:** Wenn der Nutzer weiter tippt und das erste
  Zeichen mit dem Ghost-Text übereinstimmt, wird der Vorschlag auto-advanced;
  bei Mismatch wird er verworfen (`ghost-text-helpers.ts:handleTypingDuringSuggestion`).
- **Keyboard-Hint:** `.ghost-text-hint`-Decoration zeigt "Tab übernehmen · Esc
  verwerfen · → Wort" an, fade-in nach 0.5s (`editor.css:125-134`,
  `GhostText.ts:279-282`). Lokalisiert via `t("ghostText.hint")`.
- **Fetching-Indikator:** `.ghost-text-fetching` Puls-Animation während Request
  in-flight (`editor.css:139-154`) — sofortiges Feedback (§16.3).
- **Fehler-Indikator (CR-AUFG-07-15):** `.ghost-text-error` transienter
  amber-farbener Text bei non-Abort Fetch-Fehlern, auto-clear nach 4000ms
  (`editor.css:165-174`, `ghost-text-error-status.ts`).
- **Auto-Trigger:** Nach ≥800ms Pause am Ende eines Paragraphs (≥5 Zeichen)
  (`GhostText.ts:183-186`).
- **Prefix-Cache:** LRU-Cache für Suggestions (`_cache`, `_cacheMaxAge: 30s`,
  `_cacheMaxSize: 50`) — vermeidet redundante API-Calls.
- **Onboarding:** `ghostText.onboardingHint` i18n-Key +
  `useGhostTextOnboarding`-Hook (erstmaliger Hinweis).

**Mehrere Vorschläge:** Ghost-Text bietet **einen** Vorschlag pro Trigger
(Einzelvorschlag-Modell wie GitHub Copilot, nicht Multi-Suggestion wie
Notion AI). Das ist das etablierte Copilot-Pattern und keine Lücke.

**Governed Exception:** Ghost-Text ist eine non-React TipTap-Extension und
besitzt daher einen eigenen AbortController (nicht useAIOperation).
Dies ist dokumentiert und maschinell verfolgt (`ai_interaction_exclude`,
ADR-043 non-react-extension category). Check 8 stellt sicher, dass die
Exception nicht verrottet.

### 2.3 Consistency-Check-Output

**Analysiere:**
- Wie werden Inkonsistenzen dem Nutzer präsentiert?
- Kann der Nutzer direkt zur betroffenen Stelle navigieren?
- Gibt es Schweregrade (kritisch / Warnung / Info)?
- Kann der Nutzer Befunde als "ignorieren" markieren?

**Bewertung:** ⭐⭐⭐⭐ `4/5`
**Befunde:**

**Präsentation — Gruppen mit Severity-Sortierung:**
- `ConsistencyResults.tsx` gruppiert Issues nach Kategorie
  (`groupByCategory`, `:185-195`) und zeigt sie als sectioned lists.
- Sortierung innerhalb einer Kategorie nach Schweregrad
  (`SEVERITY_ORDER`: critical=0, major=1, minor=2, info=3,
  `ConsistencyResults.tsx:16, 49-53`).
- Summary-Header zeigt Gesamtanzahl Issues + Aufschlüsselung nach Typ
  (`ConsistencyCheckPanel.tsx:149-171`).

**Severity-Badges:**
- `ConsistencyCard` (`WorldbuildingAnalysisCards.tsx:124-181`) zeigt
  Severity-Badge mit farbcodiertem Styling (`SEVERITY_COLORS`):
  - `critical`: rot (`bg-red-100 text-red-700`)
  - `major`: gelb (`bg-yellow-100 text-yellow-700`)
  - `minor`: blau (`bg-blue-100 text-blue-700`)
  - `info`: grau (`bg-gray-100 text-gray-600`)
- Dark-Mode-Varianten vorhanden (`:14-19`).

**Navigation zur betroffenen Stelle:**
- Entity-Namen sind **klickbare Links** (`ConsistencyCard`, `:138-161`):
  Wenn `onEntityClick` übergeben wird, rendert jeder Entity-Name einen
  `<button>`, der zur KB-Detail-Ansicht des Entities navigiert
  (`onEntityClick(entityId)`). Das ist KB-Entry-Navigation, nicht
  Kapitel-Text-Navigation (es gibt keine direkte "Springe zur Textstelle"-
  Funktion, da Consistency auf KB-Ebene operiert, nicht auf Chapter-Ebene).
- Confidence-Prozentsatz angezeigt (`:134-136`: `Math.round(issue.confidence * 100)%`).

**Befund-Details:**
- Jede Card zeigt: Description, Contradiction (in muted Box), und
  optional `suggested_resolution` (in grünem Box, `:170-177`).
- Sehr informative Struktur — der Nutzer versteht WAS inkonsistent ist,
  WARUM, und bekommt einen Lösungsvorschlag.

**"Ignorieren"-Markierung:**
- **Nicht implementiert.** Es gibt keinen Mechanismus, einen Befund als
  "ignorieren" oder "resolved without fix" zu markieren. Bei jedem Re-Run
  erscheinen alle Issues erneut. Dies ist eine Lücke für wiederholte
  Consistency-Checks (CR-AUFG-07-26).

**Connection-Lost & Error:**
- `ConnectionLostBanner` bei Verbindungsabbruch (`ConsistencyCheckPanel.tsx:143-147`).
- `ConsistencyError`-Komponente mit Retry-Button bei Fehlern (`:177-179`).

---

## 3. KB-Editor & Interview-UX

> Die Knowledge Base ist das Herzstück von Narrare. Wie gut ist die UX?

**Analysiere:**
- Wie intuitiv ist das Anlegen neuer KB-Einträge?
- Wie lange dauert ein typisches KB-Interview (geschätzt aus Code/Prompt-Länge)?
- Gibt es Fortschrittsanzeige beim Interview?
- Kann der Nutzer ein Interview unterbrechen und fortsetzen?
- Sind KB-Einträge durchsuchbar und filterbar?
- Gibt es visuelle Darstellung von Beziehungen (Knowledge Graph UI)?

**Bewertung:** ⭐⭐⭐⭐ `4/5`
**Befunde:**

**KB-Einträge anlegen — drei Wege:**
1. **Manuell:** `KBCreateForm` — Standard-Formular mit Feldern pro Entity-Typ
   (characters, locations, artifacts, regions, religions, magic, concepts).
2. **Mit KI erstellen (Assisted):** `KBAssistedCreationPanel` — startet eine
   KI-geführte Session mit drei Sub-Views: `fields | interview | enhance`
   (`KBAssistedCreationPanel.tsx:91-110`). Die Session erstellt automatisch
   einen Entity-Entwurf und führt durch Feld-Ausfüllung.
3. **Interview-Modus:** `KBInterviewView` — KI stellt Fragen, Nutzer antwortet,
   KI extrahiert Feld-Werte aus den Antworten (`KBInterviewView.tsx`).

**Interview-UX — detailliert:**
- **Fortschrittsanzeige:** `InterviewProgressBar` zeigt ausgefüllte/gesamte
  Felder (`KBInterviewView.tsx:129-132`: `filledFields`/`totalFields`).
  Question-Count im Header (`InterviewHeader`).
- **Loading-State:** `Loader2`-Spinner + "KI denkt nach..." während KI die
  nächste Frage generiert (`KBInterviewView.tsx:138-141`).
- **Stop/Cancel:** Stop-Button (`KBInterviewView.tsx:142-149`) +
  Escape-Handler (`:110-115`).
- **Connection-Lost:** Amber-Banner mit Retry (`:153-169`).
- **Error-State:** `InterviewErrorState` mit Retry (`:172-174`).
- **Complete-State:** `InterviewCompleteState` mit Option für weitere Fragen
  (`:191-193`).
- **Geschätzte Dauer:** Das Interview läuft bis alle required fields gefüllt
  sind UND mindestens 3 Fragen gestellt wurden
  (`KBInterviewView.tsx:85`: `filledRequired.length >= requiredFields.length && questionCount >= 3`).
  Bei ~5-10s pro KI-Frage (SSE-Streaming) sind das mindestens 15-30s reine KI-Zeit
  plus Antwort-Zeit des Nutzers. Realistisch 2-5 Minuten für einen Character.

**Interview Unterbrechen/Fortsetzen:**
- **Resume implementiert:** `use-kb-interview-resume.ts`-Hook +
  `resumeSessionId`-Prop (`KBAssistedCreationPanel.tsx:36`:
  `resumeSessionId?: string | null`). Die Session ist DB-gestützt — beim
  Abbrechen/Wiederaufrufen kann die bestehende Session fortgesetzt werden.
  `KBAssistedCreationController` handhabt die Resume-Logik.

**KB-Einträge durchsuchbar/filterbar:**
- **Suche:** `SearchInput`-Primitive (§17.6) mit URL-Sync (`?q=`)
  (`useWorldBuildingUrlSync`, `WorldBuilding.tsx:87`).KB-Search-Hook:
  `useKBSearch.ts`.
- **Filter:** Entity-Type-Filter in der Category-Sidebar
  (`KBCategorySidebar`), URL-adressierbar (`?type=character`).
- **Mention-Suche:** `MentionAutocomplete` + `KBMentionRenderer` für
  @-mentions im Editor.

**Knowledge Graph UI:**
- **Vollständig implementiert:** `KnowledgeGraphView.tsx` nutzt Cytoscape.js
  (direkt, nicht react-cytoscapejs — für Performance bei 500+ Elementen).
- **Layouts:** Force-directed (`cose`), hierarchical (`dagre`), concentric
  (`KnowledgeGraphView.tsx:34`, Layout-Selector in `KnowledgeGraphControls`).
- **Interaktion:** Node-Click → highlight edges + tooltip; Double-Click →
  KB-Entry-Detail öffnen; Edge-Click → Relationship-Info; Node-Drag →
  reposition (ephemeral).
- **Filter & Suche:** Entity-Type-Filter, Search, Zoom-Controls
  (`KnowledgeGraphZoomControls`).
- **Shortest Path:** `KnowledgeGraphPathPanel` — kürzeste Pfade zwischen
  Entities visualisieren.
- **Overlays:** `KnowledgeGraphOverlays` (Tooltips, Highlight-Effects).
- **Fehlerbehandlung:** `mapSSEError` für Graph-Ladefehler, niemals
  rohe Error-Texte (`KnowledgeGraphView.tsx:55-65`).

**KB Enhance Review (Feld-Verbesserung):**
- `KBEnhanceReview.tsx` mit `EnhanceReviewCard` pro Feld.
- Before/After-Vergleich via `AIDiffView` (field mode — zwei Spalten
  Original/Vorschlag, `EnhanceReviewCard.tsx:11`).
- Bulk-Actions: `acceptAll` / `rejectAll` / `applySelected`
  (`EnhanceReviewBulkActions`).
- Rating nach Accept/Reject (`AIRating` via `kbEnhanceRatingAdapter`).
- Keyboard: Ctrl/Cmd+Enter = apply (`ai-action-shortcuts.ts`).

**KB Improve (Analyse & Vorschläge):**
- `KBImprovePanel` + `ImproveSuggestionCard` — KI-Analyse mit strukturierten
  Verbesserungs-Vorschlägen, bulk apply via `applySelected`.
- REST-basiert (`useKBImprove.ts`), `ImproveLoadingState`-Spinner.

**Lücken:**
- Interview-Fragen sind **nicht filterbar/suchbar** im Nachhinein (lineare Q&A,
  kein Timeline-View der gestellten Fragen).
- Die KB-Editor-Detailansicht (`KBDetailPanel`/`KBEntryDetail`) ist funktional,
  aber für Nicht-Techniker könnten die vielen Felder überwältigend sein
  (7 Entity-Typen × mehrere Felder pro Typ) — kein "Guided Mode" für
  manuelles Ausfüllen (nur über den Assisted/Interview-Weg).

---

## 4. Fehlerbehandlung aus Nutzerperspektive

> Was sieht der Nutzer, wenn etwas schiefläuft?

**Szenarien prüfen:**

| Fehlerszenario | Aktuelle Fehlermeldung (laut Code) | Verständlich für Nicht-Techniker? | Handlungsempfehlung gegeben? |
|---|---|---|---|
| API-Key ungültig | `t("aiActions.errorApiKey")` = "Dein API-Schlüssel ist ungültig. Überprüfe deine KI-Einstellungen." (`ai-error-mapping.ts:22`, `studio.json:1804`). Ausgelöst bei HTTP 401 (`mapHTTPError`, `:161-170`). | Ja | Ja — "Überprüfe deine KI-Einstellungen" |
| Modell-Timeout | `t("aiActions.errorTimeout")` = "Die KI braucht zu lange. Versuche es mit weniger Kontext erneut." (`ai-error-mapping.ts:33-36`, `studio.json:1807`). Ausgelöst bei HTTP 408 (`:194-203`) oder `kind="timeout"`. `retryable: true` → Retry-Button wird eingeblendet. | Ja | Ja — "Versuche es mit weniger Kontext erneut" |
| Context zu groß | `t("aiActions.errorTextTooLong")` = "Der Text ist zu lang für die KI. Kürze die Auswahl und versuche es erneut." (`ai-error-mapping.ts:26-28`, `studio.json:1805`). Ausgelöst bei HTTP 413 (`:172-181`). `retryable: false`. | Ja | Ja — "Kürze die Auswahl" |
| Netzwerk-Unterbrechung | `t("aiActions.errorConnection")` = "Verbindung verloren. Prüfe deine Internetverbindung." (`ai-error-mapping.ts:38-40`, `studio.json:1808`). Ausgelöst bei `kind="network"` oder HTTP 5xx (`:127-136`, `:206-213`). Connection-Lost-State zusätzlich mit `t("aiActions.connectionLostRetry")` = "Erneut verbinden" (`studio.json:1798`). | Ja | Ja — "Prüfe deine Internetverbindung" + Retry-Button |
| KB-Datei korrupt | ConsistencyCheck nutzt `mapRestApiError` (`ai-rest-error.ts`) statt `mapSSEError` — analoge Struktur mit i18n-Keys. KnowledgeGraph nutzt `mapSSEError(controller.error)?.userMessage` mit Fallback `t("kb.graphLoadFailed")` (`KnowledgeGraphView.tsx:60`). KB-Session-Fehler: `controller.errorMessage || t("kb.sessionCreateFailed")` (`KBAssistedCreationPanel.tsx:77`). | Teilweise — `kb.graphLoadFailed` / `kb.sessionCreateFailed` sind generisch (nicht spezifisch "korrupt"). Spezifische "Datei korrupt"-Meldung nicht gefunden. | Teilweise — generische Fehlermeldungen ohne spezifische Handlungsempfehlung für korrupte Daten. |

**Goldstandard:** Fehlermeldungen in Narrare sollten:
- Die Ursache in einfacher Sprache nennen
- Eine konkrete Handlung vorschlagen ("Überprüfe deinen API-Key unter Einstellungen")
- Nie technische Stack-Traces zeigen (ins Log, nicht in die UI)

**Bewertung:** ⭐⭐⭐⭐ `4/5`
**Befunde:**

**Stärken — systematische, actionable Fehlerbehandlung:**
Die Fehlerbehandlung ist **architektonisch durchdacht** und maschinell erzwungen.
`mapSSEError` (`ai-error-mapping.ts`) ist der zentrale Mapper, der jede
AI-Operation durchläuft (default `errorMapper` in `useAIOperation`,
`use-ai-operation.ts:52`). Die Mapping-Regeln (Dokumentiert in `:56-70`):

| Error Kind / Status | i18n Key | DE Message | Retryable |
|---|---|---|---|
| 401 Unauthorized | `aiActions.errorApiKey` | "Dein API-Schlüssel ist ungültig. Überprüfe deine KI-Einstellungen." | Nein |
| 413 Payload Too Large | `aiActions.errorTextTooLong` | "Der Text ist zu lang für die KI. Kürze die Auswahl und versuche es erneut." | Nein |
| 429 Rate Limit | `aiActions.errorRateLimit` | "Du hast zu viele Anfragen gesendet. Warte einen Moment." | Ja |
| 408 Timeout | `aiActions.errorTimeout` | "Die KI braucht zu lange. Versuche es mit weniger Kontext erneut." | Ja |
| 5xx Server Error | `aiActions.errorConnection` | "Verbindung verloren. Prüfe deine Internetverbindung." | Ja |
| network | `aiActions.errorConnection` | (wie oben) | Ja |
| parse | `aiActions.errorParse` | "Die KI-Antwort war fehlerhaft. Versuche es erneut." | Ja |
| stream/default | `aiActions.errorDefault` | "Ein unerwarteter Fehler ist aufgetreten. Versuche es erneut." | Ja |
| AbortError | (null — swallowed) | Nutzer hat abgebrochen, kein Fehler | — |

**Alle** Messages folgen dem §16.5-Format `[What happened] [What to do]`.
Keine rohen HTTP-Statuscodes in der UI — Check 4 (`ai-ux-compliance-v2.md`)
verbietet hardcoded `error.message` in TSX maschinell.

**Retry-UI:** Wenn `retryable: true`, zeigt die Komponente einen Retry-Button
(z.B. `RewriteSuggestionModal.tsx:122-130`: `t("aiActions.retry")` = "Erneut versuchen").

**Stack-Traces:** Niemals in der UI — die ursprüngliche Exception wird im
`cause`-Feld des `AIErrorResponse` gespeichert (`ai-error-mapping.ts`,
z.B. `:95`: `cause: error`), aber nur `userMessage`/`i18nKey` gerendert.

**Lücken:**

1. **ChatPanel ignoriert strukturierte Fehler (CR-AUFG-07-25):**
   `useChat.ts:88` setzt `setError(errResponse.userMessage)` (die actionable
   Message), aber `ChatPanel.tsx:136` rendert `{error && <StatusMessage state="error" message={t("chatPanel.errorConnecting")} />}`
   — es verwendet die generische Konstante `"Verbindungsfehler"` statt der
   berechneten actionable Message. Die Handlungsempfehlung geht verloren.
   Dies widerspricht §16.5 für die Chat-Operation, obwohl der Hook korrekt ist.

2. **KB-Korruption-spezifische Meldung fehlt:** Es gibt keinen dedizierten
   `aiActions.errorDataCorrupt` oder ähnlich. Bei korrupten KB-Daten fällt
   das System auf generische `kb.graphLoadFailed` / `kb.sessionCreateFailed`
   zurück, die nicht spezifisch genug sind und keine klare Handlungsempfehlung
   geben ("Was tue ich, wenn meine KB korrupt ist?"). Niedrige Priorität, da
   KB-Korruption ein Edge-Case ist.

3. **Legacy-unübersetzte i18n-Keys (§16.4/RULE-16):** Im deutschen
   `studio.json` existiert ein Block unverdeutschter Strings (Zeilen ~1336-1343,
   alter Interview-Namespace): `"aiThinking": "AI is thinking..."`,
   `"nextQuestion": "Next Question"`, etc. — Englisch in der deutschen Locale.
   Die kanonischen `aiActions.aiThinking` (Zeile 1797 = "KI denkt nach...")
   sind korrekt, aber der Legacy-Block ist eine Inkonsistenz (CR-AUFG-07-27).

---

## 5. Onboarding & Erstkonfiguration

> Was erlebt ein Nutzer, der Narrare zum ersten Mal öffnet?

**Analysiere:**
- Gibt es einen Onboarding-Flow oder landet der Nutzer direkt im leeren Editor?
- Wird erklärt, wie KB, Storyboard und AI zusammenspielen?
- Ist die API-Key-Konfiguration intuitiv?
- Gibt es ein Demo-Projekt oder Beispiel-Inhalte?
- Wie lange bis zum ersten "Aha-Moment" (erste sinnvolle KI-Ausgabe)?

**Bewertung:** ⭐⭐⭐⭐ `4/5`
**Befunde:**

**Onboarding-Flow — Wizard (vorhanden, aber basic):**
- **WizardShell** (`WizardShell.tsx`): 5-Schritt-Setup-Wizard unter `/wizard`.
  Schritte: (1) Begrüßung/Sprache, (2) Starter-Auswahl, (3) Novel-Metadaten,
  (4) Provider-Konfiguration, (5) Bestätigung.
- **Progress-Indikator:** Kreisförmige Step-Anzeige mit ✓ für abgeschlossen,
  aktiver Step gehighlightet (`WizardShell.tsx:124-165`).
- **Quick-Start:** "Quick Start"-Link erstellt sofort ein Demo-Projekt und
  überspringt den Wizard (`useQuickStart`, `WizardShell.tsx:113-121`).
  `isQuickStarting`-Loading-State.
- **Provider-Skip:** Wenn der Nutzer bereits Provider konfiguriert hat
  (`hasProviders`), wird Step 4 übersprungen (`WizardShell.tsx:47-63, 85-91`).

**API-Key-Konfiguration:**
- In **WizardStep4** (Provider-Setup) während Onboarding UND in
  **Settings → AI-Tab** (`AiTab.tsx`) nachträglich.
- `AiTab.tsx` ist umfassend: Provider-Liste (`ProviderList`), Default-Model
  (`DefaultModelSection`), Token-Profile (`TokenProfileSection`), Category/
  Intent-Overrides, Context-Budget, System-Timeouts.
- `ModelSelector` im Wizard hilft bei Modellauswahl.
- **Intuitiv?** Funktional, aber dicht — für Nicht-Techniker ist die
  Anzahl der Optionen (Provider, Modelle, Token-Profile, Overrides)
  überwältigend. Es gibt keine "Empfohlen für Anfänger"-Voreinstellung
  oder kontextuelle Hilfetexte jenseits der i18n-Labels.

**Demo-Projekt / Beispiel-Inhalte:**
- **Quick-Start** erstellt ein **leeres Projekt** — `useQuickStart.ts:37`
  setzt `starter: "blank"`. Es wird **kein Demo-Content** (keine Beispiel-KB,
  kein Sample-Kapitel) gesät. Das Projekt startet komplett leer.
- **Kein Sample-Novel** oder Beispiel-KB im Code gefunden.

**Feature-Tour (Feature-Einführung) — global verdrahtet:**
- `FeatureTour`-Komponente (`feature-tour.tsx`) ist **global in der
  StudioWorkspaceShell gerendert** (`StudioWorkspaceShell.tsx:68`:
  `<FeatureTour steps={FEATURE_TOUR_STEPS} />`) — sichtbar in jedem
  Novel-Workspace, nicht nur nach Wizard.
- **Auslösung:** `useQuickStart.ts:48` ruft `requestFeatureTour()` nach
  Quick-Start auf; `AboutTab.tsx` bietet einen Button zur erneuten Tour.
  localStorage-Tracking (`TOUR_STORAGE_KEY`), Portal-basiert, Spotlight
  mit CSS-Selector-Targets.
- **9 Tour-Steps** (`feature-tour-steps.ts`), i18n via `studio.tour.*`:
  Step 1-2: Editor + Sidebar. Step 3-4: AI-Toolbar + Ghost-Text.
  Step 5-6: Worldbuilding + Settings. **Step 7-8: Konzeptionelle
  Workflow-Erklärungen** ("KB → Context → AI", "Storyboard → Chapter → AI").
  Step 9: "before/after demo moment".

**KB/Storyboard/AI-Zusammenspiel erklärt?**
- **Ja, via Feature-Tour.** Tour-Step 7 erklärt "KB → Context → AI",
  Step 8 erklärt "Storyboard → Chapter → AI" (`feature-tour-steps.ts:43-52`).
  Diese konzeptionellen Steps verwenden zentrierte Tooltips (kein DOM-Target,
  da konzeptionell). Die i18n-Keys `tour.step7.*` / `tour.step8.*` enthalten
  die Erklärtexte.
- **Aber:** Die Tour erklärt das Konzept textlich — sie erstellt keinen
  Beispiel-Content zum Ausprobieren. Der Nutzer versteht das Prinzip, kann
  aber nicht sofort eine AI-Operation mit echtem KB-Kontext testen (da das
  Projekt leer ist).

**"Aha-Moment"-Zeit:**
- Mit Quick-Start + bereits konfiguriertem Provider: Sehr kurz (Sofort im
  Editor, Continue-Button verfügbar; Tour startet automatisch).
- Ohne Provider: Wizard muss durchlaufen werden (Provider-Setup ist
  zwingend), dann Editor. Erste AI-Ausgabe in ~30s-2min nach Wizard-Abschluss.
- Ohne KB-Content sind AI-Ergebnisse jedoch weniger nützlich (kein Kontext).
  Der "wahre" Aha-Moment (KI mit KB-Kontext) erfordert vorheriges KB-Anlegen
  — die Tour erklärt WARUM, aber der Nutzer muss selbst KB-Einträge
  anlegen, bevor er den Effekt erlebt.

**Lücken:**
- **Kein Demo-Content-Seeding:** Quick-Start erstellt ein leeres Projekt
  (`starter: "blank"`). Ein Beispiel-Projekt mit vorausgefüllter KB würde
  den "Aha-Moment" mit KB-Kontext sofort erlebbar machen — siehe CR-AUFG-07-29.
- Provider-Setup ist dicht/technisch — keine geführten Voreinstellungen
  ("Empfohlen für Anfänger").

---

## 6. Prompt-Anpassbarkeit in der WebUI

> Laut Kontext-Review gibt es ein System zur Prompt-Anpassung. Wie gut ist die UX dafür?

**Analysiere:**
- Wo in der UI kann der Nutzer Prompts anpassen? Ist das auffindbar?
- Wie komplex ist die Oberfläche? (Für Nicht-Entwickler verständlich?)
- Gibt es Vorschau / Test-Funktion bevor Änderungen aktiv werden?
- Gibt es Reset-to-Default?
- Werden Variablen (`{{kb_context}}`, `{{chapter_text}}`) erklärt?
- Ist die Narrare-Identität bzw. Capability-Basis (falls in der UI erklärt) verständlich sichtbar?

**Bewertung:** ⭐⭐⭐⭐ `4/5`
**Befunde:**

**Auffindbarkeit:**
- Prompt-Anpassung liegt unter **Settings → "Prompts"-Tab**
  (`settings-view-config.ts:51`: `{ id: "prompts", icon: FileText, labelKey: "settings.promptsTab" }`).
  In der SettingsSidebar sichtbar (`SettingsSidebar.tsx`).
- Nach Auswahl eines Prompts öffnet sich der `PromptEditor` (`PromptEditor.tsx`).

**Funktionsumfang (PROMPT-003, CR-AUFG-07-16 — vollständig implementiert):**

| Funktion | Implementiert? | Komponente / Evidence |
|---|---|---|
| View-Modus (read-only) | ✅ | `PromptEditorViewMode` (`PromptEditor.tsx:115`) |
| Edit-Modus | ✅ | `PromptEditorEditMode` (`:107`), Save/Cancel |
| Provider-freie Vorschau | ✅ | `PromptPreviewDialog` (`:143-149`), ruft `promptsApi.preview` auf — KEIN LLM-Call, nur Template-Auflösung |
| Provider-gated Live-Test (SSE) | ✅ | `PromptLiveTestDialog` (`:150-160`), SSE-Streaming mit echtem Provider, Token-Warnungs-Gate (acknowledge vor Run), Cancel + Retry |
| Reset-to-Default | ✅ | `PromptResetConfirmDialog` (`:161-172`), zeigt effective-state + bundled-content vor Reset |
| Diff-Ansicht | ✅ | `PromptDiff` (`:48-58`), Full-Screen-Vergleich, onResolved invalidiert Queries |
| Variablen-Liste (simple) | ✅ | `PromptVariablesAside` (`:128`) — zeigt `{{var}}`-Namen in Mono-Font |
| Variablen-Metadaten (rich) | ✅ | `VariableMetadataPanel` — Tabelle mit Name, **Description**, **Provenance** (cascade source), **Security**-Klassifikation, Required-Indikator (`VariableMetadataPanel.tsx:34-72`). Daten autoritativ aus `promptsApi.preview`. |
| Prompt-Historie (CR-AUFG-07-19) | ✅ | `PromptHistoryPanel` (`:134-140`) — DB-gestützt, append-only: list/compare/restore/clear |

**Variablen erklärt?**
- **Ja, exzellent.** `VariableMetadataPanel` zeigt pro Variable:
  - Name (`{{variable_name}}`)
  - Description (menschenlesbar)
  - Provenance (cascade source: `db`/`project`/`user`/`bundled`/`bundled_en`)
  - Security-Klassifikation
  - Required-Indikator (`*`)
- Die Daten kommen autoritativ vom Backend-Preview (nie lokal fabriziert),
  was Konsistenz mit der tatsächlichen Prompt-Auflösung garantiert.

**Komplexität für Nicht-Entwickler:**
- **Hoch.** Prompt-Editing setzt Verständnis von Template-Variablen,
  Cascade-Logik und Provider-Konfiguration voraus. Die UI ist funktional
  und gut strukturiert, aber für Nicht-Entwickler ist dies eine
  Power-User-Funktion. Es gibt keine "Einfach"-Ansicht oder geführten Editor.
- Token-Warnung beim Live-Test (kostet API-Credits) ist gut — schützt Nutzer
  vor versehentlichen Kosten.

**Narrare-Identität / Capability-Basis sichtbar?**
- **Nicht in der Prompt-Editing-UI erklärt.** Die garantierten Capabilities
  (`NarrareUniversalRules`, `NarrareMeta`, `NarrareObservability`) sind
  architektonisch garantiert und NICHT über die Cascade anpassbar (siehe
  cr-00-kontext §5). Die WebUI macht dies jedoch **nicht explizit sichtbar** —
  der Nutzer sieht nur die anpassbaren Feature-Prompts, nicht die garantierte
  Capability-Basis. Ein Hinweis "Diese Regeln sind immer aktiv und können
  nicht überschrieben werden" fehlt.

**Error-State beim Prompt-Loading:**
- `loadFailed`-Fehlermeldung mit Back-Button (`PromptEditor.tsx:74-89`).

---

## 7. UX-Muster-Konsistenz

> Verhält sich die UI konsistent? Oder gibt es Feature-zu-Feature-Brüche?

**Prüfe:**
- Sind Tastenkürzel für KI-Funktionen konsistent? (oder: Strg+Enter hier, Klick dort)
- Sind Begriffe einheitlich? ("Generieren" / "Erstellen" / "Schreiben" für dieselbe Aktion?)
- Gibt es konsistente Icon-Verwendung für KI-Aktionen?
- Werden KI-generierte Inhalte immer visuell als solche markiert?

**Bewertung:** ⭐⭐⭐⭐ `4/5`
**Befunde:**

**Tastenkürzel — stark standardisiert (CR-AUFG-07-13):**
- **Ctrl/Cmd+Enter = Accept/Apply** — einheitlich across ALL AI-Output-Reviews:
  - Rewrite: `RewriteSuggestionModal.tsx:56` via `isApplyShortcut(e)`
  - Generation Review: `GenerationPanel.tsx:47` via `isApplyShortcut(e)`
  - KB Enhance Review: `KBEnhanceReview.tsx` (CR-AUFG-07-13)
  - Co-Author Review: `useCoAuthorStream.ts` (CR-AUFG-07-13)
- **Escape = Cancel/Stop/Close** — konsistent:
  - Rewrite Modal: Escape = Reject/Retry (`RewriteSuggestionModal.tsx:60-67`)
  - Generation Panel: Escape = Stop (streaming) / Close (review) (`GenerationPanel.tsx:39-46`)
  - ChatPanel: Escape = cancelStream / close (`ChatPanel.tsx:66-76`)
  - KBInterviewView: Escape = cancel (loading) / back (`KBInterviewView.tsx:110-119`)
  - ConsistencyCheckPanel: Escape = close (`ConsistencyCheckPanel.tsx:91-99`)
  - GhostText: Escape = dismiss (`GhostText.ts:148-154`)
  - SessionPanel: Escape = stop generation / end session (ADR-052)
- **Tab = Accept Ghost-Text** (`GhostText.ts:147`), **ArrowRight = First Word** (`:155`).
- Zentralisierte Shortcut-Logik in `lib/ai-action-shortcuts.ts` (`isApplyShortcut`).
- Settings → Shortcuts-Tab dokumentiert alle Shortcuts für den Nutzer
  (`settings-view-config.ts:59-125`: `SETTINGS_SHORTCUTS`).

**Begriffe — kanonisch via `studio.aiActions.*` (CR-AUFG-07-12):**
- 21 kanonische AI-Action-Labels in `studio.aiActions`-Namespace
  (DE/EN/FR-Parität, `ui-principles.md` §16.8): accept, acceptAll, reject,
  rejectAll, applySelected, retry, stop, addToDraft, insertAsNew, replace, etc.
- Check 6 (`ai-ux-compliance-v2.md`) verbietet 16 deprecated Aliases
  maschinell (`aiModal.accept`, `generation.stop`, `annotation.keep`,
  `rewrite.cancel`, `sessionPanel.addToDraft`, `coAuthor.acceptAll`, etc.).
- **Terminologie-Konsistenz:** "Übernehmen" (accept), "Verwerfen" (reject),
  "Stoppen" (stop), "Erneut versuchen" (retry) — einheitlich across Features.

**Icon-Verwendung — konsistent:**
- **Sparkles** = universelles AI-Indikator-Icon (`ui-principles.md` §12):
  Rewrite-Button, AI-Buttons, AI-Modals, Analysis-Triggers, Settings-AI-Tab.
- **Loader2** = universeller Loading-Spinner (animate-spin).
- **OctagonX / X** = Stop/Close.
- **Bot** = AI-Chat-Avatar (ChatPanel, SessionPanel).
- **Check / ChevronRight** = Accept / Selected-Indikator.
- **PenLine** = Continue-Writing.
- Konsistente Verwendung gemäß §12-Icon-Referenz bestätigt im Code.

**KI-generierte Inhalte visuell markiert?**
- **Ghost-Text:** Ja — italic, muted, opacity 0.6, nicht-selektierbar
  (`.ghost-text-suggestion`, `editor.css:116-122`). Klarer visueller Kontrast.
- **AI-Annotation (Continue/Extend):** Ja — `.ai-generated-pending` Highlight
  (subtile primärfarbige Hintergrund, 8% opacity light / 15% dark,
  `editor.css:177-185`). AI-Text ist während "pending" hervorgehoben.
- **Chat-Messages:** `aiDraftBadge`-Markierung für AI-Nachrichten
  (`ChatPanel.tsx:44`: `t("sessionPanel.aiDraftBadge")`).
- **Consistency-Results:** KI-Flag (critical/major/minor/info-Badges).
- **Rewrite-Modal:** Original vs. Vorschlag klar getrennt, AIDiffView
  mit added/removed-Segment-Farben.

**Lücken / Inkonsistenzen:**
1. **Continue-Button vs. Rewrite-Trigger:** Continue ist ein Toolbar-Button
   (`ContinueButton.tsx`), Rewrite wird über das Bubble-Menu bei Selection
   ausgelöst. Verschiedene Entry-Points, aber begründet (Continue = Cursor-Position,
   Rewrite = Selection). Konsistent genug.
2. **Consistency nutzt `mapRestApiError`, alle anderen `mapSSEError`:**
   Architekturell korrekt (REST vs. SSE), aber zwei Mapper-Pfade erhöhen
   die Wartungsfläche. Beide produzieren strukturierte `AIErrorResponse`.
3. **Legacy-i18n-Block** (siehe §4, CR-AUFG-07-27): Unverdeutschte Strings
   im alten Interview-Namespace brechen die i18n-Konsistenz.

---

## 8. Modernes AI-UX-Potenzial

> Welche UX-Patterns aus aktuellen AI-Tools (2024/2025) fehlen noch,
> würden aber gut zu Narrare passen?

Bewerte jede Idee auf: Mehrwert für Narrare-Nutzer (1–5) × Implementierungsaufwand (S/M/L/XL)

| UX-Pattern | Beispiel aus anderen Tools | Mehrwert | Aufwand | Empfehlung |
|---|---|---|---|---|
| Ghost-Text Inline-Suggest (wie Copilot) | GitHub Copilot, Notion AI | 5 | — | ✅ **Bereits implementiert** (`GhostText.ts`, voll funktionsfähig mit SSE, Fetching-Indikator, Error-Status, Cache, Onboarding) |
| Diff-Ansicht für Rewrites | Cursor, Claude Artifacts | 5 | — | ✅ **Bereits implementiert** (`AIDiffView` shared component, text + field mode, SR-Summary, CR-AUFG-07-18) |
| Prompt-Verlauf / History | ChatGPT, Perplexity | 4 | — | ✅ **Bereits implementiert** (`PromptHistoryPanel`, DB-gestützt append-only, list/compare/restore/clear, CR-AUFG-07-19) |
| KI-Aktionen per Slash-Command | Notion, Linear | 4 | — | ✅ **Bereits implementiert** (`slash-commands/registry.ts`, 6 Commands: continue/draft/rewrite/coauthor/chat/explain, Menu, Parser, CR-AUFG-07-20) |
| Mini-Chat in Sidebar während Schreiben | Cursor | 4 | — | ✅ **Bereits implementiert** (`ChatPanel.tsx`, SSE-Streaming, Cancel, connection-Indicator) |
| Regenerate mit Stil-Varianten | Midjourney, Claude | 4 | — | ✅ **Bereits implementiert** (`StyleVariantPicker`, 6-value StyleVariant enum, CR-AUFG-07-22) |
| Emotionale Intensitätskurve visualisieren | Neu / Narrare-spezifisch | 4 | L | 🟡 **Empfohlen** — Sentiment-Analyse existiert (`useSentiment.ts`, `analysis.sentiment`), aber keine Visualisierung als Kapitel-Intensitätskurve. Hohes Mehrwert für Schriftsteller (Pacing/Emotion-Editing), aber significanter Aufwand (Recharts-Integration, Kapitel-Chunking, Interaktion). Siehe CR-AUFG-07-28. |
| KI-Feedback-Rating (👍/👎 pro Vorschlag) | ChatGPT, Copilot | 4 | — | ✅ **Bereits implementiert** (`RatingPrompt.tsx` Stern-Rating + `AIRating` shared component, `useAIRating.ts`, 5 Source-Type-Adapter: coauthor/kb-field/kb-enhance/kb-improve/chat, POST /memory/feedback, CR-AUFG-07-24) |

**Bewertung aktuelles UX-Niveau:** ⭐⭐⭐⭐⭐ `5/5`
**Top-3-Empfehlungen:**

Das aktuelle AI-UX-Niveau ist **außergewöhnlich hoch** — 7 der 8 evaluierten
Modern-Patterns sind bereits implementiert (teilweise durch dedizierte AUFGs
mit maschineller Durchsetzung). Das System ist einem 2024/2025-Standard
AI-Writing-Tool ebenbürtig. Die Top-Empfehlungen fokussieren auf die
verbleibenden Lücken:

1. **Emotionale Intensitätskurve (CR-AUFG-07-28):** Das Backend hat bereits
   Sentiment-Analyse (`useSentiment.ts`). Eine Visualisierung als
   Kapitel-Intensitätskurve (Recharts LineChart, x=Kapitel-Position,
   y=Emotion-Intensity) wäre ein Narrare-spezifisches Alleinstellungsmerkmal
   für Pacing-Editing. Hohes Mehrwert, aber L-Aufwand.

2. **Consistency "Ignorieren"-Markierung (CR-AUFG-07-26):** Wiederkehrende
   Consistency-Checks zeigen gelöste/akzeptierte Issues immer wieder an.
   Eine "Ignorieren"- oder "Resolved"-Markierung mit Persistenz würde die
   Wiederholungsfrustration eliminieren. M-Aufwand.

3. **Demo-Projekt mit Beispiel-KB (CR-AUFG-07-29):** Die Feature-Tour
   erklärt bereits konzeptionell das Zusammenspiel (KB → AI), aber Quick-Start
   erstellt ein leeres Projekt (`starter: "blank"`). Ein Demo-Starter mit
   vorausgefüllter Beispiel-KB würde den Aha-Moment (KI mit KB-Kontext)
   sofort erlebbar machen. M-Aufwand.

---

## Gesamtbewertung UI/UX

**Bewertung:** ⭐⭐⭐⭐ `4/5`
**Zusammenfassung:** Narrare's AI-UX ist architekturell vorbildlich und
praktisch vollständig. Die zentrale `useAIOperation`-State-Machine erzwingt
die §16-AI-Interaction-Standards (Streaming, Cancel <2s, Loading <200ms,
Connection-Loss, actionable Errors) über alle 17 AI-Operationen hinweg,
maschinell geprüft durch 11 Gates (`just check-ai-ux`). 7 von 8 modernen
AI-UX-Patterns (Ghost-Text, Diff, History, Slash-Commands, Mini-Chat,
Stil-Varianten, Rating) sind implementiert — teils mit dedizierten AUFGs.
Diff-Ansichten, Variablen-Metadaten und Prompt-Historie sind first-class.
Hauptabzüge: eine isolierte Fehlermeldungs-Lücke im ChatPanel (generische
statt actionable Message), fehlende Consistency "Ignorieren"-Markierung,
fehlendes Demo-Content-Seeding im Onboarding (leerer Starter trotz
vorhandener Workflow-Tour) und ein Legacy-i18n-Block mit unverdeutschten
Strings. Diese sind punktuell, nicht systemisch — das Fundament ist solid.

---

## Aufgaben

<!-- Nummerierung: CR-AUFG-07-01, CR-AUFG-07-02, … -->

> **Hinweis:** CR-AUFG-07-07 bis CR-AUFG-07-24 existieren bereits (siehe
> `ai_operation_inventory.yaml` und `ai-ux-compliance-v2.md`, Status: compliant
> bzw. resolved). Neue Aufgaben beginnen bei CR-AUFG-07-25.

---

### CR-AUFG-07-25 — ChatPanel: strukturierte Fehlermeldung anzeigen statt generische Konstante

**Abschnitt:** §1, §4
**Priorität:** Mittel
**Aufwand:** S
**Status 2025-07-15:** **ERLEDIGT** — `useChat.ts` gibt nun `AIErrorResponse | null` mit `retry`/`isError` zurück; `ChatPanel.tsx` rendert `error.userMessage` + Retry-Button bei `retryable`. Regression-Test `ChatPanel.error.test.tsx` (5 Tests). Commit `3dfd8f27`.

**Problem:**
`ChatPanel.tsx:136` ignoriert die vom `useChat`-Hook berechnete actionable
Fehlermeldung und zeigt stattdessen eine generische Konstante:

```tsx
// ChatPanel.tsx:136 (AKTUELL)
{error && <StatusMessage state="error" message={t("chatPanel.errorConnecting")} />}
```

`useChat.ts:88` setzt korrekt `setError(errResponse.userMessage)` (z.B.
"Dein API-Schlüssel ist ungültig. Überprüfe deine KI-Einstellungen." bei 401),
aber die Komponente verwirft diesen Wert und zeigt `"Verbindungsfehler"`
(`chatPanel.errorConnecting`) — ohne Handlungsempfehlung.

Das widerspricht §16.5 (Error-Message Rule: "[What happened] [What to do]")
für die `chat.free_assistant`-Operation, obwohl der Hook und `mapSSEError`
korrekt arbeiten.

**Lösung:**
```tsx
// ChatPanel.tsx (VORGESCHLAGEN)
{error && (
  <StatusMessage
    state="error"
    message={error}  // ← die actionable userMessage aus useChat
    action={aiOp.isError ? { label: t("aiActions.retry"), onClick: aiOp.retry } : undefined}
  />
)}
```

Die `error`-Variable aus `useChat` enthält bereits die korrekte
`errResponse.userMessage`. Zusätzlich sollte ein Retry-Button angeboten
werden, wenn `errResponse.retryable === true` (erfordert, dass `useChat`
die `AIErrorResponse`-Struktur statt nur des Strings zurückgibt).

**Verifikation:**
- `useChat` gibt `error: AIErrorResponse | null` statt `string | null` zurück.
- `ChatPanel` rendert `error.userMessage` und bei `error.retryable` einen Retry-Button.
- Check 4 (`no hardcoded AI error.message in TSX`) bleibt grün.
- Test: `packages/web/__tests__/ChatPanel.test.tsx` — simuliere 401, erwarte
  "API-Schlüssel"-Meldung, nicht "Verbindungsfehler".

---

### CR-AUFG-07-26 — Consistency: "Ignorieren"/"Resolved"-Markierung für Befunde

**Abschnitt:** §2.3
**Priorität:** Mittel
**Aufwand:** M
**Status 2025-07-15:** **ERLEDIGT** — Backend: Dismiss-API (`POST/GET/DELETE /novels/{id}/kb/consistency/dismiss` + `DismissedFinding`-Modell + Migration `0032_dismissed_findings.py`, 31 Tests). Frontend: `useDismissedFindings`-Hook + `ConsistencyCard` Dismiss-Button + `ConsistencyResults` Filter mit Toggle (31 Tests). Commits `2f15a29f`, `554ac51c`.

**Problem:**
`ConsistencyCheckPanel` / `ConsistencyResults` haben keinen Mechanismus, einen
Befund als "ignorieren" oder "bewusst akzeptiert" zu markieren. Bei jedem
Re-Run (`handleRunCheck`, `ConsistencyCheckPanel.tsx:67-69`) erscheinen
alle Issues erneut — auch solche, die der Nutzer bereits bewusst entschieden hat.

Für wiederholte Consistency-Checks im Schreibprozess ist das frustrierend
(Noise vs. Signal).

**Lösung:**
- Backend: `POST /api/v1/novels/{id}/consistency/issues/{finding_index}/dismiss`
  mit `reason`-Feld (persistiert in DB, novel-scoped).
- Frontend: `ConsistencyCard` erhält einen "Ignorieren"-Button (IconButton
  mit `OctagonX`-Icon), der den API-Call auslöst und die Card ausblendet /
  als "dismissed" markiert.
- `ConsistencyCheckResponse` erhält ein `dismissed_findings: number[]`-Feld;
  `ConsistencyResults` filtert diese heraus (mit Toggle "Ausgeblendete zeigen").
- URL-Param `?showDismissed=1` für Transparenz.

**Verifikation:**
- Dismissed-Issues erscheinen nicht mehr im Default-View.
- Toggle zeigt sie wieder (mit dismissed-Badge).
- Persistenz über Sessions hinweg (DB-backed).

---

### CR-AUFG-07-27 — Legacy-i18n-Block: unverdeutschte Strings im deutschen studio.json entfernen

**Abschnitt:** §4, §7
**Priorität:** Niedrig
**Aufwand:** S
**Status 2025-07-15:** **ERLEDIGT** — 58 unverdeutschte Strings im `kb`-Namespace übersetzt (DE/EN/FR); 2 verwaiste Keys (`kb.aiThinking`, `kb.nextQuestion`) entfernt. i18n-Parity-Check grün. Commit `f2f37ccb`.

**Problem:**
In `packages/i18n/messages/de/studio.json` existiert ein Block unverdeutschter
englischer Strings (alter Interview-Namespace, ~Zeilen 1336-1343):

```json
"nextQuestion": "Next Question",
"submitAnswer": "Submit Answer",
"exitInterview": "Exit Interview",
"interviewProgress": "Question {current}",
"aiThinking": "AI is thinking...",
"yourAnswer": "Type your answer...",
"interviewComplete": "Interview Complete",
```

Dies widerspricht RULE-16 / §5 (German as reference language, i18n required).
Die kanonischen `aiActions.aiThinking` (Zeile 1797 = "KI denkt nach...") sind
korrekt, aber dieser Legacy-Block ist eine Inkonsistenz und potentiell
verwirrend, falls noch Komponenten diese Keys referenzieren.

**Lösung:**
1. Prüfen, ob die Legacy-Keys noch referenziert werden (`rg "interviewComplete|exitInterview|nextQuestion"`).
2. Falls ja: auf kanonische `aiActions.*` / `kb.*`-Keys migrieren.
3. Falls nein: Legacy-Block aus `studio.json` (de/en/fr) entfernen.
4. i18n-Parity-Check sollte sicherstellen, dass keine unverdeutschten
   Strings verbleiben.

**Verifikation:**
- `rg "AI is thinking" packages/i18n/` → 0 Treffer.
- Alle Interview-Strings auf Deutsch.

---

### CR-AUFG-07-28 — Emotionale Intensitätskurve visualisieren (Sentiment-Arc)

**Abschnitt:** §8
**Priorität:** Mittel (Alleinstellungsmerkmal)
**Aufwand:** L
**Status 2025-07-15:** **ERLEDIGT** — Bereits vor der Remediation implementiert. `SentimentArcGraph.tsx` (Recharts LineChart, VAD-Trajektorien über Kapitel) und `EmotionalIntensityCurve.tsx` rendern in `SentimentResults` ab ≥2 analysierten Kapiteln. Keine Änderungen erforderlich.

**Problem:**
Das Backend hat bereits Sentiment-Analyse (`useSentiment.ts`,
`analysis.sentiment`-Namespace). Es gibt jedoch **keine Visualisierung** als
Kapitel-Intensitätskurve — ein Feature, das für Schriftsteller enorm wert
wäre (Pacing-Editing, emotionale Strukturierung, "Show don't tell"-Checks).

Entsprechend `ui-principles.md` §14 ("Future chart types: sentiment arc over
chapter progression (time series)") ist dies bereits als geplantes
ANAL-Feature dokumentiert, aber nicht implementiert.

**Lösung:**
- Recharts `<LineChart>` (bereits im Stack, `ui-principles.md` §14:
  AnalysisChart-Pattern).
- X-Achse: Kapitel-Position (Token-Offset oder Absatz-Index).
- Y-Achse: Sentiment-Intensity (-1.0 bis +1.0 oder normalisiert 0-10).
- Interaktiv: Hover zeigt Text-Snippet an der Position.
- Integration in Editor-Right-Panel (`EditorRightPanelId = "sentiment"`,
  bereits im typed registry `editorRightPanelState.ts` definiert — Slot
  existiert, Panel fehlt).
- Mehrere Kapitel vergleichbar (Overlay oder getrennte Linien).

**Vorhandene Infrastruktur:**
- `useSentiment.ts`-Hook (SSE).
- `EditorRightPanelId` enthält bereits `"sentiment"` (`ui-principles.md` §13.2).
- Recharts bereits für ScoreRadar genutzt (`ui-principles.md` §14).
- Theme-Token-basierte Chart-Styling-Regeln definiert.

**Verifikation:**
- Sentiment-Panel öffnet via Toolbar/Sidebar.
- LineChart rendern mit Theme-Tokens.
- Hover-Tooltip mit Text-Snippet.
- URL-deep-linkbar (`?panel=sentiment`).

---

### CR-AUFG-07-29 — Demo-Projekt mit Beispiel-KB für sofortigen Aha-Moment

**Abschnitt:** §5
**Priorität:** Mittel
**Aufwand:** M
**Status 2025-07-15:** **ERLEDIGT** — `useQuickStart` akzeptiert optionalen `starter`-Parameter; "Mit Demo-Projekt starten"-Button im WizardShell; Empty-State-Guide in `KBEntryList`. Backend-Demo-Starter existierten bereits (`DEMO_FANTASY`, `DEMO_SCIFI`, `DEMO_GERMAN`). Commit `269c8c56`.

**Problem:**
Der Wizard (`WizardShell.tsx`) und Quick-Start (`useQuickStart.ts`) erstellen
ein **leeres Projekt** (`starter: "blank"`, `useQuickStart.ts:37`). Die
`FeatureTour` ist global verdrahtet (`StudioWorkspaceShell.tsx:68`) und
erklärt konzeptionell das Zusammenspiel (Tour-Step 7: "KB → Context → AI",
Step 8: "Storyboard → Chapter → AI", `feature-tour-steps.ts:43-52`). **Aber:**
Der Nutzer kann das Erklärte nicht sofort ausprobieren, da das Projekt leer
ist — es gibt keine Beispiel-KB, keine Beispiel-Characters, kein
Beispiel-Kapitel. Der "wahre" Aha-Moment (KI generiert Text MIT KB-Kontext)
erfordert, dass der Nutzer erst manuell KB-Einträge anlegt.

Für Neueinsteiger ist der Weg vom Onboarding zum ersten sinnvollen
KB-gestützten AI-Erlebnis zu lang.

**Lösung:**
1. **Demo-Starter (neue Option):** Quick-Start erhält einen `starter: "demo"`
   Modus, der ein Projekt mit vorausgefüllter Beispiel-KB erstellt:
   - 2 Beispiel-Characters (Protagonist + Antagonist mit Description/Backstory)
   - 1 Beispiel-Location
   - 1 Beispiel-Kapitel (~500 Wörter) mit @-Mentions der Characters
   - Beispiel-Outline
   Der Nutzer kann sofort "Weiter schreiben" mit KB-Kontext testen.
2. **Leere-State-Guides:** Wenn KB leer ist (keine Entities), zeige Hinweis
   im Worldbuilding-Panel: "Füge Characters hinzu, damit die AI deinen Roman
   kennt" mit CTA zum Assisted-Creation-Flow.
3. **Tour-Step 9 ("before/after demo moment"):** Der bereits definierte
   Tour-Step 9 (`feature-tour-steps.ts:53-57`) sollte den Nutzer aktiv
   dazu bringen, eine AI-Operation (z.B. Continue) auszulösen und den
   Unterschied mit/ohne KB-Kontext zu erleben.

**Vorhandene Infrastruktur (nicht neu bauen):**
- FeatureTour global in `StudioWorkspaceShell` gerendert (9 Steps, i18n `studio.tour.*`).
- `requestFeatureTour()` nach Quick-Start aufgerufen (`useQuickStart.ts:48`).
- KB-Assisted-Creation-Flow vorhanden (`KBAssistedCreationPanel`).
- Backend `setupApi.complete` akzeptiert `starter`-Feld — Erweiterung um
  `"demo"`-Starter mit Seeding-Logik.

**Verifikation:**
- Quick-Start mit `starter: "demo"` erstellt Projekt mit ≥2 KB-Entities.
- Continue/Extend mit Demo-KB liefert明显 bessere Ergebnisse als ohne.
- Leere-KB-State hat erklärende Hinweise mit CTA.
- "Aha-Moment" (KI mit KB-Kontext) innerhalb von 2 Minuten nach Onboarding erlebbar.

---

### CR-AUFG-07-30 — Capability-Basis-Sichtbarkeit in Prompt-Editing UI

**Abschnitt:** §6
**Priorität:** Niedrig-Mittel
**Aufwand:** S
**Status 2025-07-15:** **ERLEDIGT** — `PromptCapabilityHint.tsx` Info-Banner im PromptEditor (sichtbar in View- und Edit-Modus). i18n-Keys in DE/EN/FR. Commit `5b4e0928`.

**Problem:**
Die garantierten Capabilities (`NarrareUniversalRules`, `NarrareMeta`,
`NarrareObservability`) sind architektonisch garantiert und NICHT über die
Cascade anpassbar (cr-00-kontext §5). Die Prompt-Editing-UI macht dies jedoch
nicht explizit sichtbar — der Nutzer sieht nur die anpassbaren Feature-Prompts,
nicht die garantierte Capability-Basis. Ein Hinweis wie „Diese Regeln sind immer
aktiv und können nicht überschrieben werden" fehlt.

**Lösung:**
Im `PromptEditor` (oberhalb der Cascade-Anzeige) einen Info-Hinweis
hinzufügen, der erklärt:
- „Diese Prompts sind anpassbar. Zusätzlich gelten immer garantierte Regeln
  (Narrare-Identität, Observability, Sicherheit), die nicht überschrieben
  werden können."
- Optional: Link zur Dokumentation der Capability-Basis.

**Verifikation:**
- Hinweis ist im `PromptEditor` sichtbar.
- i18n-Key für den Hinweis-Text in DE/EN/FR vorhanden.
- Test: render `PromptEditor`, prüfe dass Hinweis gerendert wird.

---

### CR-AUFG-07-31 — KB-Korruption-spezifische Fehlermeldung

**Abschnitt:** §4
**Priorität:** Niedrig
**Aufwand:** S
**Status 2025-07-15:** **ERLEDIGT** — `aiActions.errorDataCorrupt` i18n-Key + `SyntaxError`-Erkennung in `mapSSEError`. KB-Komponenten profitieren automatisch. Unit-Test hinzugefügt. Commit `97c07f3d`.

**Problem:**
Bei korrupten KB-Daten fällt das System auf generische Meldungen
(`kb.graphLoadFailed` / `kb.sessionCreateFailed`) zurück, die nicht spezifisch
genug sind und keine klare Handlungsempfehlung geben („Was tue ich, wenn meine
KB korrupt ist?").

**Lösung:**
1. Neuen i18n-Key `aiActions.errorDataCorrupt` hinzufügen (DE/EN/FR):
   - DE: „Die Daten konnten nicht gelesen werden. Möglicherweise ist eine
     Datei beschädigt. Überprüfe deine Sicherungen oder kontaktiere den Support."
2. In `mapSSEError` und `mapRestApiError`: spezifische Erkennung von
   Data-Corruption-Signalen (z.B. JSON-Parse-Fehler bei KB-Lade-Responses
   → `errorDataCorrupt`).
3. KB-Komponenten (`KnowledgeGraphView`, `KBAssistedCreationPanel`) nutzen den
   neuen Key bei strukturierten Parse-Fehlern.

**Verifikation:**
- `aiActions.errorDataCorrupt` in DE/EN/FR vorhanden.
- KB-Komponenten zeigen spezifische Meldung bei Parse-Fehlern.
- i18n-Parity-Check bleibt grün.

---

### CR-AUFG-07-32 — Provider-Setup „Quick Setup" / progressive disclosure

**Abschnitt:** §5
**Priorität:** Niedrig-Mittel
**Aufwand:** M
**Status 2025-07-15:** **ERLEDIGT** — `AdvancedAiSettings.tsx` kollabierbare Sektion (native `<details>`) in AiTab. 5 erweiterte Sektionen standardmäßig ausgeblendet. Commit `663ea1e5`.

**Problem:**
`AiTab.tsx` zeigt alle Optionen (Provider, Modelle, Token-Profile, Overrides,
Context-Budget, Timeouts) gleichzeitig. Für Nicht-Techniker ist die Anzahl der
Optionen überwältigend. Es gibt keine „Empfohlen für Anfänger"-Voreinstellung
oder kontextuelle Hilfetexte.

**Lösung:**
1. **Progressive Disclosure:** Standardansicht zeigt nur Wesentliches
   (Provider-Auswahl + API-Key + empfohlenes Modell). Ein „Erweiterte
   Einstellungen"-Akkordeon blendet Token-Profile, Overrides, Context-Budget
   und Timeouts aus.
2. **„Empfohlen"-Badge:** Pro Provider ein Modell mit „Empfohlen für
   Einsteiger" markieren (kuratierte Liste im `ModelSelector`).
3. **Kontextuelle Hilfe:** Inline `?`-Tooltips pro Feld mit
   verständlichen Erklärungen.

**Verifikation:**
- Standardansicht zeigt nur Basis-Felder.
- Erweiterte Einstellungen sind aufklappbar.
- „Empfohlen"-Badge auf mindestens einem Modell pro Provider.
- Tooltips für alle Hauptfelder.

---

### CR-AUFG-07-33 — REST error mapper: `error.message`-Leak fixen

**Abschnitt:** §4, §7
**Priorität:** Mittel
**Aufwand:** S
**Status 2025-07-15:** **ERLEDIGT** — `mapRestApiError` delegiert nun vollständig an `mapSSEError` — kein `error.message`-Leak mehr. 7 Regression-Tests + 2 Test-Fixes. Commit `06641a77`.

**Problem:**
`mapRestApiError` (`ai-rest-error.ts:30-38`) verwendet für reguläre
`Error`-Instanzen `userMessage: error.message` — der rohe Backend-Fehlerstring
wird direkt als `userMessage` gesetzt. Dies widerspricht §16.5: alle
AI-Fehlermeldungen sollen strukturierte i18n-Keys mit Handlungsempfehlung
verwenden, niemals rohe Fehlermeldungen. Der SSE-Mapper (`mapSSEError`) macht
dies korrekt; der REST-Pfad umgeht diese Logik.

**Lösung:**
`mapRestApiError` so anpassen, dass reguläre Fetch-Fehler auf die gleichen
i18n-Keys gemappt werden wie in `mapSSEError`:
- Network-Fehler (fetch failed) → `aiActions.errorConnection`
- Timeout → `aiActions.errorTimeout`
- Unbekannt → `aiActions.errorDefault`
Das rohe `error.message` wird weiterhin im `cause`-Feld für Logging
erhalten, aber NICHT als `userMessage` gerendert.

**Verifikation:**
- `mapRestApiError` verwendet i18n-Keys, nicht `error.message`.
- Unit-Test: regulärer `Error("fetch failed")` → `aiActions.errorConnection`.
- Check 4 („no hardcoded AI error.message") bleibt grün.

---

### CR-AUFG-07-34 — Interview Q&A-Verlauf mit Suche

**Abschnitt:** §3
**Priorität:** Niedrig
**Aufwand:** M
**Status 2025-07-15:** **ERLEDIGT** — `InterviewHistory.tsx` + `useInterviewHistory`-Hook + `InterviewLoadingState.tsx` (RULE-04). Q&A-Paare mit Keyword-Suche. Commit `f384655c`.

**Problem:**
Interview-Fragen sind nicht filterbar/suchbar im Nachhinein (lineare Q&A,
kein Timeline-View). Die Q&A-Daten sind bereits DB-gestützt (resume-Sessions),
aber es gibt keine UI zum Durchsuchen vergangener Fragen.

**Lösung:**
1. **„Interview-Verlauf"-View:** Nach Interview-Abschluss eine scrollbare
   Timeline aller Q&A-Paare (Frage + Antwort + resultierendes Feld).
2. **Suche/Filter:** Nach Keyword innerhalb der Q&A-Historie.
3. **Re-Edit:** Klick auf eine vergangene Antwort springt zum entsprechenden
   Feld für Nachbearbeitung.

**Verifikation:**
- Verlauf-View zeigt alle Q&A-Paare nach Interview-Abschluss.
- Suche filtert Questions/Answers nach Keyword.
- Klick auf Antwort navigiert zum Feld.

---

### CR-AUFG-07-35 — KB-Editor progressive disclosure / Guided Mode

**Abschnitt:** §3
**Priorität:** Niedrig
**Aufwand:** M
**Status 2025-07-15:** **ERLEDIGT** — `KBFieldLabel.tsx` (Help-Tooltip) + `KBMoreFields.tsx` (progressive Disclosure) in `KBEntryTemplateFields` und `KBFlatEditor`. Commit `4c3cdc06`.

**Problem:**
`KBDetailPanel`/`KBEntryDetail` zeigt für 7 Entity-Typen alle Felder
gleichzeitig. Für Nicht-Techniker ist dies überwältigend. Es gibt keinen
„Guided Mode" für manuelles Ausfüllen (nur über den Assisted/Interview-Weg).

**Lösung:**
1. **Feld-Gruppierung:** Felder in logische Sektionen organisieren
   (Basis, Details, Beziehungen).
2. **Progressive Disclosure:** Pflichtfelder + Description zuerst; optionale
   Felder hinter „Weitere Felder anzeigen".
3. **Inline-Hilfe:** Pro Feld ein `?`-Tooltip mit Erklärung.
4. **„Nur Pflichtfelder"-Toggle.**

**Verifikation:**
- Pflichtfelder sind ohne Scroll sichtbar.
- Optionale Felder sind aufklappbar.
- Tooltips für alle Felder vorhanden.

---

### CR-AUFG-07-36 — Prompt-Editing „Einfach"-Modus

**Abschnitt:** §6
**Priorität:** Niedrig
**Aufwand:** M-L
**Status 2025-07-15:** **ERLEDIGT** — `usePromptEditorMode.ts` + `PromptEditorModeToggle.tsx` + `PromptCapabilityHint.tsx`. Einfach/Experte-Toggle mit localStorage-Persistenz. Commit `cd6a0d28`.

**Problem:**
Prompt-Editing setzt Verständnis von Template-Variablen, Cascade-Logik und
Provider-Konfiguration voraus. Die UI ist funktional, aber für Nicht-Entwickler
eine Power-User-Funktion. Es gibt keine „Einfach"-Ansicht.

**Lösung:**
1. **„Einfach"/„Experte"-Toggle:** Einfach-Modus zeigt nur Prompt-Text +
   Live-Vorschau + Reset. Experte-Modus zeigt Variablen, Cascade, Live-Test,
   Diff, Historie.
2. **Natürliche Prompt-Beschreibungen:** Statt technischem Key
   (`kb.enhance.character.description`) verständlichen Titel anzeigen
   („Beschreibung eines Characters verbessern").
3. **Vordefinierte Variationen:** Kuratierte alternative Formulierungen zur
   Auswahl statt Raw-Text-Editing.

**Verifikation:**
- Toggle zwischen Einfach/Experte funktional.
- Einfach-Modus zeigt nur Prompt-Text + Preview + Reset.
- Natürliche Beschreibungen für alle Prompts.

---

## Accepted Risks

**Accepted Risk (2025-07-14) — B5: Continue hat keine Diff-Ansicht:**
Continue ist ein Append-Modell (Text wird nach Cursor eingefügt, kein Replace).
Für Continue ist Diff weniger relevant als für Rewrite (welches Selection
ersetzt). Der vorläufige AI-Text wird mit `.ai-generated-pending`-Highlight
visuell markiert, was ausreichenden Kontrast bietet. Diff-Ansicht für Continue
bleibt als optionale Enhancement, ist aber nicht als Aufgabe priorisiert.

**Accepted Risk (2025-07-14) — B6: Continue hat keine explizite Partial-Accept UX-Action:**
Teilweises Übernehmen (z.B. nur 2 von 3 Sätzen) ist nicht als explizite
UX-Action implementiert. Der Nutzer akzeptiert den gesamten generierten Text
und editiert dann manuell (natürlicher Workflow, durch TipTap Undo abgesichert).
Modify-Detection (`getPendingModification`) erkennt, ob der Nutzer den AI-Text
verändert hat, bevor er akzeptiert. Ghost-Text bietet bereits wortweises
Übernehmen via ArrowRight. Eine dedizierte Partial-Accept-Action würde
signifikante ProseMirror-Komplexität (Mark-Splitting, Sub-Range-Tracking) für
marginalen Nutzen hinzufügen.

---

## Abschluss-Status

**Review:** CR-07 – UI/UX & AI-Interaktionsqualität
**Datum:** 2025-07-15
**Branch:** `chore/review-07-ux-fixes`

### Aufgaben-Übersicht

| Aufgabe | Status | Aufwand | Evidence |
|---------|--------|---------|----------|
| CR-AUFG-07-25 | ✅ Resolved | S | `useChat` + `ChatPanel` actionable error + retry, 5 Tests, Commit `3dfd8f27` |
| CR-AUFG-07-26 | ✅ Resolved | M | Dismiss-API backend + frontend, 62 Tests, Commits `2f15a29f`/`554ac51c` |
| CR-AUFG-07-27 | ✅ Resolved | S | 58 i18n-Strings übersetzt, 2 Orphans entfernt, Commit `f2f37ccb` |
| CR-AUFG-07-28 | ✅ Resolved (pre-existing) | L | `SentimentArcGraph` + `EmotionalIntensityCurve` bereits implementiert |
| CR-AUFG-07-29 | ✅ Resolved | M | Demo-Starter in Quick-Start + Empty-State-Guide, Commit `269c8c56` |
| CR-AUFG-07-30 | ✅ Resolved | S | Capability-Basis-Hinweis im PromptEditor, Commit `5b4e0928` |
| CR-AUFG-07-31 | ✅ Resolved | S | `errorDataCorrupt`-Mapping für KB-Korruption, Commit `97c07f3d` |
| CR-AUFG-07-32 | ✅ Resolved | M | Progressive Disclosure in AiTab, Commit `663ea1e5` |
| CR-AUFG-07-33 | ✅ Resolved | S | REST error mapper `error.message`-Leak fix, Commit `06641a77` |
| CR-AUFG-07-34 | ✅ Resolved | M | Interview Q&A-Verlauf mit Suche, Commit `f384655c` |
| CR-AUFG-07-35 | ✅ Resolved | M | KB-Editor progressive Disclosure + Tooltips, Commit `4c3cdc06` |
| CR-AUFG-07-36 | ✅ Resolved | M-L | Prompt-Editor Einfach/Experte-Modus, Commit `cd6a0d28` |

### Accepted Risks

- **B5:** Continue ohne Diff-Ansicht — Append-Modell, Diff weniger relevant.
- **B6:** Continue ohne Partial-Accept — Accept→Edit ist natürlicher Workflow.

### Neue Aufgaben aus Gap-Detection

7 neue Aufgaben (CR-AUFG-07-30 bis CR-AUFG-07-36) aus Prose-Gap-Detection erstellt und alle implementiert.

### Prevention-Maßnahmen

Keine strukturellen Prevention-Maßnahmen erforderlich — alle Ursachen waren One-Offs (isolierte Befunde) oder Feature-Arbeit, keine wiederkehrenden Muster.

### Zusammenfassung

12 von 12 Aufgaben resolved. 2 Accepted Risks dokumentiert. Alle Pre-Commit-Hooks (Architecture, RULE-04, i18n, TypeScript, Biome) bei jedem Commit grün.
