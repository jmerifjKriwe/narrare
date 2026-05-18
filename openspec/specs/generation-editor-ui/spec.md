# Generation Editor UI

**Purpose**: The system SHALL provide a user interface in the editor for triggering, controlling, and managing AI generation of chapter content.

## Requirements

### Requirement: Generation trigger panel
The system SHALL provide a `GenerationPanel` component in the editor that allows users to trigger chapter generation with four input modes: from outline, from prompt, auto-continue, and interactive session.

#### Scenario: User opens generation panel from editor toolbar
- **WHEN** a user clicks the "Generate" button in the editor toolbar or presses the keyboard shortcut (Cmd+G)
- **THEN** the `GenerationPanel` opens as a side panel showing the four mode options with a brief description of each.

#### Scenario: User selects "from outline" mode
- **WHEN** a user selects "From Outline" mode
- **THEN** the panel shows a textarea for pasting or typing an outline, with optional fields for word target and tone selection. A "Generate" button starts the generation.

#### Scenario: User selects "from prompt" mode
- **WHEN** a user selects "From Prompt" mode
- **THEN** the panel shows a single textarea for a freeform description of what should happen, with word target and tone options.

#### Scenario: User selects "auto-continue" mode
- **WHEN** a user selects "Auto-Continue"
- **THEN** the panel shows a brief description ("AI continues from where you left off") and a "Generate" button. No additional input required.

#### Scenario: User selects "interactive" mode
- **WHEN** a user selects "Interactive Session"
- **THEN** the panel transitions to a chat interface (SessionPanel) for conversational writing with the AI.

### Requirement: Real-time streaming text display
The system SHALL display generated text in real-time as it streams from the server. Text appears in the editor area, visually distinguished from existing content (e.g., lighter background, "AI Draft" badge).

#### Scenario: Text streams into editor during generation
- **WHEN** generation starts and SSE chunks arrive
- **THEN** the text appears character-by-character (or sentence-by-sentence) in the editor, in a visually distinct "draft zone" that is separate from the user's existing chapter content.

#### Scenario: Connection lost during streaming
- **WHEN** the SSE connection drops during generation
- **THEN** the UI shows a "Connection lost" banner with a "Retry" button. All text received before the disconnection is preserved in the draft zone.

### Requirement: Generation controls
The system SHALL provide stop, resume (scene-by-scene only), and regenerate controls during and after generation.

#### Scenario: User stops generation mid-stream
- **WHEN** a user clicks "Stop" during active generation
- **THEN** the system sends a stop signal, generation halts, and the partial text is preserved in the draft zone. Controls update to show "Accept", "Reject", and "Regenerate".

#### Scenario: User regenerates after stopping or rejecting
- **WHEN** a user clicks "Regenerate" after stopping or rejecting a draft
- **THEN** the system starts a new generation with the same parameters, replacing the previous draft in the draft zone.

#### Scenario: User advances to next scene (scene-by-scene mode)
- **WHEN** scene-by-scene generation completes a scene
- **THEN** the draft zone shows the completed scene with an "Accept & Continue" button and a "Revise" button. "Accept & Continue" triggers generation of the next scene.

### Requirement: Draft acceptance and rejection flow
The system SHALL provide clear accept/reject actions for generated drafts. Accepting inserts the draft into the chapter content. Rejecting discards it.

#### Scenario: User accepts generated draft
- **WHEN** a user clicks "Accept Draft"
- **THEN** the system sends the accept request, the draft text replaces the draft zone and becomes part of the chapter content, and the editor returns to normal editing mode.

#### Scenario: User rejects generated draft
- **WHEN** a user clicks "Reject"
- **THEN** the system sends the reject request, the draft zone is cleared, and the editor returns to normal editing mode. The chapter content is unchanged.

#### Scenario: User edits draft before accepting
- **WHEN** a user edits text in the draft zone before accepting
- **THEN** the system detects modifications and records a "modify" feedback event (not "accept") when the user clicks "Accept", enabling the memory layer to learn from changes.

### Requirement: Word count progress indicator
The system SHALL display a real-time word count progress indicator during generation, showing current word count vs. target word count.

#### Scenario: Progress bar updates during generation
- **WHEN** generation is active with a word target of 3000
- **THEN** a progress indicator shows the current word count (e.g., "1,247 / 3,000 words") and a visual progress bar that fills as text is generated.

#### Scenario: No word target set
- **WHEN** generation is started without a word target
- **THEN** the progress indicator shows only the current word count (e.g., "1,247 words") without a target.

### Requirement: Interactive session chat UI
The system SHALL provide a `SessionPanel` component for interactive writing sessions (WRITE-005) with a chat interface: message history, input field, and prose preview.

#### Scenario: Session chat shows conversation
- **WHEN** an interactive session is active
- **THEN** the SessionPanel displays the conversation history (user messages and AI responses) in a chat layout. AI-generated prose appears in distinct message bubbles with "Add to draft" buttons.

#### Scenario: User sends direction in session
- **WHEN** a user types "Make the dialogue more terse" and presses Enter
- **THEN** the message is sent via WebSocket, and the AI's response (revised prose) streams into a new message bubble.

#### Scenario: User saves prose from session
- **WHEN** a user clicks "Save to Chapter" in the session panel
- **THEN** the accumulated prose buffer is saved as an AI draft in the chapter, and the user can continue the session or end it.

### Requirement: CommandPalette integration
The system SHALL register generation-related commands in the editor's CommandPalette (Cmd+K): "Generate Chapter", "Generate from Outline", "Auto-Continue", "Start Interactive Session", "Stop Generation", "Accept Draft", "Reject Draft".

#### Scenario: User triggers generation via CommandPalette
- **WHEN** a user opens the CommandPalette (Cmd+K) and types "generate"
- **THEN** the palette shows matching commands: "Generate Chapter", "Generate from Outline", "Auto-Continue", "Start Interactive Session".

#### Scenario: Command availability based on state
- **WHEN** no generation is active
- **THEN** "Stop Generation", "Accept Draft", and "Reject Draft" commands are hidden. Generation trigger commands are shown.
