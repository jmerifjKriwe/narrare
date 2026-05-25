## ADDED Requirements

### Requirement: GenerationMode.REWRITE enum value
The system SHALL define `REWRITE = "rewrite"` in the `GenerationMode` enum (`core/writing/_enums.py`) and the corresponding `GenerationModeEnum` in `apps/api/narrare/writing/schemas.py`.

#### Scenario: Pipeline dispatches to rewrite
- **WHEN** `WritingPipeline.generate()` receives a request with `mode == GenerationMode.REWRITE`
- **THEN** the pipeline SHALL delegate to `WritingPipeline._rewrite()`

#### Scenario: Invalid mode rejected
- **WHEN** a request is created with mode "rewrite" but no `selection_text` is provided
- **THEN** validation SHALL reject the request with code `MISSING_INPUT`

### Requirement: RewriteRequest API schema
The system SHALL define a `RewriteRequest` Pydantic model with fields: `selection_text` (str, required, min 50 chars, max 2000 chars), `context_before` (str, optional, max 500 characters), `context_after` (str, optional, max 500 characters), `mode` (RewriteMode enum: "tone" | "style" | "voice" | "fix" | "custom"), `options` (dict, optional, mode-specific settings), `character_id` (UUID, optional, required when mode is "voice"), `custom_instructions` (str, optional, max 500 chars, required when mode is "custom"), `count` (int, default 1, ge 1, le 3), `tone` (str, default "balanced"), `language` (str, default "en").

#### Scenario: Valid rewrite request with tone mode
- **WHEN** a request with `selection_text`, `mode: "tone"`, `options: {"shift": "more_dramatic"}`, `count: 2` is submitted
- **THEN** the system SHALL accept the request and create a generation_request row

#### Scenario: Voice mode without character_id rejected
- **WHEN** a request with `mode: "voice"` but no `character_id` is submitted
- **THEN** the system SHALL return a 422 validation error

#### Scenario: Custom mode without instructions rejected
- **WHEN** a request with `mode: "custom"` but no `custom_instructions` is submitted
- **THEN** the system SHALL return a 422 validation error

#### Scenario: Selection text too short rejected
- **WHEN** a request with `selection_text` shorter than 50 characters is submitted
- **THEN** the system SHALL return a 422 validation error

#### Scenario: Selection text too long rejected
- **WHEN** a request with `selection_text` longer than 2000 characters is submitted
- **THEN** the system SHALL return a 422 validation error

### Requirement: POST /rewrite SSE-direct endpoint
The system SHALL expose `POST /api/v1/writing/chapters/{chapter_id}/rewrite` that accepts `RewriteRequest`, validates chapter access, checks for concurrent generation, assembles context, invokes the writing pipeline in rewrite mode, and returns an SSE stream directly with `<alternative>` tagged chunks.

#### Scenario: Successful rewrite initiation
- **WHEN** a valid RewriteRequest is submitted for a chapter the user owns
- **THEN** the system SHALL create a `generation_request` row with `mode = "rewrite"` and status "streaming"
- **AND** the SSE response SHALL stream alternatives wrapped in `<alternative>` tags

#### Scenario: Concurrent rewrite prevention
- **WHEN** a rewrite request is submitted while another generation is active for the same chapter
- **THEN** the system SHALL return a 409 Conflict error

#### Scenario: Unauthorized chapter access
- **WHEN** a rewrite request targets a chapter the user does not own
- **THEN** the system SHALL return a 404 error

### Requirement: WritingPipeline._rewrite() method
The system SHALL implement `_rewrite()` on `WritingPipeline` (extracted into `pipeline_rewrite.py` per RULE-04) that performs a single LLM call using the `rewrite_selection` prompt, streams the result, and applies `DraftProcessor` post-processing.

#### Scenario: Rewrite produces structured multi-alternative output
- **WHEN** `_rewrite()` is called with `count=2`
- **THEN** the prompt SHALL instruct the LLM to produce 2 alternatives wrapped in `<alternative label="...">` tags

#### Scenario: Rewrite uses rewrite_selection prompt
- **WHEN** `_rewrite()` builds the prompt context
- **THEN** it SHALL set `mode="rewrite_selection"` so the composer resolves to `prompts/_bundled/writing/{lang}/rewrite_selection/system.md`

#### Scenario: Rewrite assembles selection context
- **WHEN** `_rewrite()` assembles context for the prompt
- **THEN** it SHALL include `selection_text`, `context_before`, `context_after`, `rewrite_mode_instructions` (mode-specific strategy), `character_profile` (if voice mode), and `tone_instructions`

#### Scenario: Rewrite uses rewrite-specific budget allocation
- **WHEN** `_rewrite()` allocates context budget
- **THEN** the `TokenBudgetManager` SHALL use `_REWRITE_PERCENTAGES` (immediate: 40%, recent: 15%, kb_referenced: 25%, kb_suggested: 10%, pinned: 10%)
- **AND** the `immediate` tier SHALL include selection text, context_before, and context_after

