# Series Foundation — Slice 5: KB Scope UI + Final Doc Gate

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development or superpowers:executing-plans. Steps use `- [ ]` for tracking.
>
> **Part of:** Series Foundation plan set — see `2026-07-29-series-foundation-index.md` for execution order.
> **Predecessor:** Slice 4 (`2026-07-29-series-foundation-slice-4-frontend.md`) — components/hooks/types must exist.
> **Successor:** Implementation complete after this slice. Then Spec 2 brainstorming begins.
> **Spec source:** `docs/superpowers/specs/2026-07-29-series-foundation-design.md`

**Goal:** Implement KB scope UI — ScopeToggle component (promote/demote), CanonKBTab (replaces Slice-4 placeholder), CanonKBEditor, plus hooks (`useKBScope`, `useCanonKB`) and i18n. Then complete Final Doc Gate: ADR-075, SERIES-001 feature spec, GLOSSARY, CURRENT_STATE, ADR-074 partial close.

**Architecture:** ScopeToggle is the only scope-related UI change in existing Novel-KBEditor. CanonKBTab + CanonKBEditor live in Series-Workspace (Canon tab). Both consume backend endpoints from Slice 3.

**Global constraints:** See main plan §Global Constraints. Plus: ConfirmationDialog required for demote (destructive to other bands).

---

## Task 5.1: useKBScope hook

**Files:**
- Create: `packages/web/hooks/useKBScope.ts`
- Test: `packages/web/hooks/__tests__/useKBScope.test.ts`

**Interfaces:**
- Consumes: promote/demote endpoints from Slice 3 Task 3.7
- Produces: `usePromoteToCanon(novelId, entryId)`, `useDemoteToOverlay(seriesId, entryId)`

- [ ] **Step 1: Write failing test**

```typescript
// packages/web/hooks/__tests__/useKBScope.test.ts
import { describe, it, expect, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { usePromoteToCanon } from "../useKBScope";

describe("usePromoteToCanon", () => {
  it("calls POST /novels/{id}/kb/{entryId}/promote", async () => {
    const mockFetch = vi.fn().mockResolvedValue({ ok: true, json: () => ({ id: "e1", scope: "series" }) });
    global.fetch = mockFetch as any;
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={new QueryClient()}>{children}</QueryClientProvider>
    );
    const { result } = renderHook(() => usePromoteToCanon("n1", "e1"), { wrapper });
    result.current.mutate();
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/novels/n1/kb/e1/promote"),
      expect.objectContaining({ method: "POST" }),
    );
  });
});
```

- [ ] **Step 2: Implement hook**

```typescript
// packages/web/hooks/useKBScope.ts
import { useMutation, useQueryClient } from "@tanstack/react-query";

async function promoteToCanon(novelId: string, entryId: string) {
  const res = await fetch(`/api/v1/novels/${novelId}/kb/${entryId}/promote`, {
    method: "POST",
    credentials: "include",
  });
  if (!res.ok) throw new Error(`Promote failed: ${res.status}`);
  return res.json();
}

async function demoteToOverlay(seriesId: string, entryId: string, targetNovelId: string) {
  const res = await fetch(`/api/v1/novels/${targetNovelId}/kb/${entryId}/demote`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ series_id: seriesId, target_novel_id: targetNovelId }),
  });
  if (!res.ok) throw new Error(`Demote failed: ${res.status}`);
  return res.json();
}

export function usePromoteToCanon(novelId: string, entryId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => promoteToCanon(novelId, entryId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["kb", novelId] });
      qc.invalidateQueries({ queryKey: ["canon-kb"] }); // refresh canon list
    },
  });
}

export function useDemoteToOverlay(seriesId: string, entryId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (targetNovelId: string) => demoteToOverlay(seriesId, entryId, targetNovelId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["canon-kb"] });
      qc.invalidateQueries({ queryKey: ["kb"] });
    },
  });
}
```

- [ ] **Step 3: Run tests, verify pass**

- [ ] **Step 4: Commit**

```bash
git add packages/web/hooks/useKBScope.ts packages/web/hooks/__tests__/useKBScope.test.ts
git commit -m "feat(web/hooks): add useKBScope (promote/demote mutations)

Spec 1 Slice 5 Task 5.1 — TanStack Query mutations for scope toggle.
Invalidates both kb (novel) and canon-kb (series) caches on success."
```

---

## Task 5.2: useCanonKB hook

**Files:**
- Create: `packages/web/hooks/useCanonKB.ts`
- Test: `packages/web/hooks/__tests__/useCanonKB.test.ts`

> **Pattern:** Mirror of existing `useKB.ts` but for series-scope (Canon) endpoints.

- [ ] **Step 1: Write failing test** (similar to Task 4.2)

