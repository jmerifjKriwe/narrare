## ADDED Requirements

### Requirement: ChapterSummaryAgent generates structured summaries

The system SHALL implement a `ChapterSummaryAgent` as a subclass of `NarrareAgent` that generates concise chapter summaries via LLM.

- The agent SHALL accept `SummaryDeps` with fields: `language: str`, `genre: str`, `chapter_title: str`, `max_sentences: int` (default 4)
- The agent SHALL produce `SummaryOutput` with fields: `summary: str` (2-4 sentences), `key_points: list[str]`, `word_count: int`
- The agent SHALL use the pydantic-ai output function pattern (`_process_summary`) to structure LLM responses
- The agent SHALL use a system prompt placed at `prompts/_bundled/writing/en/summary/system.md`

#### Scenario: Summary generated from chapter content
- **WHEN** the agent receives chapter content with `language="en"` and `max_sentences=4`
- **THEN** the output SHALL contain a non-empty `summary` field with 2-4 sentences
- **AND** the output SHALL contain a `key_points` list with at least one entry
- **AND** the output SHALL contain a `word_count` integer > 0

#### Scenario: Agent works with TestModel
- **WHEN** the agent is instantiated with a `FunctionModel` (pydantic-ai TestModel)
- **THEN** the agent SHALL produce valid `SummaryOutput` without any real LLM call

#### Scenario: Short content produces short summary
- **WHEN** the input content is very short (< 100 words)
- **THEN** the summary SHALL be proportionally shorter (1-2 sentences)
- **AND** the key_points list SHALL contain at most the same number of sentences

### Requirement: Summary prompt file exists at correct path

The system SHALL provide a prompt file at `prompts/_bundled/writing/en/summary/system.md` that is auto-discoverable by the PromptComposer.

- The prompt SHALL instruct the LLM to generate concise, plot-relevant summaries
- The prompt SHALL instruct the LLM to identify key points (character developments, plot advances, setting changes)
- The file path SHALL match the Composer's category mapping: category `analysis`, mode `summarize`, language `en`

#### Scenario: Prompt is auto-discoverable
- **WHEN** `composer.build(LLMIntent.SUMMARIZE, context)` is called with `context.language="en"`
- **THEN** the composer SHALL find and load the prompt from `analysis/en/summarize/system.md`
- **AND** the composed prompt SHALL contain a non-empty `system` field

### Requirement: SummaryOutput types are defined

The system SHALL define `SummaryOutput` as a Pydantic BaseModel with the following fields:
- `summary: str` — The generated summary text
- `key_points: list[str]` — Key narrative points extracted from the chapter
- `word_count: int` — Word count of the summary itself
- `metadata: dict[str, Any]` — Additional metadata (model, tokens used, etc.)

#### Scenario: SummaryOutput can be created with defaults
- **WHEN** `SummaryOutput()` is instantiated with no arguments
- **THEN** `summary` SHALL be `""`, `key_points` SHALL be `[]`, `word_count` SHALL be `0`

#### Scenario: SummaryOutput can be created with values
- **WHEN** `SummaryOutput(summary="Chapter summary", key_points=["Plot point"], word_count=10)` is created
- **THEN** all fields SHALL match the provided values
