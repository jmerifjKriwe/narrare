## Context

WRITE-004 (Rewrite Selection) is the second AI writing feature in Phase 6, following WRITE-003 (Extend Chapter). It enables writers to select any passage in the editor and request an AI-powered rewrite with style, tone, voice, or fix instructions. The system generates 1-3 alternatives for side-by-side comparison.

**Current state:**
- `LLMIntent.REWRITE` already exists in `intents.py` and is mapped in `MODEL_ROUTING`
- Rewrite prompt templates exist for all 3 languages (`_bundled/writing/{en,de,fr}/rewrite_selection/system.md`)
- The prompt currently outputs freeform text — it must be updated to produce structured multi-alternative output with `<alternative>` tags
- `WritingService` is at 295 lines (near the 300-line RULE-04 limit), requiring a separate `RewriteService`
- The AIAnnotation infrastructure from WRITE-003 (mark, tracker, lifecycle API, clean save, floating actions) is fully reusable for rewrite
- The evaluation framework from WRITE-003 (promptfoo evals) provides the pattern for rewrite evals

**Key architectural constraint: Multi-alternative output parsing.** Unlike extend (which streams a single continuation), rewrite must produce 1-3 labeled alternatives. This requires structured output from the LLM and client-side parsing to split alternatives for side-by-side display.

## Goals / Non-Goals

**Goals:**
- Writers can select text, choose a rewrite mode, and get 1-3 AI alternatives
- Alternatives are presented in a comparison UI with inline diff highlighting
- Writers can replace the original selection with one click, or insert as new text
- The rewrite lifecycle integrates with AIAnnotation (pending mark, accept/reject/modify) and feedback tracking
- Rewrite prompts produce structured `<alternative>` output that the client can parse from the SSE stream