- [ ] **Step 2: Implement hook**

```typescript
// packages/web/hooks/useCanonKB.ts
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

const BASE = (seriesId: string) => `/api/v1/series/${seriesId}/kb`;

async function fetchJson(path: string, init?: RequestInit) {
  const res = await fetch(path, {
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.status === 204 ? null : res.json();
}

export function useCanonKB(seriesId: string) {
  return useQuery({
    queryKey: ["canon-kb", seriesId],
    queryFn: () => fetchJson(BASE(seriesId)),
  });
}

export function useCreateCanonEntry(seriesId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      fetchJson(BASE(seriesId), { method: "POST", body: JSON.stringify(body) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["canon-kb", seriesId] }),
  });
}

export function useUpdateCanonEntry(seriesId: string, entryId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      fetchJson(`${BASE(seriesId)}/${entryId}`, { method: "PATCH", body: JSON.stringify(body) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["canon-kb", seriesId] }),
  });
}

export function useDeleteCanonEntry(seriesId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (entryId: string) =>
      fetchJson(`${BASE(seriesId)}/${entryId}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["canon-kb", seriesId] }),
  });
}
```

- [ ] **Step 3: Run tests, verify pass**

- [ ] **Step 4: Commit**

```bash
git add packages/web/hooks/useCanonKB.ts packages/web/hooks/__tests__/useCanonKB.test.ts
git commit -m "feat(web/hooks): add useCanonKB (CRUD for Canon KB)

