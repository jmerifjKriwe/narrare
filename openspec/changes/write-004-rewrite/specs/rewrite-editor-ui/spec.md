## ADDED Requirements

### Requirement: Text selection detection and rewrite trigger
The system SHALL detect text selection in the TipTap editor and provide "AI Rewrite" as an action via the existing BubbleMenu when a selection of 50-2000 characters is active.

#### Scenario: Rewrite button enabled on valid selection
- **WHEN** the user selects between 50 and 2000 characters of text in the editor
- **THEN** the "AI Rewrite" button in the BubbleMenu SHALL become active
- **AND** a "Rewrite selection" option SHALL appear in the context menu (right-click)

#### Scenario: Rewrite button disabled on short selection
- **WHEN** the user selects fewer than 50 characters
- **THEN** the "AI Rewrite" button in the BubbleMenu SHALL be disabled with a tooltip explaining the minimum length

#### Scenario: Rewrite button disabled on long selection
- **WHEN** the user selects more than 2000 characters
- **THEN** the "AI Rewrite" button in the BubbleMenu SHALL be disabled with a tooltip explaining the maximum length

#### Scenario: BubbleMenu AI Rewrite button triggers rewrite flow
- **WHEN** the user selects 50-2000 characters and clicks the "AI Rewrite" button in the BubbleMenu
- **THEN** the editor SHALL show the RewriteModeSelector before sending the request
- **AND** the existing AISuggestion modal SHALL be reused for displaying alternatives

#### Scenario: No selection means no rewrite available
- **WHEN** no text is selected in the editor
- **THEN** the "AI Rewrite" button in the BubbleMenu SHALL be hidden or disabled

### Requirement: Editor state preservation during streaming
The system SHALL prevent document changes that would invalidate the selection range while rewrite alternatives are being streamed.

#### Scenario: User edits during streaming
- **WHEN** rewrite alternatives are being streamed and the user types or edits text in the editor
- **THEN** the modal SHALL dismiss with a brief notification ("Generation cancelled — document changed")
- **AND** no changes SHALL be applied to the document
- **AND** the ongoing stream SHALL be aborted via AbortController

#### Scenario: User scrolls during streaming
- **WHEN** rewrite alternatives are being streamed and the user scrolls the editor
- **THEN** streaming SHALL continue normally
- **AND** the modal SHALL remain visible when scrolling stops

### Requirement: RewriteMode selector UI
The system SHALL provide a mode selector component with 5 rewrite modes: Tone, Style, Voice, Fix, and Custom.

#### Scenario: User selects Tone mode
- **WHEN** the user clicks "Rewrite" and selects "Tone"
- **THEN** the mode selector SHALL display tone options: more dramatic, more subdued, more humorous, more tense, more formal, more casual

#### Scenario: User selects Style mode
- **WHEN** the user selects "Style"
- **THEN** the mode selector SHALL display style options: simplify, elaborate, more active, more descriptive, varied sentence structure

#### Scenario: User selects Voice mode
- **WHEN** the user selects "Voice"
- **THEN** the mode selector SHALL display a character dropdown populated from the KB
- **AND** selecting a character SHALL include their name and a brief voice description

#### Scenario: User selects Fix mode
- **WHEN** the user selects "Fix"
- **THEN** the mode selector SHALL display fix options: show don't tell, remove redundancies, strengthen weak verbs, fix awkward phrasing

#### Scenario: User selects Custom mode
- **WHEN** the user selects "Custom"
- **THEN** the mode selector SHALL display a free-text input field for custom instructions (max 500 chars)

#### Scenario: Count selector for alternatives
- **WHEN** the mode and options are selected
- **THEN** a count selector SHALL allow the user to choose 1, 2, or 3 alternatives (default: 1)

### Requirement: Alternatives comparison UI (reuses AISuggestion modal)
The system SHALL reuse the existing AISuggestion modal in TipTapEditor for displaying rewrite alternatives, extending it with mode selection, inline diff highlighting, and replace/insert actions.

#### Scenario: Single alternative displayed in modal
- **WHEN** the LLM produces 1 alternative (`count=1`)
- **THEN** the existing AISuggestion modal SHALL display the alternative as a selectable card with the original text above
- **AND** inline diff highlighting SHALL show additions (green) and removals (red/strikethrough)

#### Scenario: Multiple alternatives as selectable cards
- **WHEN** the LLM produces 2-3 alternatives (`count=2` or `count=3`)
- **THEN** the modal SHALL display all alternatives as selectable cards with labels reflecting each alternative's focus
- **AND** clicking a card SHALL select it (highlighting with border + checkmark, same as current pattern)
- **AND** diff highlighting SHALL update to show changes from original for the selected alternative

#### Scenario: User replaces selection with alternative (Replace action)
- **WHEN** the user clicks "Replace" (currently labeled "Accept" in the modal)
- **THEN** the original selection SHALL be removed from the editor
- **AND** the alternative text SHALL be inserted in its place wrapped with an `ai-generated` mark (`source: "rewrite"`, `status: "pending"`)
- **AND** the modal SHALL dismiss

#### Scenario: User inserts alternative as new text (Insert as new action)
- **WHEN** the user clicks "Insert as new"
- **THEN** the alternative text SHALL be inserted after the original selection as new text wrapped with an `ai-generated` mark
- **AND** the original selection SHALL remain unchanged
- **AND** the modal SHALL dismiss

#### Scenario: User dismisses modal without selecting
- **WHEN** the user presses Escape or clicks the X button in the modal
- **THEN** the modal SHALL dismiss with no changes to the editor content

### Requirement: Alternative stream parsing (client-side state machine)
The frontend SHALL parse the SSE stream from the rewrite endpoint, splitting the response into separate alternatives using a client-side state machine that buffers partial `<alternative>` tags across chunk boundaries.

