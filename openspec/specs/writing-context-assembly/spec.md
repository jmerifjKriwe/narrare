# Writing Context Assembly

**Purpose**: The system SHALL assemble comprehensive writing context from multiple sources (chapter content, history, KB entities) to inform AI generation with relevant information.

## Requirements

### Requirement: Writing context assembly produces structured WritingContext
The system SHALL assemble a `WritingContext` from 5 context tiers: immediate chapter content, recent chapter history, referenced KB entities, similarity-suggested KB entities, and user-pinned KB entities. Each tier SHALL have a defined token budget allocation.

#### Scenario: Full context assembly for chapter with rich KB
- **WHEN** context assembly is requested for a chapter that has frontmatter references (pov_character, location), 3+ recent chapters, and 10+ KB entities
- **THEN** the system produces a `WritingContext` containing: current chapter content and frontmatter (30% budget), summaries of last 2-3 chapters (20% budget), referenced character/location/faction profiles (25% budget), top similarity-ranked KB entries (15% budget), and user-pinned items (10% budget)

#### Scenario: Context assembly with sparse KB
- **WHEN** context assembly is requested for a chapter where the project has fewer than 3 KB entities
- **THEN** the system produces a `WritingContext` with immediate context and recent history filled, and reduced KB context. The system SHALL NOT fail when KB is sparse.

#### Scenario: Context assembly for first chapter with no history
- **WHEN** context assembly is requested for the first chapter of a project (no previous chapters exist)
- **THEN** the system produces a `WritingContext` with 100% of history budget reallocated to KB entries, and includes a flag indicating first-chapter context for prompt adaptation.

### Requirement: KB entity relevance ranking
The system SHALL rank KB entities using a weighted score of 50% relevance (semantic similarity to chapter content/outline), 30% usage frequency (how often the entity appears in previous chapters), and 20% recency (how recently the entity appeared).

#### Scenario: Character ranked by frontmatter reference
- **WHEN** a chapter's frontmatter specifies `pov_character: "elara-voss"` and `location: "ember-road"`
- **THEN** the referenced character "Elara Voss" and location "Ember Road" SHALL be included in the "referenced KB entities" tier regardless of their similarity score, and SHALL NOT consume budget from the "suggested" tier.

#### Scenario: Character ranked by similarity to outline
- **WHEN** a chapter outline mentions "the Council chamber" but no Council faction is referenced in frontmatter
- **THEN** the system SHALL include the "Council" faction in the "suggested KB entries" tier based on semantic similarity, subject to available budget.

### Requirement: Token budget enforcement
The system SHALL enforce token budgets per tier. If a tier's content exceeds its budget, the system SHALL truncate from the bottom of the relevance ranking. Pinned items SHALL bypass budget limits.

#### Scenario: Pinned items exceed their tier budget
- **WHEN** a user has pinned 5 KB entries that together exceed the 10% pinned-item budget
- **THEN** all pinned items SHALL be included in full, and the overflow SHALL reduce the budget available for the "suggested KB entries" tier.

#### Scenario: Long chapter content exceeds immediate context budget
- **WHEN** the current chapter content exceeds the 30% immediate context budget
- **THEN** the system SHALL include only the most recent portion of the chapter content (truncated from the beginning) that fits within the budget.

### Requirement: Recent chapter summarization
The system SHALL include recent chapters as summaries when full chapter text would exceed the history tier budget. Summarization SHALL preserve plot developments, character appearances, and key events.

#### Scenario: Three recent chapters within budget
- **WHEN** the last 3 chapters' full text fits within the history tier budget
- **THEN** the system SHALL include the full text of all 3 recent chapters.

#### Scenario: Recent chapters exceed history budget
- **WHEN** the last 3 chapters' full text exceeds the history tier budget
- **THEN** the system SHALL summarize the older chapters and include only the most recent chapter's full text, with summaries of preceding chapters.

### Requirement: WritingContext integrates with PromptContext
The system SHALL produce a `WritingContext` that maps its assembled content to the extended `PromptContext` fields from the foundation (`user_preferences`, `avoidance_patterns`) and writing-specific variables (`{{kb_characters}}`, `{{kb_locations}}`, `{{recent_chapters}}`, `{{style_examples}}`).

#### Scenario: WritingContext maps to prompt variables
- **WHEN** a `WritingContext` is assembled with characters, locations, chapter summaries, and user preferences
- **THEN** the system SHALL produce a dictionary of prompt variables where `kb_characters` contains formatted character profiles, `kb_locations` contains formatted location descriptions, `recent_chapters` contains chapter summaries, and `user_preferences` contains the user's preference profile from the memory layer.