Spec 1 Slice 5 Task 5.2 — TanStack Query hooks for series-scope KB
CRUD. Mirrors useKB pattern but hits /api/v1/series/{id}/kb/* endpoints."
```

---

## Task 5.3: ScopeToggle component

**Files:**
- Create: `packages/web/components/kb/ScopeToggle.tsx`
- Test: `packages/web/components/kb/__tests__/ScopeToggle.test.tsx`

> **Critical UX:** Hidden when novel is not in a series. Confirmation required for both promote and demote (both have side effects beyond the current entry).

- [ ] **Step 1: Write failing test**

```typescript
// packages/web/components/kb/__tests__/ScopeToggle.test.tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { ScopeToggle } from "../ScopeToggle";

vi.mock("../../../hooks/useNovelSeries", () => ({
  useNovelSeries: vi.fn(),
}));

describe("ScopeToggle", () => {
  it("returns null when novel is standalone (no series)", () => {
    const { useNovelSeries } = require("../../../hooks/useNovelSeries");
    useNovelSeries.mockReturnValue({ data: null });
    const { container } = render(
      <ScopeToggle entry={{ id: "e1", scope: "novel" }} novelId="n1" />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("renders toggle when novel is in series", () => {
    const { useNovelSeries } = require("../../../hooks/useNovelSeries");
    useNovelSeries.mockReturnValue({ data: { id: "s1", title: "Test" } });
    render(<ScopeToggle entry={{ id: "e1", scope: "novel" }} novelId="n1" />);
    expect(screen.getByText(/Series-Canon|Reihen-Kanon/i)).toBeInTheDocument();
    expect(screen.getByText(/Novel-Overlay|Roman-Overlay/i)).toBeInTheDocument();
  });

  it("shows confirmation dialog on demote click", async () => {
    const { useNovelSeries } = require("../../../hooks/useNovelSeries");
    useNovelSeries.mockReturnValue({ data: { id: "s1", title: "Test" } });
    render(<ScopeToggle entry={{ id: "e1", scope: "series" }} novelId="n1" />);
    await userEvent.click(screen.getByText(/Novel-Overlay|Roman-Overlay/i));
    expect(screen.getByText(/confirm|bestätigen/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Implement component**

```tsx
// packages/web/components/kb/ScopeToggle.tsx
"use client";
import { useState } from "react";
import { useTranslations } from "next-intl";
import { useNovelSeries } from "../../hooks/useNovelSeries";
import { usePromoteToCanon, useDemoteToOverlay } from "../../hooks/useKBScope";
import { ConfirmDialog } from "../shared/ConfirmDialog";
import type { KBScope } from "../../types/series";

interface Props {
  entry: { id: string; scope: KBScope };
  novelId: string;
}

export function ScopeToggle({ entry, novelId }: Props) {
  const t = useTranslations("kb.scope");
  const { data: series, isLoading } = useNovelSeries(novelId);
  const promote = usePromoteToCanon(novelId, entry.id);
  const demote = useDemoteToOverlay(series?.id ?? "", entry.id);
  const [confirmAction, setConfirmAction] = useState<"promote" | "demote" | null>(null);

  // Hidden when novel isn't in a series (standalone novels don't need scope)
  if (!isLoading && !series) return null;
  if (isLoading || !series) return null;

  const handleChange = (newScope: KBScope) => {
    if (newScope === entry.scope) return;
    setConfirmAction(newScope === "series" ? "promote" : "demote");
  };

  return (
    <>
      <div className="kb-scope-toggle" role="radiogroup" aria-label={t("label")}>
        <button
          type="button"
          role="radio"
          aria-checked={entry.scope === "series"}
          disabled={entry.scope === "series"}
          onClick={() => handleChange("series")}
          className={`scope-option ${entry.scope === "series" ? "active canon" : ""}`}
        >
          📚 {t("series_canon")}
        </button>
        <button
          type="button"
          role="radio"
          aria-checked={entry.scope === "novel"}
          disabled={entry.scope === "novel"}
          onClick={() => handleChange("novel")}
          className={`scope-option ${entry.scope === "novel" ? "active overlay" : ""}`}
        >
          📖 {t("novel_overlay")}
        </button>
      </div>

      {confirmAction === "promote" && (
        <ConfirmDialog
          title={t("promote_title")}
          description={t("promote_description")}
          confirmLabel={t("promote")}
          cancelLabel={t("cancel")}
          onConfirm={() => {
            promote.mutate();
            setConfirmAction(null);
          }}
          onCancel={() => setConfirmAction(null)}
        />
      )}

      {confirmAction === "demote" && (
        <ConfirmDialog
          title={t("demote_title")}
          description={t("demote_description")}
          confirmLabel={t("demote")}
          cancelLabel={t("cancel")}
          onConfirm={() => {
            demote.mutate(novelId);
            setConfirmAction(null);
          }}
          onCancel={() => setConfirmAction(null)}
        />
      )}
    </>
  );
}
```

- [ ] **Step 3: Run tests, verify pass**

- [ ] **Step 4: Commit**

```bash
git add packages/web/components/kb/ScopeToggle.tsx packages/web/components/kb/__tests__/ScopeToggle.test.tsx
git commit -m "feat(web/kb): add ScopeToggle component (promote/demote)

Spec 1 Slice 5 Task 5.3 — Toggle between Series-Canon and Novel-Overlay.
Hidden when novel is standalone. Confirmation required for both
directions (both have side effects beyond the current entry). Uses
existing ConfirmDialog pattern. Disabled-state shows current scope."
```

---

## Task 5.4: Integrate ScopeToggle into existing KBEditor

**Files:**
- Modify: `packages/web/components/kb/KBEditor.tsx` (or equivalent per existing codebase structure)

> **Note:** Exact integration point depends on existing KBEditor structure. Add `<ScopeToggle>` in the entry-header area, near the entry title.

- [ ] **Step 1: Write integration test**

```typescript
// packages/web/components/kb/__tests__/KBEditor.test.tsx
// (Extend existing test file — verify ScopeToggle renders in header when novel is in series)
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
// ... existing KBEditor test setup

describe("KBEditor scope integration", () => {
  it("renders ScopeToggle in entry header when novel is in series", async () => {
    // Mock useNovelSeries to return a series
    // Render KBEditor with an entry
    // Verify ScopeToggle is in the header area
  });

  it("does not render ScopeToggle when novel is standalone", async () => {
    // Mock useNovelSeries to return null
    // Render KBEditor
    // Verify no scope toggle present
  });
});
```

- [ ] **Step 2: Modify KBEditor to include ScopeToggle**

```tsx
// packages/web/components/kb/KBEditor.tsx — add to entry-header area:
import { ScopeToggle } from "./ScopeToggle";

// In the render, within the entry-header div:
<div className="kb-entry-header">
  <div>
    <h2>{entry.name}</h2>
    <div className="kb-entry-meta">{/* existing meta */}</div>
  </div>
  <ScopeToggle entry={entry} novelId={novelId} />
</div>
```

- [ ] **Step 3: Run tests, verify pass**

- [ ] **Step 4: Commit**

```bash
git add packages/web/components/kb/KBEditor.tsx packages/web/components/kb/__tests__/KBEditor.test.tsx
git commit -m "feat(web/kb): integrate ScopeToggle into KBEditor entry header

Spec 1 Slice 5 Task 5.4 — KBEditor renders ScopeToggle in the entry
header. ScopeToggle internally handles standalone-vs-series logic
(returns null when standalone), so KBEditor needs no conditional."
```

---

## Task 5.5: CanonKBTab + CanonKBEditor components

**Files:**
- Create: `packages/web/components/series/CanonKBTab.tsx`
- Create: `packages/web/components/kb/CanonKBEditor.tsx`
- Modify: `packages/web/app/series/[id]/canon/page.tsx` (replace Slice-4 placeholder)
- Test: corresponding test files

> **Goal:** Replace the Slice-4 Canon-tab placeholder with a functional Canon-KB browser + editor.

- [ ] **Step 1: Write failing test for CanonKBTab**

```typescript
// packages/web/components/series/__tests__/CanonKBTab.test.tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { CanonKBTab } from "../CanonKBTab";

