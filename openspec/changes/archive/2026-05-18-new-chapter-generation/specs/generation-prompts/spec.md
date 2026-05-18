## ADDED Requirements

### Requirement: Bundled writing prompts for new chapter generation
The system SHALL provide bundled prompt templates under `prompts/_bundled/writing/` for new chapter generation in English, German, and French. Each language SHALL have system prompts for all four generation modes.

#### Scenario: Full draft system prompt loads correctly
- **WHEN** the `PromptComposer` resolves a prompt for `LLMIntent.WRITE` with mode `new_chapter` and language `en`
- **THEN** the system loads `prompts/_bundled/writing/en/new_chapter/system.md` containing the writing persona, generation instructions, and variable slots.

#### Scenario: Scene-by-scene prompt loads correctly
- **WHEN** the `PromptComposer` resolves a prompt for `LLMIntent.WRITE` with mode `scene_by_scene` and language `de`
- **THEN** the system loads `prompts/_bundled/writing/de/scene_by_scene/system.md`.

#### Scenario: Interactive session prompt loads correctly
- **WHEN** the `PromptComposer` resolves a prompt for `LLMIntent.CO_AUTHOR` with mode `interactive_session` and language `fr`
- **THEN** the system loads `prompts/_bundled/writing/fr/interactive_session/system.md`.

### Requirement: Prompt templates include required variable slots
All writing prompt templates SHALL include variable slots for: `{{project_title}}`, `{{genre}}`, `{{language}}`, `{{chapter_outline}}`, `{{kb_characters}}`, `{{kb_locations}}`, `{{recent_chapters}}`, `{{word_target}}`, and `{{user_preferences}}`.

#### Scenario: All variables populated from WritingContext
- **WHEN** a generation prompt is built from a fully populated `WritingContext`
- **THEN** all variable slots in the system prompt are replaced with assembled context content. No `{{variable}}` placeholders remain in the final prompt.

#### Scenario: Optional variables missing gracefully
- **WHEN** a `WritingContext` has no style examples (fewer than 3 chapters written)
- **THEN** the `{{style_examples}}` variable slot is replaced with an empty string or a neutral default. The prompt does not reference style matching.

### Requirement: Interview prompt template
The system SHALL provide a separate interview prompt template (`_bundled/writing/{lang}/interview/system.md`) for the structured interview phase of `interview_assisted` mode. This template instructs the AI to ask targeted questions about scene goals, characters, tone, and conflict.

#### Scenario: Interview prompt asks structured questions
- **WHEN** the interview prompt is loaded and invoked with chapter context
- **THEN** the AI produces 3-5 targeted questions about the upcoming chapter scene, adapting questions based on available KB data (e.g., asking about specific characters if they're referenced in frontmatter).

### Requirement: Prompt cascade includes writing prompts
Writing prompts SHALL participate in the foundation's prompt override cascade: bundled → genre-specific → database override. Users can override any writing prompt through the prompt management service.

#### Scenario: User overrides new chapter system prompt
- **WHEN** a user has saved a database override for the `writing/new_chapter/en/system` prompt
- **THEN** the `PromptComposer` resolves and uses the user's override instead of the bundled version, following the cascade order.

### Requirement: Per-tone prompt variants
The system SHALL support optional per-tone prompt variants (dramatic, quiet, suspenseful, balanced) via a `{{tone_instructions}}` injectable section in the system prompt. Default tone is `balanced`.

#### Scenario: User selects suspenseful tone
- **WHEN** a user selects tone "suspenseful" for generation
- **THEN** the `{{tone_instructions}}` variable is populated with suspense-specific writing guidance (short sentences, cliffhangers, sensory details, withheld information).
