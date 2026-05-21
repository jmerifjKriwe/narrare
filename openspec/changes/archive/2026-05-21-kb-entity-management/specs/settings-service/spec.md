## MODIFIED Requirements

### Requirement: Demo loader populates KB entries
The demo loader SHALL use the new `KBEntry` model from `apps/api/narrare/kb/models.py` instead of the deferred import. The `_load_kb_entries` method SHALL parse Markdown frontmatter into metadata JSONB and content into body TEXT, then persist via the KB entries table.

#### Scenario: Load demo KB entries successfully
- **WHEN** the setup wizard loads a demo project
- **THEN** the demo loader imports KBEntry without ImportError, parses each .md file's frontmatter as metadata, stores the Markdown body as body, and creates entries with correct entity_type, name, slug, tags, and status

#### Scenario: Skip KB loading when no kb/ directory exists
- **WHEN** a demo project directory has no kb/ subdirectory
- **THEN** the demo loader logs the absence and proceeds without error

#### Scenario: Character demo entry with all fields
- **WHEN** `char-elara.md` is loaded (frontmatter: id, name, type, tags, age, role, arc, first_appearance, pov_character, affiliation, element, occupation)
- **THEN** the KBEntry is created with entity_type="character", name="Elara Thornwind", slug="char-elara", tags from frontmatter array, metadata containing all type-specific fields (age, role, etc.), and body containing the Markdown content