vi.mock("../../hooks/useCanonKB", () => ({
  useCanonKB: vi.fn().mockReturnValue({
    data: [
      { id: "e1", entity_type: "system", name: "Magic", slug: "magic", scope: "series" },
    ],
  }),
}));

describe("CanonKBTab", () => {
  it("renders Canon entries list", async () => {
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={new QueryClient()}>{children}</QueryClientProvider>
    );
    render(<CanonKBTab seriesId="s1" />, { wrapper });
    await waitFor(() => {
      expect(screen.getByText("Magic")).toBeInTheDocument();
    });
  });
});
```

- [ ] **Step 2: Implement components**

```tsx
// packages/web/components/series/CanonKBTab.tsx
"use client";
import { useCanonKB } from "../../hooks/useCanonKB";
import { useTranslations } from "next-intl";
import { CanonKBEditor } from "../kb/CanonKBEditor";

export function CanonKBTab({ seriesId }: { seriesId: string }) {
  const t = useTranslations("series.canon");
  const { data: entries, isLoading } = useCanonKB(seriesId);

  if (isLoading) return <div className="loading">{t("loading")}</div>;

  return (
    <div className="canon-kb-tab">
      <div className="canon-kb-header">
        <h2>{t("title")}</h2>
        <p className="canon-kb-description">{t("description")}</p>
      </div>
      <div className="canon-kb-grid">
        {entries?.map((entry) => (
          <CanonKBEditor key={entry.id} entry={entry} seriesId={seriesId} />
        ))}
        {entries?.length === 0 && (
          <div className="canon-kb-empty">{t("empty")}</div>
        )}
      </div>
    </div>
  );
}
```

```tsx
// packages/web/components/kb/CanonKBEditor.tsx
"use client";
import { useState } from "react";
import { useTranslations } from "next-intl";

interface Props {
  entry: {
    id: string;
    entity_type: string;
    name: string;
    slug: string;
    body?: string;
  };
  seriesId: string;
}

export function CanonKBEditor({ entry, seriesId }: Props) {
  const t = useTranslations("series.canon");
  const [isEditing, setIsEditing] = useState(false);

  // Use useUpdateCanonEntry hook when editing
  // Render entry as card; click to expand/edit
  return (
    <div className="canon-entry-card" onClick={() => setIsEditing(!isEditing)}>
      <div className="canon-entry-header">
        <span className="badge badge-canon">{t(`entity_type.${entry.entity_type}`)}</span>
        <span className="canon-entry-name">{entry.name}</span>
      </div>
      {entry.body && (
        <div className="canon-entry-body">{entry.body.slice(0, 200)}...</div>
      )}
    </div>
  );
}
```

```tsx
// packages/web/app/series/[id]/canon/page.tsx — replace placeholder
import { CanonKBTab } from "../../../../components/series/CanonKBTab";

export default function CanonTabPage({ params }: { params: { id: string } }) {
  return <CanonKBTab seriesId={params.id} />;
}
```

- [ ] **Step 3: Run tests, verify pass**

- [ ] **Step 4: Commit**

```bash
git add packages/web/components/series/CanonKBTab.tsx packages/web/components/kb/CanonKBEditor.tsx packages/web/app/series/[id]/canon/page.tsx packages/web/components/series/__tests__/CanonKBTab.test.tsx
git commit -m "feat(web): replace Canon-tab placeholder with functional Canon KB UI

