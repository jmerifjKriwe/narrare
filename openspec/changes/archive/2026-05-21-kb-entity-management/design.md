## Context

Narrare is a creative writing tool with AI-powered features. The Knowledge Base (KB) is the structured memory of a user's story world — characters, locations, factions, objects, systems, and timelines. Every AI feature (writing sessions, context assembly, consistency checks, suggestions) depends on the KB for entity context.

Currently, the demo loader attempts to import a non-existent `KBEntry` model and silently skips KB loading. The database has no KB tables. The frontend has no KB UI. The core package has old scratch code (`_scratch/packages/core/narrare_core/kb/`) with schemas and formatting utilities, but no production implementation.

Three demo projects contain ~30 KB entries as Markdown files with YAML frontmatter (e.g., `char-elara.md`, `loc-thornwall.md`). These files represent the import format but have no runtime representation.

The project is in Phase 5 (Integration & Polish). Infrastructure (auth, novels, chapters, volumes, settings, LLM gateway, prompt system, event bus) is complete. The KB is the next major domain module.

## Goals / Non-Goals

**Goals:**

- Persistent storage for KB entries across 6 entity types, queryable by type, tags, name, and content
- Structured metadata (JSONB) with type-specific validation (Pydantic schemas per entity type)
- Narrative body (TEXT) as free-form Markdown — templates recommend sections but do not enforce them
- Typed, directed relationships between entries — no auto-generated inverses, consistency checks deferred to KB-004
- Template system with cascade resolution (user project → user global → bundled defaults), protocol-based, with versioning
- Working demo loader that populates the KB tables from existing Markdown files
- Full CRUD API with search capabilities
- Frontend KB browser with entity type tabs, list view, detail view, create/edit forms, and relationship management

**Non-Goals:**

- AI Interview sessions (KB-002) — future change
- AI Improve (KB-003) — future change
- Consistency checking (KB-004) — future change; this change only lays the relationship model that KB-004 will consume
- Proactive suggestions (KB-005) — future change
- Worldbuilding assistant (KB-006) — future change
- Entity extraction from chapters (KB-007) — future change
- Knowledge graph visualization (KB-008) — future change; this change provides the data model KB-008 will render
- Semantic/embedding search — uses pgvector but requires embedding provider abstraction (Q-003), deferred
- Filesystem sync (bidirectional DB ↔ files) — future change
- Template override UI — this change implements cascade resolution and versioning, but no UI for managing overrides

## Decisions

### D1: Single polymorphic table with JSONB metadata (Variante C)

**Decision**: One `kb_entries` table for all 6 entity types. `metadata` column is JSONB, validated at application level by entity-type-specific Pydantic schemas.

**Rationale**: Avoids 6 tables with 6 repository classes while maintaining type safety. PostgreSQL JSONB supports indexing (GIN) and querying (`metadata->>'age'`). Pydantic schemas in core provide validation without DB-level constraints on the JSONB shape.

**Alternatives considered**:
- Separate tables per entity type: type-safe in DB, but 6× boilerplate for models, repositories, services. Overkill when metadata is flexible.
- Single table with plain TEXT content: simpler, but no structured querying. Metadata and body would need parsing at runtime.

### D2: Split content into `metadata` (JSONB) + `body` (TEXT)

**Decision**: `metadata` holds structured, queryable fields (age, role, location_type, owner, etc.). `body` holds narrative Markdown content (description, backstory, personality prose, etc.).

**Rationale**: The two serve different consumers. Metadata is for filtering, sorting, and structured queries. Body is for LLM context injection and human reading. The demo files already separate these: YAML frontmatter = metadata, Markdown body = body.

### D3: Relationships as directed edges, no auto-inverses

**Decision**: `kb_relationships` stores directed source→target edges with a free-form `rel_type` string. The core provides suggested inverse pairs (`INVERSE_SUGGESTIONS`), but the service never auto-creates inverse relationships. Every relationship must be explicitly created.

**Rationale**: KB-004 (Consistency Check) treats relationship asymmetries as potential story elements, not data errors. "Elara sees Verrick as mentor, Verrick sees Elara as a burden" is valid character development. Auto-inverses would destroy this information. The `INVERSE_SUGGESTIONS` constant powers frontend prompts and future consistency checks.

