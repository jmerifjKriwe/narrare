## ADDED Requirements

### Requirement: Entity-type-specific metadata schemas in core
The system SHALL provide Pydantic models for each entity type's metadata: `CharacterMetadata`, `LocationMetadata`, `FactionMetadata`, `ObjectMetadata`, `SystemMetadata`, and `TimelineMetadata`. All inherit from a common `KBEntryMetadata` base model.

#### Scenario: Validate character metadata
- **WHEN** metadata `{"age": "thirty"}` is validated against CharacterMetadata
- **THEN** validation fails because `age` must be an integer or null

#### Scenario: Validate location metadata
- **WHEN** metadata `{"location_type": "city", "parent_location": "kingdom-of-aldrath"}` is validated against LocationMetadata
- **THEN** validation passes and returns a typed LocationMetadata instance

### Requirement: Metadata schema registry maps entity types to schemas
The system SHALL provide a registry that maps entity type strings to their corresponding Pydantic schema classes.

#### Scenario: Look up schema by entity type
- **WHEN** the registry is queried with entity_type "character"
- **THEN** it returns the CharacterMetadata class

#### Scenario: Unknown entity type returns base schema
- **WHEN** the registry is queried with an entity type not in the registry
- **THEN** it returns the base KBEntryMetadata class (which allows any extra fields)

### Requirement: Metadata schemas allow extra fields
All metadata schemas SHALL use `model_config = ConfigDict(extra="allow")` so that user-defined or AI-generated fields beyond the schema are preserved, not rejected.

#### Scenario: Character with custom field
- **WHEN** metadata `{"age": 25, "favorite_color": "blue"}` is validated against CharacterMetadata
- **THEN** validation passes and the `favorite_color` field is preserved in the model

### Requirement: Metadata schemas define optional typed fields
Each entity-type schema SHALL define optional typed fields matching the template frontmatter structure. Fields are all optional (defaults to None) to support partial entries.

#### Scenario: Character schema fields
- **WHEN** the CharacterMetadata schema is inspected
- **THEN** it includes optional fields for: age (int), role (str), arc (str), gender (str), pronouns (str), nationality (str), pov_character (bool), affiliation (str), first_appearance (str), and aliases (list[str])

#### Scenario: Location schema fields
- **WHEN** the LocationMetadata schema is inspected
- **THEN** it includes optional fields for: location_type (str), parent_location (str), coordinates (str), climate (str), terrain (str), first_appearance (str)