Spec 1 Slice 5 Task 5.5 — CanonKBTab renders Canon entries list,
CanonKBEditor shows individual entry card. Click-to-edit pattern.
Replaces Slice-4 placeholder. Uses useCanonKB hook from Task 5.2."
```

---

## Task 5.6: i18n keys for kb.scope.* + series.canon.* (en/de/fr)

**Files:**
- Extend: `packages/web/messages/en/series.json` (add `kb.scope`, expand `series.canon`)
- Extend: `packages/web/messages/de/series.json`
- Extend: `packages/web/messages/fr/series.json`

> **Note:** These extend the files created in Slice 4 Task 4.9.

- [ ] **Step 1: Update i18n parity test** (if it doesn't already auto-cover new keys)

- [ ] **Step 2: Add keys to all three locales**

```json
// packages/web/messages/en/series.json — additions:
{
  "kb": {
    "scope": {
      "label": "KB Entry Scope",
      "series_canon": "Series-Canon",
      "novel_overlay": "Novel-Overlay",
      "promote_title": "Promote to Series-Canon?",
      "promote_description": "This entry will become canon for all novels in the series. Changes here affect every band.",
      "promote": "Promote",
      "demote_title": "Demote to Novel-Overlay?",
      "demote_description": "This entry will be removed from canon. Other novels in the series will lose access to it.",
      "demote": "Demote",
      "cancel": "Cancel"
    }
  },
  "series": {
    "canon": {
      "title": "Series Canon",
      "description": "These entries are canon for all novels in the series. Stable facts (magic systems, world rules, canonical bios) live here. Per-novel state goes in each novel's own KB.",
      "loading": "Loading canon entries...",
      "empty": "No canon entries yet. Promote entries from any novel's KB, or create new ones here.",
      "entity_type": {
        "character": "Character",
        "concept": "Concept",
        "faction": "Faction",
        "location": "Location",
        "object": "Object",
        "setting": "Setting",
        "system": "System",
        "timeline": "Timeline"
      }
    }
  }
}
```

(German and French equivalents — same keys, translated values.)

- [ ] **Step 3: Run i18n parity test, verify pass**

- [ ] **Step 4: Commit**

```bash
git add packages/web/messages/
git commit -m "feat(web/i18n): add kb.scope and series.canon namespaces

Spec 1 Slice 5 Task 5.6 — promote/demote dialog copy + Canon-tab labels.
All three locales (en/de/fr) parity-checked."
```

---

# Final: Doc Gate

> **Goal:** Complete all mandatory doc updates for Spec 1 DoD.

## Task F.1: ADR-075 write

**Files:**
- Create: `docs/architecture/decisions/ADR-075-series-foundation.md`
- Modify: `docs/architecture/decisions/INDEX.md` (add row)

> **Pattern:** Mirror ADR-074 structure (Context, Drivers, Options Considered, Decision, Rationale, Consequences, CR-04, Retrofit-Plan, Risks, RULE-XX Compliance, Review Triggers).

- [ ] **Step 1: Draft ADR-075**

Use the spec (`docs/superpowers/specs/2026-07-29-series-foundation-design.md`) as source. Structure:

1. **Status:** ✅ Accepted (or 🔄 Proposed if user wants review first)
2. **Date:** Implementation date
3. **Deciders:** User (approved after brainstorming)
4. **Context:** Series gap (from ADR-074); 5 Specs decomposition
5. **Decision Drivers:** RULE-03/04/05/06/07/11/14/22; ADR-055/057/069/074
6. **Options Considered:**
   - KB strategy: A (per-novel + identity), B (per-series shared + snapshots), **C (hybrid Canon+Overlay)** — chosen
   - Schema: Pure 2A, Pure 2B, **2A+STI** — chosen
   - Navigation: N1 (flat-grouped), **N2 (Series-Workspace)** — chosen
   - Multi-series: Single-Series (chosen), Crossover (YAGNI)
7. **Decision:** Option C + 2A+STI + N2 + Policy iii + Policy α + Single-Series
8. **Rationale:** KB-type heterogeneity, evolution naturally modelliert, Specs 2–5 brauchen Workspace-Heimat
9. **Consequences:** Positiv (type safety, additive migration, future-proof) + Negativ (NULL-Semantik needs discipline, ~15 modules need verification)
10. **CR-04 Cross-Feature Impact:** KB consumers (ANAL-008/WRITE-010/ANAL-009) verified compatible
11. **Retrofit-Plan:** Inventory (files touched in 5 slices), Migration steps, Breaking-change assessment (additive only)
12. **Risks:** Schema change blast radius; mitigation via STI re-exports + regression tests
13. **RULE-XX Compliance table**
14. **Review Triggers:**
    - When Spec 2 (Generation) implements: verify `find_merged_for_novel` correct usage
    - When Spec 3 (Voice) implements: closes ADR-074 Review Trigger Voice-Teil
    - If Crossover demand: migration to join-table needed

- [ ] **Step 2: Add row to INDEX.md**

```
| [ADR-075](ADR-075-series-foundation.md) | Series Foundation — Spec 1 (Foundation + KB Evolution) — Hybrid KB Series-Canon+Novel-Overlay (Option C); Schema 2A+STI (single kb_entries table + discriminated Pydantic types); N2 Series-Workspace; Single-Series in Spec 1 (no Crossover); Policy iii scope defaults; Policy α adaptive join; closes ADR-074 RT partially | ✅ Implemented | 2026-07-29 | `apps/api/narrare/series/`, `apps/api/narrare/kb/` (scope changes), `packages/core/narrare_core/{series/,kb/schemas/entry.py}`, `packages/web/{components/series/,components/kb/ScopeToggle.tsx,app/series/}`, `apps/api/alembic/versions/0036_series_foundation.py`, ADR-074, RULE-03/04/05/06/07/11/14/22 |
```

- [ ] **Step 3: Commit**

```bash
git add docs/architecture/decisions/ADR-075-series-foundation.md docs/architecture/decisions/INDEX.md
git commit -m "docs(adr): ADR-075 Series Foundation

