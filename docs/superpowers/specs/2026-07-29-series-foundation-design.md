# Series / Reihe — Spec 1: Foundation + KB Evolution

> **Status:** Draft — awaiting user review (per brainstorming-skill step 8)
> **Date:** 2026-07-29
> **Authors:** Coordinator (brainstorming synthesis)
> **Brainstorming session:** 2026-07-28/29 (6 clarifying questions + 5 design sections)
> **Companion file:** `docs/superpowers/specs/2026-07-28-series-cross-spec-notes.md`
> **Predecessor:** [ADR-074](../../architecture/decisions/ADR-074-author-voice-storage.md) (Series gap identified; partial close in ADR-075)
> **Successor ADR:** ADR-075-series-foundation (to be created based on this spec)

---

## 1. Context

### 1.1 Series Gap

Narrare hat heute **kein Reihen-Konzept**. Jeder Roman ist eine isolierte Einheit mit eigener Knowledge Base. Mehrere Romane einer Reihe sind völlig getrennte Projekte ohne Verbindungspunkt.

**Verifiziert** (per ADR-074 §„Volume ≠ Series"):
- `apps/api/narrare/volumes/models.py:19` — `Volume.novel_id ForeignKey("novels.id", ondelete="CASCADE")`. Volume ist **intra-novel** Chapter-Grouping, **nicht** inter-novel.
- Keine `Series`-Tabelle, kein `Novel.series_id`, keine Series-Migration.
- `KBEntry` ist strikt an `novel_id` gebunden (`nullable=False`, `ondelete="CASCADE"`). Harry Potter in Roman 1 und Roman 2 sind heute zwei völlig getrennte Zeilen ohne Link.

### 1.2 Program-Level Decomposition (5 Sequenzielle Specs)

Series/Reihe ist ein **Programm**, kein einzelnes Feature. Es wird in 5 sequenzielle Specs decomposed, von denen jeder implementiert wird, bevor der nächste brainstormed wird:

| # | Spec | Inhalt | Vorbedingung |
|---|------|--------|--------------|
| **1** | **Series Foundation + KB Evolution** *(dieses Dokument)* | Series-Entity, Novel.series_id, KB Series-Canon+Novel-Overlay-Modell, CRUD, Navigation, UI | — |
| 2 | Series Generation Context | Reihen-Kontext für Band N (state-at-(N−1) Read-Merge) | Spec 1 implementiert |
| 3 | Series Voice Hierarchy | Override/Blend/Cascade für Reihen-Basisstimme + Roman-Nuancen | Spec 1 implementiert (schließt ADR-074 Review Trigger Voice-Teil) |
| 4 | Series Cross-Novel Drift | ANAL-009 series-scope-Erweiterung | Spec 1+2+3 |
| 5 | Series Export | Reihen-Manuskript / Reihen-Bibel / Einzeltitel | Spec 1 |

### 1.3 Warum Spec 1 „Foundation + KB Evolution" in einem Spec

Foundation (Series-Entity) und KB Evolution (Charakter-States über Bände hinweg) sind **nicht trennbar** in separate Specs, weil:

1. **KB-Strategie bestimmt das Datenmodell.** Ob eine Reihe eine geteilte KB hat oder pro-Roman mit Cross-References, entscheidet ob `KBEntry` ein optionales `series_id` braucht oder nicht.
2. **KB-Strategie bestimmt die Migration.** Geteilte KB = Datenbewegung. Per-Roman-KB mit Scope = reine Schema-Erweiterung.
3. **KB-Strategie bestimmt alle Folgekosten.** Generation, Drift, Export, Voice — alle Consumer der KB stellen unterschiedliche Queries je nach Strategie.

---

## 2. Design Decisions (aus Brainstorming)

Alle 8 Entscheidungen dokumentiert im [Cross-Spec Notes File](2026-07-28-series-cross-spec-notes.md) §Decisions Log. Zusammenfassung:

| # | Entscheidung | Wahl |
|---|--------------|------|
| D1 | KB-Strategie | **Option C** — Hybrid: Series-Canon (kanonisch, geteilt) + Novel-Overlay (per-Band-State) |
| D2 | Scope-Policy für neue Entries | **Policy (iii)** — Entity-Typ-basiertes Default mit Override |
| D3 | Migration beim „Join Series" | **Policy (α)** — adaptiv: Heuristik bei leerem Canon, Novel-Overlay bei nicht-leerem Canon |
| D4 | Series-Datenmodell | Schema bestätigt; Status `draft\|active\|completed`; `SeriesSettings.author_voice` leer in Spec 1 angelegt (forward-compat Spec 3) |
| D5 | Navigation | **N2** — Series als First-Class-Workspace mit 4 Tabs |
| D6 | Multi-Series-Membership | **Single-Series in Spec 1** (Crossover YAGNI; Migrationspfad bekannt) |
| D7 | Schema-Repräsentation | **2A + STI** — Single `kb_entries`-Tabelle + discriminated `SeriesKBEntry`/`NovelKBEntry` Pydantic-Typen in Core |
| D8 | Phasing | **5 vertikale Slices** (Data Foundation → KB Scope → Series CRUD + Join → Frontend → KB Scope UI) |

### 2.1 Warum Option C (KB Hybrid)

**Heterogenität der KB-Entity-Typen:**
- `system/concept/setting/location/object/timeline` (Mehrheit der Fakten) → selten pro-Band variieren → profitieren von einer kanonischen Quelle
- `character/faction` (Minderheit) → starker Evolution pro Band → brauchen Per-Band-State

Option A (Per-Novel + Identity-Layer) würde Magiesystem/Setting/etc. in jedem Band duplizieren → Drift, Sync-Aufwand.
Option B (Per-Series Shared + Snapshots) bricht jede existierende KB-Query und bricht Migration.
**Option C** respektiert Heterogenität: stabile Fakten leben im Canon, evolutionäre Fakten als Overlay.

### 2.2 Warum 2A + STI (Schema)

| Option | Physisch | Logisch | Read-Path | Blast Radius |
|--------|----------|---------|-----------|--------------|
| Pure 2A | Single table | NULL-Discriminator | Einfach | Klein |
| Pure 2B | Two tables | Getrennte Typen | UNION/2-Queries | Groß (~15 Module) |
| **2A + STI** | Single table | Discriminated Pydantic-Typen | Einfach | Klein |

Pure 2B's Typ-Sicherheit-Vorteil ist echt, aber Read-Path-UNION, cross-table-Relationships und Blast-Radius überwiegen. **2A + STI holt 2B's Typ-Sicherheit ohne 2B's Hauptkosten.**

### 2.3 Warum N2 (Series-Workspace)

Specs 2–5 brauchen **alle** eine Heimat für Reihen-Level-UI (Generation-Settings, Voice, Drift, Export). N1 (Flat-Grouped) würde für jeden Spec ad-hoc-Orte finden (wahrscheinlich eingebettet in beliebige Romane). N2 gibt ihnen von Anfang an eine kohärente Heimat mit Tabs.

---

## 3. Architecture

### 3.1 Modul-Struktur (RULE-05)

**Neu Backend `apps/api/narrare/series/`** (mirror des `novels/`-Patterns):
```
series/
├── __init__.py
├── models.py            ← Series, SeriesSettings (SQLAlchemy)
├── contracts.py         ← SeriesRepositoryProtocol, SeriesServiceProtocol, SeriesJoinServiceProtocol
├── schemas.py           ← Pydantic Request/Response
├── repository.py        ← DB-Queries für Series
├── service.py           ← CRUD Business-Logic
├── join_service.py      ← Join-Flow (Policy α, Preview, Heuristik)
├── router.py            ← FastAPI Routes (delegiert sofort an Service)
└── dependencies.py      ← DI-Fabriken
```

**Neu Core `packages/core/narrare_core/series/`** (klein, fokussiert):
- `__init__.py`
- `schemas.py` — `Series`, `SeriesSettings` Pydantic-Typen (pure, kein HTTP/DB)

**Modifiziert Backend:**
- `novels/models.py` — +`series_id`, `series_position`, `subtitle`
- `kb/models.py` — +`series_id`, `base_entry_id`; `novel_id` wird nullable
- `kb/repository.py` — +Scope-aware Queries (`find_canon_for_series`, `find_overlay_for_novel`, `find_merged_for_novel`)

**Modifiziert Core:**
- `kb/schemas/entry.py` (NEU) — STI-Hierarchie (`KBEntryBase` → `SeriesKBEntry`, `NovelKBEntry`)
- `kb/schemas/__init__.py` — re-export `KBEntry` discriminated union für Abwärtskompatibilität

### 3.2 STI Type Design (Core)

```python
# packages/core/narrare_core/kb/schemas/entry.py

from typing import Annotated, Literal, Union
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

class KBEntryBase(BaseModel):
    """Common fields. Single physical table kb_entries (Schema 2A)."""
    model_config = ConfigDict(extra="allow")

    id: UUID
    entity_type: str
    name: str
    slug: str
    status: str = "draft"
    body: str | None = None
    metadata_: dict[str, object] | None = None
    tags: list[str] | None = None
    template_version: str | None = None
    source: str = "manual"
    review_status: str = "approved"
    scope: Literal["series", "novel"]  # discriminator

class SeriesKBEntry(KBEntryBase):
    """Series-Canon KB entry — shared across all novels in the series.

    DB invariant: novel_id IS NULL, series_id IS NOT NULL, base_entry_id IS NULL.
    """
    scope: Literal["series"] = "series"
    series_id: UUID
    novel_id: None = None
    base_entry_id: None = None

class NovelKBEntry(KBEntryBase):
    """Novel-Overlay KB entry — valid in one specific novel.

    DB invariant: novel_id IS NOT NULL.
    series_id set iff novel belongs to a series.
    base_entry_id optional: link to Series-Canon entry this is an overlay of.
    """
    scope: Literal["novel"] = "novel"
    novel_id: UUID
    series_id: UUID | None = None
    base_entry_id: UUID | None = None

KBEntry = Annotated[Union[SeriesKBEntry, NovelKBEntry], Field(discriminator="scope")]
```

DB-CHECK-Constraint `ck_kb_entries_scope_invariant` spiegelt die Typ-Invariante physisch wider.

### 3.3 SQL Schema-Änderungen

**Neue Tabellen:**

```sql
-- series
CREATE TABLE series (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    title VARCHAR(500) NOT NULL,
    subtitle VARCHAR(500),
    description TEXT,
    genre VARCHAR(100),
    writing_language VARCHAR(100),
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    planned_novel_count INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_series_status CHECK (status IN ('draft', 'active', 'completed'))
);
CREATE INDEX ix_series_user_id ON series(user_id);

-- series_settings (1:1 zu series)
CREATE TABLE series_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    series_id UUID NOT NULL UNIQUE REFERENCES series(id) ON DELETE CASCADE,
    author_voice JSONB,  -- empty in Spec 1; populated in Spec 3 (closes ADR-074 RT)
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

**Modifikationen:**

```sql
-- novels: +series_id, +series_position, +subtitle
ALTER TABLE novels
    ADD COLUMN series_id UUID REFERENCES series(id) ON DELETE SET NULL,
    ADD COLUMN series_position INTEGER,
    ADD COLUMN subtitle VARCHAR(500);
CREATE INDEX ix_novels_series_id ON novels(series_id);
ALTER TABLE novels ADD CONSTRAINT uq_novels_series_position UNIQUE (series_id, series_position);

-- kb_entries: +series_id, +base_entry_id, novel_id nullable
ALTER TABLE kb_entries
    ALTER COLUMN novel_id DROP NOT NULL,
    ADD COLUMN series_id UUID REFERENCES series(id) ON DELETE CASCADE,
    ADD COLUMN base_entry_id UUID REFERENCES kb_entries(id) ON DELETE SET NULL;
CREATE INDEX ix_kb_entries_series_id ON kb_entries(series_id);
CREATE INDEX ix_kb_entries_base_entry_id ON kb_entries(base_entry_id);

-- Unique-Constraint-Änderung (partial indexes statt COALESCE-Trick)
ALTER TABLE kb_entries DROP CONSTRAINT uq_kb_entries_novel_slug;
CREATE UNIQUE INDEX uq_kb_canon_per_series ON kb_entries(series_id, slug)
    WHERE novel_id IS NULL;
CREATE UNIQUE INDEX uq_kb_overlay_per_novel ON kb_entries(novel_id, slug)
    WHERE novel_id IS NOT NULL;

-- Scope-Invariant CHECK
ALTER TABLE kb_entries ADD CONSTRAINT ck_kb_entries_scope_invariant CHECK (
    (novel_id IS NULL AND series_id IS NOT NULL AND base_entry_id IS NULL)  -- Series-Canon
    OR
    (novel_id IS NOT NULL)  -- Novel-Overlay
);
```

### 3.4 Migration (Alembic `0036_series_foundation.py`)

Atomic, mit `upgrade()` + `downgrade()` (RULE-14). Reihenfolge:

1. Create `series` table + indexes
2. Create `series_settings` table
3. ALTER `novels` (+series_id, +series_position, +subtitle) + indexes + UNIQUE
4. ALTER `kb_entries` (+series_id, +base_entry_id, novel_id DROP NOT NULL) + indexes
5. DROP `uq_kb_entries_novel_slug`
6. CREATE zwei partielle Unique-Indexes + CHECK-Constraint

Jeder Schritt im eigenen `op.`-Block für saubere Downgrade-Reihenfolge.

**Backward-Kompatibilität:** bestehende `kb_entries`-Rows haben `series_id=NULL`, `novel_id` bleibt gesetzt → bestehende Queries funktionieren unverändert (sehen nur Novel-Overlay).

### 3.5 Dependency Direction (RULE-07)

```
apps/series/router → apps/series/service → apps/series/repository → DB
                          ↓
                       core/series/schemas (Series, SeriesSettings)
                       core/kb/schemas/entry (STI: KBEntryBase, SeriesKBEntry, NovelKBEntry, KBEntry)
```

Core niemals aus `apps/`. Service injected Core-Typen für Compile-Time-Safety.

---

## 4. Backend

### 4.1 Contracts (RULE-03 — zuerst)

`apps/api/narrare/series/contracts.py` definiert **vor** jeder Implementation:

```python
class SeriesRepositoryProtocol(Protocol):
    async def create(self, data: SeriesCreate) -> Series: ...
    async def get(self, series_id: UUID) -> Series | None: ...
    async def list_for_user(self, user_id: UUID) -> list[Series]: ...
    async def update(self, series_id: UUID, patch: SeriesUpdate) -> Series: ...
    async def delete(self, series_id: UUID) -> None: ...
    async def list_novels(self, series_id: UUID) -> list[Novel]: ...
    async def reorder_novels(self, series_id: UUID, novel_ids: list[UUID]) -> None: ...

class SeriesServiceProtocol(Protocol):
    async def create_series(self, user_id: UUID, request: SeriesCreateRequest) -> SeriesResponse: ...
    async def get_series(self, series_id: UUID) -> SeriesResponse: ...
    async def list_series(self, user_id: UUID) -> list[SeriesSummary]: ...
    async def update_series(self, series_id: UUID, patch: SeriesUpdateRequest) -> SeriesResponse: ...
    async def delete_series(self, series_id: UUID) -> None: ...

class SeriesJoinServiceProtocol(Protocol):
    """Policy α: adaptive scope assignment on join."""
    async def preview_join(self, series_id: UUID, novel_id: UUID) -> JoinPreview: ...
    async def apply_join(self, series_id: UUID, novel_id: UUID, position: int) -> JoinResult: ...
```

### 4.2 Series CRUD

`SeriesService` → `SeriesRepository` (Standard-Pattern). Validierung:
- **Status-Transitions:** `draft → active → completed` (kein Sprung; „Abbrechen" → zurück zu `draft`)
- **Position-Lücken:** reorder schließt Lücken automatisch
- **Löschverhalten:** `DELETE /series/{id}` → `ON DELETE SET NULL` macht Romane zu Standalones. `SeriesSettings` CASCADE-deleted. Response: 204.

### 4.3 Join-Flow (Policy α — das Herzstück)

`SeriesJoinService`:

**`preview_join(series_id, novel_id)`** gibt zurück (`JoinPreview`):
- Canon-State der Ziel-Series (leer oder nicht-leer)
- Für jeden KB-Eintrag des Romans: würde bei Apply zu Canon promoted oder als Overlay belassen (laut Policy iii-Heuristik, falls Canon leer)
- 409 Conflict, falls Roman schon in anderer Series

**`apply_join(series_id, novel_id, position)`** führt Preview aus:
- Setzt `Novel.series_id` + `series_position`
- **Wenn Canon der Ziel-Series leer:** Heuristik anwenden — `system/concept/setting/location/object/timeline`-Entries bekommen `novel_id=NULL, series_id=<series>` (werden Canon); `character/faction` bleiben Overlay
- **Wenn Canon nicht leer:** alle Entries bleiben Novel-Overlay; nur `series_id` wird am Roman gesetzt
- Alles in einer Transaktion (atomic)

### 4.4 KB Scope Logic

`kb/repository.py` bekommt drei neue Methoden:
- `find_canon_for_series(series_id) → list[SeriesKBEntry]` — `WHERE novel_id IS NULL AND series_id = ?`
- `find_overlay_for_novel(novel_id) → list[NovelKBEntry]` — `WHERE novel_id = ?`
- `find_merged_for_novel(novel_id) → list[KBEntry]` — Canon der Eltern-Series + Overlay des Romans, gemerged (Overlay gewinnt bei Slug-Kollision). Spec 2 nutzt das für Generation-Context-Assembly; Spec 1 testet es vor.

Zwei Scope-Toggle-Methoden:
- `promote_to_canon(novel_id, entry_id) → SeriesKBEntry` — aus Overlay wird Canon
- `demote_to_overlay(series_id, entry_id, target_novel_id) → NovelKBEntry` — aus Canon wird Overlay; braucht Ziel-Novel (welcher Roman übernimmt)

### 4.5 API-Endpunkte

**Series CRUD** (`apps/api/narrare/series/router.py`):
- `POST /api/v1/series`
- `GET /api/v1/series`
- `GET /api/v1/series/{id}`
- `PATCH /api/v1/series/{id}`
- `DELETE /api/v1/series/{id}`
- `GET /api/v1/series/{id}/novels`
- `POST /api/v1/series/{id}/novels` (Preview-Step)
- `POST /api/v1/series/{id}/novels/{novel_id}/apply` (Apply-Step)
- `DELETE /api/v1/series/{id}/novels/{novel_id}` (Roman → Standalone)
- `PATCH /api/v1/series/{id}/novels/reorder`
- `GET /api/v1/series/{id}/settings`
- `PATCH /api/v1/series/{id}/settings`

**KB Series-Canon** (`apps/api/narrare/kb/router_series.py` — neu, parallel zu bestehendem `router.py`):
- `GET /api/v1/series/{id}/kb` — list Canon entries
- `POST /api/v1/series/{id}/kb` — create Canon entry
- `GET/PATCH/DELETE /api/v1/series/{id}/kb/{entry_id}`

**KB Scope-Toggle** (Erweiterung auf bestehendem `apps/api/narrare/kb/router.py`):
- `POST /api/v1/novels/{novel_id}/kb/{entry_id}/promote` — Overlay → Canon
- `POST /api/v1/novels/{novel_id}/kb/{entry_id}/demote` — Canon → Overlay (Body: `{target_novel_id}`)

### 4.6 Error Handling (RULE-11)

| Fall | Response |
|------|----------|
| Series nicht gefunden | 404 mit klarer Message |
| Series gelöscht (mit Novels) | 204 — Novels werden via SET NULL zu Standalones |
| Novel schon in anderer Series | 409 Conflict mit Series-Referenz |
| Demote scheitert (Canon hat Overlays in anderen Bänden) | 409 mit Liste betroffener Romane |
| try/except with `pass` | **Verboten** (RULE-11) — alle Fehler gelogged + propagated |

### 4.7 RULE-13 (Two-Method run/stream)

Nicht anwendbar auf Series Spec 1 — Series ist pure CRUD, kein LLM. Spec 3 (Series-Voice) wird RULE-13 nutzen.

---

## 5. Frontend

### 5.1 Next.js App Router — Neue Routen

```
/                              Dashboard (modifiziert: N2 mit Series+Standalone-Cards)
/series/[id]                   Series-Workspace (default: Bände-Tab)
/series/[id]/canon             Series-Canon KB-Tab
/series/[id]/settings          Settings-Tab
/series/[id]/voice             Voice-Tab (disabled placeholder in Spec 1)
/novels/[id]                   bestehend (unverändert außer Scope-Toggle in KB)
```

Segments statt Query-Param für Shareability/Bookmarks.

### 5.2 Komponenten-Struktur

**Neu `components/series/`** (mirror von `components/novels/`-Pattern):
```
series/
├── SeriesWorkspace.tsx       ← Main container + Tab-Routing
├── SeriesHero.tsx            ← Title, Status, Meta
├── BändeList.tsx             ← Novel-Liste mit Position-Pills + up/down-Buttons
├── CanonKBTab.tsx            ← Series-Canon KB-Browser (filtered Repository)
├── SeriesSettings.tsx        ← Settings-Form
└── VoiceTab.tsx              ← Disabled Placeholder (Spec 3 füllt)
```

**Modifiziert `components/dashboard/`:**
- `DashboardGrid.tsx` — render Series-Cards + Standalone-Cards gemischt (Farb-Diskriminator)
- `SeriesCard.tsx` (NEU) — wie `NovelCard.tsx`, aber mit Series-Meta (Bände-Anzahl, Status)

**Modifiziert `components/kb/`:**
- `ScopeToggle.tsx` (NEU) — Toggle zwischen Series-Canon / Novel-Overlay; nur sichtbar wenn Novel in Series
- `KBEditor.tsx` (bestehend) — integriert ScopeToggle oben rechts
- `CanonKBEditor.tsx` (NEU oder Variante) — für Canon-Tab im Series-Workspace (kein Novel-Kontext)

### 5.3 Hooks (TanStack Query — bestehend Pattern)

```typescript
// hooks/useSeries.ts
useSeriesList(), useSeries(id), useCreateSeries(), useUpdateSeries(), useDeleteSeries()

// hooks/useSeriesJoin.ts
useJoinPreview(seriesId, novelId), useApplyJoin(seriesId, novelId)

// hooks/useKBScope.ts
usePromoteToCanon(novelId, entryId), useDemoteToOverlay(seriesId, entryId, targetNovelId)

// hooks/useCanonKB.ts (mirror von useKB.ts, aber für Canon-Scope)
useCanonKB(seriesId), useCreateCanonEntry(seriesId), ...

// hooks/useNovelSeries.ts (solider Hook, mind. 3 Consumer)
useNovelSeries(novelId)  // returns Series | null
```

### 5.4 State Management (bestehend Pattern)

- **Server-State:** TanStack Query (alle Hooks oben)
- **UI-State:** Zustand — `useSeriesStore` für aktiven Series-Context (welche Reihe ist offen, aktiver Tab)
- **Ephemeral:** useState für Forms, Toggle-UI
- **Kein neues Pattern** — Frontend bleibt konsistent mit bestehend.

### 5.5 i18n (3 Locales: en/de/fr)

Neue Keys in bestehender Struktur:
- `dashboard.series.*` — Series-Cards im Dashboard
- `series.workspace.*` — Workspace UI (Hero, Tab-Labels, Stats)
- `series.bände.*` — Bände-List
- `series.canon.*` — Series-Canon KB-Tab
- `series.settings.*` — Settings-Form
- `kb.scope.*` — Scope-Toggle, Promote/Demote-Dialoge
- `series.join.*` — Preview-Dialog, Heuristik-Explanation

Alle 3 Sprachen in Spec 1 (keine Staggering).

### 5.6 Animation (motion-Variants — bestehend Pattern)

Reuse aus `lib/motion-variants.ts`:
- Series-Cards: `overlay` oder `listItem` (stagger)
- Series-Workspace Übergang: `panelSlideRight`
- Tab-Wechsel: `crossfade`
- Scope-Toggle: subtle morph (neuer Variante in `motion-variants.ts`, klein)
- `MotionProvider` honored (reduced-motion-support via globaler Config)

### 5.7 ScopeToggle-Komponente (Skizze)

```tsx
// components/kb/ScopeToggle.tsx
function ScopeToggle({ entry, novelId }: Props) {
  const series = useNovelSeries(novelId);  // null wenn Standalone
  if (!series) return null;  // kein Scope-Konzept ohne Series

  const promote = usePromoteToCanon(novelId, entry.id);
  const demote = useDemoteToOverlay(series.id, entry.id);

  return (
    <ToggleGroup value={entry.scope} onChange={handleChange}>
      <ToggleGroupItem value="series" disabled={entry.scope === 'series'}>
        📚 Series-Canon
      </ToggleGroupItem>
      <ToggleGroupItem value="novel" disabled={entry.scope === 'novel'}>
        📖 Novel-Overlay
      </ToggleGroupItem>
    </ToggleGroup>
  );

  function handleChange(newScope: 'series' | 'novel') {
    if (newScope === 'series') {
      confirmDialog(/* warn: becomes visible to all bands */)
        .then(() => promote.mutate());
    } else {
      confirmDialog(/* warn: other bands lose this canon */)
        .then(() => demote.mutate({ targetNovelId: novelId }));
    }
  }
}
```

Confirmation-Dialoge besonders bei Demote (destruktiv für andere Bände).

### 5.8 Was NICHT in Spec 1 Frontend

- Drag-Sort für Bände → up/down-Buttons (YAGNI)
- Series-Stats (Wortzahl, Fortschritt) → leerer State in Spec 1
- Conflict-Warning-UI → Spec 2
- Batch-Selection → Spec 2
- Series-Suche/Filter → Spec 2

---

## 6. Testing (ADR-014 — TDD-Workflow)

### 6.1 Core-Tests

**STI Type Tests** (`tests/unit/core/kb/schemas/test_entry.py`):
- `SeriesKBEntry` validiert korrekt (rejected `novel_id`, required `series_id`)
- `NovelKBEntry` validiert korrekt (required `novel_id`)
- Discriminated-Union-Dispatch: `scope="series"` → `SeriesKBEntry`, `scope="novel"` → `NovelKBEntry`
- JSON-Roundtrip: serialisieren/deserialisieren erhält Subtyp
- `extra="allow"` Verhalten (forward-compat)
- Reject-Versuche: `SeriesKBEntry(novel_id=uuid)` → `ValidationError`

**Series Schema Tests** (`tests/unit/core/series/test_schemas.py`):
- Status-Enum `draft | active | completed` validiert und rejected andere Werte
- Optionale Felder default `None`

### 6.2 Backend-Tests

**Repository Tests** (`tests/unit/api/kb/test_scope_repository.py`):
- `find_canon_for_series(series_id)` — returns only Canon (novel_id IS NULL)
- `find_overlay_for_novel(novel_id)` — returns only Overlay (novel_id = X)
- `find_merged_for_novel(novel_id)` — Canon der Eltern-Series + Overlay des Romans; Overlay gewinnt bei Slug-Kollision
- `promote_to_canon()` / `demote_to_overlay()` Roundtrip
- **Backward-Compat-Critical:** bestehende Queries (`WHERE novel_id = X`) returnen nach Migration dieselben Ergebnisse wie vorher (nur Overlay)

**Service Tests** (`tests/unit/api/series/test_service.py`, `test_join_service.py`):
- Status-Transitions: `draft→active→completed` erlaubt; Sprung `draft→completed` rejected
- Join-Flow mit **leerem Canon**: Heuristik angewendet (`system/concept/setting/location/object/timeline → Canon`; `character/faction → Overlay`)
- Join-Flow mit **nicht-leerem Canon**: alle Entries bleiben Overlay; nur `series_id` wird am Roman gesetzt
- `preview_join()` returns korrekte `JoinPreview`
- `apply_join()` ist atomic (Transaktion rollt zurück bei Teil-Fehler)
- 409 Conflict, wenn Novel schon in anderer Series
- `delete_series()` macht Novals zu Standalones (via SET NULL)

**Router Tests** (`tests/unit/api/series/test_router.py`):
- Alle Endpoints: korrekte Status-Codes (200/201/204/404/409)
- Auth-Enforcement (nur Owner kann Series CRUD'en)
- Rate-Limiting greift (bestehende Pattern)

**Migration Tests** (`tests/integration/test_migration_0036.py`):
- `upgrade()` + `downgrade()` Roundtrip (RULE-14)
- Schema-Roundtrip-Test: assert columns exist post-migration
- Partial-Unique-Indexes vorhanden (`uq_kb_canon_per_series`, `uq_kb_overlay_per_novel`)
- CHECK-Constraint `ck_kb_entries_scope_invariant` existiert und enforced
- **Regression:** bestehende `kb_entries`-Rows bleiben lesbar nach Migration

### 6.3 Frontend-Tests

**Component Tests (Vitest):**
- `ScopeToggle`: versteckt wenn Novel nicht in Series; korrekte Confirmation-Dialoge; Mutations getriggert
- `SeriesCard`: rendert Meta korrekt
- `SeriesWorkspace`: Tab-Routing via Segmente
- `CanonKBTab`: filtered scope
- `JoinPreview`: rendert Heuristik-Plan korrekt

**Hook Tests:**
- `useSeries`, `useSeriesList`, `useSeriesJoin`, `useKBScope`, `useCanonKB`, `useNovelSeries`
- Mock Backend-Responses; verify Query-Key-Caching

**i18n Tests:**
- Alle neuen Keys in en/de/fr
- Keine English-Fallbacks wenn de/fr-Übersetzung existiert

**Animation Tests:**
- Reduced-Motion respected (globaler `MotionProvider` bereits in Spec-1-Erbe)

### 6.4 Architektur-Validation-Tests

`just check` muss weiterhin grün sein:
- Neue `series/` Module folgt RULE-05 (eigene DB-Models, Contracts, Service, Router)
- STI in `core/kb/schemas/entry.py` folgt RULE-06 (eine Verantwortung pro File)
- Keine `core/`→`apps/` Imports (RULE-07)
- Migration im selben Task wie Model-Change (RULE-14)
- File-Size-Limits (RULE-04) eingehalten

### 6.5 Coverage-Targets

| Layer | Target |
|-------|--------|
| Core (STI + Series schemas) | 90%+ |
| Backend (Repository + Service + Router) | 85%+ |
| Frontend (Components + Hooks) | 80%+ |
| Migration (upgrade/downgrade roundtrip) | 100% |

### 6.6 Regression-First (per ADR-014)

Bevor irgendwelche Series-Features implementiert werden:
1. **Regression-Test für KB-Backward-Compat** (grün vor Schema-Änderung, bleibt grün nach Migration): bestehende `WHERE novel_id = X` Queries returnen dasselbe Result Set
2. **Regression-Test für bestehende KB-Consumer** (ANAL-008/WRITE-010/ANAL-009 Tests): alle grün nach STI-Einführung (Core-Types sind kompatibel via Re-Export)

---

## 7. Doc Gate

### 7.1 Pflicht-Updates (Spec 1 DoD)

| Doc | Was | Verantwortlich |
|-----|-----|----------------|
| `docs/architecture/decisions/ADR-075-series-foundation.md` (NEU) | Vollständige ADR-Dokumentation aller 8 Klärungsentscheidungen. Mirror der ADR-074-Struktur. | Architecture Specialist |
| `docs/features/series/SERIES-001-foundation.md` (NEU) | User-facing Feature-Spec mit Help-Texten (Frontmatter wie WRITE-011-Pattern) | Docs Specialist |
| `docs/_shared/CURRENT_STATE.md` | Eintrag unter „Phase 6 — In Progress" wenn Spec 1 landet | Platform Specialist |
| `docs/_shared/GLOSSARY.md` | Neue Begriffe: Series/Reihe, Series-Canon, Novel-Overlay, Scope, STI, Band | Docs Specialist |
| `docs/architecture/decisions/ADR-074-author-voice-storage.md` | Review-Trigger teilweise schließen | Architecture Specialist |
| `docs/architecture/decisions/INDEX.md` | ADR-075 in Decision Log eintragen | Architecture Specialist |

### 7.2 ADR-075 — Struktur (mirror ADR-074)

Pflicht-Sektionen: Context, Decision Drivers, Options Considered (alle 8), Decision, Rationale, Consequences, CR-04 Cross-Feature Impact, Retrofit-Plan, Risks, RULE-XX Compliance, Review Triggers.

### 7.3 Doc Gate Trigger innerhalb Spec 1

Nach jedem der 5 Phasing-Slices:
1. **Nach Slice 1 (Data Foundation):** ADR-075 Draft erstellt (Schema ist final)
2. **Nach Slice 2 (KB Scope):** ADR-075 CR-04 + Risks-Sektion vervollständigt
3. **Nach Slice 3 (Series CRUD + Join):** Feature-Spec SERIES-001 erstellt
4. **Nach Slice 4 (Frontend Dashboard + Workspace):** Help-Texte, i18n-Keys finalisiert
5. **Nach Slice 5 (KB Scope UI):** GLOSSARY-Update, ADR-075 finalisiert, CURRENT_STATE-Eintrag, ADR-074 Review-Trigger teilweise geschlossen

### 7.4 Optional Docs (YAGNI-deferred, transparent dokumentiert)

Siehe Cross-Spec-Notes-File §„YAGNI — What's Deferred from Spec 1" für die vollständige Liste der verschobenen Dokumente (Directory-Structure-Update, CHANGELOG, Orchestrator-Notes) und Features.

---

## 8. Implementation Phasing — 5 Vertical Slices

| Slice | Inhalt | Abhängigkeiten |
|-------|--------|----------------|
| **1. Data Foundation** | `Series` + `SeriesSettings` SQLAlchemy + Alembic-Migration (Tabellen + Novel-Spalten) + Core Pydantic-Contracts für Series | — |
| **2. KB Scope** | `KBEntry`-Schema-Erweiterung (`series_id`, `base_entry_id`, `novel_id` nullable) + Alembic + STI Core-Types (`KBEntryBase`, `SeriesKBEntry`, `NovelKBEntry`, `KBEntry`) + Repository-Erweiterung (`find_canon_for_series`, `find_overlay_for_novel`, `find_merged_for_novel`) | Slice 1 (Core series/ Modul existiert) |
| **3. Series CRUD + Join-Flow** | Backend Series/Novels-Services + CRUD-Router + Join-with-Preview (Policy α) + Heuristik-Application (Policy iii) + Scope-Toggle-Endpoints | Slices 1+2 |
| **4. Frontend Dashboard + Workspace** | Dashboard-Cards (Series + Standalone) + `/series/[id]` Workspace (4 Tabs) + Bände-Liste + Settings-Form | Slice 1 (für Series-Daten); Slice 3 (für CRUD-Endpoints) |
| **5. KB Scope UI** | Scope-Toggle im KB-Editor + Canon-Tab im Series-Workspace + i18n | Slices 2+3 |

Slices 1+2 können parallel (unterschiedliche Tabellen/Module); 3 braucht 1+2; 4 braucht 1 (und 3 für volle Funktionalität); 5 braucht 2+3.

---

## 9. YAGNI — What's NOT in Spec 1

Vollständige Liste im [Cross-Spec Notes File](2026-07-28-series-cross-spec-notes.md) §„YAGNI". Highlights:

- Conflict-Detection (Canon says X, Overlay says Y) → Spec 2+
- Series stats endpoint & UI → Spec 2
- Drag-Sort für Bände → Spec 2 (initial: up/down-Buttons)
- Batch-Promote/Demote → Spec 2
- Series-Suche/Filter → Spec 2
- Series-Cover-Upload → Spec 5
- Series-Voice-Tab funktional → Spec 3 (disabled Placeholder in Spec 1)
- Series-Export → Spec 5
- Generation-Context für Band N → Spec 2
- Cross-Novel-Drift → Spec 4
- Multi-Series-Membership / Crossover → No Spec (YAGNI)
- Optional Docs → später, wenn natürlich

**Reversal-Cost-Awareness:** Alle deferred Items sind additiv, wenn sie landen — keines erfordert Spec-1-Arbeit rückgängig zu machen.

---

## 10. Risks and Mitigations

| Risk | Severity | Mitigation |
|------|----------|------------|
| KB Schema-Änderung bricht bestehende Consumer (~15 Module) | Hoch | STI + Re-Exports garantieren, dass bestehende `from narrare_core.kb.schemas import KBEntry` Imports weiterhin funktionieren. Regression-Tests für ANAL-008/WRITE-010/ANAL-009 als Safety-Net. |
| Migration macht bestehende KB-Queries kaputt | Hoch | `WHERE novel_id = X` Queries returnieren weiterhin nur Overlay (Canon hat `novel_id IS NULL` und wird nicht erfasst). Regression-Test verifies das explizit. |
| Scope-Invariant wird verletzt (z.B. Canon-Entry mit novel_id) | Mittel | DB-CHECK-Constraint `ck_kb_entries_scope_invariant` enforced physisch. Pydantic-STI enforced logisch. Doppelschutz. |
| Heuristik (Policy iii) fährt falsche Default-Entscheidungen | Mittel | User kann jederzeit via Scope-Toggle überschreiben. Heuristik-Verhalten ist in Preview sichtbar, bevor Apply läuft. |
| Spec-1-Scope driftet (z.B. Conflict-Detection „muss noch rein") | Mittel | YAGNI-Liste ist verbindlich; neue Features müssen begründet werden, nicht stillschweigend addiert. |
| Perry-Rhodan-Edge-Case (1000 Bände) skaliert nicht | Niedrig | 1000 Series-Canon-Entries + 1000×Character-Overlays sind speichertechnisch trivial. Spec 1 ist nicht der Skalierungs-Punkt; Spec 2 (Generation) muss ggf. Pagination/Priority-Ranking adressieren. |

---

## 11. Open Questions for Future Specs

Diese Fragen sind in Spec 1 **nicht** gelöst und werden in den jeweiligen Specs behandelt:

- **Spec 2:** Wie werden Band-Summaries erzeugt (WIKI-001-Aggregation vs. explizites „Band-N-Summary"-Feld)? Wie viel Series-Canon + Overlay wird bei Generation für Band N injiziert (Token-Budget)?
- **Spec 3:** Override vs. Blend vs. Cascade für Voice-Hierarchy? Wie geht die Cascade-Fallback-Kritik aus ADR-074 in Series-Kontext auf?
- **Spec 4:** Read-Scope für Series-Drift (Full-Series-Scan vs. Current-vs-Prior-Band)? Performance für lange Reihen?
- **Spec 5:** Series-Export-Formate? Series-Bibel-Layout?

Siehe [Cross-Spec Notes File](2026-07-28-series-cross-spec-notes.md) §„Notes for Spec 2/3/4/5" für detailliertere Vorab-Notizen.

---

## 12. Success Criteria (Spec 1 DoD)

- [ ] Alle 5 Slices implementiert + getestet
- [ ] Alembic-Migration `0036_series_foundation` upgrade + downgrade roundtrip-grün
- [ ] ADR-075 geschrieben und committed
- [ ] Feature-Spec SERIES-001 geschrieben
- [ ] CURRENT_STATE-Eintrag mit Commit-Range
- [ ] GLOSSARY-Update mit neuen Begriffen
- [ ] ADR-074 Review-Trigger teilweise geschlossen (Series-Storage-Teil)
- [ ] `just check` grün (Architecture + Adoption + AI-UX + Frontend-Size + Streaming + Prompt-Structure + Doc-Drift)
- [ ] Test-Suite grün: Core 90%+, Backend 85%+, Frontend 80%+, Migration 100%
- [ ] Regression-Tests für ANAL-008/WRITE-010/ANAL-009 grün
- [ ] i18n-Parität en/de/fr
- [ ] Keine neuen Architecture-Exceptions ohne ADR

---

## 13. Appendix: Brainstorming Decisions Log

Siehe [Cross-Spec Notes File](2026-07-28-series-cross-spec-notes.md) §„Decisions Log (chronological)" für die chronologische Auflistung aller 11 Entscheidungen mit Datum, Rationale und Betroffenheit.

---

> **Nächster Schritt (per brainstorming-skill):** Spec-Self-Review (Placeholder-Scan, Konsistenz, Scope, Ambiguity) → User-Review des Specs → Transition zu `writing-plans`-Skill für Implementation-Plan-Erstellung.
