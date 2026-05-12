# ADR-011 — Content Versioning for Chapters

> **Status:** ✅ Accepted
> **Date:** 2026-05-12
> **Deciders:** Architecture Agent

---

## Context

Narrare is a creative writing tool. Users **will** overwrite content and want
it back. Currently every save is destructive — no undo beyond browser-level
Ctrl+Z, lost on page refresh.

PostgreSQL 17 supports temporal tables (SQL:2011), but they affect ALL queries
(`FOR SYSTEM_TIME` everywhere) and version the entire row, not just content.
We need versioning only for chapter content.

---

## Decision Drivers

- Non-destructive editing — users must recover work
- Version only chapter content, not all entity fields
- Predictable queries — no implicit temporal magic in every SELECT
- Source tracking — distinguish autosave, manual save, AI drafts
- Controllable retention — old versions prunable
- Simple API — list versions, restore a version

---

## Options Considered

### Option A — Explicit `chapter_versions` table (chosen)

Dedicated table storing historical snapshots, inserted on every update.

```sql
chapter_versions (
    id UUID PK,
    chapter_id UUID FK chapters,
    content TEXT NOT NULL,
    word_count INTEGER NOT NULL,
    version_number INTEGER NOT NULL,
    source VARCHAR(20) DEFAULT 'autosave',  -- autosave|manual|ai_draft
    created_at TIMESTAMP DEFAULT NOW(),
    created_by VARCHAR(20) DEFAULT 'user'   -- user|ai
)
```

**Pros:** Scoped to content only; source tracking; simple retention; no query
impact on other entities; easy restore (update from version row).
**Cons:** Trigger logic in repository; additional table; storage grows (mitigated
by retention limit).

### Option B — PostgreSQL temporal tables

Automatic row versioning built into PostgreSQL 17.

**Pros:** No application trigger logic; built into DB.
**Cons:** Affects ALL queries; versions entire row; no source metadata; ORM
configuration complexity; overkill for single-entity versioning.

### Option C — Event sourcing (append-only diffs)

Store content as sequence of patches.

**Pros:** Minimal storage for small changes.
**Cons:** Expensive reconstruction; complex diff logic; overkill for creative
writing — users want snapshots, not diffs.

---

## Decision

**We choose an explicit `chapter_versions` table.**

Control is the decisive factor. We version only chapter content, track why each
version was created, and don't pollute other queries with temporal awareness.

---

## Rationale

Temporal tables are elegant for schema-wide audit logging. We need targeted
undo for chapter content with source attribution. An explicit table gives us
scoped versioning, source metadata, retention control, and zero query impact
on non-chapter operations.

The repository pattern makes trigger logic clean: `update_content()` inserts
old content into `chapter_versions` before updating. No middleware, no signals.

---

## Consequences

**Positive:** Users browse/restore previous versions; AI drafts preserved
separately; simple mental model (snapshot list); no non-chapter query impact.
**Negative:** Additional table and repository methods; storage grows with
versions (mitigated: 50 × avg chapter size is manageable).

---

## Implementation Notes

### Schema

```sql
CREATE TABLE chapter_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chapter_id UUID NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    word_count INTEGER NOT NULL,
    version_number INTEGER NOT NULL,
    source VARCHAR(20) NOT NULL DEFAULT 'autosave',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by VARCHAR(20) NOT NULL DEFAULT 'user'
);
CREATE INDEX ix_chapter_versions_chapter
    ON chapter_versions(chapter_id, version_number DESC);
```

### Repository pattern

```python
# chapters/repository.py
async def update_content(self, chapter_id: UUID, content: str,
                         source: str = "autosave") -> Chapter:
    chapter = await self._get(chapter_id)
    await self._version_chapter(chapter, source)  # snapshot old content
    chapter.content = content
    chapter.word_count = len(content.split())
    await self.session.flush()
    return chapter
```

### API

```
GET  /novels/{id}/chapters/{cid}/versions                — list versions
POST /novels/{id}/chapters/{cid}/versions/{vid}/restore  — restore version
```

Retention: 50 versions per chapter (configurable via `settings.max_chapter_versions`).

---

## Review Trigger

- [ ] If average chapter size makes 50 versions exceed storage budget
- [ ] If users request diff view between versions (may need append-only then)
- [ ] If versioning is needed for entities beyond chapters
