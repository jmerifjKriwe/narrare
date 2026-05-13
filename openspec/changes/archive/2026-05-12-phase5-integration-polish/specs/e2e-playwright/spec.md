## ADDED Requirements

### Requirement: Playwright test infrastructure
The system SHALL have a Playwright configuration at the project root with baseURL pointing to the running application, Chromium as the default browser, and appropriate timeout/retry settings for CI.

#### Scenario: Playwright config exists and is valid
- **WHEN** `npx playwright test --config=playwright.config.ts` is executed
- **THEN** the configuration is loaded without errors and tests are discovered

### Requirement: E2E test fixtures for authentication
The system SHALL provide Playwright fixtures that handle user authentication (login, token storage) so that tests can skip manual login flows when needed.

#### Scenario: Authenticated fixture provides valid session
- **WHEN** a test uses the authenticated fixture
- **THEN** the test browser session has a valid JWT token and can access protected routes

### Requirement: LLM provider response mocking
The system SHALL mock all LLM provider responses in E2E tests using Playwright's `route.fulfill()`. No real LLM API calls SHALL be made during E2E test execution.

#### Scenario: Setup wizard provider validation is mocked
- **WHEN** the E2E test reaches setup wizard step 4 (AI provider configuration)
- **THEN** the provider validation endpoint returns a successful mocked response without calling any real LLM provider

#### Scenario: No real LLM tokens are consumed
- **WHEN** the full E2E test suite runs
- **THEN** zero outgoing requests are made to any LLM provider API (OpenAI, Anthropic, Z.AI, etc.)

### Requirement: Hero E2E flow test
The system SHALL have a single end-to-end test that covers the complete MVP user journey: user registration → setup wizard (all 5 steps with demo content selection) → dashboard with demo novel → editor opens with chapter content → autosave triggers on content change.

#### Scenario: Complete user journey succeeds
- **WHEN** a new user completes signup and runs through the full setup wizard selecting the Fantasy demo project
- **THEN** the dashboard shows the demo novel with chapters, clicking a chapter opens the editor, and editing content triggers autosave

#### Scenario: Autosave persists changes
- **WHEN** the user types new content in the editor
- **THEN** after the debounce interval, a save request is sent to the API and the content is persisted

### Requirement: E2E CI integration
The E2E test suite SHALL be integrated into CI and run only on the main branch. The full stack (API, web, PostgreSQL, Redis) SHALL be available during E2E test execution.

#### Scenario: E2E tests run in CI on main branch
- **WHEN** a commit is pushed to main
- **THEN** the CI pipeline starts the full stack and runs Playwright E2E tests