### Requirement: Rewrite prompt structured output
The rewrite prompt templates SHALL produce structured output with `<alternative>` XML tags, one per requested alternative.

#### Scenario: Single alternative output
- **WHEN** the prompt is invoked with `count=1`
- **THEN** the output SHALL contain a single `<alternative label="Rewritten text">` block

#### Scenario: Multiple alternative output
- **WHEN** the prompt is invoked with `count=3`
- **THEN** the output SHALL contain 3 `<alternative label="...">` blocks with distinct labels reflecting each alternative's focus

#### Scenario: Mode-specific instructions in prompt
- **WHEN** the rewrite mode is "tone" with options `{"shift": "more_dramatic"}`
- **THEN** the prompt SHALL include tone-specific rewrite instructions (adjust emotional language, pacing, word choice)

#### Scenario: Voice mode includes character profile
- **WHEN** the rewrite mode is "voice" with a `character_id`
- **THEN** the prompt SHALL include the character's speech patterns, personality traits, and vocabulary preferences from the KB

#### Scenario: Prompt instructs LLM to avoid alternative tags in content
- **WHEN** the rewrite prompt is composed
- **THEN** it SHALL include an instruction that the LLM MUST NOT use `<alternative>` or `</alternative>` tags within the rewritten text content
- **AND** the LLM SHALL only use these tags as structural delimiters between alternatives

#### Scenario: Voice mode with character lacking speech metadata
- **WHEN** voice mode is selected with a valid `character_id` but the character entity has no speech metadata in the KB
- **THEN** the system SHALL proceed using the character's name and any available personality traits
- **AND** the voice profile section in the prompt SHALL be empty (graceful degradation)
- **AND** the rewrite SHALL still be produced, relying on the character's name and context rather than specific speech patterns

### Requirement: RewriteService with SSE streaming
The system SHALL implement a `RewriteService` class (in `writing/rewrite_service.py`, separate from WritingService per RULE-04) with a `stream_rewrite()` method that creates the generation request AND streams alternatives in a single HTTP response.

#### Scenario: SSE stream with alternatives
- **WHEN** `stream_rewrite()` is called
- **THEN** the first SSE event SHALL contain `type: "request_info"` with `request_id`
- **AND** subsequent events SHALL contain text chunks within `<alternative>` blocks
- **AND** the final event SHALL contain `is_final: true` with token usage

#### Scenario: Stream error handling
- **WHEN** an LLM call fails during streaming
- **THEN** the service SHALL send an SSE error event and close the stream gracefully

### Requirement: RewriteServiceProtocol contract
The system SHALL define a `RewriteServiceProtocol` in `writing/contracts_rewrite.py` (RULE-03) specifying the `stream_rewrite()` method signature, before implementation.

#### Scenario: Dependency injection uses protocol
- **WHEN** the FastAPI dependency `get_rewrite_service()` is called
- **THEN** it SHALL return an instance that satisfies `RewriteServiceProtocol`

### Requirement: Rewrite budget allocation
The `TokenBudgetManager` SHALL define `_REWRITE_PERCENTAGES` as a `ClassVar[dict[str, float]]` with values: `immediate: 0.40`, `recent: 0.15`, `kb_referenced: 0.25`, `kb_suggested: 0.10`, `pinned: 0.10`.

#### Scenario: Rewrite mode selects rewrite percentages
- **WHEN** `TokenBudgetManager.allocate(mode="rewrite")` is called
- **THEN** the budget SHALL use `_REWRITE_PERCENTAGES` instead of `_BASE_PERCENTAGES` or `_EXTEND_PERCENTAGES`

#### Scenario: Rewrite budget emphasizes KB entities for voice mode
- **WHEN** rewrite mode is "voice" and a `character_id` is provided
- **THEN** the `kb_referenced` tier (25%) SHALL be populated with the referenced character's profile including speech patterns, personality traits, and vocabulary

### Requirement: Rewrite feedback lifecycle integration
The rewrite feature SHALL reuse the existing accept/reject/feedback endpoints for post-generation feedback.

#### Scenario: Accept rewrite alternative
- **WHEN** the user accepts a rewrite alternative
- **THEN** a FeedbackEvent with action ACCEPT SHALL be recorded with source "rewrite"

#### Scenario: Reject rewrite alternative
- **WHEN** the user rejects a rewrite alternative
- **THEN** a FeedbackEvent with action REJECT SHALL be recorded with source "rewrite"

#### Scenario: Modify and accept rewrite alternative
- **WHEN** the user accepts a rewrite alternative but modifies the text
- **THEN** a FeedbackEvent with action MODIFY SHALL be recorded with the original and modified text
