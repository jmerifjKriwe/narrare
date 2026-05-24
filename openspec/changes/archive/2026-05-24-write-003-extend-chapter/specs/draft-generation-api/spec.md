## MODIFIED Requirements

### Requirement: GenerationMode enum supports EXTEND
The `GenerationMode` enum SHALL include `EXTEND = "extend"` alongside the existing
FULL_DRAFT, SCENE_BY_SCENE, INTERVIEW_ASSISTED, and INTERACTIVE_SESSION values.

#### Scenario: Extend mode in pipeline dispatch
- **WHEN** `WritingPipeline.generate()` receives a request with `mode == EXTEND`
- **THEN** it SHALL dispatch to `_extend()` instead of raising `WritingError("Unsupported generation mode")`

#### Scenario: Extend mode stored in generation_requests
- **WHEN** a generation_request is created with `mode = "extend"`
- **THEN** the mode column SHALL accept the value without CHECK constraint violation

#### Scenario: Extend mode in API schema
- **WHEN** a `GenerateRequest` or `ExtendRequest` uses mode "extend"
- **THEN** the `GenerationModeEnum` SHALL validate it as a legal value
