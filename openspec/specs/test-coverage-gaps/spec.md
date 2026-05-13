## Purpose

Closing test coverage gaps in backend and frontend identified during Phase 5. Covers unit tests for settings/gateway/retry, integration tests for seeding/demo loading, and frontend component tests for editor/wizard/dashboard.

## Requirements

### Requirement: Settings service unit tests
The system SHALL have unit tests for the settings module covering user settings and project settings CRUD operations, including happy path, validation errors, and not-found cases.

#### Scenario: User settings update succeeds
- **WHEN** a valid update request is made for user settings
- **THEN** the settings are updated and the response reflects the new values

#### Scenario: Settings for non-existent user returns error
- **WHEN** settings are requested for a user that does not exist
- **THEN** an appropriate error is raised

### Requirement: Dev user seeding integration test
The system SHALL have an integration test that verifies the `seed_dev_user.py` script creates the development user with correct credentials and that the user can authenticate.

#### Scenario: Seed script creates dev user
- **WHEN** the seed script runs against a fresh database
- **THEN** the user `dev@narrare.local` exists with the correct hashed password and can successfully log in

### Requirement: Demo loader integration tests
The system SHALL have integration tests for the `DemoLoader` covering chapter loading, KB entry loading, and the complete setup flow for all three demo projects (Fantasy, SciFi, German).

#### Scenario: Fantasy demo loads all chapters and KB entries
- **WHEN** the Fantasy demo project is loaded
- **THEN** 4 chapters and 15 KB entries are created with correct titles and content

#### Scenario: German demo loads correctly
- **WHEN** the German demo project ("Im stillen Wald") is loaded
- **THEN** 2 chapters and 5 KB entries are created

### Requirement: LLM gateway error classification tests
The system SHALL have unit tests for `LLMGateway._classify_error()` covering pydantic-ai typed exceptions, standard library exceptions, string fallback, and unknown error types.

#### Scenario: pydantic-ai typed error is classified correctly
- **WHEN** a pydantic-ai `ModelHTTPError` with status 429 is classified
- **THEN** it is categorized as a rate limit error with appropriate retry behavior

#### Scenario: Unknown error falls back to generic classification
- **WHEN** an unrecognized exception type is classified
- **THEN** it is categorized as an unknown error with no automatic retry

### Requirement: Retry logic tests
The system SHALL have unit tests for `with_retry()` covering successful first attempt, retry on transient failure, max retries exceeded, and exponential backoff timing.

#### Scenario: Retry succeeds on second attempt
- **WHEN** the first call fails with a transient error and the second succeeds
- **THEN** the result is returned without error

#### Scenario: Max retries exceeded raises error
- **WHEN** all retry attempts fail with transient errors
- **THEN** the final error is raised to the caller

### Requirement: Frontend editor component tests
The system SHALL have component tests for the editor components covering: EditorSurface (autosave trigger on content change, word count display, chapter content loading), ChapterSidebar (chapter list rendering, chapter selection click), and StatusBar (save status display, word count display).

#### Scenario: Autosave triggers after content change
- **WHEN** the editor content changes
- **THEN** after the debounce interval, an API call to save the chapter content is made

#### Scenario: Chapter list renders in sidebar
- **WHEN** the ChapterSidebar receives a list of chapters
- **THEN** all chapter titles are rendered as clickable items

#### Scenario: Chapter click switches content
- **WHEN** a chapter in the sidebar is clicked
- **THEN** the editor loads the content for that chapter

### Requirement: Frontend setup wizard component tests
The system SHALL have component tests for the setup wizard covering: step transitions (next/previous), form validation on each step, and completion navigation to dashboard.

#### Scenario: Wizard advances to next step on valid input
- **WHEN** the user fills in valid data on step 1 and clicks next
- **THEN** the wizard transitions to step 2

#### Scenario: Wizard blocks advance on invalid input
- **WHEN** the user leaves required fields empty and clicks next
- **THEN** validation errors are displayed and the wizard stays on the current step

### Requirement: Frontend dashboard component test
The system SHALL have a component test for DashboardView that verifies novel list rendering with mocked API data and navigation to the editor on novel click.

#### Scenario: Dashboard renders novel cards
- **WHEN** the DashboardView loads with mocked novel data
- **THEN** novel cards are displayed with titles and metadata

### Requirement: Frontend shared component tests
The system SHALL have component tests for ErrorBoundary (catches errors and displays fallback UI) and StatusBar (displays save status: idle, saving, saved, error).

#### Scenario: ErrorBoundary catches render error
- **WHEN** a child component throws during render
- **THEN** the ErrorBoundary displays a fallback error message instead of crashing

#### Scenario: StatusBar shows saving state
- **WHEN** the autosave is in progress
- **THEN** the StatusBar displays a "saving" indicator
