## MODIFIED Requirements

### Requirement: Mark lifecycle supports selection replacement
The AIAnnotation API SHALL support replacing an editor selection with AI-generated text, in addition to inserting text at the cursor position.

#### Scenario: Replace selection with AI text (rewrite use case)
- **WHEN** `replaceSelectionWithAIContent(editor, requestId, source, newText, from, to)` is called with a text range
- **THEN** the function SHALL delete the selected text range (from→to) and insert `newText` in its place
- **AND** the inserted text SHALL be wrapped with an `ai-generated` mark with `source`, `requestId`, `originalText=newText` (the AI text), and `status="pending"`
- **AND** the operation SHALL be a single atomic ProseMirror transaction (no intermediate state without selection)

#### Scenario: Insert at cursor remains unchanged
- **WHEN** `insertAIContent(editor, requestId, source, text)` is called (extend use case)
- **THEN** the existing behavior SHALL remain — text is inserted at cursor position with an `ai-generated` mark
- **AND** no selection is removed
