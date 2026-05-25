## MODIFIED Requirements

### Requirement: GenerationMode enum supports REWRITE
The `GenerationMode` enum SHALL include `REWRITE = "rewrite"` alongside the existing FULL_DRAFT, SCENE_BY_SCENE, INTERVIEW_ASSISTED, INTERACTIVE_SESSION, and EXTEND values.

#### Scenario: Rewrite mode in pipeline dispatch
- **WHEN** `WritingPipeline.generate()` receives a request with `mode == REWRITE`
- **THEN** it SHALL dispatch to `_rewrite()` instead of raising `WritingError("Unsupported generation mode")`

#### Scenario: Rewrite mode stored in generation_requests
- **WHEN** a generation_request is created with `mode = "rewrite"`
- **THEN** the mode column SHALL accept the value without CHECK constraint violation

#### Scenario: Rewrite mode in API schema
- **WHEN** a `RewriteRequest` uses mode "rewrite"
- **THEN** the `GenerationModeEnum` SHALL validate it as a legal value
