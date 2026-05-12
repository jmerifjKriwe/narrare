## ADDED Requirements

### Requirement: Architecture questions updated
The file `docs/architecture/questions/Q-001-to-Q-004.md` SHALL reflect current status: Q-004 marked as resolved (→ TaskIQ, ADR-007), Q-003 re-scoped as post-MVP (removing "Phase 1" blocking note), Q-001 and Q-002 remain open with corrected blocking scope (post-MVP only).

#### Scenario: Q-004 shows resolved status
- **WHEN** a developer reads the questions file
- **THEN** Q-004 shows status ✅ Resolved with reference to ADR-007 and the TaskIQ decision

#### Scenario: Q-003 no longer claims to block Phase 1
- **WHEN** a developer reads Q-003
- **THEN** the blocking note says "post-MVP" not "Phase 1"

### Requirement: Questions INDEX links corrected
The file `docs/architecture/questions/INDEX.md` SHALL reference the actual file `Q-001-to-Q-004.md` instead of non-existent individual files.

#### Scenario: INDEX links resolve correctly
- **WHEN** a developer clicks a question link in INDEX.md
- **THEN** the link resolves to the correct location in Q-001-to-Q-004.md

### Requirement: CURRENT_STATE next session marked as post-MVP
The "Next Session Should Start With" section in `docs/_shared/CURRENT_STATE.md` SHALL clearly separate Phase 5 scope from post-MVP items. SSE streaming sessions, KB editor UI, and analysis panels SHALL be explicitly labeled as post-MVP.

#### Scenario: Post-MVP items are clearly labeled
- **WHEN** a developer reads the "Next Session" section
- **THEN** AI features (SSE, KB editor, analysis) are listed under a "Post-MVP" heading, not mixed with Phase 5 work

### Requirement: Testing standards E2E section corrected
The `docs/development/testing-standards.md` E2E section SHALL NOT require real LLM calls. It SHALL specify that LLM responses are mocked in E2E tests.

#### Scenario: E2E section specifies mocked LLM
- **WHEN** a developer reads the E2E test section
- **THEN** it specifies Playwright route mocking for LLM responses, not "real LLM (cheapest model)"

### Requirement: README with setup instructions
The `README.md` SHALL contain complete, accurate setup instructions matching the actual project structure: prerequisites, `just dev-setup`, `just dev`, `just test`, `just check`.

#### Scenario: Fresh developer can set up project
- **WHEN** a new developer follows the README instructions on a clean machine
- **THEN** they can successfully run `just dev` and access the application

### Requirement: CHANGELOG v0.1.0 entry
The `CHANGELOG.md` SHALL have a v0.1.0 entry listing all MVP features: repository foundation, core infrastructure (LLM gateway, prompt system), API foundation (auth, CRUD, setup wizard), frontend (editor, dashboard, setup wizard, auth), and demo content.

#### Scenario: CHANGELOG documents v0.1.0 scope
- **WHEN** the CHANGELOG is read
- **THEN** it contains a v0.1.0 section with all implemented features organized by phase
