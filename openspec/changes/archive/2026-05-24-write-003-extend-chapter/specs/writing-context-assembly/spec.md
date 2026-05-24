## MODIFIED Requirements

### Requirement: Context assembly supports extend mode budget emphasis
The `WritingContextAssembler` SHALL support a mode-aware budget emphasis where
extend operations allocate more budget to immediate context (pre/post text) and
less to recent chapters.

#### Scenario: Extend mode budget allocation
- **WHEN** the context assembler is called for an extend operation
- **THEN** the immediate context tier SHALL receive approximately 50% of the token
  budget (vs. 30% for full draft)
- **AND** the recent chapters tier SHALL receive approximately 15% (vs. 20%)
- **AND** KB tiers and pinned items SHALL retain their relative proportions

#### Scenario: Extend receives pre-text as chapter_content
- **WHEN** `WritingPipeline._extend()` passes `chapter_content` to the assembler
- **THEN** the assembler SHALL treat it as the primary immediate context
- **AND** the `existing_content` field in `PromptContext` SHALL be populated with
  the pre-text marked with `[CONTINUE FROM HERE]` and optional post-text
