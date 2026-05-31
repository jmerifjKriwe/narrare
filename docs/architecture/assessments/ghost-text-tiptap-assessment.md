---
id: ASSESS-001
title: "Ghost-Text Extension for TipTap — Architectural Assessment"
date: 2026-05-23
status: draft
area: frontend
related: [WRITE-007, AUFG-03-01]
---

# Ghost-Text Extension for TipTap — Architectural Assessment

## Executive Summary

**Recommendation: PROCEED with a phased approach, but BUILD a custom extension rather than adopting an external package.**

The ghost-text feature (Copilot-style inline AI suggestions) is feasible within Narrare's architecture. A ProseMirror `DecorationSet`-based approach works correctly with TipTap v3 and all existing custom extensions. The backend intent (`LLMIntent.SUGGEST`) exists already — only a frontend extension and a lightweight SSE endpoint need building.

---

## 1. Technical Evaluation: ProseMirror Decorations API

### 1.1 `DecorationSet`, `Decoration.widget()`, vs `Decoration.inline()`

| Method | Use Case | Ghost Text Fit |
|--------|----------|----------------|
| `Decoration.widget(pos, dom)` | Inserts a **standalone DOM element** at a position, not tied to existing content. Rendered outside the ProseMirror content flow. | **Wrong** for ghost text. Widgets sit *between* nodes, not inline with text. The reference implementation uses this — it would render a `<span>` floating outside the prose flow. |
| `Decoration.inline(from, to, attrs)` | Applies **attributes/styling** to an existing range of content. Used for highlights, mark-like effects. | **Close but wrong**. It modifies existing content but cannot insert *new* virtual text that doesn't exist in the document. |
| `Decoration.replace(from, to, attrs, spec?)` | **Widget + inline combined** — replaces a range with a custom DOM element while preserving cursor semantics. | **Best fit** for ghost text. `Decoration.replace(from, to, {class: "ghost-text"}, {widget: ghostSpan})` allows placing a virtual element at cursor position that renders as gray text. |

**Correct approach for ghost text:**

```ts
// The ghost text is rendered as a Decoration that "replaces" an
// empty range at cursor position with a styled widget element.
// Cursor position = {from: cursorPos, to: cursorPos}

const ghostEl = document.createElement('span');
ghostEl.textContent = suggestionText;
ghostEl.className = 'ghost-text';  // Tailwind: text-gray-400 italic

return DecorationSet.create(state.doc, [
  Decoration.inline(cursorPos, cursorPos, {
    class: 'ghost-text-suggestion'
  }),
  // Or use replace + widget for more control:
]);
```

**Key correction to the reference implementation:** The reference code uses `Decoration.widget()` which inserts at a position *between* content. This works superficially but:
- Widgets don't participate in cursor movement naturally
- Widgets don't get selected with surrounding text
- They sit in a separate "widget" layer, not the content layer

**The better pattern** is a combination approach used by `prosemirror-completion`:
- Use `DecorationSet.create()` with `Decoration.inline()` at `[cursorPos, cursorPos]`
- Add a `class` attribute for the ghost text CSS styling
- Use `pointer-events: none` on the decoration span
- The ghost text is rendered as a CSS `::after` pseudo-element on a zero-width inline decoration

### 1.2 Cursor Interaction

Ghost text **must not** affect cursor behavior:

- **Cursor at end of document**: The ghost text appears *after* the cursor. `Decoration.inline(pos, pos, ...)` with a zero-width range at cursor head ensures cursor stays visible and the ghost text visually follows it.
- **Cursor movement**: Arrow keys move through real content; ghost text is transparent to cursor movement (decorations are visual-only).
- **Selection**: If user selects text that overlaps with the ghost decoration, the decoration should be hidden (dismissed).

### 1.3 Ghost Text Disappearance on Typing

Three mechanisms work together:

1. **Editor `onUpdate` event**: On any content change (typing), the extension recalculates decorations. If the cursor moved or content changed since the suggestion was received, decorations are cleared.
2. **Character mismatch detection**: On each keystroke, compare the user's new character against the first character of the ghost text. If they differ → dismiss. If they match → advance the cursor and trim the ghost text first character (Copilot-style).
3. **Cursor position change**: If cursor moves away from the suggestion position → dismiss.