**Non-Goals:**
- Interactive/conversational rewriting (that's WRITE-006 Co-Author)
- Multi-draft comparison across sessions (that's WRITE-008 Multi-Draft)
- Voice analysis or speech pattern extraction (that's ANAL-008)
- Version history for rewrites (future consideration, not MVP)

## Decisions

### D1: Separate GenerationMode.REWRITE (not a flag on FULL_DRAFT)

**Decision:** Add `REWRITE = "rewrite"` as its own `GenerationMode` enum value.

**Why:** Rewrite has a fundamentally different input contract (selection text + mode + options) than full draft (outline/prompt + word target). Combining them would violate RULE-03 (contract before implementation) and create branching logic inside the pipeline. A separate mode gives clean dispatch in `WritingPipeline.generate()`.

**Alternatives considered:**
- **Flag on FULL_DRAFT:** Would require conditional branching in the pipeline for selection text vs. outline, options vs. word target. Muddies the contract.
- **Separate HTTP method (PUT instead of POST):** Overloads HTTP semantics. Rewrite creates a new generation request, which is POST semantics.

### D2: SSE-direct endpoint like extend (not two-step create+stream)

**Decision:** `POST /api/v1/writing/chapters/{chapter_id}/rewrite` returns SSE stream directly.

**Why:** Same reasoning as extend — the user expects immediate streaming output, not a create-then-poll flow. The alternatives are parsed on the client side from the stream.

**Alternatives considered:**
- **Two-step (create → poll → stream):** Adds latency and complexity. No UX benefit for rewrite since the user is waiting in the editor.
- **WebSocket:** Over-engineered since we don't need bidirectional communication for single-response streaming.

### D3: Structured output via `<alternative>` XML tags in prompt

**Decision:** The rewrite prompt instructs the LLM to produce 1-3 alternatives wrapped in `<alternative label="...">` tags. The client parses these from the SSE stream to split alternatives for display.

**Why:** XML tags are reliably parseable by the client, don't interfere with the flowing text, and work well with streaming. The backend streams raw SSE chunks exactly like extend — the client-side `AlternativeParser` buffers partial tags across chunk boundaries and emits complete alternatives as they close. This is a pure-function state machine in the frontend (no XML library needed), following the same architectural pattern as `parseSSELines()` in the existing streaming infrastructure.

**Alternatives considered:**
- **JSON structured output:** Requires the entire response before parsing. No streaming.
- **Function/tool calling:** Model-specific, not all providers support it, and it's designed for agents, not creative generation.
- **Separator lines (e.g., `---`):** Fragile — the LLM might produce `---` within the text. XML tags are more robust and self-describing.
- **Separate requests per alternative:** Would triple latency and cost. Single request with structured output is better.

### D4: Separate RewriteService (not added to WritingService)

**Decision:** Create `writing/rewrite_service.py` as a separate service class, following the same pattern as `ExtendService`.

**Why:** `WritingService` is at 295 lines (approaching 300-line RULE-04 limit). Rewrite logic (multi-alternative parsing, context assembly for selection, mode-specific handling) is substantial enough to warrant its own file. This follows the established pattern from `ExtendService`.

### D5: Rewrite alternatives use AIAnnotation with `source: "rewrite"`

**Decision:** Rewrite alternatives are inserted using the same AIAnnotation mark lifecycle as extend continuations, but with `source: "rewrite"` to distinguish them in the UI and feedback tracking.

**Why:** The AIAnnotation infrastructure (mark, tracker, single-pending constraint, clean save, floating actions) is fully built. Reusing it avoids duplication. The `source` attribute distinguishes rewrite from extend for labeling and analytics.

**Alternatives considered:**
- **Separate ProseMirror decoration for rewrites:** Would duplicate most of the AIAnnotation logic. Violates RULE-20 (no half-implementations).
- **No annotation for rewrites:** Would lose feedback tracking and clean save behavior.

### D6: Only one pending alternative at a time

**Decision:** When the user selects an alternative from the comparison UI, it's inserted as the single pending `ai-generated` mark (replacing the original selection). The other alternatives are discarded.

**Why:** The single-pending-mark constraint from AIAnnotation already enforces this. The comparison UI shows all alternatives, but only the chosen one enters the document as a pending mark. This simplifies the state model and avoids conflicting marks.

### D7: Frontend sends selection text + context window (not cursor position)

**Decision:** The frontend extracts the selected text and 200 tokens of surrounding context (pre+post), sends it in the request body, and removes the selection from the editor upon receiving the first streaming chunk.

**Why:** Same reasoning as extend — sending text instead of cursor position avoids autosave race conditions and gives the backend exactly what it needs for prompt construction. The surrounding context is limited to 200 tokens to control prompt length.

### D8: Rewrite reuses existing Modal UI (not new overlay)

**Decision:** The existing "AI Suggestion" Modal in `TipTapEditor.tsx` is the rewrite comparison UI. The BubbleMenu "AI Rewrite" button, the `AISuggestion` state with `original`/`suggestions[]`/`position`, and the full-screen modal with selectable cards are already implemented — currently wired to mock data.

**Why:** No new overlay component is needed. The existing pattern (BubbleMenu → Modal) is the established UX for text rewriting in the editor. Adding a separate overlay/popover would violate UI consistency. The modal is already fullscreen, supports multiple cards, and has accept/reject actions.

**What changes:**
- Wire `handleAIRewrite()` to call `streamRewrite()` instead of generating mock data
- Add `RewriteModeSelector` before the modal (shown after clicking "AI Rewrite" in BubbleMenu)
- Add inline diff highlighting to the suggestion cards (using `diff-match-patch`)
- Add "Insert as new" action alongside existing "Accept"
- Replace `editor.commands.insertContent()` with `replaceSelectionWithAIContent()` for AIAnnotation integration

**Alternatives considered:**
- New popover/overlay component near selection — breaks consistency with existing pattern, adds a new positioning system
- Side panel layout — too invasive for an operation that should feel quick and in-place

## Risks / Trade-offs

- **[Multi-alternative parsing]** LLMs may not always produce perfectly formatted `<alternative>` tags → Mitigation: Robust client-side parser with fallback (if tag parsing fails, treat entire response as single alternative). Server-side validation is not needed since parsing is client-side.

- **[Selection length limits]** Very short selections (< 50 words) may not give enough context for meaningful rewrites; very long selections (> 2000 words) may exceed prompt budget or lose coherence → Mitigation: Enforce min/max in backend validation (422 error). Frontend disables "Rewrite" button for selections outside the range.

- **[Prompt complexity]** The rewrite prompt must handle 5 modes (tone, style, voice, fix, custom) with different strategies → Mitigation: Mode-specific instruction blocks in the prompt template, selected by `{{rewrite_mode_instructions}}` variable populated by the prompt composer.

- **[Diff highlighting quality]** Computing inline diffs for the comparison UI requires a reliable diff algorithm → Mitigation: Use an existing diff library (`diff-match-patch` or similar). No need to build custom.

- **[Streaming + structured output]** Parsing `<alternative>` tags from a streaming SSE response requires buffering partial tags → Mitigation: Client-side parser holds partial data until a complete `<alternative>` tag closes before rendering. First alternative renders immediately while subsequent alternatives buffer.

## Migration Plan

1. **Phase 1 (this change):** Core pipeline + backend endpoint + streaming. Frontend gets the comparison UI and annotation integration.
2. **Phase 2 (future):** Voice mode connects to KB character profiles for voice-specific rewrites.
3. **Phase 3 (future):** Promptfoo eval baseline for rewrite quality.

No database migration needed — the rewrite request reuses the existing `generation_requests` table with `mode = "rewrite"`.

## Open Questions

- Should the comparison UI render alternatives as tabs or side-by-side cards? → **Decided: Tab layout** (less screen space, works on mobile, can be switched to side-by-side in a future iteration)
- Should count=3 be the default, or count=1? → **Decided: Default count=1, max=3** — single alternative is most common, reducing latency and cost
- Should the original selection be removed from the editor before or after the alternatives finish streaming? → **Decided: After the user selects an alternative** — the original selection stays in place until the user picks a replacement. Pending alternatives are shown in an overlay/popover, not replacing the editor content live.
