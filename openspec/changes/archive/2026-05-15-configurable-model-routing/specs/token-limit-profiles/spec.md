## ADDED Requirements

### Requirement: Named token limit profiles
The system SHALL provide named token limit profiles that define default generation parameters (temperature, max_tokens) for all categories:

| Profile | Description |
|---------|-------------|
| quick | Low token limits, fast responses (max_tokens: 500 default) |
| balanced | Moderate limits for most use cases (max_tokens: 2000 default) |
| long_texts | High limits for long-form writing (max_tokens: 8000 default) |
| custom | User-defined per-category limits |

#### Scenario: Default profile for new user
- **WHEN** user completes setup
- **THEN** their token limit profile is set to "balanced"

#### Scenario: Select quick profile
- **WHEN** user selects the "quick" profile
- **THEN** all categories use the quick defaults (lower max_tokens) unless individually overridden

### Requirement: Per-category token limit overrides
Within a token limit profile, users SHALL be able to override `max_tokens` per category. A per-category override SHALL take precedence over the profile default for that category.

#### Scenario: Override max_tokens for writing category
- **WHEN** user has profile "balanced" (max_tokens: 2000) AND override for "writing" = `{max_tokens: 8000}`
- **THEN** writing intents use max_tokens=8000; analysis intents use max_tokens=2000 (profile default)

#### Scenario: Override temperature for analysis category
- **WHEN** user sets override for "analysis" = `{temperature: 0.2}`
- **THEN** analysis intents use temperature=0.2; writing intents use the profile/writing default

### Requirement: Per-intent token limit overrides
Users SHALL be able to override `max_tokens` and `temperature` for individual intents, overriding both the profile default and the category override.

#### Scenario: Intent override takes precedence over category
- **WHEN** user has category override for "analysis" = `{max_tokens: 1500}` AND intent override for `SENTIMENT` = `{max_tokens: 500}`
- **THEN** SENTIMENT uses max_tokens=500; other analysis intents use max_tokens=1500

### Requirement: Token limit resolution follows cascade
Token limit resolution SHALL follow the same cascade as model routing: project-level intent → project-level category → user-level intent → user-level category → profile default.

#### Scenario: Project-level token limit override
- **WHEN** project has override for "writing" = `{max_tokens: 12000}` AND user has override for "writing" = `{max_tokens: 8000}`
- **THEN** writing intents in that project use max_tokens=12000 (project wins)

#### Scenario: No overrides, profile default applies
- **WHEN** user has profile "balanced" and no category or intent overrides
- **THEN** all intents use the balanced profile defaults

### Requirement: Token limits are validated against provider context window
The system SHALL validate that `max_tokens` does not exceed the known context window of the selected model. If the context window is unknown, validation SHALL be skipped with a warning.

#### Scenario: max_tokens exceeds context window
- **WHEN** user sets max_tokens=200000 for a model with context window 128000
- **THEN** system rejects the setting with error "max_tokens (200000) exceeds model context window (128000)"

#### Scenario: Unknown context window
- **WHEN** user sets max_tokens=8000 for a model with unknown context window
- **THEN** system accepts the setting with warning "Could not verify max_tokens against model context window"

### Requirement: Token limit overrides stored as validated JSONB
Token limit overrides at user and project level SHALL be stored as JSONB columns validated by Pydantic schemas. The schema SHALL enforce: `max_tokens >= 1`, `temperature >= 0.0 and <= 2.0`.

#### Scenario: Invalid temperature rejected
- **WHEN** user submits override with temperature=3.0
- **THEN** system rejects with validation error "temperature must be between 0.0 and 2.0"

#### Scenario: Invalid max_tokens rejected
- **WHEN** user submits override with max_tokens=0
- **THEN** system rejects with validation error "max_tokens must be at least 1"