### 1.4 Implementation Pattern (TipTap Extension)

```ts
export const GhostText = Extension.create({
  name: 'ghostText',

  addOptions() {
    return {
      fetchSuggestion: null as ((context: {
        textBefore: string;
        textAfter: string;
      }) => Promise<string | null>) | null,
      debounceMs: 300,
      minTriggerLength: 5,
    };
  },

  addStorage() {
    return {
      currentSuggestion: null as string | null,
      suggestionPos: null as number | null,
      abortController: null as AbortController | null,
      debounceTimer: null as ReturnType<typeof setTimeout> | null,
    };
  },

  addProseMirrorPlugins() {
    return [
      new Plugin({
        key: new PluginKey('ghostText'),
        state: {
          init: () => DecorationSet.empty,
          apply: (tr, set) => {
            // Recalculate decorations after transactions
            return set.map(tr.mapping, tr.doc);
          },
        },
        props: {
          decorations(state) {
            const { currentSuggestion, suggestionPos } = this.getState(/*...*/);
            if (!currentSuggestion || suggestionPos === null) {
              return DecorationSet.empty;
            }
            const ghostEl = document.createElement('span');
            ghostEl.textContent = currentSuggestion;
            ghostEl.className = 'ghost-text inline-suggestion';
            ghostEl.setAttribute('aria-hidden', 'true');
            return DecorationSet.create(state.doc, [
              Decoration.widget(suggestionPos, ghostEl, {
                side: 1,  // place after cursor
                key: 'ghost',
              }),
            ]);
          },
        },
      }),
    ];
  },
});
```

---

## 2. Integration Analysis with Existing Extensions

### 2.1 No Conflicts Expected

All four existing extensions operate on *different layers*:

| Extension | Layer | How it Works |
|-----------|-------|-------------|
| `NarrareDocument` | Schema definition | Sets `content: "block+"` — affects what nodes are valid, not decorations |
| `SceneBreak` | Block node | Parses/rules for `---` → rendered as `<p class="scene-break">` |
| `DialogueMark` | Inline mark | Applies mark to quote-delimited text ranges |
| `Autosave` | Plugin (lifecycle) | Listens to `onUpdate`, debounces save — no ProseMirror plugins |
| **GhostText (proposed)** | Plugin (decorations) | Adds `DecorationSet` to editor via ProseMirror plugin |

**Why no conflict:**
- `DialogueMark` uses `Mark.inputRule` and `Mark.pasteRule` — these work at the schema/parsing level, not the decoration layer
- `SceneBreak` adds `Node` + `InputRule` — no decoration interaction
- `Autosave` has zero ProseMirror plugin footprint — pure TipTap lifecycle hooks
- Decorations are a *separate overlay layer* on top of the document. They don't modify the document schema or content.
- Multiple `DecorationSet`-producing plugins can coexist — ProseMirror merges them automatically

### 2.2 Potential Edge Case: `DialogueMark` + Ghost Decoration

If the user is typing inside a dialogue span (marked by `DialogueMark`), the ghost text decoration should still work correctly:
- The dialogue mark is part of the document schema; the ghost decoration is a ProseMirror plugin overlay
- The decoration doesn't interact with marks — it sits *on top* of the text layer
- **One caveat**: If the ghost text includes quote characters, the paste/input rules of `DialogueMark` won't fire (decorations aren't content)

### 2.3 Autosave Interaction

Ghost text content is **never saved** — it's a visual decoration. When the user accepts (Tab), the ghost text becomes real content via `editor.commands.insertContent()`, which triggers `onUpdate`, which triggers autosave. This is the correct behavior:
- Rejected/dismissed ghost text = no autosave trigger
- Accepted ghost text = normal content change → autosave

---

