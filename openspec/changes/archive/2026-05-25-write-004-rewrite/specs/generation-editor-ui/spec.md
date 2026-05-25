## MODIFIED Requirements

### Requirement: CommandPalette integration
The system SHALL register generation-related commands in the editor's CommandPalette (Cmd+K): "Generate Chapter", "Generate from Outline", "Auto-Continue", "Continue Writing", "Rewrite Selection", "Start Interactive Session", "Stop Generation", "Accept Draft", "Reject Draft".

#### Scenario: User triggers rewrite via CommandPalette
- **WHEN** a user opens the CommandPalette (Cmd+K) with text selected and types "rewrite"
- **THEN** the palette shows the "Rewrite Selection" command
- **AND** selecting it SHALL trigger the rewrite flow

#### Scenario: Rewrite command hidden when no selection
- **WHEN** no text is selected in the editor and the user opens the CommandPalette
- **THEN** the "Rewrite Selection" command SHALL be hidden or shown as disabled

#### Scenario: Command availability based on state
- **WHEN** no generation is active
- **THEN** "Stop Generation", "Accept Draft", and "Reject Draft" commands are hidden. Generation and rewrite trigger commands are shown (rewrite only if text is selected).
