# 05 — AI Toolbar Batch 1 (audit) — RESULTS

Env: web :3001 / API :8000 (pydantic-ai TestModel via ollama-test-model), chapter 1
"The Compass Points" (569 words) of "Audit Demo Novel" open in editor.
Run scripts: `05-ai-toolbar.py`, `05b-generate-prompt.py` (+ raw-SSE curl probes).
Storage state refreshed at end (`/tmp/opencode/audit/state.json`, 20:02).

## Per-function results

### 1. Generate (WRITE-002)
- TRIGGER: toolbar button "Generate" → right panel "AI Generation" opens.
- OPTIONS (config panel, verbatim): modes `Full Draft | Scene by Scene | Interview |
  Interactive`; fields `OUTLINE` (textarea, empty), `PROMPT` (textarea, empty),
  `WORD TARGET` (number, empty), `TONE` (select: balanced*SELECTED, dramatic,
  humorous, suspenseful, contemplative, romantic, dark, adventurous, quiet);
  buttons Close panel / 4 mode / Generate. Interactions counter "0/50 interactions".
- 6a) Defaults (all empty) → `POST /api/v1/writing/chapters/{chId}/generate?novel_id=…`
  → **422** body code `MISSING_INPUT` "At least one of prompt, outline, or
  auto_continue must be provided". UI RENDER: **"Verbindung verloren. Prüfe deine
  Internetverbindung." + Retry** — wrong mapping (a 422 validation error shown as
  connection-lost) AND German text in an otherwise English UI. Panel has an unused
  i18n message `generationPanel.validationMissingInput` ("At least one of outline,
  prompt, or auto-continue must be provided.") that never rendered.
- 6b) With PROMPT filled → start POST **200** `{request_id, status:"pending",
  mode:"full_draft"}` → `GET /api/v1/writing/generation/{rid}/stream` → **200
  text/event-stream (SSE)**. SSE payload: single `context_meta` event, then
  `data: [DONE]` — **no draft chunks, no error event**. Backend log:
  `agent_model_retry_exhausted` / `generation_stream_failed` "Model retries
  exhausted: Exceeded maximum output retries (1)".
  UI RENDER: stuck in streaming "AI Draft / 0 / 3.000 words / Waiting for AI
  response..." with **Accept / Reject / Retry buttons enabled and empty draft** —
  silent failure; Accept is clickable with 0 words. No draft text ever renders, so
  insert-vs-preview could not be observed (design: review phase with Accept
  (Ctrl/⌘+Enter) / Reject / Retry; accept would insert into editor).
- CLEAN_EXIT: yes — Reject clicked → `POST …/reject` 200 `draft_rejected`,
  rating prompt "Rate this suggestion / Submit / Skip" appeared, panel closed.

### 2. Beta Reader (ANAL-001)
- TRIGGER: toolbar button (aria "Get AI-powered feedback as if from a beta reader")
  → panel auto-runs on open. LOADING rendered: "Reading your chapter... / Analyzing
  plot, characters, pacing, and prose" + Stop.
- API: `POST /api/v1/analysis/beta-reader?novel_id=…` (application/json, NOT SSE)
  → **500** (×2). Backend: "Chapter is too short for meaningful analysis (569
  words, minimum 1000)." — business rule returned as HTTP 500 with generic
  "Internal server error" body.
- RENDER: "Analysis failed / Internal server error / Try Again" (tabs never
  appeared: Strengths/Issues/Questions/Overall all absent).
- CLEAN_EXIT: yes.

### 3. Sentiment (ANAL-002)
- TRIGGER: toolbar button → auto-run. LOADING rendered: "Analyzing sentiment... /
  Processing VAD scores, emotions, and narrative arc".
- API: `POST /api/v1/analysis/sentiment?novel_id=…` → **500** (×2, JSON).
  Backend: `sentiment_analysis_failed` — **"No module named 'spacy'"** (missing
  dependency in the audit API env).
- RENDER: "Analysis failed / Internal server error / Try Again".
- CLEAN_EXIT: yes.

