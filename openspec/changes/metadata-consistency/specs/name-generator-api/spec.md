## MODIFIED Requirements

### Requirement: Generate names endpoint
The system SHALL provide a `POST /api/v1/generation/names` endpoint that accepts name_type, name_style, count, gender, and explanation_language parameters, and returns a list of generated names with metadata. **BREAKING**: `culture` field renamed to `name_style`, `language` field renamed to `explanation_language`.

#### Scenario: Generate fantasy character names with new fields
- **WHEN** `POST /api/v1/generation/names` is called with `name_type="character"`, `name_style="fantasy"`, `count=10`, `explanation_language="en"`
- **THEN** a list of 10 generated names is returned, each with `name`, `pronunciation` (optional), `meaning` (optional), and `is_duplicate` (checked against KB)

#### Scenario: Generate names with freetext name_style
- **WHEN** `POST /api/v1/generation/names` is called with `name_style="Nordische Mythologie, aber futuristisch"`
- **THEN** the request succeeds and generates names fitting that description
- **AND** the name_style string is passed to the prompt as a natural language instruction

#### Scenario: Generate names with novel writing_language as default explanation_language
- **WHEN** the name generator is invoked from the UI without explicitly setting explanation_language
- **THEN** explanation_language defaults to the novel's writing_language

#### Scenario: Legacy culture field rejected
- **WHEN** `POST /api/v1/generation/names` is called with `culture="fantasy"` (old field name)
- **THEN** a 422 validation error is returned indicating the field is not recognized

### Requirement: Name generator uses generation intent
The system SHALL route name generation through `LLMIntent.NAME_GENERATE` and use the `PromptComposer` to build the prompt with name_style injection and explanation_language instruction.

#### Scenario: Correct intent used with new fields
- **WHEN** `NameGeneratorService.generate()` is called
- **THEN** it calls `PromptComposer.build()` with `LLMIntent.NAME_GENERATE` and context containing `name_style`, `name_type`, `count`, `gender`, `explanation_language`, and `existing_names`
- **AND** the prompt file is selected based on UI language
- **AND** the explanation_language is injected as "Erkläre die Namensbedeutungen auf: {explanation_language}"

### Requirement: Name generator schemas
The system SHALL define Pydantic request/response schemas in `generation/schemas.py` for the name generation endpoint with validation (count: 1-50, name_type enum, name_style: freetext string 1-100 chars, gender enum, explanation_language: string 2-50 chars).

#### Scenario: Name_style freetext accepted
- **WHEN** `POST /api/v1/generation/names` is called with `name_style="Klingonische Namen aus Star Trek"`
- **THEN** the request is accepted and names are generated

#### Scenario: Empty name_style rejected
- **WHEN** `POST /api/v1/generation/names` is called with `name_style=""`
- **THEN** a 422 validation error is returned

### Requirement: Name generator returns structured output
The system SHALL request structured JSON output from the LLM and parse it into typed `GeneratedName` objects. The `culture` response field is renamed to `name_style`.

#### Scenario: Structured response parsed with new field
- **WHEN** the LLM returns a JSON array of name objects
- **THEN** each is parsed into a `GeneratedName` with typed fields: `name: str`, `pronunciation: str | None`, `meaning: str | None`, `type: NameType`, `name_style: str`, `is_duplicate: bool`, `confidence: float`

## ADDED Requirements

### Requirement: Name style datalist suggestions
The Name Generator UI SHALL provide `<datalist>` suggestions for common name styles to guide users while allowing freetext input.

#### Scenario: Datalist shows name style suggestions
- **WHEN** the user types in the name_style input field
- **THEN** the browser shows filtered suggestions from a predefined list including: Fantasy, Sci-Fi, Nordisch, Elbisch, Arabisch, Japanisch, Keltisch, Steampunk, Cyberpunk, Römisch, Afrikanisch, Viktorianisch
- **AND** the user can type any custom value

## REMOVED Requirements

### Requirement: Generate with culture not found
**Reason**: Replaced by freetext name_style — there is no "not found" state for freetext. The name_style string is always passed to the LLM as a natural language instruction.
**Migration**: Any code that resolved culture definition files and handled "not found" gracefully now passes the name_style string directly. If a matching definition file exists, it can still be resolved; otherwise the raw string is used.

### Requirement: Culture definition cascade override (from prompt-culture-injection)
**Reason**: With freetext name_style, the structured culture definition file system becomes optional rather than required. The name_style is passed as a prompt variable directly. Pre-existing definition files can still be resolved when they match, but the system no longer requires them.
**Migration**: Culture definition files are renamed to name-style definition files. The cascade mechanism remains but is used opportunistically (if a matching file exists, use it; otherwise raw string).
