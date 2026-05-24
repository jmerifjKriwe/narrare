# AI Annotation

**Purpose**: The system SHALL provide a ProseMirror mark-based annotation system for tracking AI-generated text in the editor, enabling user review (accept/reject), modification detection, and clean save behavior.

## Requirements

### Requirement: AI-generated Mark schema
The system SHALL define a ProseMirror `Mark` named `ai-generated` with the following attributes: `request_id` (UUID string), `source` (enum: "extend", "rewrite", "unblock"), `original_text` (string), `status` ("pending"), and `created_at` (Unix timestamp ms).

#### Scenario: Mark applied to inserted AI text
- **WHEN** any AI feature inserts text into the editor
- **THEN** the inserted text range SHALL be wrapped with an `ai-generated` mark containing the request ID, feature source, the original generated text, status "pending", and the creation timestamp

#### Scenario: Mark attributes are queryable
- **WHEN** the editor state is inspected
- **THEN** all `ai-generated` marks SHALL be discoverable via ProseMirror's `doc.descendants()` iteration with their full attribute set

### Requirement: AIAnnotationTracker Plugin
The system SHALL provide a ProseMirror Plugin that monitors all transactions touching regions with pending `ai-generated` marks.

#### Scenario: Modification detected within pending mark
- **WHEN** a user edits text inside a pending `ai-generated` mark range
- **THEN** the tracker SHALL compare the current text content of the mark range with the `original_text` attribute
- **AND** if they differ, the tracker SHALL record a pending modification diff (original vs. current)

#### Scenario: No modification when text unchanged
- **WHEN** a transaction occurs but does not change text within a pending mark range
- **THEN** the tracker SHALL NOT flag a modification

#### Scenario: Transaction mapping preserves mark ranges
- **WHEN** text is inserted or deleted before a pending `ai-generated` mark
- **THEN** ProseMirror's transaction mapping SHALL correctly update the mark's from/to positions without manual intervention

### Requirement: Single pending mark constraint
The system SHALL ensure at most one pending `ai-generated` mark exists at any time.

#### Scenario: New AI insertion while mark is pending
- **WHEN** a new AI text insertion is triggered while a pending mark exists
- **THEN** the existing pending mark SHALL be auto-resolved as accepted (mark removed, text stays, implicit ACCEPT feedback event queued)
- **AND** the new insertion SHALL create a fresh pending mark

### Requirement: Clean Save behavior
The system SHALL remove all `ai-generated` marks before persisting chapter content.

#### Scenario: Autosave fires with pending mark
- **WHEN** the Autosave extension triggers a save while a pending `ai-generated` mark exists
- **THEN** the mark SHALL be removed from the document before the save function is called
- **AND** the text content SHALL remain in the document as normal prose
- **AND** an ACCEPT feedback event SHALL be recorded with the `request_id` and `source` from the mark's attributes

#### Scenario: Autosave fires with modified pending mark
- **WHEN** autosave triggers and the pending mark's text differs from `original_text`
- **THEN** a MODIFY feedback event SHALL be recorded instead of ACCEPT
- **AND** the event SHALL include both the `original_text` and the current text as `modification`

#### Scenario: No pending marks on save
- **WHEN** autosave triggers and no pending marks exist
- **THEN** save proceeds normally with no additional processing

### Requirement: Mark lifecycle resolution
The system SHALL provide explicit resolution actions for pending marks.

#### Scenario: Accept action
- **WHEN** the user triggers "Keep" on a pending mark
- **THEN** the mark SHALL be removed (text stays as normal prose)
- **AND** a feedback event SHALL be recorded (ACCEPT or MODIFY depending on whether the text was edited)

#### Scenario: Reject action
- **WHEN** the user triggers "Undo" on a pending mark
- **THEN** the marked text SHALL be removed from the document via ProseMirror undo
- **AND** a REJECT feedback event SHALL be recorded with the `original_text`

#### Scenario: Rating after resolution
- **WHEN** a pending mark is resolved (accept or reject)
- **THEN** the RatingPrompt component SHALL be displayed
- **AND** the optional rating (1–5) and reason SHALL be included in the feedback event

### Requirement: AIAnnotationUI floating actions
The system SHALL render floating accept/reject/rate controls adjacent to the pending `ai-generated` mark in the editor viewport.

#### Scenario: Floating actions appear on pending mark
- **WHEN** a pending `ai-generated` mark exists in the document
- **THEN** a floating UI element SHALL appear positioned near the marked region
- **AND** the element SHALL display "Keep" (accept), "Undo" (reject), and contextual information (word count, source label)

#### Scenario: Floating actions disappear on resolution
- **WHEN** the pending mark is resolved (accept, reject, or clean save)
- **THEN** the floating UI element SHALL be removed from the viewport

#### Scenario: Source label reflects feature origin
- **WHEN** a pending mark has `source: "extend"`
- **THEN** the floating actions SHALL display a label like "AI Continuation" (source-specific, i18n-keyed)
