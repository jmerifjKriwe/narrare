# Extend Chapter

**Purpose**: The system SHALL provide an "extend" generation mode that continues writing from existing chapter content, enabling users to generate AI text inline in the editor with annotation tracking and feedback lifecycle integration.

## Requirements

### Requirement: GenerationMode.EXTEND enum value
The system SHALL define `EXTEND = "extend"` in the `GenerationMode` enum (`core/writing/_enums.py`) and the corresponding `GenerationModeEnum` in `apps/api/narrare/writing/schemas.py`.

#### Scenario: Pipeline dispatches to extend
- **WHEN** `WritingPipeline.generate()` receives a request with `mode == GenerationMode.EXTEND`
- **THEN** the pipeline SHALL delegate to `WritingPipeline._extend()`

#### Scenario: Invalid mode rejected
- **WHEN** a request is created with mode "extend" but no `text_before` is provided
- **THEN** validation SHALL reject the request with code `MISSING_INPUT`

### Requirement: ExtendRequest API schema
The system SHALL define an `ExtendRequest` Pydantic model with fields: `text_before` (str, required, max 10000), `text_after` (str, optional, max 2000), `length` (ExtendLength enum: "short" | "medium" | "long"), `tone` (str, default "balanced"), `language` (str, default "en").

#### Scenario: Valid extend request
- **WHEN** a request with `text_before`, `length: "medium"`, `tone: "balanced"` is submitted
- **THEN** the system SHALL accept the request and create a generation_request row

#### Scenario: Missing text_before rejected
- **WHEN** a request without `text_before` is submitted
- **THEN** the system SHALL return a 422 validation error

### Requirement: POST /extend endpoint
The system SHALL expose `POST /api/v1/writing/chapters/{chapter_id}/extend` that accepts `ExtendRequest`, validates chapter access, creates a `generation_request` with `mode = "extend"`, and returns `{request_id, status, mode}`.

#### Scenario: Successful extend initiation
- **WHEN** a valid ExtendRequest is submitted for a chapter the user owns
- **THEN** a `generation_request` row SHALL be created with status "pending"
- **AND** the response SHALL contain `request_id`, `status: "pending"`, `mode: "extend"`

#### Scenario: Concurrent extend prevention
- **WHEN** an extend request is submitted while another is active for the same chapter
- **THEN** the system SHALL return a 409 Conflict error

#### Scenario: Unauthorized chapter access
- **WHEN** an extend request targets a chapter the user does not own
- **THEN** the system SHALL return a 404 error

### Requirement: WritingPipeline._extend() method
The system SHALL implement `_extend()` on `WritingPipeline` that performs a single LLM call using the `extend_chapter` prompt, streams the result, and applies `DraftProcessor` post-processing.

#### Scenario: Extend produces streaming output
- **WHEN** `_extend()` is called with a valid request and assembled context
- **THEN** it SHALL yield `StreamChunk` instances containing text fragments
- **AND** the final chunk SHALL have `is_final=True` with token usage

#### Scenario: Extend uses extend_chapter prompt
- **WHEN** `_extend()` builds the prompt context
- **THEN** it SHALL set `mode="extend_chapter"` so the composer resolves to `prompts/_bundled/writing/{lang}/extend_chapter/system.md`

#### Scenario: Extend respects length preference
- **WHEN** `length` is "short" → word_target ~150, "medium" → ~400, "long" → ~750
- **THEN** the `word_target` SHALL be passed to the prompt context as a hint

### Requirement: Extend prompt files
The system SHALL include `extend_chapter/system.md` prompt files in three languages (en, de, fr) under `prompts/_bundled/writing/{lang}/extend_chapter/`.

#### Scenario: English prompt resolves
- **WHEN** the composer resolves `LLMIntent.EXTEND` with `language="en"`
- **THEN** it SHALL load `prompts/_bundled/writing/en/extend_chapter/system.md`

#### Scenario: German prompt resolves
- **WHEN** the composer resolves `LLMIntent.EXTEND` with `language="de"`
- **THEN** it SHALL load `prompts/_bundled/writing/de/extend_chapter/system.md`

#### Scenario: Fallback to English for unsupported language
- **WHEN** the composer resolves `LLMIntent.EXTEND` with a language that has no prompt file
- **THEN** it SHALL fall back to the English prompt per registry fallback logic

### Requirement: Extend reuses SSE streaming lifecycle
The extend endpoint SHALL reuse the existing `GET /generation/{request_id}/stream` SSE endpoint for streaming text chunks to the frontend.

#### Scenario: Extend streams via existing SSE endpoint
- **WHEN** a generation_request with mode "extend" is in "pending" status
- **THEN** `GET /generation/{request_id}/stream` SHALL stream extend output identically to other generation modes

### Requirement: Extend integrates with feedback lifecycle
The extend feature SHALL reuse the existing accept/reject/feedback endpoints (`POST /generation/{id}/accept`, `POST /generation/{id}/reject`).

#### Scenario: Accept extend draft
- **WHEN** the user accepts an extend draft
- **THEN** a FeedbackEvent with action ACCEPT SHALL be recorded
- **AND** mem0 SHALL receive the feedback for preference extraction

#### Scenario: Reject extend draft
- **WHEN** the user rejects an extend draft
- **THEN** a FeedbackEvent with action REJECT SHALL be recorded
- **AND** mem0 SHALL receive the rejection context

#### Scenario: Modify extend draft
- **WHEN** the user accepts an extend draft but modified the text
- **THEN** a FeedbackEvent with action MODIFY SHALL be recorded
- **AND** mem0 SHALL receive both the original and modified text
