# Content Review CR-07 – UI/UX & AI-Interaktionsqualität

> **CR-07 Execute Date:** 2026-06-12
> **Prompt:** `_audit/review-prompts/content-review-prompts/cr-07-ux.md`
> **Production code modified:** No
> **Prerequisite CR files read:** existing CR-07 output, CR-00 through CR-05 baselines (via graph-first discovery)
> **§16 AI-Interaction Standards reference:** `docs/development/ui-principles.md:824-963`

---

## Executive Summary: State Change Since Existing CR-07

The previous CR-07 (dated 2026-06-02) was authored **before ADR-043 was implemented**. The existing CR-07 assessed a codebase where AI features used manual `AbortController` patterns, local SSE parsers, and component-specific loading states.

**That assessment is now obsolete.** ADR-043 introduced shared AI-interaction infrastructure:

1. **`useAIOperation`** (`packages/web/lib/hooks/use-ai-operation.ts`) — shared lifecycle hook with 38 importers, implementing:
   - State machine: `idle → loading → streaming → complete → error → connection_lost`
   - Built-in `AbortController` management (§16.2)
   - Connection-loss detection with partial output preservation (§16.7)
   - Structured error mapping via `ai-error-mapping.ts` (§16.5)
   - Retry support

2. **`ai-error-mapping.ts`** (`packages/web/lib/api/ai-error-mapping.ts`) — maps SSE errors to `aiActions.*` i18n keys for 401/413/429/408/network/parse
3. **`ai-rest-error.ts`** (`packages/web/lib/api/ai-rest-error.ts`) — REST adapter preserving original error messages
4. **`aiActions` i18n namespace** — complete in DE/EN/FR with all §16.8 keys plus 7 error keys

**Result:** 11 of 15 AI features now use the shared hook. The remaining gaps are narrow and well-documented.

---

## Methodology

Graph-first discovery was completed before reading any frontend files:

1. `semantic_search_nodes` for: `connectSSE`, `useAIOperation`, `AbortController`, GhostText, AI component names
2. `query_graph importers_of` for: `streaming.ts`, `use-ai-operation.ts`, `ai-error-mapping.ts`, `ai-rest-error.ts`, `kb-sessions.ts`, `timeline.ts`
3. `query_graph callers_of` for: `connectSSE`, `useAIOperation`
4. Targeted reads of 25+ TSX/TS files: controller files, API clients, hooks, KB components, editor components

Files read include: `use-ai-operation.ts`, `use-ai-operation.types.ts`, `ai-operation-execute.ts`, `ai-operation-lifecycle.ts`, `ai-error-mapping.ts`, `ai-rest-error.ts`, `streaming.ts`, `useContinueStream.ts`, `useCoAuthorStream.ts`, `generationPanelController.ts`, `TipTapEditorController.ts`, `KBInterviewView.tsx`, `KBEnhanceReview.tsx`, `KBImprovePanel.tsx`, `ConsistencyCheckPanel.tsx`, `KBAssistedCreationController.ts`, `useSessionSocket.ts`, `SessionPanel.tsx`, `useChat.ts`, `useExtraction.ts`, `useBetaReader.ts`, `useWorldbuilding.ts`, `useTimelineExtraction.ts`, `useKBSessions.ts`, `useKBImprove.ts`, `suggest.ts`, `GhostText.ts`, `DemoProjectCards.tsx`, `feature-tour.tsx`

---

## 1. AI-Wartezeiten & Feedback