## 3. Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND                                  │
│                                                                   │
│  ┌──────────────┐    ┌─────────────────────────────────────────┐  │
│  │  TipTapEditor │    │  GhostText Extension                     │  │
│  │               │    │                                          │  │
│  │  ┌──────────┐ │    │  ┌──────────┐  ┌───────────────────┐   │  │
│  │  │ Editor   │ │    │  │ Plugin   │  │ DecorationSet     │   │  │
│  │  │ Instance │◄───────┤ (deco-   │──►│ Create/Update     │   │  │
│  │  │          │ │    │  │ rations) │  │                   │   │  │
│  │  └──────────┘ │    │  └────┬─────┘  └───────────────────┘   │  │
│  │       │       │    │       │                                  │  │
│  │  ┌────▼─────┐ │    │  ┌────▼─────┐                            │  │
│  │  │ onUpdate │ │    │  │ Debounce │                            │  │
│  │  │ onChange │ │    │  │ (300ms)  │                            │  │
│  │  └──────────┘ │    │  └────┬─────┘                            │  │
│  └──────────────┘    │       │                                   │  │
│                      │  ┌────▼─────┐                            │  │
│                      │  │ .fetch-  │                            │  │
│                      │  │ Suggestion│◄── context: textBefore     │  │
│                      │  │           │                            │  │
│                      │  │ When user │                            │  │
│                      │  │ presses   │                            │  │
│                      │  │ Tab →     │──► insertContent(...)     │  │
│                      │  │ Escape →  │──► clear decoration        │  │
│                      │  └───────────┘                            │  │
│                      └─────────────────────────────────────────┘  │
│                                │                                   │
│                     ┌──────────▼──────────┐                       │
│                     │   streaming.ts       │                      │
│                     │   connectSSE()       │                      │
│                     │   POST /api/v1/...    │                      │
│                     └──────────┬──────────┘                       │
└────────────────────────────────┼─────────────────────────────────┘
                                 │ SSE stream
                                 ▼
