## ADDED Requirements

### Requirement: Modify-tracking in generation draft
The `GenerationDraft` component SHALL detect when the user edits the AI-generated text before accepting. When the text has been modified, the accept action SHALL send `action="modify"` with the diff between original and modified text.

#### Scenario: User accepts without editing
- **WHEN** the user clicks "Accept" on an unmodified AI draft
- **THEN** `writingApi.acceptDraft(requestId)` is called without `modified_text`

#### Scenario: User edits then accepts
- **WHEN** the user edits the draft text in the draft zone and clicks "Accept"
- **THEN** `writingApi.acceptDraft(requestId, modifiedText)` is called with the edited text, and the backend records action="modify"

### Requirement: Rating UI after feedback
After an accept or reject action, the system SHALL show an optional inline rating prompt (1-5 stars) and, for rejections, an optional text field for the rejection reason. Rating and reason SHALL be sent to `POST /memory/feedback` as `rating` and `modification` fields.

#### Scenario: Rating after accept
- **WHEN** the user accepts a draft and then clicks 4 out of 5 stars
- **THEN** a feedback request is sent with `action="accept"`, `rating=4`, and the suggestion context

#### Scenario: Rejection reason after reject
- **WHEN** the user rejects a draft and types "too wordy" as the reason
- **THEN** a feedback request is sent with `action="reject"` and `modification="too wordy"`

#### Scenario: Rating dismissed without selection
- **WHEN** the user accepts a draft and dismisses the rating prompt without selecting stars
- **THEN** a feedback request is sent with `action="accept"` and `rating=null`

### Requirement: Learning status indicator
The system SHALL display a learning progress indicator in the GenerationPanel or MetadataSidebar showing the number of feedback interactions relative to a learning threshold (e.g., "12/50 interactions"). The indicator SHALL include a tooltip explaining that AI becomes more personalized over time.

#### Scenario: Progress displayed during cold start
- **WHEN** a user has provided 12 feedback events
- **THEN** the indicator shows "12/50 interactions" with a progress bar at 24%

#### Scenario: Learning threshold reached
- **WHEN** a user has provided 50+ feedback events
- **THEN** the indicator shows "Learning active" with a checkmark icon

### Requirement: Preference profile page
The system SHALL provide a "Learning" tab in Settings that displays the user's preference profile for the selected project. The page SHALL show: style preferences (key-value list), content preferences (key-value list), avoidance patterns (bulleted list), confidence score, total event count, project selector, and a "Reset Preferences" button.

#### Scenario: Display populated profile
- **WHEN** the user navigates to Settings → Learning and has 25 feedback events with extracted preferences
- **THEN** the page displays style preferences, content preferences, avoidance patterns, confidence score, event count, and the project selector

#### Scenario: Display empty profile
- **WHEN** the user navigates to Settings → Learning for a project with no feedback history
- **THEN** the page displays an empty state message ("Start providing feedback on AI suggestions to build your preference profile")

#### Scenario: Reset preferences
- **WHEN** the user clicks "Reset Preferences" and confirms
- **THEN** `DELETE /memory/preferences` is called for the selected project, the profile is cleared, and the page updates to the empty state

### Requirement: Feedback API client
The system SHALL provide a `memoryApi` client in `lib/api/memory.ts` with methods: `recordFeedback`, `getPreferences`, `resetPreferences`, `triggerAnalysis`.

#### Scenario: API client methods exist
- **WHEN** `memoryApi` is imported
- **THEN** it exposes `recordFeedback(data)`, `getPreferences(projectId)`, `resetPreferences(projectId)`, `triggerAnalysis(projectId)` methods

### Requirement: Memory hooks
The system SHALL provide TanStack Query hooks in `lib/hooks/useMemory.ts`: `usePreferences(projectId)`, `useMemoryStatus(projectId)`, `useRecordFeedback()`.

#### Scenario: usePreferences fetches profile
- **WHEN** `usePreferences(projectId)` is called
- **THEN** it fetches from `GET /memory/preferences?project_id=...` and returns the PreferenceProfile

### Requirement: Feedback loop i18n
All feedback loop UI text SHALL use i18n keys in the "studio" and "settings" namespaces. Translations SHALL be provided for en, de, and fr locales.

#### Scenario: German translation for preference reset
- **WHEN** the UI language is "de" and the user views the reset button
- **THEN** the button displays the German translation of "Reset Preferences"