#### Scenario: Parser buffers partial tags across chunks
- **WHEN** an SSE chunk contains `<alterna` and the next chunk contains `tive label="Tone shift">`
- **THEN** the parser SHALL buffer the partial tag until it completes
- **AND** SHALL NOT emit an alternative until its closing `</alternative>` tag arrives

#### Scenario: First alternative renders immediately
- **WHEN** the first `</alternative>` closing tag is detected
- **THEN** the parser SHALL emit the first alternative immediately
- **AND** the modal SHALL render the first alternative card while subsequent alternatives buffer

#### Scenario: Subsequent alternatives appear as tabs
- **WHEN** additional `</alternative>` closing tags are detected
- **THEN** each alternative SHALL be added to the modal as a new selectable card

#### Scenario: Fallback for unparseable response
- **WHEN** the entire SSE stream contains no `<alternative>` tags (LLM didn't follow format)
- **THEN** the parser SHALL treat the entire response as a single alternative with label "Rewritten text"
- **AND** the modal SHALL display it as a single card

#### Scenario: Parser handles tag-like content within alternatives
- **WHEN** the LLM produces text containing `<alternative` within the content of an alternative (not at a line boundary)
- **THEN** the parser SHALL treat it as regular text content (not a tag boundary)
- **AND** the parser SHALL only recognize `<alternative` as a tag opener when it appears at the start of a line or immediately after a closing `</alternative>` tag

#### Scenario: LLM produces fewer alternatives than requested
- **WHEN** the user requested `count=3` but the LLM only produces 2 complete `<alternative>` blocks
- **THEN** the parser SHALL emit and display all 2 received alternatives
- **AND** no error SHALL be raised — partial delivery is acceptable

#### Scenario: LLM produces more alternatives than requested
- **WHEN** the user requested `count=1` but the LLM produces 2 `<alternative>` blocks
- **THEN** the parser SHALL use only the first `count` alternatives and discard the rest
- **AND** the modal SHALL display only the requested number of alternatives

### Requirement: Rewrite integrates with AIAnnotation lifecycle
The rewrite feature SHALL use the AIAnnotation infrastructure (marks, tracker, floating actions) with `source: "rewrite"` to distinguish from extend continuations.

#### Scenario: Replace inserts text with rewrite mark
- **WHEN** the user replaces the original selection with a rewrite alternative
- **THEN** the inserted text SHALL be wrapped with an `ai-generated` mark with `source: "rewrite"` and `status: "pending"`

#### Scenario: Accept rewrite mark
- **WHEN** the user accepts a pending rewrite mark
- **THEN** the AIAnnotationActions floating UI SHALL appear with source label "AI Rewrite" (i18n-keyed)
- **AND** clicking "Keep" SHALL remove the mark (text stays) and record an ACCEPT feedback event

#### Scenario: Reject rewrite mark
- **WHEN** the user rejects a pending rewrite mark
- **THEN** clicking "Undo" SHALL remove the marked text from the document and record a REJECT feedback event

#### Scenario: Clean save with rewrite mark
- **WHEN** autosave fires while a pending rewrite mark exists
- **THEN** the mark SHALL be removed before saving and an ACCEPT or MODIFY feedback event SHALL be recorded

### Requirement: Rewrite command registration
The system SHALL register a "Rewrite selection" command in the editor's `commands.ts` that triggers the rewrite flow.

#### Scenario: Rewrite command available in CommandPalette
- **WHEN** the user opens the CommandPalette (Cmd+K) with text selected
- **THEN** a "Rewrite selection" command SHALL appear in the command list

#### Scenario: Rewrite command hidden when no selection
- **WHEN** no text is selected in the editor
- **THEN** the "Rewrite selection" command SHALL be hidden from the CommandPalette

#### Scenario: Command state includes selection info
- **WHEN** the `CommandState` is computed for the rewrite command
- **THEN** it SHALL include `hasSelection: boolean` and `selectionLength: number` derived from the editor state

### Requirement: Inline diff calculation for alternatives
The system SHALL use `diff-match-patch` to compute inline diffs between the original selection text and each rewrite alternative, highlighting additions and removals.

#### Scenario: Added text highlighted
- **WHEN** an alternative contains text not in the original
- **THEN** the diff SHALL highlight the added text with a green background in the comparison card

#### Scenario: Removed text highlighted
- **WHEN** the original text contains text not in the alternative
- **THEN** the diff SHALL highlight the removed text with a red/strikethrough background in the comparison card

#### Scenario: Unchanged text displayed normally
- **WHEN** text is the same in both original and alternative
- **THEN** the comparison card SHALL display it without highlighting

### Requirement: Rewrite API client method
The frontend API client (`lib/api/generation.ts`) SHALL include a `streamRewrite()` method for SSE-direct streaming of rewrite alternatives.

#### Scenario: streamRewrite API call
- **WHEN** the frontend calls `streamRewrite(chapterId, novelId, rewriteRequest, callbacks)`
- **THEN** a POST request SHALL be sent to `/writing/chapters/${chapterId}/rewrite?novel_id=${novelId}` with the `RewriteRequest` body
- **AND** the response SHALL be consumed as an SSE stream
- **AND** `callbacks.onAlternative(label, text)` SHALL be called for each parsed `<alternative>` block
- **AND** `callbacks.onAlternativeFinal()` SHALL be called when all alternatives are received

#### Scenario: RewriteRequest TypeScript type
- **WHEN** an `RewriteRequest` object is constructed with `selection_text`, `mode`, `options`, `count`, etc.
- **THEN** the field names and types SHALL match the backend Pydantic schema exactly