┌──────────────────────────────────────────────────────────────────┐
│                        BACKEND                                    │
│                                                                   │
│  ┌──────────────────────────┐                                     │
│  │  FastAPI Router           │                                     │
│  │  (writing/router.py)      │                                     │
│  │                           │                                     │
│  │  POST /chapters/{id}/     │                                     │
│  │  suggest (NEW)            │                                     │
│  └─────────┬────────────────┘                                     │
│            │                                                        │
│  ┌─────────▼────────────────┐                                     │
│  │  DraftService.suggest_    │                                     │
│  │  inline() (NEW)           │                                     │
│  │                           │                                     │
│  │  - validates access       │                                     │
│  │  - assembles context      │                                     │
│  │    (last 200 tokens)      │                                     │
│  │  - returns SSE stream     │                                     │
│  └─────────┬────────────────┘                                     │
│            │                                                        │
│  ┌─────────▼────────────────┐                                     │
│  │  WritingPipelineProtocol  │                                     │
│  │  (generate_suggest() )   │                                     │
│  │                           │                                     │
│  │  Uses: LLMIntent.SUGGEST  │                                     │
│  │  Mode: "inline_suggest"   │                                     │
│  │  Max tokens: 50-100      │                                     │
│  │  Temperature: 0.3        │                                     │
│  └─────────┬────────────────┘                                     │
│            │                                                        │
│  ┌─────────▼────────────────┐                                     │
│  │  InlineSuggestAgent       │                                     │
│  │  (pydantic-ai agent)     │                                     │
│  │                           │                                     │
│  │  - Complete sentence      │                                     │
│  │  - Max 3 sentences        │                                     │
│  │  - Use KB context         │                                     │
│  └──────────────────────────┘                                     │
└──────────────────────────────────────────────────────────────────┘
```

### Data Flow (happy path)

1. User types 5+ characters → pause 300ms
2. `GhostText` extension calls `this.options.fetchSuggestion(context)`
3. Frontend calls `connectSSE()` with `{ chapter_id, text_before, text_after }`
4. Backend `DraftService.suggest_inline()` validates, assembles context
5. Pipeline generates completion (1-3 sentences) via `InlineSuggestAgent`
6. SSE streams chunks: `{ "text": "...", "is_final": false }`
7. Extension updates `DecorationSet` on each chunk — ghost text grows
8. On `is_final: true` → suggestion ready
9. User presses **Tab** → `editor.commands.insertContent(suggestion)` → ghost text becomes real
10. User presses **Escape** → `clearSuggestion()` → decorations removed
11. User types mismatching character → `clearSuggestion()` → decorations removed

---

## 4. Risk Assessment Matrix

| Risk | Severity | Likelihood | Mitigation |
|------|----------|------------|------------|
| **Cursor position desync** | High | Medium | Always snap ghost decoration to `state.selection.head`. Verify with Playwright cursor tests. Use `Decoration.widget()` with `side: 1` (after cursor). |
| **SSE race condition** (user types before suggestion arrives) | Medium | High | Track `lastTypedAt` timestamp. Discard suggestions whose trigger timestamp is older than the last keystroke. Abort stale requests via `AbortController`. |
| **Performance: decoration recalculation on every keystroke** | Low | High | `DecorationSet.map()` is O(n) where n = decoration count. With 1 ghost decoration, cost is negligible. Monitor with React DevTools profiler. |
| **Mobile/touch keyboard** | Medium | Low | Ghost text renders fine on mobile, but Tab key is unavailable. Add an "accept suggestion" button in the floating toolbar or keyboard accessory. |
| **Conflict with other plugins** (future) | Low | Medium | Document in extension README: this plugin uses `PluginKey('ghostText')` which is unique. Follow TipTap's plugin registration pattern to avoid key collisions. |
| **SSE connection lifecycle** (page navigation while streaming) | Medium | Medium | `AbortSignal` from extension storage. Cancel on `editor.destroy()`, component unmount, or new suggestion trigger. |
| **Ghost text not accessible** | Low | Low | Add `aria-hidden="true"` to ghost decoration element. Screen readers should not announce suggestions — they're visual hints. |
| **Suggestions are too slow** (>500ms) | High | Medium | Use a faster, smaller model for inline suggestions (e.g., `gpt-4o-mini`, `claude-3-haiku`). Cache identical prefixes. Set `max_tokens: 60`. |
| **User acceptance of ghost text** (distraction) | Medium | Medium | Must be toggleable. Settings panel: enable/disable, adjust trigger word count, disable on double-tap (accessibility). |

---

## 5. npm Package Landscape — Decision

### Evaluated Options

| Package | Verdict | Rationale |
|---------|---------|-----------|
| `@tiptap/suggestion` | **Not suitable** | Designed for slash-command popups (@mentions, /commands). Not ghost text. |
| `@tiptap/extension-placeholder` | **Not suitable** | Static empty-state placeholder ("Write something..."). Uses decorations but only for empty doc. |
| `@tiptap-pro/extension-ai` | **Not feasible** | Commercial (paid). Requires online connection to Tiptap Pro. No source access. Lock-in risk. |
| `prosemirror-completion` | **Best reference** | MIT-licensed, purpose-built for Copilot-style ghost text. Has `callCompletion`, Tab/Escape keymap, debounce. However: it's a raw ProseMirror plugin, needs adapter for TipTap v3. |
| `@sereneinserenade/tiptap-inline-suggestion` | **Not recommended** | 78 stars, low maintenance. Uses CSS `::after` pseudo-elements on data attributes — clever but fragile. No streaming support. No accept/reject keybindings out of box. Would need significant fork. |
| **Custom build** | **RECOMMENDED** | Build a ~150-line TipTap extension using ProseMirror decorations directly. Fits Narrare's architecture, no external dependency, full control. See Phase 1 below. |

### Why Custom Build Wins

1. **No external dependency** → no supply chain risk, no breaking upstream changes
2. **Total control** over accept/reject UX (Tab, Escape, ArrowRight word-accept)
3. **Direct SSE integration** via `connectSSE()` — no adapter needed
4. **Follows existing patterns** — same architecture as `Autosave.ts` (`Extension.create`, `addStorage`, `addProseMirrorPlugins`)
5. **Minimal code** — a well-structured GhostText extension is ~150-200 lines
6. **TipTap v3 compatibility guaranteed** — we control the `@tiptap/pm` version pin

---

## 6. Phased PoC Roadmap

### Phase 1: Static Ghost Text (validate decoration approach)
**Effort: ~1 day** | **Files:** 1 new, 0 modified

**Goal:** Prove that a `DecorationSet`-based ghost text renders correctly in the TipTap editor without conflicts.

**Deliverables:**
- `packages/web/components/studio/editor/extensions/GhostText.ts`
  - Static suggestion: "The old house stood at the end of the lane…"
  - Appears after typing 5 characters + 1s pause
  - Rendered as gray italic text at cursor
  - Disappears when any key is pressed
  - No SSE, no accept/reject keybindings

**Validation criteria:**
- [ ] Ghost text renders at cursor position in Chrome, Firefox, Safari
- [ ] Cursor remains visible and operable
- [ ] No interaction with existing SceneBreak, DialogueMark, Autosave
- [ ] Component renders without error in TipTapEditor

### Phase 2: Simulated Streaming with Accept/Reject (validate UX)
**Effort: ~2 days** | **Files:** 1 modified, 0 new

**Goal:** Validate the full accept/reject interaction loop with simulated streaming.

**Deliverables:**
- Enhance `GhostText.ts`:
  - `fetchSuggestion` callback receives `{ textBefore, textAfter }` → returns `Promise<string>`
  - Phase 2 uses a local generator (not API):
    - Simulate SSE with `setTimeout`-based character emission
    - Simulated completions based on trigger text
  - **Tab** key → `editor.commands.insertContent(suggestion)` → ghost becomes real → autosave triggers
  - **Escape** key → decorations cleared
  - **Typing mismatch** → auto-dismiss (compare incoming char vs first ghost char)
  - **ArrowRight** → accept first word (Copilot-style) — stretch goal
  - Ghost text is `aria-hidden="true"` — no screen reader distraction
  - `AbortController` management for cancellation

**Validation criteria:**
- [ ] Tab inserts ghost text as real content
- [ ] Escape clears ghost text
- [ ] Typing mismatched character clears ghost text
- [ ] ArrowRight accepts first word only (if implemented)
- [ ] Ghost text updates (streaming) appear character-by-character
- [ ] No cursor desync after accept
- [ ] Autosave fires after accept

### Phase 3: Connect to Real SSE Endpoint (validate end-to-end)
**Effort: ~3 days (split: 1 frontend, 2 backend)** | **Files:** 4 new (backend), 1 modified (frontend)

**Goal:** End-to-end flow from keystroke → SSE request → LLM response → ghost text → accept.

**Backend deliverables (new contract + handler):**
- `DraftServiceProtocol.suggest_inline()` in `writing/contracts.py`
- `DraftService.suggest_inline()` in `writing/draft_service.py` (NEW)
  - Validates chapter access
  - Assembles minimal context: last 200 tokens of user text, chapter frontmatter
  - Calls WritingPipeline with `LLMIntent.SUGGEST`, mode `"inline_suggest"`
  - Streams `StreamChunk` with `{ text, is_final }`
- `POST /api/v1/writing/chapters/{chapter_id}/suggest` SSE endpoint in `writing/router.py`
  - Accepts `{ text_before: string, text_after?: string }`
  - Returns SSE stream of text chunks
  - Max 60 tokens per suggestion
  - Temperature 0.3 for predictable completions
- `InlineSuggestAgent` in `packages/core/narrare_core/agents/` (or reuse `WritingGraph` with short mode)
  - Prompt: "Complete the following text naturally. Max 3 sentences. Use the story context."

**Frontend deliverables:**
- `GhostText.ts` wired to real backend:
  - `fetchSuggestion` calls `connectSSE<{text: string; is_final: boolean}>()`
  - Passes `{ chapter_id, text_before }` in request body
  - Updates decorations as each SSE chunk arrives
  - Clears on abort/error
- Config panel (simple):
  - Enable/disable toggle (stored in `editorStore` or local state)
  - Trigger word count slider (3/5/10 words)
  - Keyboard shortcut indicator

**Validation criteria (same as Phase 2 but with real LLM responses):**
- [ ] Suggestion appears < 500ms from trigger
- [ ] Suggestions are contextually relevant (use character names, setting)
- [ ] Suggestions never exceed 3 sentences
- [ ] SSE cancellation works (navigate away mid-stream → no error)
- [ ] Backend validates access before streaming (404 for wrong user/chapter)
- [ ] Rate limiting: max 1 suggest request per 500ms per chapter
- [ ] Accessible: toggleable, adjustable trigger word count

### Phase 4: Polish & Production (optional, future)
**Effort: ~5 days**

- **Word-level acceptance**: `ArrowRight` accepts a single word, not the whole suggestion
- **Suggestion diversity**: Multiple alternatives (accessible via arrow keys like Copilot)
- **Suggestion caching**: Cache identical prefixes to avoid redundant API calls
- **Style adaptation**: Learn user's writing patterns for better suggestions
- **Keyboard shortcut guide**: Inline hint showing "Tab to accept · Esc to dismiss"
- **Analytics**: Track accept/reject rate for quality monitoring

---

## 7. Detailed Backend Contract (for Phase 3)

### New API Endpoint

```python
# writing/router.py — new route