### 4. Readability (ANAL-003) — only function that rendered results
- TRIGGER: toolbar button → auto-run (loading snapshot missed, too fast).
- API: `POST /api/v1/analysis/readability?novel_id=…` → **200** (JSON, ×2).
- RENDER (verbatim, panel): "Readability Scores / Flesch Reading Ease 66.5 /
  Flesch-Kincaid Grade 9.8 / Gunning Fog Index 8.9 / Text Statistics: Words 662,
  Sentences 39, Avg. Sentence Length 17.0words, Complex Words 10.9% / Genre
  Comparison: Middle Grade 80.0 (−13.5), Young Adult 70.0 (−3.5), Commercial
  Fiction 65.0 (+1.5), Literary Fiction 50.0 (+16.5) / No problematic sentences
  detected!"
- NOTE: deterministic metrics only. Backend logged `readability_agent_failed` —
  "Missing required prompt variable 'kb_characters' in analysis/en/readability" —
  LLM sentence analyses silently skipped (`sentence_analyses=[]`), yet UI claims
  "No problematic sentences detected!" (silent degradation) and shows no
  Overall Assessment section. Minor nit: "17.0words" missing space.
- CLEAN_EXIT: yes.

### 5. POV (ANAL-004)
- TRIGGER: toolbar button → auto-run.
- API: `POST /api/v1/analysis/pov?novel_id=…` → **500** (×2).
  Backend: `PromptVariableError: Missing required prompt variable 'kb_characters'
  in analysis/en/pov` → AnalysisError → unhandled → 500.
- RENDER: "Failed to analyze POV / Internal server error / Retry".
- CLEAN_EXIT: yes.

### 6. Coreference (ANAL-005)
- TRIGGER: toolbar button → auto-run SSE. LOADING rendered: "Analyzing
  coreference... / Resolving pronouns and tracking character mentions".
- API: `POST /api/v1/analysis/coreference/{chapterId}` → **200
  text/event-stream (SSE)**. Raw stream: `data: {"event": "error", "result": null,
  "error": "Coreference analysis failed.", "is_final": true}` + `[DONE]`.
  Backend: `agent_model_retry_exhausted` → `coreference_agent_failed` /
  `coreference_sse_failed` "Model retries exhausted: Exceeded maximum output
  retries (1)" (TestModel empty output rejected by CoreferenceAgent output
  validator; `CoreferenceOutput(resolutions=[], character_mentions=[],
  clarity_score=0.0, summary='')` visible in log).
- RENDER: "Failed to analyze coreference / Verbindung verloren. Prüfe deine
  Internetverbindung. / Try Again" — server-side analysis failure surfaced as
  connection-lost, in German.
- CLEAN_EXIT: yes.

## Shared root cause (stream functions)
TestModel output fails the agents' output validation → 1 retry → stream fails.
- Coreference: at least emits an SSE error event (UI maps it badly).
- Generation: emits NOTHING (context_meta + [DONE]) → UI silently enters review
  with empty draft (RULE-11 violation at the SSE protocol level).
- Analysis prompts require `kb_characters` variable that the composer does not
  provide when the novel KB has characters but none resolve (or empty KB) —
  hard-fails POV (500), soft-fails readability.

## Pollution
NONE. Chapter 1 "The Compass Points": word_count 569 before → 569 after every
flow; generation drafts never accepted (Reject only); rejected probe request
f2bf690c cleaned up; status "draft", summary empty. Chapter list intact.

## Console / network
- Console errors: 8 total, 7 non-401 — all "Failed to load resource: … 500
  (Internal Server Error)" matching sentiment ×2 / POV ×2 / beta-reader ×2 (+1
  duplicate during load). Zero 401 bursts beyond auth-refresh at boot. No
  pageerrors. Network failures (requestfailed): 0.

## Files
05-run.log, 05-report.txt, 05-ai-toolbar.py, 05-api-calls.json, 05-results.json,
05-baseline.json, 05-after.json, 05-{sentiment,readability,pov,coreference,beta,
generate}-*.txt/.png, 05b-* (script, run.log, dumps, screenshots).
