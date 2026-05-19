## 1. Core: KB Metadata Schemas

- [x] 1.1 Create `packages/core/narrare_core/kb/schemas/base.py` with `KBEntryMetadata` base model (extra="allow", all fields optional)
- [x] 1.2 Create `packages/core/narrare_core/kb/schemas/character.py` with `CharacterMetadata` (age, role, arc, gender, pronouns, nationality, pov_character, affiliation, element, first_appearance, aliases)
- [x] 1.3 Create `packages/core/narrare_core/kb/schemas/location.py` with `LocationMetadata` (location_type, parent_location, coordinates, climate, terrain, size, first_appearance)
- [x] 1.4 Create `packages/core/narrare_core/kb/schemas/faction.py` with `FactionMetadata` (founded, members, ideology, first_appearance)
- [x] 1.5 Create `packages/core/narrare_core/kb/schemas/object.py` with `ObjectMetadata` (object_type, owner, origin, first_appearance)
- [x] 1.6 Create `packages/core/narrare_core/kb/schemas/system.py` with `SystemMetadata` (system_type, practitioners, first_appearance)
- [x] 1.7 Create `packages/core/narrare_core/kb/schemas/timeline.py` with `TimelineMetadata` (era, start_date, end_date, first_appearance)
- [x] 1.8 Create `packages/core/narrare_core/kb/schemas/registry.py` with `SCHEMA_REGISTRY` mapping entity types to schema classes and `get_schema(entity_type)` helper
- [x] 1.9 Write unit tests for all 7 schemas (validation, extra fields, registry lookup)

## 2. Core: Relationship Types

- [x] 2.1 Create `packages/core/narrare_core/kb/relationships.py` with `RelationshipType` constants organized by entity-type pair
- [x] 2.2 Add `INVERSE_SUGGESTIONS` dict mapping relationship types to suggested inverses
- [x] 2.3 Add `suggested_for(source_type, target_type)` function returning applicable relationship types
- [x] 2.4 Write unit tests for relationship constants, inverse lookup, and suggested_for

## 3. Core: Template System

- [x] 3.1 Create `packages/core/narrare_core/templates/models.py` with `Template`, `TemplateMeta`, `TemplateField` Pydantic models
- [x] 3.2 Create `packages/core/narrare_core/templates/contracts.py` with `TemplateResolver` protocol (resolve, list_available)
- [x] 3.3 Create `packages/core/narrare_core/templates/parser.py` with `parse_template(raw: str) -> Template` function
- [x] 3.4 Move bundled templates from `_scratch/packages/core/narrare_core/templates/global/` to `packages/core/narrare_core/templates/defaults/` (en, de, fr subdirectories)
- [x] 3.5 Create `packages/core/narrare_core/templates/defaults/__init__.py` with `importlib.resources` access to bundled templates
- [x] 3.6 Create `packages/core/narrare_core/templates/schema_bridge.py` connecting template fields to KB metadata schema fields
- [x] 3.7 Write unit tests for parser (valid template, missing frontmatter, multi-language), schema bridge, and defaults loading

## 4. API: KB Database Models & Migration

- [x] 4.1 Create `apps/api/narrare/kb/models.py` with `KBEntry` model (id, novel_id, entity_type CHECK, name, slug UNIQUE per novel, status, tags JSONB, metadata JSONB, body TEXT, template_version, embeddings_dirty, timestamps)
- [x] 4.2 Add `KBRelationship` model to `apps/api/narrare/kb/models.py` (id, source_id FK, target_id FK, rel_type, label, direction, metadata JSONB, UNIQUE constraint, CHECK source!=target, timestamps)
- [x] 4.3 Register both models in `apps/api/narrare/_app/database.py` or Alembic `env.py` for autogenerate
- [x] 4.4 Create Alembic migration `XXXX_kb_entries_relationships.py` with tables, indexes (GIN on metadata, FTS on name+body), and constraints
- [x] 4.5 Verify migration upgrade/downgrade works, write schema regression test

## 5. API: KB Contracts, Schemas, Repository