@router.post("/chapters/{chapter_id}/suggest")
async def suggest_inline(
    chapter_id: uuid.UUID,
    request: InlineSuggestRequest,
    user_id: CurrentUserIdDep,
    session: SessionDep,
) -> StreamingResponse:
    """SSE stream for inline ghost text suggestions."""
    service = await get_writing_service(session, user_id)

    async def event_stream():
        async for chunk in service.suggest_inline(chapter_id, request, user_id):
            yield f"data: {json.dumps({'text': chunk})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

```python
# writing/schemas.py — new model

class InlineSuggestRequest(BaseModel):
    text_before: str = Field(..., max_length=5000)
    text_after: str | None = Field(default=None, max_length=1000)
```

### Intent Mapping (already exists)

```python
# prompts/composer.py — already configured
LLMIntent.SUGGEST → category: "writing", mode: "inline_suggest"
```

No changes needed to the intent system. The prompt mode `"inline_suggest"` just needs a prompt file:

```
prompts/_bundled/writing/en/inline_suggest/system.md
```

### Pipeline Mode

A new, lightweight pipeline method rather than reusing the full `WritingPipeline`:

```python
# Inline mode: direct agent call, no graph, no multi-step
async def generate_suggestion(
    self, context: WritingContext
) -> AsyncIterator[str]:
    model = await self.registry.get_model(self.config)
    agent = InlineSuggestAgent(model=model)
    deps = InlineSuggestDeps(
        context=context,
        max_sentences=3,
    )
    async for chunk in agent.run_stream(
        prompt=context.text_before,
        deps=deps,
    ):
        yield chunk.text
```