**Alternatives considered**:
- Auto-generated inverses: simpler for users, but prevents intentional asymmetries. Conflicts with KB-004 design.
- DB-level ENUM for rel_type: requires migration for every new type. Users and AI should be able to define custom relationship types without schema changes.

### D4: Template system split across core and API

**Decision**: Core owns the template protocol (`TemplateResolver`), model classes, parser, bundled defaults, and schema bridge. API owns the cascade resolver implementation (which needs DB/filesystem access) and override management.

**Rationale**: RULE-07 (dependency direction is one-way: core never imports from apps). The parser is pure logic (no IO). The bundled defaults use `importlib.resources` to work in any deployment. The cascade resolver needs DB access for project-level overrides and filesystem access for user-global overrides — both are API-layer concerns.

### D5: Templates as recommendations, not enforcement

**Decision**: Templates define suggested sections and fields. The metadata schema validates types of fields that ARE provided (if `age` is set, it must be an integer). But no field is mandatory (except `name` and `entity_type` which are top-level columns). Body sections are entirely optional.

**Rationale**: A forest location has no economy section. A non-magical character has no magic section. Templates guide creation, they don't constrain it. AI features (KB-003 Improve) can later suggest adding missing sections based on the template.

### D6: Template versioning for override awareness

**Decision**: Each template carries `template_version` (semver) in its frontmatter. When a user overrides a template, the override records `based_on_version`. On app updates, the system compares the user's `based_on_version` with the current bundled version. If they differ, a notification is shown (not auto-merged). User chooses: keep, update, or diff.

**Rationale**: Auto-merging Markdown templates is unreliable. User overrides represent creative decisions. The fork-based approach respects user autonomy while keeping them informed of changes.

### D7: File format (Markdown + YAML frontmatter) as import/export only

**Decision**: The Markdown+YAML format used by demo data is the import/export format. At runtime, the database is the source of truth. No filesystem sync in this change.

**Rationale**: Files are great for bundled content and future export, but the runtime needs transactions, concurrent access, querying, and relationships — all of which require a database.

## Risks / Trade-offs

**[JSONB query performance]** → Mitigated by GIN index on `metadata` column. For KB sizes up to 1000 entries (typical for a novel), performance is not a concern. For very large worlds, entity-type filtering and the GIN index keep queries fast.

**[JSONB schema drift]** → Metadata schema is enforced at application level (Pydantic), not at DB level. Invalid metadata could exist if validation is bypassed. Mitigated by: all writes go through the service layer which validates via the schema registry. No raw SQL writes. Migration safety: the demo loader parses frontmatter and validates before insert.

**[Relationship explosion]** → A character with connections to 50 other entities creates 50 edges. Not a performance problem at typical novel scale (< 500 entities), but KB-008 (graph visualization) may need pagination. The `kb_relationships` table is indexed on both `source_id` and `target_id`.

**[Template override complexity]** → The cascade system adds complexity. Mitigated by: the core protocol is simple (resolve type+lang → template), and the cascade resolver is the only implementation. No competing cascade logic (the problem RULE-02 was created to prevent for prompts).

**[6 entity types may grow]** → The CHECK constraint on `entity_type` needs a migration for new types. Acceptable trade-off: entity types are a stable domain concept, not user-configurable. New types are rare and deserve schema consideration.

## Open Questions

- **Q-KB-1**: Should user-global template overrides live in `~/.config/narrare/templates/` (filesystem) or in the database? Database is simpler to manage but couples template storage to the API. Filesystem works offline but needs file watching. Recommendation: DB for now, filesystem sync as future feature.

- **Q-KB-2**: How many metadata fields should the core schemas define upfront? The templates have ~20 fields for characters. We can start with the fields present in the demo data and extend as needed — Pydantic schemas with `model_config = ConfigDict(extra="allow")` handle forward compatibility.

- **Q-KB-3**: Should the frontend KB browser be a dedicated page or a panel within the editor? The specs say "Knowledge Base panel" suggesting a panel, but for initial implementation a dedicated page at `/novel/[id]/kb/` is simpler and provides more screen space. Panel integration can come later when the context panel needs to show KB data.