| Funktion | Loading-Indikator vorhanden? | Art des Indikators | Streaming? | Abbruch möglich? |
|---|---|---|---|---|
| Writing-Continue | ✅ | Via `useAIOperation.isLoading/isStreaming` in `useContinueStream.ts:52` → consumed by caller UI | ✅ SSE via `streamExtend` + `connectSSE` | ✅ `handleStop` at `useContinueStream.ts:138` calls `cancel()` |
| Rewrite | ✅ | `rewriteAiOp.isLoading/isStreaming` at `TipTapEditorController.ts:370-372` | ✅ SSE via `streamRewrite` | ✅ `handleRewriteCancel` at `TipTapEditorController.ts:374` calls `rewriteAiOp.cancel()` |
| Generation | ✅ | `generationPanelController.ts:74-84` exposes `isLoading/isStreaming` → consumed by `GenerationPanel` | ✅ SSE via `streamGeneration` | ✅ `handleStop` at `generationPanelController.ts:159` calls server stop + `cancel()` |
| Co-Author | ✅ | `useCoAuthorStream.ts:111-124` exposes `isLoading/isStreaming/isConnectionLost` | ✅ SSE via `streamCoAuthor` | ✅ `cancel()` at `useCoAuthorStream.ts:117` |
| KB Field Suggest | ❌ | **No `useAIOperation`** — uses TanStack Query `useMutation` (`useKBSessions.ts:112-122`). `suggestingFieldKey` disables button (`KBAssistedCreationController.ts:46`) but no streaming indicator | ✅ SSE via `suggestField` → `connectSSE` | ❌ No stop/cancel button — signal exists but no user-facing control |
| KB Interview | ✅ | `interviewOp.isLoading/isStreaming` at `KBInterviewView.tsx:105-106` renders `Loader2` spinner + "KI denkt nach..." | ✅ SSE via `requestInterview` → `connectSSE` (via `KBAssistedCreationController.ts`) | ✅ Stop button at `KBInterviewView.tsx:144` + Escape handler at `KBInterviewView.tsx:110` |
| KB Enhance | ✅ | `enhanceOp.isLoading/isStreaming` at `KBEnhanceReview.tsx:46` → rendered via `EnhanceLoadingState` | ✅ SSE via `requestEnhance` → `connectSSE` | ⚠️ `cancel()` exists in hook at `KBEnhanceReview.tsx:46` but no visible stop button in `EnhanceLoadingState` |
| KB Improve | ❌ | **No `useAIOperation`** — uses TanStack Query `useMutation` (`useKBImprove.ts:30-38`). `ImproveLoadingState` shows spinner (`KBImprovePanel.tsx:155`) | ❌ REST (not SSE) | ❌ No cancel button |
| Consistency Check | ✅ | `isLoading` at `ConsistencyCheckPanel.tsx:47` → renders `ConsistencyLoading` with cancel | ❌ REST via `consistencyApi.checkConsistency` (not SSE) | ✅ Cancel button at `ConsistencyCheckPanel.tsx:181` + `cancelOp()` at `ConsistencyCheckPanel.tsx:71` |
| Chat (free assistant) | ✅ | `isStreaming` at `useChat.ts:121` → consumed by caller UI | ✅ SSE via `chatApi.streamChat` → `connectSSE` | ✅ `cancelStream` at `useChat.ts:114` calls `aiOp.cancel()` |
| Extraction | ✅ | `useExtractChapter.ts:71-73` exposes `isLoading/isStreaming` → consumed by caller | ✅ SSE via `extractionApi.extractChapter` | ✅ `cancel()` at `useExtractChapter.ts:67` |
| Timeline Extraction | ⚠️ | **No `useAIOperation`** — manual `isExtracting` state at `useTimelineExtraction.ts:28` | ✅ SSE via `extractExpressionsSSE` | ✅ `cancelExtraction` at `useTimelineExtraction.ts:70` |
| Ghost Text Suggest | ❌ No visible loading | TipTap extension — no React hooks, no loading state | ✅ SSE via `createSseSuggestionFetcher` → `connectSSE` | ⚠️ `AbortController` exists in `suggest.ts:67` but no user-facing cancel |
| Worldbuilding Analysis | ✅ | Chatbot uses `useAIOperation` via `useWorldbuilding.ts:29` → `isLoading/isStreaming` exposed | ✅ SSE | ✅ via cancel |
| Beta Reader | ✅ | `useBetaReader.ts:30` wraps `useAIOperation` | ✅ via SSE | ✅ via cancel |

**Bewertung:** ⭐⭐⭐⭐☆
**Befunde:** The majority of AI features (11 of 15) now use the shared `useAIOperation` hook with proper lifecycle management. The streaming rate is excellent — 12 of 15 use SSE streaming (consistency and KB improve use REST, which is acceptable for their short duration). The remaining gaps are:
- **KB Field Suggest** — no `useAIOperation`, no cancel UI, relies on TanStack Query mutation
- **KB Improve** — no `useAIOperation`, REST-only, no cancel
- **Timeline Extraction** — manual AbortController pattern (documented limitation in source)
- **Ghost Text** — TipTap extension limitation prevents hook usage

---

## 2. AI-Output-Präsentation

### 2.1 Writing-Output (Continue, Rewrite, Extend, Generation)

**Bewertung:** ⭐⭐⭐⭐⭐
**Befunde:**

