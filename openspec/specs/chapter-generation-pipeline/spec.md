# Chapter Generation Pipeline

**Purpose**: The system SHALL orchestrate AI chapter generation across multiple modes using existing infrastructure while ensuring proper error handling and post-processing.

## Requirements

### Requirement: Pipeline orchestrates generation in four modes
The system SHALL provide a `WritingPipeline` that orchestrates context assembly, prompt building, LLM streaming, and post-processing. The pipeline SHALL support four generation modes: `full_draft`, `scene_by_scene`, `interview_assisted`, and `interactive_session`.

#### Scenario: Full draft generation
- **WHEN** the pipeline is invoked with mode `full_draft`, a chapter ID, and a user prompt or outline
- **THEN** the system assembles writing context, builds the generation prompt, streams LLM output via the gateway, post-processes the generated text, and returns a streaming generator of text chunks.

#### Scenario: Scene-by-scene generation first scene
- **WHEN** the pipeline is invoked with mode `scene_by_scene`, a chapter ID, and a scene outline
- **THEN** the system generates only the first scene from the outline, streams it, and signals completion. The pipeline SHALL wait for a client signal before generating the next scene.

#### Scenario: Interview-assisted generation
- **WHEN** the pipeline is invoked with mode `interview_assisted` and a chapter ID
- **THEN** the system conducts a structured interview (3-5 questions about scene goals, characters, tone, conflict, length), collects answers, then performs `full_draft` generation using the interview answers as context.

#### Scenario: Interactive session generation
- **WHEN** the pipeline is invoked with mode `interactive_session` and a chapter ID
- **THEN** the system enters a conversational loop where the user provides direction and the AI generates prose iteratively. The pipeline maintains conversation history and prose buffer across turns.

### Requirement: Pipeline consumes existing infrastructure
The pipeline SHALL use `PromptComposer` for prompt building, `LLMGateway` for LLM calls (RULE-01), and the foundation's memory layer for preference injection. The pipeline SHALL NOT make direct LLM provider calls.

#### Scenario: Pipeline uses gateway for all LLM calls
- **WHEN** the pipeline generates text in any mode
- **THEN** every LLM call goes through `LLMGateway.run()` or `LLMGateway.stream()` with `LLMIntent.WRITE`. No direct provider imports exist outside `core/llm/`.

#### Scenario: Pipeline uses PromptComposer for prompt assembly
- **WHEN** the pipeline builds a generation prompt
- **THEN** it delegates to `PromptComposer.build()` with a `PromptContext` populated from the assembled `WritingContext`. No prompt f-strings exist in the pipeline code (RULE-02).

### Requirement: Post-processing cleans generated text
The system SHALL post-process generated text to: strip LLM artifacts (prefixed labels like "Chapter 1:", "Here's the draft:"), normalize Markdown formatting, remove incomplete trailing sentences, and enforce word count limits.

#### Scenario: LLM artifacts removed from output
- **WHEN** the LLM generates text starting with "Here is your chapter draft:" followed by the actual prose
- **THEN** the post-processor strips the prefix and returns only the prose content.

#### Scenario: Incomplete trailing sentence cleaned
- **WHEN** generation is stopped mid-stream and the last sentence is incomplete (no terminal punctuation)
- **THEN** the post-processor removes the incomplete trailing sentence fragment.

#### Scenario: Word count target enforced
- **WHEN** the user sets a word count target and the LLM exceeds it by more than 10%
- **THEN** the post-processor truncates the output at the nearest complete sentence at or above the target word count.

### Requirement: Pipeline handles generation failures gracefully
The system SHALL handle LLM errors, token limit errors, and timeout errors without data loss. Partial generation results SHALL be preserved.

#### Scenario: LLM provider returns an error mid-generation
- **WHEN** the LLM provider returns an error after 500 words have been streamed
- **THEN** the system preserves the 500 words of partial generation, marks the generation request as `failed` with the error message, and makes the partial text available to the user.

#### Scenario: Generation exceeds model token limit
- **WHEN** the generation is approaching the model's maximum output token limit
- **THEN** the system stops generation cleanly at the nearest complete sentence, marks the generation as `completed` with a `truncated` flag, and notifies the user that the output was truncated.

### Requirement: Pipeline supports stop signal
The system SHALL support stopping an in-progress generation at any time. Stopped generations preserve all text generated up to the stop point.

#### Scenario: User stops generation mid-stream
- **WHEN** a user sends a stop signal during an active generation
- **THEN** the system stops the LLM call, preserves all text generated so far, and marks the generation request as `stopped`.