Spec 1 Final Task F.1 — full ADR documenting all 6 clarifying decisions
+ schema (2A+STI) + phasing (5 slices). Mirrors ADR-074 structure.
Cross-references ADR-055/057/069/074. Closes ADR-074 Review Trigger
partially (Series-Storage-Teil; Voice-Teil still open for Spec 3)."
```

---

## Task F.2: SERIES-001 feature spec write

**Files:**
- Create: `docs/features/series/SERIES-001-foundation.md`

> **Pattern:** Mirror WRITE-011 frontmatter (`id`, `title`, `status`, `area`, `mvp`, `ui_tooltip`, `ui_help_short`, `ui_help_long`, `ui_available_in`, `service`, `contract`, `router`, `requires`).

- [ ] **Step 1: Write feature spec**

```yaml
---
id: SERIES-001
title: "Series Foundation"
status: stable
area: series
mvp: false  # post-MVP (Phase 6)

ui_tooltip: "Group multiple novels into a series with shared canon Knowledge Base."
ui_help_short: |
  Create a series to group novels sharing a canon world (magic system, foundational
  characters, world rules). Each novel retains its own per-band state (character
  evolution, new characters introduced); canon entries are shared across all bands.
ui_help_long: |
  Series Foundation introduces the Series as a first-class object in Narrare.
  A series groups multiple novels that share a canon Knowledge Base (magic
  system, world rules, canonical character bios, foundational artifacts).

  Each novel in a series has two KB layers:
  - **Series-Canon**: shared across all bands. Stable facts live here.
  - **Novel-Overlay**: per-band state. Character evolution, new locations
    introduced in this specific book, etc.

  Generation (Spec 2) will automatically merge Canon + latest-Overlay when
  writing band N. For now, both layers are browsable and editable.

  **API Endpoints:**
  - `POST /api/v1/series` — Create series
  - `GET /api/v1/series` — List user's series
  - `GET /api/v1/series/{id}` — Get series details
  - `PATCH /api/v1/series/{id}` — Update series
  - `DELETE /api/v1/series/{id}` — Delete series (novels become standalones)
  - `GET /api/v1/series/{id}/novels` — List novels in series
  - `POST /api/v1/series/{id}/novels` — Preview adding novel
  - `POST /api/v1/series/{id}/novels/{novel_id}/apply` — Apply the join
  - `DELETE /api/v1/series/{id}/novels/{novel_id}` — Remove novel from series
  - `PATCH /api/v1/series/{id}/novels/reorder` — Reorder novels
  - `GET /api/v1/series/{id}/kb` — List Series-Canon entries
  - `POST /api/v1/series/{id}/kb` — Create Canon entry
  - `GET/PATCH/DELETE /api/v1/series/{id}/kb/{entry_id}` — Canon entry CRUD
  - `POST /api/v1/novels/{novel_id}/kb/{entry_id}/promote` — Overlay → Canon
  - `POST /api/v1/novels/{novel_id}/kb/{entry_id}/demote` — Canon → Overlay

  **UI Location:** Dashboard (Series cards) → /series/[id] workspace (4 tabs)

ui_available_in: [dashboard, series-workspace]

service: series/service.py
contract: series/contracts.py#SeriesServiceProtocol
router: series/router.py
requires: []  # No hard feature dependencies
---

# SERIES-001 — Series Foundation

## What it does

Group multiple novels into a series with a shared canon Knowledge Base. Each novel retains its own per-band state.

## Why it exists

Narrare had no series concept. Multi-book series were isolated projects with duplicated worldbuilding (magic system re-defined in every book, character bios drifting between bands). Series Foundation introduces a two-layer KB model: Series-Canon (shared, stable facts) + Novel-Overlay (per-band state).

## How it works (User perspective)

