## ADDED Requirements

### Requirement: Collapsible storyboard panel above editor
The system SHALL display a collapsible `StoryboardPanel` component in the EditorView, positioned **above the toolbar and the entire editor area** at full viewport width. The panel SHALL default to collapsed state and be toggleable.

#### Scenario: Storyboard panel is collapsed by default
- **WHEN** the editor page loads for a novel
- **THEN** the storyboard panel SHALL be collapsed above the toolbar, showing only a single summary row with the structure name, chapter count, and toggle control
- **THEN** the editor area (toolbar + editor) SHALL occupy full available height

#### Scenario: Expand storyboard
- **WHEN** the user clicks the storyboard toggle control on the collapsed summary row
- **THEN** the panel SHALL expand to reveal the full storyboard with stages and chapter cards, spanning full viewport width
- **THEN** the toolbar and editor area SHALL reduce in height to accommodate the expanded panel

#### Scenario: Collapse storyboard
- **WHEN** the user clicks the collapse control on the expanded storyboard
- **THEN** the panel SHALL animate back to the collapsed summary row
- **THEN** the toolbar and editor area SHALL reclaim the space

#### Scenario: Storyboard uses full viewport width
- **WHEN** the storyboard is expanded
- **THEN** it SHALL span the full width of the viewport, not limited to the editor column width
- **THEN** the storyboard SHALL be positioned above both the sidebar and the editor columns

### Requirement: Structure-aware stage layout
The storyboard SHALL display stages in a layout appropriate to the novel's story structure. Each structure type SHALL have a distinct visual arrangement.

#### Scenario: Three-act structure shows horizontal stages
- **WHEN** the storyboard loads for a novel with `three_act` structure
- **THEN** it SHALL display 3 stage columns arranged horizontally: Act 1 (Setup), Act 2 (Confrontation), Act 3 (Resolution)

#### Scenario: Hero's journey shows journey stages
- **WHEN** the storyboard loads for a novel with `heros_journey` structure
- **THEN** it SHALL display stages in a journey-appropriate layout (e.g., condensed 8-card flow showing the major journey phases)

#### Scenario: Save the cat shows beats within acts
- **WHEN** the storyboard loads for a novel with `save_the_cat` structure
- **THEN** it SHALL display 3 act groups, each containing its expected beats as sub-items

### Requirement: Chapter cards with sync status
Each chapter SHALL be displayed as a `StoryboardCard` within its assigned stage, showing the chapter title, a color-coded sync status badge, and word count.

#### Scenario: Chapter card displays status badge
- **WHEN** a chapter with `"on_track"` sync status is rendered
- **THEN** the card SHALL show a green badge with the sync status

#### Scenario: Chapter card for planned chapter
- **WHEN** a chapter with `"planned"` sync status is rendered
- **THEN** the card SHALL show a blue badge indicating planned but not written

#### Scenario: Empty chapter slot
- **WHEN** a stage has no chapters assigned
- **THEN** the storyboard SHALL show an empty drop zone with a dashed border

### Requirement: Drag and drop chapter cards between stages
Users SHALL be able to drag chapter cards between stages to reassign them, using @dnd-kit (same library as ChapterSidebar).

#### Scenario: Drag card to different stage
- **WHEN** the user drags a chapter card from "Act 1: Setup" and drops it on "Act 2: Confrontation"
- **THEN** the system SHALL update the chapter's stage_assignment to the new stage
- **THEN** the backend SHALL persist the change via `PUT /api/v1/planning/outlines/{chapter_id}`
- **THEN** the storyboard SHALL re-render with the chapter in its new stage

#### Scenario: Drop zone highlighted on drag over
- **WHEN** the user drags a chapter card and hovers over a different stage
- **THEN** that stage SHALL show a highlighted drop zone indicator

#### Scenario: Cancel drag returns card to original position
- **WHEN** the user starts dragging a card and releases it outside any valid drop zone
- **THEN** the card SHALL return to its original stage position

### Requirement: Horizontal scroll with arrow navigation
When the storyboard content exceeds viewport width, the system SHALL provide left/right arrow navigation buttons for horizontal scrolling.