- [x] 5.1 Create `apps/api/narrare/kb/contracts.py` with Protocols: `KBServiceProtocol`, `KBRepositoryProtocol`, `RelationshipServiceProtocol`
- [x] 5.2 Create `apps/api/narrare/kb/schemas.py` with Pydantic request/response models (KBEntryCreate, KBEntryUpdate, KBEntryResponse, KBEntryListResponse, KBRelationshipCreate, KBRelationshipResponse, KBSearchRequest)
- [x] 5.3 Create `apps/api/narrare/kb/repository.py` with `KBRepository` class implementing CRUD, search (full-text + type filter + tag filter), and pagination
- [x] 5.4 Create `apps/api/narrare/kb/relationship_repository.py` with relationship CRUD and entry-scoped queries
- [x] 5.5 Write unit tests for repository (CRUD, search, pagination, constraints) using test database

## 6. API: KB Service & Router

- [x] 6.1 Create `apps/api/narrare/kb/service.py` with `KBService` implementing `KBServiceProtocol` — delegates to repository, validates metadata via core schema registry, generates slugs
- [x] 6.2 Create `apps/api/narrare/kb/relationship_service.py` with `RelationshipService` — delegates to relationship_repository, provides inverse suggestions, ownership validation
- [x] 6.3 Create `apps/api/narrare/kb/router.py` with FastAPI routes: CRUD for entries, search, CRUD for relationships, all scoped to novel with ownership check
- [x] 6.4 Create dependency injection helpers in `apps/api/narrare/kb/dependencies.py`
- [x] 6.5 Write unit tests for KBService (metadata validation, slug generation, ownership checks)
- [x] 6.6 Write integration tests for KB API routes (create, list, get, update, delete, search, relationships)

## 7. API: Template Cascade Resolver

- [x] 7.1 Create `apps/api/narrare/templates/cascade_resolver.py` implementing core `TemplateResolver` protocol with cascade: user_project → user_global → bundled defaults
- [x] 7.2 Create `apps/api/narrare/templates/template_override_service.py` for CRUD on user template overrides with `based_on_version` tracking
- [x] 7.3 Write unit tests for cascade resolver (override precedence, language fallback, version mismatch detection)

## 8. API: Demo Loader Integration

- [x] 8.1 Update `apps/api/narrare/setup/demo_loader.py` to remove the deferred import try/except and use the real `KBEntry` model
- [x] 8.2 Update `_load_kb_entries` to separate frontmatter into metadata JSONB and content into body TEXT
- [x] 8.3 Write integration test verifying demo projects load with correct KB entries, metadata, and bodies

## 9. Frontend: KB Browser & API Client

- [x] 9.1 Create API client functions in `packages/web/lib/api/kb.ts` (listEntries, getEntry, createEntry, updateEntry, deleteEntry, searchEntries, listRelationships, createRelationship, deleteRelationship)
- [x] 9.2 Create TanStack Query hooks in `packages/web/lib/hooks/useKB.ts` (useKBEntries, useKBEntry, useKBSearch, useKBRelationships)
- [x] 9.3 Create KB browser page at `packages/web/app/(app)/novel/[id]/kb/page.tsx` with entity type tabs and entry list/grid
- [x] 9.4 Create KB entry card component in `packages/web/components/kb/EntryCard.tsx`
- [x] 9.5 Create KB entry detail view with rendered Markdown, metadata display, relationship list
- [x] 9.6 Create KB entry create/edit form with entity type selector, name field, Markdown editor for body, tag input, status selector
- [x] 9.7 Create relationship management UI (add relationship dialog with entity search, type selector, inverse suggestion prompt)
- [x] 9.8 Add KB navigation link to editor sidebar with entry count badge
- [x] 9.9 Add i18n keys for KB UI to all three locales (en, de, fr)
- [x] 9.10 Write component tests for KB browser, entry card, detail view, and forms

## 10. Validation & Architecture

- [x] 10.1 Run `scripts/check_architecture.py` and fix any violations (file size, import rules)
- [x] 10.2 Run full test suite (unit + integration) and ensure all tests pass
- [x] 10.3 Verify Alembic migration works against clean database
- [ ] 10.4 Manual smoke test: create novel, verify demo KB loads, browse entries, create/edit/delete entries, manage relationships
