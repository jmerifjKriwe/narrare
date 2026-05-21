## ADDED Requirements

### Requirement: SummaryService orchestrates chapter summarization

The system SHALL implement a `SummaryService` in `apps/api/narrare/writing/summary_service.py` that orchestrates chapter summarization.

- The service SHALL accept a `chapter_id` and optional `SummaryConfig` (max_sentences, language override)
- The service SHALL use `ModelRegistry` to get a model for the `LLMIntent.SUMMARIZE` intent
- The service SHALL instantiate `ChapterSummaryAgent` and run it with the chapter's content
- The service SHALL persist the resulting summary to `chapters.summary`
- The service SHALL return the generated summary text and word count

#### Scenario: Summary generated and persisted
- **WHEN** `summary_service.summarize(chapter_id)` is called with a valid chapter ID
- **THEN** the service SHALL call `ChapterSummaryAgent.run()` with the chapter content
- **AND** the service SHALL update `chapter.summary` with the generated text
- **AND** the service SHALL return `SummaryResponse(summary="...", word_count=N)`

#### Scenario: Chapter not found
- **WHEN** `summary_service.summarize(nonexistent_id)` is called
- **THEN** the service SHALL raise `NotFoundError`

#### Scenario: LLM failure during summarization
- **WHEN** the `ChapterSummaryAgent` raises an exception
- **THEN** the service SHALL catch the exception, log it, and raise `WritingError`
- **AND** the chapter summary SHALL remain unchanged

### Requirement: REST endpoint POST /api/v1/chapters/{id}/summarize

The system SHALL expose a REST endpoint to trigger chapter summarization.

- The endpoint SHALL accept POST requests to `/api/v1/chapters/{chapter_id}/summarize`
- The endpoint SHALL accept an optional JSON body with `max_sentences` (int) and `language` (str)
- The endpoint SHALL require authentication (user owns the chapter's novel)
- The endpoint SHALL return `200 OK` with `{"summary": "...", "word_count": N}`

#### Scenario: Successful summarization
- **WHEN** a POST request is sent with a valid chapter ID the user owns
- **THEN** the response SHALL have status 200
- **AND** the response body SHALL contain `summary` (non-empty string) and `word_count` (int)

#### Scenario: Chapter not found
- **WHEN** a POST request is sent with a nonexistent chapter ID
- **THEN** the response SHALL have status 404

#### Scenario: Unauthorized access
- **WHEN** a POST request is sent by a user who does not own the chapter's novel
- **THEN** the response SHALL have status 403 or 404

### Requirement: SummaryServiceProtocol contract

The system SHALL define `SummaryServiceProtocol` in `contracts.py` with:
- `summarize(chapter_id: UUID) -> SummaryResult` method signature
- `SummaryResult` dataclass with `summary: str`, `word_count: int`, `key_points: list[str]`

#### Scenario: Protocol is usable for DI
- **WHEN** a class is annotated with `SummaryServiceProtocol` as a dependency
- **THEN** any class implementing the protocol methods SHALL be accepted structurally
