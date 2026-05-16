# Capability: Generation Intents

## Purpose
Define LLM intent values, model routing configurations, category mappings, and mode mappings for generation-related AI operations (general generation, name generation, title generation). These intents drive prompt resolution and model selection in the LLM gateway.

## Requirements

### Requirement: Generation intent enumeration
The system SHALL define `GENERATE`, `NAME_GENERATE`, and `TITLE_GENERATE` as values in the `LLMIntent` enum in `core/llm/intents.py`.

#### Scenario: Intent values exist
- **WHEN** a developer inspects `LLMIntent` enum members
- **THEN** `GENERATE`, `NAME_GENERATE`, and `TITLE_GENERATE` are present with values `"generate"`, `"name_generate"`, and `"title_generate"` respectively

### Requirement: Generation intent model routing
The system SHALL define `ModelConfig` entries in `MODEL_ROUTING` for each generation intent with appropriate model, temperature, max_tokens, and streaming settings.

#### Scenario: NAME_GENERATE routing
- **WHEN** `get_model_config(LLMIntent.NAME_GENERATE)` is called
- **THEN** it returns a `ModelConfig` with temperature ≤ 0.7, max_tokens ≤ 1500, streams=False, and a fast/structured-output model

#### Scenario: TITLE_GENERATE routing
- **WHEN** `get_model_config(LLMIntent.TITLE_GENERATE)` is called
- **THEN** it returns a `ModelConfig` with temperature ≥ 0.7, max_tokens ≤ 500, streams=False, and a model suitable for creative short-form output

#### Scenario: GENERATE routing
- **WHEN** `get_model_config(LLMIntent.GENERATE)` is called
- **THEN** it returns a `ModelConfig` with balanced defaults suitable for general structured generation

### Requirement: Generation intent category mapping
The system SHALL map all generation intents to the `"generation"` category in `PromptComposer._INTENT_TO_CATEGORY`.

#### Scenario: Intent resolves to generation category
- **WHEN** `PromptComposer.build()` is called with `LLMIntent.NAME_GENERATE`
- **THEN** the category `"generation"` is used for prompt file resolution

### Requirement: Generation intent mode mapping
The system SHALL map each generation intent to a default mode in `PromptComposer._INTENT_TO_MODE`: `GENERATE` → `"general"`, `NAME_GENERATE` → `"names"`, `TITLE_GENERATE` → `"titles"`.

#### Scenario: NAME_GENERATE resolves to names mode
- **WHEN** `PromptComposer.build()` is called with `LLMIntent.NAME_GENERATE` and no explicit `context.mode`
- **THEN** the mode `"names"` is used for prompt file resolution