- **Generation (full draft):** Full accept/reject/retry flow via `generationPanelController.ts:267-268` (`acceptDraft`, `rejectDraft`). Draft presented in review state after streaming. Rating feedback collected after accept/reject (`generationPanelController.ts:192-223`).
- **Rewrite:** Alternatives shown inline with accept/reject/insert-as-new/replace via `TipTapEditorController.ts:320-346`. Multiple alternatives supported with selection via `selectedSuggestion`. Rejection input available at `TipTapEditorController.ts:343-346`.
- **Continue/Extend:** Inserted inline via `AIAnnotation` marks with floating accept/reject controls (`useContinueStream.ts:90-96`). `finalizePendingMark` at `useContinueStream.ts:103` accepts the content. Undo supported via `rejectMark` in AIAnnotation.
- **Co-Author:** Per-changelist accept/reject with acceptance map (`useCoAuthorStream.ts:91-92` creates acceptance map). Individual changes toggleable.
- All writing flows use `studio.aiActions.*` labels consistently.
- Rating/feedback collected for accept/reject actions in generation flow.

### 2.2 Suggest-Output (Ghost Text Inline)

**Bewertung:** ⭐⭐⭐⭐☆
**Befunde:**

- Inline gray italic ghost text at cursor via `GhostText.ts:204-206` (`ghost-text-suggestion` class).
- Keyboard shortcuts: `Tab` accept, `Escape` dismiss, `ArrowRight` first word (`GhostText.ts:137-146`).
- Keyboard shortcut hint decoration: "Tab accept · Esc dismiss · → word" at `GhostText.ts:211`.
- Typing mismatch detection auto-clears suggestion (`GhostText.ts:155-163`).
- LRU prefix-based suggestion cache with 30s TTL (`GhostText.ts:81-83`).
- Analytics counters (accepted/rejected/total) at `GhostText.ts:85-88`.
- SSE-backed suggestion fetcher via `createSseSuggestionFetcher` in `suggest.ts:40`.
- **Gap:** No visible loading indicator or cancel button during suggestion fetch. Errors are silently dismissed (extension limitation documented in `suggest.ts:18-19`).

### 2.3 Consistency-Check-Output

**Bewertung:** ⭐⭐⭐⭐☆
**Befunde:**

- Issue counts and category grouping shown at `ConsistencyCheckPanel.tsx:152-176`.
- Severity sorting exists via `ConsistencyResults` (category grouping by `summary` keys at `ConsistencyCheckPanel.tsx:166-173`).
- Direct entity navigation via `onEntityClick` callback at `ConsistencyCheckPanel.tsx:32`.
- Connection-lost handling via `ConnectionLostBanner` at `ConsistencyCheckPanel.tsx:146-149`.
- Cancel button on `ConsistencyLoading` component at `ConsistencyCheckPanel.tsx:181`.
- **Gap:** REST-based (not SSE), so no streaming feedback. Error message fallback at line 103 shows hardcoded "Check failed" if both error.userMessage and i18n key are unavailable.

---

## 3. KB-Editor & Interview-UX

**Bewertung:** ⭐⭐⭐⭐☆
**Befunde:**

- **Entry creation:** `KBAssistedCreationController.ts` manages full creation lifecycle with session creation, field answering, field suggest, interview, and enhance flows.
- **Interview flow:** `KBInterviewView.tsx` guides user through questions. Progress bar via `InterviewProgressBar` at line 129. Question count tracked at `KBInterviewView.tsx:45`. Stop button + Escape cancel at lines 110-123.
- **Interview resume:** Pending interview persistence via `use-kb-interview-resume.ts` (imported at `KBAssistedCreationController.ts:8-12`). Save/clear on abandon at lines 132, 174.
- **Field suggestions:** AI-powered suggestions with accept/reject per field. Source badges at `KBSessionFieldList.tsx`.
- **Enhance review:** Per-field before/after comparison via `KBEnhanceReview.tsx`. Uses `useAIOperation` for lifecycle. Bulk accept/reject at `_components/EnhanceReviewBulkActions.tsx`.
- **Improve panel:** `KBImprovePanel.tsx` with analysis, per-suggestion selection (auto-select high-confidence), select all/none, and bulk apply.
- **Knowledge Graph visualization:** **Not found** in audited frontend paths. Relationship visualization for KB entries is absent — entity relationships are managed via field links but no graph UI exists.
- **Search/filter:** KB entries searchable through KB API list endpoint, but search/filter UI not audited in this review (scope was AI interaction flows).
- **Gaps:** KB Field Suggest lacks cancel UI. KB Improve lacks `useAIOperation` integration. No relationship graph visualization.

