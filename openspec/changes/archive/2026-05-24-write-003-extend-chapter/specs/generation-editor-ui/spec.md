## MODIFIED Requirements

### Requirement: Editor supports inline AI text insertion with annotation
The generation editor UI SHALL support inline insertion of AI-generated text
with `ai-generated` mark annotation, in addition to the existing side-panel
draft generation flow.

#### Scenario: Extend inserts text with mark at cursor
- **WHEN** the user triggers "Continue" from the editor toolbar or keyboard shortcut
- **THEN** the AI-generated text SHALL be inserted at the current cursor position
- **AND** the inserted range SHALL be wrapped with an `ai-generated` mark
  (`source: "extend"`, `status: "pending"`)

#### Scenario: Extend command registered in CommandPalette
- **WHEN** the user opens the command palette (Cmd+K)
- **THEN** a "Continue writing" command SHALL be available
- **AND** selecting it SHALL trigger the extend flow at the current cursor position

#### Scenario: Continue button in editor toolbar
- **WHEN** the editor toolbar is rendered
- **THEN** a "Continue" button SHALL be visible
- **AND** clicking it SHALL present length options (short/medium/long) then trigger
  the extend flow

#### Scenario: Extend streaming inserts incrementally
- **WHEN** SSE chunks arrive from the extend endpoint
- **THEN** each chunk SHALL be appended to the marked range in a single
  ProseMirror transaction
- **AND** the `ai-generated` mark's range SHALL grow to encompass the new text

## ADDED Requirements

### Requirement: Extend API client methods
The frontend API client (`lib/api/generation.ts`) SHALL include methods for
starting an extend request.

#### Scenario: startExtend API call
- **WHEN** the frontend calls `writingApi.startExtend(chapterId, novelId, extendRequest)`
- **THEN** a POST request SHALL be sent to `/writing/chapters/${chapterId}/extend`
  with the `ExtendRequest` body
- **AND** the response SHALL conform to `GenerateResponse` shape (`request_id`, `status`, `mode`)

### Requirement: ExtendRequest TypeScript type
The frontend SHALL define an `ExtendRequest` type matching the backend schema.

#### Scenario: ExtendRequest type matches backend
- **WHEN** an `ExtendRequest` object is constructed with `text_before`, `text_after`,
  `length`, `tone`, and `language`
- **THEN** the field names and types SHALL match the backend Pydantic schema exactly