---

## 8. Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Decoration method** | `Decoration.widget()` with `side: 1` | Simplest approach that works with cursor. `Decoration.replace()` offers more control but adds complexity. |
| **Plugin key** | `new PluginKey('ghostText')` | Unique key prevents conflicts with other plugins. |
| **Streaming approach** | `connectSSE()` via `fetchSuggestion` callback | Extension stays decoupled from API transport. The callback can be mocked in tests. |
| **Abort mechanism** | `AbortController` stored in `addStorage()` | Ensures stale requests are cancelled. Follows existing `connectSSE` API pattern. |
| **Backend endpoint** | New SSE route (not WebSocket) | Consistent with existing generation endpoint (`stream_generation`). WebSocket adds connection management complexity not needed here. |
| **LLM model** | Small/fast model (Haiku, 4o-mini) via `LLMIntent.SUGGEST` | Existing routing already supports per-intent model selection. Inline suggestions need low latency over quality. |
| **Suggested tokens** | Max 60 tokens, temp 0.3 | Short completions, predictable output. |
| **Framework** | Custom TipTap extension | No external dependency. Follows `Autosave.ts` pattern. Full control. |

---

## 9. Conclusion & Recommendation

**PROCEED with a phased custom implementation.**

| Phase | Risk | Value | Effort |
|-------|------|-------|--------|
| Phase 1: Static Decoration | Low | Medium (validates approach) | 1 day |
| Phase 2: Accept/Reject UX | Low | High (validates UX) | 2 days |
| Phase 3: SSE Integration | Medium | Critical (end-to-end) | 3 days |
| Phase 4: Polish | Low | Medium | 5 days |

**Root cause for doing this as a PoC:** The core question is whether ghost text decorations work correctly in the TipTap editor alongside existing extensions, and whether the SSE streaming pipeline can sustain the <500ms latency requirement. Phase 1 and 2 are low-risk investments that answer the first question. Phase 3 answers the second.

**No blocker exists** for starting Phase 1 now — it requires no backend changes and no new npm packages.