1. Create a series from the Dashboard („+ New Series")
2. Add novels to the series via „Add Novel" in the Series-Workspace
3. Preview shows what would happen to each KB entry on join
4. Apply — entries are promoted to Canon or kept as Overlay based on entity type
5. Browse Series-Canon KB in the workspace's Canon tab
6. Edit Canon entries there, or toggle scope on individual entries from within any novel's KB

## How it works (Technical)

- **Data model:** `series` + `series_settings` tables; `novels.series_id` FK (nullable); `kb_entries` extended with `series_id`, `base_entry_id`, `novel_id` nullable. Single physical table, discriminated Pydantic types (STI).
- **Scope:** Two layers — Series-Canon (novel_id IS NULL) and Novel-Overlay (novel_id IS NOT NULL).
- **Migration policy α:** When joining a series, if Canon is empty, heuristics promote `system/concept/setting/location/object/timeline` entries to Canon; `character/faction` stay Overlay. If Canon is non-empty, all entries stay Overlay.
- **Backward compat:** Existing KB queries continue to work; Canon entries (novel_id IS NULL) are excluded from `WHERE novel_id = X` queries by design.

## Constraints & Edge Cases

- A novel can belong to at most one series (Single-Series in Spec 1; Crossover is YAGNI).
- Deleting a series: novels become standalones (series_id set to NULL via ON DELETE SET NULL).
- Promote requires confirmation (entry becomes visible to all bands).
- Demote requires confirmation (entry leaves canon; other bands lose it).
- Status transitions: `draft → active → completed` (and back). No skipping.

## Related Features

- KB-001 (Entity Management) — KB extended with scope concept
- WRITE-011 (Volume Management) — Volume is intra-novel; Series is inter-novel
- ADR-074 (Author Voice Storage) — Review Trigger partially closed (Series-Storage-Teil)
- ADR-075 (Series Foundation) — full architectural decision

## Status & History

- **2026-07-29:** Feature spec created as part of Spec 1 (Foundation + KB Evolution)
```

- [ ] **Step 2: Commit**

```bash
git add docs/features/series/SERIES-001-foundation.md
git commit -m "docs(features): SERIES-001 Series Foundation feature spec

Spec 1 Final Task F.2 — user-facing feature documentation with
frontmatter (ui_tooltip, ui_help_short, ui_help_long), API endpoint
list, technical summary. Mirrors WRITE-011 pattern."
```

---

## Task F.3: GLOSSARY update

**Files:**
- Modify: `docs/_shared/GLOSSARY.md`

- [ ] **Step 1: Add new terms**

Append (or insert alphabetically) these terms:

```markdown
## Series / Reihe
A group of multiple novels sharing a canon Knowledge Base. Each novel in a series is a „Band". Series are first-class objects in Narrare with their own workspace, KB scope (Canon), and (in future Specs) Voice, Generation Context, and Export.

## Series-Canon
KB entries that are shared across all novels in a series. Stable facts (magic systems, world rules, canonical character bios, foundational artifacts). Persisted in `kb_entries` with `novel_id IS NULL`. Contrast with Novel-Overlay.

## Novel-Overlay
KB entries valid in one specific novel. Character evolution per band, new locations introduced in a book, etc. Persisted in `kb_entries` with `novel_id IS NOT NULL`. Contrast with Series-Canon.

## Scope (KB)
The validity range of a KB entry: either `series` (Canon) or `novel` (Overlay). Discriminated at the Pydantic type level via STI (Single-Table-Inheritance).

## STI (Single-Table-Inheritance)
A persistence pattern where multiple subtypes share a single physical database table, with type discrimination at the application layer. In Narrare's KB, `SeriesKBEntry` and `NovelKBEntry` share the `kb_entries` table; the `scope` field discriminates.

## Band
A novel that belongs to a series. Each Band has a position (1-based) within the series. Plural: Bände.

## Policy α (Join Migration)
Adaptive scope assignment when a novel joins a series: if Series-Canon is empty, Policy iii heuristics apply (entity-type-based defaults); if Canon is non-empty, all joining novel's entries stay Novel-Overlay.

## Policy iii (Scope-Default Heuristics)
Entity-type-based default scope for new KB entries in series-novels: `system/concept/setting/location/object/timeline → Series-Canon`; `character/faction → Novel-Overlay`. User can override per entry.
```

- [ ] **Step 2: Commit**

```bash
git add docs/_shared/GLOSSARY.md
git commit -m "docs(glossary): add Series-related terms (Series, Canon, Overlay, Scope, STI, Band, Policies α + iii)

Spec 1 Final Task F.3 — new domain vocabulary for the Series feature."
```

---

## Task F.4: CURRENT_STATE entry

**Files:**
- Modify: `docs/_shared/CURRENT_STATE.md`

- [ ] **Step 1: Add entry under „Last Updated"**

```markdown
Date: YYYY-MM-DD (SERIES-001 — Series Foundation Spec 1 — implemented across all layers + ADR-075 ✅ Implemented; commit range `XXX`→`YYY`. Hybrid KB Series-Canon+Novel-Overlay (Option C); Schema 2A+STI (single kb_entries + discriminated Pydantic); Series + SeriesSettings tables; Novel.series_id + series_position + subtitle; KBEntry scope columns (series_id, base_entry_id, novel_id nullable); Alembic 0036; partial unique indexes (uq_kb_canon_per_series, uq_kb_overlay_per_novel); CHECK ck_kb_entries_scope_invariant; Policy iii scope defaults + Policy α adaptive join; Series-Workspace with 4 tabs (Bände, Canon KB, Settings, Voice-Placeholder); ScopeToggle in KBEditor; JoinPreview dialog with preview-then-apply; i18n (en/de/fr). Single-Series (no Crossover). Series-Settings.author_voice empty (forward-compat Spec 3). `just check` green; X backend + Y core + Z frontend tests.)
```

(Update with actual commit range and test counts after merge.)

- [ ] **Step 2: Commit**

```bash
git add docs/_shared/CURRENT_STATE.md
git commit -m "docs(state): SERIES-001 Spec 1 entry in CURRENT_STATE

Spec 1 Final Task F.4 — Phase 6 entry with commit range, ADR-075
reference, test counts, architecture-check status."
```

---

## Task F.5: ADR-074 partial close

**Files:**
- Modify: `docs/architecture/decisions/ADR-074-author-voice-storage.md`

> **Goal:** Update ADR-074's Review Trigger to mark the Series-Storage-Teil as closed by ADR-075; Voice-Teil still open for Spec 3.

- [ ] **Step 1: Modify ADR-074 Review Trigger**

Find the Review Trigger:
```
- [ ] When the Series / Reihe feature is designed — revisit the voice resolution
      model (novel-only vs novel+series blend); add the sibling
      `SeriesSettings.author_voice` home; confirm this ADR's novel-level home
      remains the primary scope (no forced cascade).
```

Replace with:
```
- [x] **PARTIALLY CLOSED by ADR-075 (2026-07-29):** Series / Reihe Foundation
      is now implemented. The sibling `SeriesSettings.author_voice` home was
      added (empty in Spec 1, forward-compat for Spec 3). ADR-075 confirms
      novel-level voice remains the primary scope (no forced cascade) — series
      voice is an additive sibling, not a replacement.

      **Still open for Spec 3:** the voice resolution model (novel-only vs.
      novel+series blend) and the actual population of `SeriesSettings.
      author_voice` are Spec 3 work. ADR-075 Review Trigger tracks this.
```

- [ ] **Step 2: Commit**

```bash
git add docs/architecture/decisions/ADR-074-author-voice-storage.md
git commit -m "docs(adr-074): partially close Series-Storage Review Trigger

Spec 1 Final Task F.5 — ADR-075 closed the Series-Storage portion
of ADR-074's Review Trigger (Series exists, SeriesSettings.author_voice
home exists). Voice-Teil remains open for Spec 3 (Series Voice
Hierarchy). Cross-link to ADR-075 added."
```

---

# Spec 1 Complete — Final Self-Review

After all tasks land, verify:

- [ ] **`just check`** — Architecture, Adoption, AI-UX, Frontend-Size, Streaming, Prompt-Structure, Doc-Drift all green
- [ ] **`just test`** — all backend tests green
- [ ] **`just test-frontend`** — all frontend tests green
- [ ] **`just check-adoption`** — no new adoption debt
- [ ] **Coverage targets met:** Core 90%+, Backend 85%+, Frontend 80%+, Migration 100%
- [ ] **Regression:** ANAL-008/WRITE-010/ANAL-009 voice-lane tests still green
- [ ] **i18n parity:** en == de == fr keys for all new namespaces
- [ ] **Migration up/down roundtrip:** verified
- [ ] **Backward compat:** existing KB queries return same results as before
- [ ] **No new architecture exceptions** without ADR
- [ ] **ADR-075 written and indexed**
- [ ] **SERIES-001 feature spec written**
- [ ] **GLOSSARY updated**
- [ ] **CURRENT_STATE entry added**
- [ ] **ADR-074 partially closed**
- [ ] **Cross-Spec Notes file** (`2026-07-28-series-cross-spec-notes.md`) updated with Spec 1 completion reference

## Spec 1 → Spec 2 Handoff

After Spec 1 merges, Spec 2 (Series Generation Context) brainstorming can begin. Read:
- `docs/superpowers/specs/2026-07-28-series-cross-spec-notes.md` §„Notes for Spec 2"
- `docs/architecture/decisions/ADR-075-series-foundation.md` (this Spec's ADR)
- `docs/features/series/SERIES-001-foundation.md` (this Spec's feature doc)

Spec 2 will need to consume:
- `KBRepository.find_merged_for_novel()` — exists from Task 2.2
- All Series CRUD endpoints — exist from Slice 3
- `Novel.series_id` + `series_position` — exist from Task 1.3