#### Scenario: Arrows appear on overflow
- **WHEN** the total width of stages and cards exceeds the viewport width
- **THEN** semi-transparent ◀/▶ arrow buttons SHALL appear at the left and right edges of the storyboard

#### Scenario: Click arrow scrolls storyboard
- **WHEN** the user clicks the right arrow button
- **THEN** the storyboard SHALL smooth-scroll horizontally by approximately 200px
- **THEN** the left arrow SHALL become visible if not already at the start

#### Scenario: Arrows hidden at scroll boundaries
- **WHEN** the storyboard is scrolled to the far left
- **THEN** the left arrow SHALL be hidden
- **WHEN** the storyboard is scrolled to the far right
- **THEN** the right arrow SHALL be hidden

#### Scenario: Touch and trackpad scrolling works natively
- **WHEN** the user uses touch swipe or trackpad horizontal scroll on the storyboard
- **THEN** the content SHALL scroll horizontally via native `overflow-x: auto` behavior

### Requirement: Click-to-navigate to chapter
When a chapter card is clicked (without dragging), the system SHALL set that chapter as the active chapter in the editor, analogous to clicking a chapter in the sidebar.

#### Scenario: Click chapter card activates chapter
- **WHEN** the user clicks (without dragging) a StoryboardCard for chapter 5
- **THEN** the editor SHALL load chapter 5 as the active chapter via `editorStore.setActiveChapterId`
- **THEN** the storyboard panel SHALL remain in its current expanded/collapsed state

#### Scenario: Click distinguishes from drag
- **WHEN** the user clicks a card without moving the mouse (no drag threshold exceeded)
- **THEN** the system SHALL treat it as a navigation click, not a drag initiation

### Requirement: Outline editor for selected chapter
When a chapter is selected in the storyboard, the system SHALL show an inline outline editor with editable planned beats and outline notes.

#### Scenario: Select chapter shows outline editor
- **WHEN** the user clicks a chapter card in the expanded storyboard
- **THEN** an outline panel SHALL appear showing the chapter's planned beats as a checklist
- **THEN** the user SHALL be able to check/uncheck beats and edit outline notes

#### Scenario: Toggle beat completion
- **WHEN** the user toggles a planned beat's completed checkbox
- **THEN** the system SHALL save the updated beat status to the backend
- **THEN** the sync status SHALL recalculate

### Requirement: Structure change confirmation dialog
When the user changes the novel's story structure in Settings, the frontend SHALL show a confirmation dialog showing the remap preview before committing.

#### Scenario: Structure change triggers dialog
- **WHEN** the user changes the story structure dropdown and clicks save
- **THEN** a `StructureChangeDialog` SHALL appear with a preview of how chapters will be remapped
- **THEN** the dialog SHALL list each chapter with its current stage and proposed new stage

#### Scenario: Confirm structure change
- **WHEN** the user clicks "Confirm" in the structure change dialog
- **THEN** the system SHALL send the remap request with `confirm: true`
- **THEN** the storyboard SHALL reload with the new structure layout

#### Scenario: Cancel structure change
- **WHEN** the user clicks "Cancel" in the structure change dialog
- **THEN** the structure change SHALL be reverted
- **THEN** the storyboard SHALL remain unchanged

### Requirement: Storyboard respects dark/light mode
The storyboard panel SHALL use Tailwind CSS design tokens (CSS variables) for all colors, ensuring proper rendering in both light and dark mode.

#### Scenario: Dark mode rendering
- **WHEN** the system is in dark mode
- **THEN** the storyboard panel SHALL use `bg-card`, `text-foreground`, `border-border` tokens
- **THEN** sync status badges SHALL maintain sufficient contrast

### Requirement: Storyboard is i18n-aware
All storyboard text (stage names, status labels, button text) SHALL use i18n keys from the `studio` namespace, supporting en, de, and fr locales.

#### Scenario: German locale displays translated stages
- **WHEN** the storyboard loads with locale "de"
- **THEN** stage names SHALL display in German (e.g., "Aufzug 1: Aufbau" for Act 1)
