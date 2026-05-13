## ADDED Requirements

### Requirement: Name generator contract
The system SHALL define a `NameGeneratorProtocol` in `generation/contracts.py` that specifies the interface for name generation operations.

#### Scenario: Protocol defined before implementation
- **WHEN** the generation module is implemented
- **THEN** `contracts.py` with `NameGeneratorProtocol` exists before `name_service.py`

### Requirement: Generate names endpoint
The system SHALL provide a `POST /api/v1/generation/names` endpoint that accepts name_type, culture, count, gender, and language parameters, and returns a list of generated names with metadata.

#### Scenario: Generate fantasy character names
- **WHEN** `POST /api/v1/generation/names` is called with `name_type="character"`, `culture="fantasy"`, `count=10`, `language="en"`
- **THEN** a list of 10 generated names is returned, each with `name`, `pronunciation` (optional), `meaning` (optional), and `is_duplicate` (checked against KB)

#### Scenario: Generate with culture not found
- **WHEN** `POST /api/v1/generation/names` is called with `culture="nonexistent"`
- **THEN** the request succeeds but uses the base prompt without culture guidelines (graceful degradation)

### Requirement: Name deduplication against KB
The system SHALL check generated names against existing Knowledge Base entries for the project and mark duplicates with `is_duplicate: true`.

#### Scenario: Duplicate detected
- **WHEN** name generation produces "Elara" and a character named "Elara" already exists in the project's KB
- **THEN** the generated name entry has `is_duplicate: true`

#### Scenario: No duplicate
- **WHEN** name generation produces a unique name not found in the project's KB
- **THEN** the generated name entry has `is_duplicate: false`

### Requirement: Name generator uses generation intent
The system SHALL route name generation through `LLMIntent.NAME_GENERATE` and use the `PromptComposer` to build the prompt with culture injection.

#### Scenario: Correct intent used
- **WHEN** `NameGeneratorService.generate()` is called
- **THEN** it calls `PromptComposer.build()` with `LLMIntent.NAME_GENERATE` and context containing `culture`, `name_type`, `count`, and `existing_names`

### Requirement: Name generator returns structured output
The system SHALL request structured JSON output from the LLM and parse it into typed `GeneratedName` objects.

#### Scenario: Structured response parsed
- **WHEN** the LLM returns a JSON array of name objects
- **THEN** each is parsed into a `GeneratedName` with typed fields: `name: str`, `pronunciation: str | None`, `meaning: str | None`, `type: NameType`, `culture: str`, `is_duplicate: bool`, `confidence: float`

### Requirement: Name generator schemas
The system SHALL define Pydantic request/response schemas in `generation/schemas.py` for the name generation endpoint with validation (count: 1-50, name_type enum, culture string, gender enum).

#### Scenario: Invalid count rejected
- **WHEN** `POST /api/v1/generation/names` is called with `count=100`
- **THEN** a 422 validation error is returned indicating count must be between 1 and 50

#### Scenario: Invalid name type rejected
- **WHEN** `POST /api/v1/generation/names` is called with `name_type="invalid_type"`
- **THEN** a 422 validation error is returned