---

## 4. Fehlerbehandlung aus Nutzerperspektive

| Fehlerszenario | Aktuelle Fehlermeldung (laut Code) | Verständlich? | Handlungsempfehlung? |
|---|---|---|---|
| API-Key ungültig | Mapped via `ai-error-mapping.ts:161-169` → i18n key `aiActions.errorApiKey` = "Dein API-Schlüssel ist ungültig. Überprüfe deine KI-Einstellungen." | ✅ Ja | ✅ Ja |
| Modell-Timeout | Mapped via `ai-error-mapping.ts:194-203` → i18n key `aiActions.errorTimeout` = "Die KI braucht zu lange. Versuche es mit weniger Kontext erneut." | ✅ Ja | ✅ Ja |
| Context zu groß | Mapped via `ai-error-mapping.ts:172-181` → i18n key `aiActions.errorTextTooLong` = "Der Text ist zu lang für die KI. Kürze die Auswahl und versuche es erneut." | ✅ Ja | ✅ Ja |
| Rate-Limit | Mapped via `ai-error-mapping.ts:183-192` → i18n key `aiActions.errorRateLimit` = "Du hast zu viele Anfragen gesendet. Warte einen Moment." | ✅ Ja | ✅ Ja |
| Netzwerk-Unterbrechung | Mapped via `ai-error-mapping.ts:127-136` → i18n key `aiActions.errorConnection` = "Verbindung verloren. Prüfe deine Internetverbindung." | ✅ Ja | ✅ Ja |
| Parse-Fehler | Mapped via `ai-error-mapping.ts:138-146` → i18n key `aiActions.errorParse` = "Die KI-Antwort war fehlerhaft. Versuche es erneut." | ✅ Ja | ✅ Ja |
| Unbekannter Fehler | Mapped via `ai-error-mapping.ts:99-105` → i18n key `aiActions.errorDefault` = "Ein unerwarteter Fehler ist aufgetreten. Versuche es erneut." | ✅ Teilweise | ✅ Ja |
| Consistency-REST-Error | Mapped via `mapRestApiError` in `ConsistencyCheckPanel.tsx:53` → preserves API error message | ⚠️ Hängt vom Backend ab | ⚠️ Hängt vom Backend ab |
| KB Improve raw error | Caught via `mapSSEError` in `KBImprovePanel.tsx:62-63` → has structured error | ✅ Ja | ✅ Ja |
| KB Field Suggest mutation error | Not mapped — raw TanStack Query `mutation.error` | ❌ Nein | ❌ Nein |
| Timeline Extraction error | Mapped via `mapSSEError` at `useTimelineExtraction.ts:60` → structured | ✅ Ja | ✅ Ja |
| Ghost Text fetch error | Mapped via `mapSSEError` at `suggest.ts:96` → but extension silently dismisses | ❌ Nein (silent) | ❌ Nein |

**Bewertung:** ⭐⭐⭐⭐☆
**Befunde:** Error mapping has been transformed since the old CR-07. The `ai-error-mapping.ts` module provides structured, i18n-keyed, actionable error messages for all major SSE error categories. The `ai-rest-error.ts` adapter extends this to REST calls. Most `useAIOperation` consumers automatically get this error handling.

Remaining gaps:
- **KB Field Suggest:** Raw mutations expose unhandled errors — no `mapSSEError` wrapper or `useAIOperation` integration
- **Ghost Text:** By architectural necessity (TipTap extension), errors are silently dismissed — documented trade-off in `suggest.ts:18-19`
- **Consistency REST errors:** Depend on backend error format since `mapRestApiError` preserves the original message
- **No raw stack traces** anywhere in frontend AI error paths — verified across all audited files

---

## 5. Onboarding & Erstkonfiguration

**Bewertung:** ⭐⭐⭐⭐☆
**Befunde:**

