## Why

The Knowledge Base is the foundation of Narrare's AI capabilities — it provides the structured memory that every AI feature (writing sessions, context assembly, consistency checks, suggestions) depends on. Currently, the demo loader has a deferred import for a non-existent KB module: demo projects are created with chapters but their KB entries are silently skipped. Phase 5 (Integration & Polish) cannot proceed meaningfully without a working KB, because writing sessions need entity context and the editor's context panel has nothing to display.

Building the KB storage layer now, with the right architecture from day one, ensures that all subsequent AI features (KB-002 through KB-008) have a solid, queryable foundation — no migrations from a "simple MVP" to a "real" system later.

## What Changes

- **New DB models**: `kb_entries` table (polymorphic, with JSONB metadata + TEXT body) and `kb_relationships` table (typed, directed relationships between entries)
- **New API module** (`apps/api/narrare/kb/`): Full CRUD for KB entries and relationships, with search (full-text + tag filter + entity type filter) and list endpoints
- **New core schemas** (`packages/core/narrare_core/kb/schemas/`): Entity-type-specific Pydantic models for metadata validation (character, location, faction, object, system, timeline), with a registry mapping entity types to schemas
- **New core relationships module**: Relationship type constants with suggested inverse pairs, powering frontend suggestions and future consistency checks
- **New template system** (`packages/core/narrare_core/templates/`): Protocol-based template resolver, parser for Markdown+YAML templates, bundled defaults per language, and schema bridge connecting template fields to KB metadata schemas
- **Updated demo loader**: The deferred `from narrare.kb.models import KBEntry` import becomes functional — demo KB entries load into the new tables
- **New Frontend**: KB browser UI (list view with entity type tabs, detail view, create/edit forms, relationship management) — so users can see and manage their story world
- **DB migration**: New Alembic migration for `kb_entries` and `kb_relationships` tables

## Capabilities

### New Capabilities

- `kb-storage`: Database models, repository, and CRUD service for KB entries and relationships — the persistence foundation
- `kb-schemas`: Entity-type-specific Pydantic metadata schemas in core, with validation registry — the type safety layer
- `kb-relationships`: Relationship type constants, suggested inverse pairs, and relationship CRUD — the connection layer
- `kb-templates`: Template resolver protocol, parser, bundled defaults, and cascade resolution — the structure guidance layer
- `kb-api`: FastAPI routes for KB CRUD, search, and relationships — the HTTP interface
- `kb-frontend`: KB browser, detail view, create/edit forms, and relationship management in Next.js — the user interface

### Modified Capabilities

- `settings-service`: Demo loader updated to use the new KB models instead of the deferred import

## Impact

**Database**: New tables `kb_entries` and `kb_relationships` with indexes on `entity_type`, `novel_id`, and full-text search on `body`. JSONB GIN index on `metadata`. Migration required.

**Core package**: New `packages/core/narrare_core/kb/schemas/` (entity-type validation) and `packages/core/narrare_core/templates/` (template system). No changes to existing modules.

**API**: New domain module `apps/api/narrare/kb/` following the standard structure (contracts → models → schemas → repository → service → router). No breaking changes to existing endpoints.

**Frontend**: New pages under `app/(app)/novel/[id]/kb/` with entity type tabs, list/detail views, and create/edit forms. Context panel will later consume KB data but is not in scope for this change.

**Dependencies**: No new external dependencies. Uses existing SQLAlchemy, Pydantic, FastAPI, TanStack Query, and `importlib.resources` from stdlib.

**AI features**: This change does NOT implement KB-002 (AI Interview), KB-003 (AI Improve), KB-004 (Consistency Check), or KB-008 (Knowledge Graph) — those build on top of this foundation in future changes.