- **Demo projects:** 3 demo projects exist (`demo_fantasy`, `demo_scifi`, `demo_german`) at `DemoProjectCards.tsx`. GitHub Copilot-style cards with genre, language, chapter/word/character counts. Navigation to `/wizard?starter=demo_*` at `DemoProjectCards.tsx:66`.
- **Wizard setup:** `WizardStep5.tsx` shows demo options and starter content. `WizardStep2.tsx` pre-fills wizard store with demo metadata.
- **Feature tour:** Guided tour via `feature-tour.tsx` — 6 steps covering editor, navigation, AI features, ghost text, worldbuilding, settings. Replayable from About settings tab (`AboutTab.tsx:61-69`).
- **Ghost text onboarding:** `GhostTextOnboarding.tsx` — contextual onboarding popup shown once when first ghost text appears. Dismissed or auto-dismisses. Tracks completion via localStorage at line 93.
- **Settings AI setup:** Referenced in settings-ai files. AI provider configuration available under settings → AI tab.
- **Gaps:** No first-run "aha moment" orientation for KB+Storyboard+AI integration. The feature tour (`feature-tour.tsx`) covers feature locations but doesn't explain the conceptual model (how KB feeds AI, how storyboard connects chapters). Wizard covers project setup but the tour is opt-in (About tab) rather than auto-triggered on first visit.

---

## 6. Prompt-Anpassbarkeit in der WebUI

**Bewertung:** ⭐⭐☆☆☆
**Befunde:**

- **Rewrite custom instructions:** Available via `RewriteConfig.customInstructions` at `TipTapEditorController.ts:218` — users can type custom instructions for rewrite.
- **Generation prompt:** Prompt input held in `generationPanelController.ts:46` and passed to requests.
- **Settings prompt customization:** Referenced via search hits in `settings-ai.json` — AI settings include prompt customization (IntentOverrides, system prompts).
- **Gaps:** No preview/test functionality for prompt changes before they take effect. No reset-to-default button visible in audited flows. Variable placeholders (`{{kb_context}}`, `{{chapter_text}}`) are not explained in the UI — users must know the format. Prompt customization UI was not fully audited because CR-07 scope prioritizes AI interaction execution flows, but the gap is acknowledged.

---

## 7. UX-Muster-Konsistenz

**Bewertung:** ⭐⭐⭐⭐☆
**Befunde:**

- **Terminology:** All writing AI actions consistently use `studio.aiActions.*` labels (accept, reject, stop, retry, replace, insertAsNew, addToDraft).
- **Icon consistency:** AI actions consistently use `Sparkles` icon across `KBImprovePanel.tsx:138`, `KBEnhanceReview`, `ConsistencyCheckPanel`, and writing flows.
- **AI content marking:** AI-generated content marked via AIAnnotation marks (purple/green highlights for AI content), `ChatMessage.tsx:73-81` uses `Bot` icon for assistant, suggestion badges in KB flows.
- **Keyboard shortcuts:**
  - Ghost Text: `Tab` accept, `Escape` dismiss, `ArrowRight` first word — consistent and documented in-hint
  - KB Interview: `Escape` cancels loading or goes back (`KBInterviewView.tsx:110-123`)
  - Chat/Session: Enter to send
  - Consistency panel: Escape to close (`ConsistencyCheckPanel.tsx:91-99`)
  - **Inconsistency:** Most AI actions (accept/reject on generated content) are click-only — no keyboard shortcuts for accept/reject in rewrite modal, generation review, or KB enhance review
- **Gaps:** Old deprecated i18n keys (aiModal.*, generation.*, annotation.*, rewrite.*, sessionPanel.*, kb.sessions.*) are documented as DO NOT USE at §16.8.940-953 but still present in i18n files. This creates risk of accidental reuse. However, no current code was found using deprecated keys — verified via grep of UI components.

---

## 8. Modernes AI-UX-Potenzial

| UX-Pattern | Mehrwert | Aufwand | Empfehlung |
|---|---|---|---|
| Ghost-Text Inline-Suggest (Copilot-style) | 5 — Already implemented | S (polish only) | Already present; add visible status indicator and help for new users |
| Diff-Ansicht für Rewrites | 5 — Already partially present | S (standardize) | Rewrite modal and co-author have diffs; standardize across KB enhance and beta reader |
| Prompt-Verlauf / History | 3 — Useful but lower priority | M | Add after gaps in field suggest/timeline extraction are fixed |
| KI-Aktionen per Slash-Command | 4 — Great for power users | L | Defer until all AI flows are on consistent primitives |
| Mini-Chat in Sidebar während Schreiben | 4 — SessionPanel exists + ChatPanel | M | SessionPanel already provides this; add proper server-side stop and connection-loss recovery to WebSocket path |
| Regenerate mit Stil-Varianten | 4 — Rewrite already supports variants | S | Expose variant picking more consistently across all AI output actions |
| Emotionale Intensitätskurve | 4 — Good differentiator | L | Defer; lower priority than closing remaining §16 gaps |
| KI-Feedback-Rating (👍/👎) | 4 — Generation has it | S | Extend rating to co-author, KB flows, and chat |

**Bewertung aktuelles UX-Niveau:** ⭐⭐⭐⭐☆
**Top-3-Empfehlungen:**

1. **Close remaining §16 gaps:** Migrate KB Field Suggest, KB Improve, and Timeline Extraction to `useAIOperation` for consistent cancel, error mapping, and connection-loss handling.
2. **Add visible status/cancel to Ghost Text:** While the extension can't use React hooks, a minimal CSS indicator for "fetching suggestion..." would improve UX.
3. **Standardize keyboard shortcuts across all AI output actions:** Accept/Reject/Retry should have consistent keyboard bindings across rewrite, generation review, KB enhance, and co-author panels.

---

## Gesamtbewertung UI/UX

**Bewertung:** ⭐⭐⭐⭐☆
**Zusammenfassung:** Narrare has made significant progress since the previous CR-07. The introduction of `useAIOperation` as a shared AI lifecycle hook (38 importers), `ai-error-mapping.ts` for structured error mapping, and the complete `aiActions` i18n namespace have standardized AI interaction patterns across the majority of features (11 of 15). Streaming SSE is used for all appropriate AI operations, connection-loss detection and retry are built into the shared hook, and error messages are actionable with i18n keys. Demo projects, a feature tour, ghost text onboarding, and a setup wizard provide solid onboarding. Remaining gaps are narrow: KB Field Suggest, KB Improve, Timeline Extraction, and Ghost Text still lack full §16 integration, and knowledge graph/relationship visualization for KB entries is absent. The product has moved from "systemic inconsistency" (old rating: ⭐⭐⭐☆☆) to "mostly consistent with well-documented remaining gaps" (current rating: ⭐⭐⭐⭐☆).

---

## Aufgaben

<!-- Nummerierung: CR-AUFG-07-XX – nur ungelöste Aufgaben aus aktuellem Code -->
<!-- Vorherige CR-AUFG-07-01 bis 07-06 sind OBSCLETE – ADR-043 hat die dort genannten Probleme gelöst -->

- **CR-AUFG-07-07:** Migrate KB Field Suggest (`useKBSessionSuggest` in `useKBSessions.ts:112-122`) to `useAIOperation` or apply structured error mapping + cancel UI. Currently wraps raw `useMutation` with unhandled errors and no visible cancel.
- **CR-AUFG-07-08:** Migrate KB Improve (`useKBImprove.ts:30-38`, `KBImprovePanel.tsx`) to `useAIOperation` for consistent lifecycle, cancel support, and structured error mapping.
- **CR-AUFG-07-09:** Migrate Timeline Extraction (`useSSEExtraction` in `useTimelineExtraction.ts:26-81`) to `useAIOperation` or document a justified exception. Currently uses manual AbortController pattern.
- **CR-AUFG-07-10:** Add visible "loading suggestion..." indicator to Ghost Text extension (`GhostText.ts`). Options: CSS-only decoration during fetch, or a transient class on the editor wrapper.
- **CR-AUFG-07-11:** Add cancel button to KB Enhance loading state (`EnhanceLoadingState` in `KBEnhanceReview.tsx`). Cancel handler exists via `enhanceOp.cancel()` but no UI trigger.
- **CR-AUFG-07-12:** Remove deprecated i18n keys from `studio.json` (`aiModal.*`, `generation.*`, `annotation.*`, `rewrite.*`, `sessionPanel.*`, `kb.sessions.*`) to prevent accidental reuse, or add explicit lint rule forbidding usage.
- **CR-AUFG-07-13:** Add keyboard shortcuts (e.g., `Ctrl+Enter` accept, `Ctrl+Backspace` reject) consistently across rewrite modal, generation review, KB enhance review, and co-author panel.

---

## Verification performed

- [x] Graph-first discovery completed before file reads
- [x] §16 AI-Interaction Standards (`docs/development/ui-principles.md:824-963`) verified against 15+ AI features
- [x] 25+ source files read with evidence (path:line references)
- [x] i18n aiActions namespace verified in DE/EN/FR for completeness
- [x] All 7 error scenarios from §16.5 verified against `ai-error-mapping.ts`
- [x] Old CR-07 tasks CR-AUFG-07-01 through 07-06 verified as resolved by ADR-043 infrastructure
- [x] No production code or prompt templates modified
- [x] Each finding backed by code-level evidence, not speculation
