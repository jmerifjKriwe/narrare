# Series Foundation — Slice 4: Frontend Dashboard + Workspace

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development or superpowers:executing-plans. Steps use `- [ ]` for tracking.
>
> **Part of:** Series Foundation plan set — see `2026-07-29-series-foundation-index.md` for execution order.
> **Predecessor:** Slice 3 (`2026-07-29-series-foundation-slice-3-crud-join.md`) — backend endpoints must be live.
> **Successor:** Slice 5 (KB Scope UI) — can run in parallel with parts of Slice 4 once types/hooks land.
> **Spec source:** `docs/superpowers/specs/2026-07-29-series-foundation-design.md`

**Goal:** Implement frontend for N2 navigation: Dashboard with mixed Series+Standalone cards, Series-Workspace with 4 tabs (Bände, Canon KB, Settings, Voice placeholder), join flow UI with preview-then-apply, full i18n (en/de/fr).

**Architecture:** Next.js 16 App Router with segment-based tab routing (`/series/[id]/canon` etc.). TanStack Query for server state, Zustand for UI state. Reuse `lib/motion-variants.ts`. Reuse existing `useKB.ts` pattern for `useCanonKB.ts`.

**Global constraints:** See main plan §Global Constraints. Plus: i18n parity en/de/fr simultaneous; reduced-motion respected via global `MotionProvider`; no English fallback when de/fr exists.

---

## Task 4.1: TS types + API client

**Files:**
- Create: `packages/web/types/series.ts`
- Create: `packages/web/lib/api/series.ts`
- Test: `packages/web/types/__tests__/series.test.ts`, `packages/web/lib/api/__tests__/series.test.ts`

**Interfaces:**
- Consumes: Backend endpoints from Slice 3
- Produces: `Series`, `SeriesSummary`, `SeriesCreate`, `SeriesUpdate`, `JoinPreview`, `JoinResult`, `JoinEntryTreatment`, `SeriesSettings`, `KBScope` types; API client functions `seriesApi.{list,get,create,update,delete,previewJoin,applyJoin,...}` — used by all hooks in Tasks 4.2-4.4

- [ ] **Step 1: Write failing test**

```typescript
// packages/web/types/__tests__/series.test.ts
import { describe, it, expect } from "vitest";
import type { Series, SeriesSummary, JoinPreview } from "../series";

describe("Series type", () => {
  it("accepts a valid Series object", () => {
    const s: Series = {
      id: "uuid-1", user_id: "user-1", title: "The Expanse",
      subtitle: null, description: null, genre: "sci-fi",
      writing_language: "en", status: "draft",
      planned_novel_count: 9, novel_count: 0,
    };
    expect(s.title).toBe("The Expanse");
  });
});

// packages/web/lib/api/__tests__/series.test.ts
import { describe, it, expect, vi } from "vitest";
import { seriesApi } from "../series";

describe("seriesApi.list", () => {
  it("calls GET /api/v1/series", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => [],
    });
    global.fetch = mockFetch as any;
    await seriesApi.list();
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/series"),
      expect.anything(),
    );
  });
});
```

- [ ] **Step 2: Run, verify fail**

```bash
cd packages/web && pnpm vitest run types/__tests__/series.test.ts lib/api/__tests__/series.test.ts
```
Expected: FAIL — modules don't exist.

- [ ] **Step 3: Implement types**

```typescript
// packages/web/types/series.ts
export type SeriesStatus = "draft" | "active" | "completed";
export type KBScope = "series" | "novel";

export interface Series {
  id: string;
  user_id: string;
  title: string;
  subtitle: string | null;
  description: string | null;
  genre: string | null;
  writing_language: string | null;
  status: SeriesStatus;
  planned_novel_count: number | null;
  novel_count: number;
}

export interface SeriesSummary {
  id: string;
  title: string;
  subtitle: string | null;
  status: SeriesStatus;
  novel_count: number;
}

export interface SeriesCreate {
  title: string;
  subtitle?: string;
  description?: string;
  genre?: string;
  writing_language?: string;
  status?: SeriesStatus;
  planned_novel_count?: number;
}

export interface SeriesUpdate {
  title?: string;
  subtitle?: string;
  description?: string;
  genre?: string;
  writing_language?: string;
  status?: SeriesStatus;
  planned_novel_count?: number;
}

export interface SeriesSettings {
  series_id: string;
  author_voice: Record<string, unknown> | null;
}

export interface JoinEntryTreatment {
  entry_id: string;
  slug: string;
  entity_type: string;
  current_scope: "novel";
  target_scope: "series" | "novel";
  reason: string;
}

export interface JoinPreview {
  series_id: string;
  novel_id: string;
  canon_empty: boolean;
  treatments: JoinEntryTreatment[];
}

export interface JoinResult {
  series_id: string;
  novel_id: string;
  position: number;
  promoted_to_canon: number;
  kept_as_overlay: number;
}
```

- [ ] **Step 4: Implement API client**

```typescript
// packages/web/lib/api/series.ts
import type {
  Series, SeriesSummary, SeriesCreate, SeriesUpdate,
  SeriesSettings, JoinPreview, JoinResult,
} from "../../types/series";

const BASE = "/api/v1/series";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    ...init,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? `HTTP ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const seriesApi = {
  list: () => request<SeriesSummary[]>(BASE),
  get: (id: string) => request<Series>(`${BASE}/${id}`),
  create: (body: SeriesCreate) =>
    request<Series>(BASE, { method: "POST", body: JSON.stringify(body) }),
  update: (id: string, body: SeriesUpdate) =>
    request<Series>(`${BASE}/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  delete: (id: string) =>
    request<void>(`${BASE}/${id}`, { method: "DELETE" }),

  listNovels: (seriesId: string) =>
    request<unknown[]>(`${BASE}/${seriesId}/novels`),

  previewJoin: (seriesId: string, novelId: string) =>
    request<JoinPreview>(`${BASE}/${seriesId}/novels`, {
      method: "POST",
      body: JSON.stringify({ novel_id: novelId }),
    }),

  applyJoin: (seriesId: string, novelId: string, position: number) =>
    request<JoinResult>(`${BASE}/${seriesId}/novels/${novelId}/apply`, {
      method: "POST",
      body: JSON.stringify({ position }),
    }),

  removeNovel: (seriesId: string, novelId: string) =>
    request<void>(`${BASE}/${seriesId}/novels/${novelId}`, { method: "DELETE" }),

  reorderNovels: (seriesId: string, novelIds: string[]) =>
    request<void>(`${BASE}/${seriesId}/novels/reorder`, {
      method: "PATCH",
      body: JSON.stringify({ novel_ids: novelIds }),
    }),

  getSettings: (seriesId: string) =>
    request<SeriesSettings>(`${BASE}/${seriesId}/settings`),
  updateSettings: (seriesId: string, body: Partial<SeriesSettings>) =>
    request<SeriesSettings>(`${BASE}/${seriesId}/settings`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
};
```

- [ ] **Step 5: Run tests, verify pass**

```bash
cd packages/web && pnpm vitest run types/__tests__/series.test.ts lib/api/__tests__/series.test.ts
```

- [ ] **Step 6: Commit**

```bash
git add packages/web/types/series.ts packages/web/lib/api/series.ts packages/web/types/__tests__/series.test.ts packages/web/lib/api/__tests__/series.test.ts
git commit -m "feat(web): add Series types + API client

Spec 1 Slice 4 Task 4.1 — TS types mirror Core Pydantic schemas.
seriesApi client covers all endpoints from Slice 3 (CRUD, novels,
join preview/apply, settings). Used by hooks in Tasks 4.2-4.4."
```

---

## Task 4.2: useSeries + useSeriesList hooks

**Files:**
- Create: `packages/web/hooks/useSeries.ts`
- Test: `packages/web/hooks/__tests__/useSeries.test.ts`

**Interfaces:**
- Consumes: `seriesApi` (Task 4.1)
- Produces: `useSeriesList()`, `useSeries(id)`, `useCreateSeries()`, `useUpdateSeries()`, `useDeleteSeries()`

- [ ] **Step 1: Write failing test**

```typescript
// packages/web/hooks/__tests__/useSeries.test.ts
import { describe, it, expect, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useSeriesList } from "../useSeries";

describe("useSeriesList", () => {
  it("fetches series list from API", async () => {
    const mockList = vi.fn().mockResolvedValue([
      { id: "1", title: "Test", subtitle: null, status: "draft", novel_count: 0 },
    ]);
    vi.mock("../../lib/api/series", () => ({ seriesApi: { list: mockList } }));

    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={new QueryClient()}>
        {children}
      </QueryClientProvider>
    );
    const { result } = renderHook(() => useSeriesList(), { wrapper });
    await waitFor(() => expect(result.current.data).toBeDefined());
    expect(result.current.data).toHaveLength(1);
    expect(result.current.data[0].title).toBe("Test");
  });
});
```

- [ ] **Step 2: Implement hooks**

```typescript
// packages/web/hooks/useSeries.ts
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { seriesApi } from "../lib/api/series";
import type { SeriesCreate, SeriesUpdate } from "../types/series";

const QK = {
  list: ["series"] as const,
  detail: (id: string) => ["series", id] as const,
};

export function useSeriesList() {
  return useQuery({
    queryKey: QK.list,
    queryFn: () => seriesApi.list(),
  });
}

export function useSeries(id: string) {
  return useQuery({
    queryKey: QK.detail(id),
    queryFn: () => seriesApi.get(id),
    enabled: !!id,
  });
}

export function useCreateSeries() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: SeriesCreate) => seriesApi.create(body),
    onSuccess: () => qc.invalidateQueries({ queryKey: QK.list }),
  });
}

export function useUpdateSeries(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: SeriesUpdate) => seriesApi.update(id, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: QK.detail(id) });
      qc.invalidateQueries({ queryKey: QK.list });
    },
  });
}

export function useDeleteSeries() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => seriesApi.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: QK.list }),
  });
}
```

- [ ] **Step 3: Run tests, verify pass**

- [ ] **Step 4: Commit**

```bash
git add packages/web/hooks/useSeries.ts packages/web/hooks/__tests__/useSeries.test.ts
git commit -m "feat(web/hooks): add useSeries, useSeriesList, useCreate/Update/Delete

Spec 1 Slice 4 Task 4.2 — TanStack Query hooks for Series CRUD.
Invalidates list query on mutations. Standard Narrare pattern."
```

---

## Task 4.3: useNovelSeries + useSeriesJoin hooks

**Files:**
- Create: `packages/web/hooks/useNovelSeries.ts`
- Create: `packages/web/hooks/useSeriesJoin.ts`
- Test: corresponding test files

- [ ] **Step 1: Write failing tests** (similar pattern to Task 4.2)

```typescript
// packages/web/hooks/__tests__/useNovelSeries.test.ts
import { describe, it, expect, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useNovelSeries } from "../useNovelSeries";

describe("useNovelSeries", () => {
  it("returns null when novel has no series", async () => {
    vi.mock("../../lib/api/novels", () => ({
      novelsApi: { get: vi.fn().mockResolvedValue({ series_id: null }) },
    }));
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={new QueryClient()}>
        {children}
      </QueryClientProvider>
    );
    const { result } = renderHook(() => useNovelSeries("novel-1"), { wrapper });
    await waitFor(() => expect(result.current.data !== undefined).toBe(true));
    expect(result.current.data).toBeNull();
  });
});
```

- [ ] **Step 2: Implement hooks**

```typescript
// packages/web/hooks/useNovelSeries.ts
import { useQuery } from "@tanstack/react-query";
import { novelsApi } from "../lib/api/novels";  // existing
import { seriesApi } from "../lib/api/series";

/**
 * Returns the Series a novel belongs to, or null if standalone.
 * Used by: ScopeToggle (Task 5.3), SeriesCard, BändeList.
 */
export function useNovelSeries(novelId: string | undefined) {
  return useQuery({
    queryKey: ["novel-series", novelId],
    queryFn: async () => {
      if (!novelId) return null;
      const novel = await novelsApi.get(novelId);
      if (!novel.series_id) return null;
      return seriesApi.get(novel.series_id);
    },
    enabled: !!novelId,
  });
}
```

```typescript
// packages/web/hooks/useSeriesJoin.ts
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { seriesApi } from "../lib/api/series";

export function useJoinPreview(seriesId: string) {
  return useMutation({
    mutationFn: (novelId: string) => seriesApi.previewJoin(seriesId, novelId),
  });
}

export function useApplyJoin(seriesId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ novelId, position }: { novelId: string; position: number }) =>
      seriesApi.applyJoin(seriesId, novelId, position),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["series", seriesId] });
      qc.invalidateQueries({ queryKey: ["series"] });
    },
  });
}
```

- [ ] **Step 3: Run tests, verify pass**

- [ ] **Step 4: Commit**

```bash
git add packages/web/hooks/useNovelSeries.ts packages/web/hooks/useSeriesJoin.ts packages/web/hooks/__tests__/
git commit -m "feat(web/hooks): add useNovelSeries + useSeriesJoin (preview + apply)

Spec 1 Slice 4 Task 4.3 — useNovelSeries returns Series|null for a novel
(used by ScopeToggle, SeriesCard). useSeriesJoin has two mutations:
previewJoin (returns JoinPreview without applying), applyJoin (executes).
Standard TanStack Query invalidation."
```

---

## Task 4.4: SeriesCard component

**Files:**
- Create: `packages/web/components/dashboard/SeriesCard.tsx`
- Test: `packages/web/components/dashboard/__tests__/SeriesCard.test.tsx`

- [ ] **Step 1: Write failing test**

```typescript
// packages/web/components/dashboard/__tests__/SeriesCard.test.tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { SeriesCard } from "../SeriesCard";
import type { SeriesSummary } from "../../../types/series";

describe("SeriesCard", () => {
  it("renders title and novel count", () => {
    const series: SeriesSummary = {
      id: "s1", title: "The Expanse", subtitle: null,
      status: "active", novel_count: 4,
    };
    render(<SeriesCard series={series} onClick={() => {}} />);
    expect(screen.getByText("The Expanse")).toBeInTheDocument();
    expect(screen.getByText(/4 Bände/)).toBeInTheDocument();  // or i18n key
  });

  it("renders status badge", () => {
    const series: SeriesSummary = {
      id: "s1", title: "X", subtitle: null,
      status: "completed", novel_count: 3,
    };
    render(<SeriesCard series={series} onClick={() => {}} />);
    expect(screen.getByText("completed")).toBeInTheDocument();
  });

  it("calls onClick when clicked", async () => {
    const onClick = vi.fn();
    const series: SeriesSummary = {
      id: "s1", title: "X", subtitle: null,
      status: "draft", novel_count: 0,
    };
    render(<SeriesCard series={series} onClick={onClick} />);
    await userEvent.click(screen.getByText("X"));
    expect(onClick).toHaveBeenCalledWith("s1");
  });
});
```

- [ ] **Step 2: Implement component**

```tsx
// packages/web/components/dashboard/SeriesCard.tsx
"use client";
import { motion } from "motion/react";
import { useTranslations } from "next-intl";
import type { SeriesSummary } from "../../types/series";
import { overlayVariants } from "../../lib/motion-variants";

interface Props {
  series: SeriesSummary;
  onClick: (id: string) => void;
}

export function SeriesCard({ series, onClick }: Props) {
  const t = useTranslations("dashboard.series");

  return (
    <motion.button
      variants={overlayVariants}
      type="button"
      onClick={() => onClick(series.id)}
      className="series-card"
      style={{
        border: "1px solid var(--series-border, #bfdbfe)",
        background: "var(--series-bg, #eff6ff)",
      }}
    >
      <div className="series-card-cover" aria-hidden />
      <div className="series-card-title">{series.title}</div>
      {series.subtitle && (
        <div className="series-card-subtitle">{series.subtitle}</div>
      )}
      <div className="series-card-meta">
        <span className="badge badge-status">{t(`status.${series.status}`)}</span>
        <span>{t("novel_count", { count: series.novel_count })}</span>
      </div>
    </motion.button>
  );
}
```

- [ ] **Step 3: Run tests, verify pass**

- [ ] **Step 4: Commit**

```bash
git add packages/web/components/dashboard/SeriesCard.tsx packages/web/components/dashboard/__tests__/SeriesCard.test.tsx
git commit -m "feat(web): add SeriesCard component for dashboard N2

Spec 1 Slice 4 Task 4.4 — clickable card showing series title, subtitle,
status badge, novel count. Uses motion overlayVariants. i18n via
dashboard.series namespace. onClick callback for navigation."
```

---

## Task 4.5: Dashboard modification (mixed Series + Standalone cards)

**Files:**
- Modify: `packages/web/app/page.tsx` (or equivalent Dashboard component)
- Test: extend existing Dashboard tests

> **Note:** The exact file depends on existing structure. The Dashboard should now fetch both novels AND series (parallel queries), render them in a mixed grid.

- [ ] **Step 1: Write failing test (Dashboard renders both card types)**

```typescript
// packages/web/app/__tests__/page.test.tsx (or extend existing)
import { describe, it, expect, vi } from "vitest";

describe("Dashboard", () => {
  it("renders SeriesCard and NovelCard in mixed grid", async () => {
    // Mock both APIs
    vi.mock("../../lib/api/series", () => ({
      seriesApi: { list: vi.fn().mockResolvedValue([
        { id: "s1", title: "The Expanse", subtitle: null, status: "active", novel_count: 4 },
      ])},
    }));
    vi.mock("../../lib/api/novels", () => ({
      novelsApi: { list: vi.fn().mockResolvedValue([
        { id: "n1", title: "Standalone Book", /* ... */ },
      ])},
    }));

    const { renderPage } = await import("../test-utils");
    renderPage();

    expect(await screen.findByText("The Expanse")).toBeInTheDocument();
    expect(await screen.findByText("Standalone Book")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Modify Dashboard to fetch + render mixed**

```tsx
// packages/web/app/page.tsx — modifications
"use client";
import { useQuery } from "@tanstack/react-query";
import { seriesApi } from "../lib/api/series";
import { novelsApi } from "../lib/api/novels";
import { SeriesCard } from "../components/dashboard/SeriesCard";
import { NovelCard } from "../components/dashboard/NovelCard"; // existing
import { useRouter } from "next/navigation";

export default function DashboardPage() {
  const router = useRouter();
  const { data: seriesList } = useQuery({
    queryKey: ["series"],
    queryFn: () => seriesApi.list(),
  });
  const { data: novels } = useQuery({
    queryKey: ["novels"],
    queryFn: () => novelsApi.list(),
  });

  return (
    <div className="dashboard">
      <header>
        <h1>{/* i18n: dashboard.title */}</h1>
        <NewSeriesButton />
      </header>
      <div className="grid">
        {seriesList?.map((s) => (
          <SeriesCard key={s.id} series={s} onClick={(id) => router.push(`/series/${id}`)} />
        ))}
        {novels?.filter(n => !n.series_id).map((n) => (
          <NovelCard key={n.id} novel={n} onClick={(id) => router.push(`/novels/${id}`)} />
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Run tests, verify pass**

- [ ] **Step 4: Commit**

```bash
git add packages/web/app/page.tsx packages/web/app/__tests__/
git commit -m "feat(web/dashboard): N2 mixed Series+Standalone cards

Spec 1 Slice 4 Task 4.5 — Dashboard now fetches both series and novels
in parallel, renders mixed grid. Standalone novels (series_id=null) appear
as before; series appear as SeriesCards routing to /series/[id]. Click
on NovelCard opens /novels/[id] (existing)."
```

---

## Task 4.6: SeriesWorkspace main + tab routing

**Files:**
- Create: `packages/web/app/series/[id]/layout.tsx` (shared layout with tab nav)
- Create: `packages/web/app/series/[id]/page.tsx` (Bände tab, default)
- Create: `packages/web/app/series/[id]/canon/page.tsx` (placeholder for Slice 5)
- Create: `packages/web/app/series/[id]/settings/page.tsx`
- Create: `packages/web/app/series/[id]/voice/page.tsx` (placeholder)
- Create: `packages/web/components/series/SeriesWorkspace.tsx`
- Test: `packages/web/components/series/__tests__/SeriesWorkspace.test.tsx`

- [ ] **Step 1: Write failing test**

```typescript
// packages/web/components/series/__tests__/SeriesWorkspace.test.tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";

describe("SeriesWorkspace", () => {
  it("renders hero with series title", async () => {
    const series = { id: "s1", title: "The Expanse", status: "active", /* ... */ };
    render(<SeriesWorkspace series={series}>{/* tabs */}</SeriesWorkspace>);
    expect(screen.getByText("The Expanse")).toBeInTheDocument();
  });

  it("renders four tabs with correct labels", () => {
    const series = { id: "s1", title: "X", status: "draft" };
    render(<SeriesWorkspace series={series}>{null}</SeriesWorkspace>);
    expect(screen.getByRole("tab", { name: /Bände/ })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /Canon/ })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /Settings/ })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /Voice/ })).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Implement layout + workspace**

```tsx
// packages/web/app/series/[id]/layout.tsx
import { SeriesWorkspace } from "../../../components/series/SeriesWorkspace";
import { seriesApi } from "../../../lib/api/series";

export default async function SeriesLayout({
  params, children,
}: { params: { id: string }; children: React.ReactNode }) {
  const series = await seriesApi.get(params.id);
  return <SeriesWorkspace series={series}>{children}</SeriesWorkspace>;
}
```

```tsx
// packages/web/components/series/SeriesWorkspace.tsx
"use client";
import { motion } from "motion/react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTranslations } from "next-intl";
import type { Series } from "../../types/series";
import { SeriesHero } from "./SeriesHero";
import { PhaseCrossfade } from "../../components/shared/PhaseCrossfade";

interface Props {
  series: Series;
  children: React.ReactNode;
}

export function SeriesWorkspace({ series, children }: Props) {
  const t = useTranslations("series.workspace");
  const pathname = usePathname();
  const basePath = `/series/${series.id}`;

  const tabs = [
    { id: "bände", href: basePath, label: t("tabs.bände") },
    { id: "canon", href: `${basePath}/canon`, label: t("tabs.canon") },
    { id: "settings", href: `${basePath}/settings`, label: t("tabs.settings") },
    { id: "voice", href: `${basePath}/voice`, label: t("tabs.voice"), disabled: true },
  ];

  return (
    <div className="series-workspace">
      <SeriesHero series={series} />
      <nav role="tablist" className="series-tabs">
        {tabs.map((tab) => {
          const active = pathname === tab.href ||
            (tab.id !== "bände" && pathname.startsWith(tab.href));
          return (
            <Link
              key={tab.id}
              href={tab.href}
              role="tab"
              aria-selected={active}
              aria-disabled={tab.disabled}
              data-active={active}
              className={`tab ${active ? "tab-active" : ""} ${tab.disabled ? "tab-disabled" : ""}`}
            >
              {tab.label}
              {tab.id === "voice" && (
                <span className="tab-coming-soon">({t("coming_in_spec_3")})</span>
              )}
            </Link>
          );
        })}
      </nav>
      <PhaseCrossfade mode="wait">
        <motion.div key={pathname} className="series-tab-content">
          {children}
        </motion.div>
      </PhaseCrossfade>
    </div>
  );
}
```

```tsx
// packages/web/app/series/[id]/page.tsx — Bände tab (default)
import { BändeList } from "../../../components/series/BändeList";

export default async function BändeTabPage({ params }: { params: { id: string } }) {
  return <BändeList seriesId={params.id} />;
}
```

```tsx
// packages/web/app/series/[id]/canon/page.tsx — placeholder for Slice 5
import { useTranslations } from "next-intl";
export default function CanonTabPage() {
  const t = useTranslations("series.canon");
  return <div>{t("coming_in_slice_5")}</div>;
}
```

```tsx
// packages/web/app/series/[id]/settings/page.tsx
import { SeriesSettings } from "../../../components/series/SeriesSettings";
export default function SettingsPage({ params }: { params: { id: string } }) {
  return <SeriesSettings seriesId={params.id} />;
}
```

```tsx
// packages/web/app/series/[id]/voice/page.tsx — placeholder for Spec 3
import { useTranslations } from "next-intl";
export default function VoiceTabPage() {
  const t = useTranslations("series.voice");
  return (
    <div className="voice-placeholder">
      <h2>{t("title")}</h2>
      <p>{t("coming_in_spec_3")}</p>
    </div>
  );
}
```

- [ ] **Step 3: Run tests, verify pass**

- [ ] **Step 4: Commit**

```bash
git add packages/web/app/series/ packages/web/components/series/SeriesWorkspace.tsx packages/web/components/series/__tests__/
git commit -m "feat(web/series): add SeriesWorkspace with 4 tab routing

Spec 1 Slice 4 Task 4.6 — Next.js layout + segment-based tab routing
(/series/[id], /canon, /settings, /voice). Voice tab disabled placeholder
(Spec 3 fills). PhaseCrossfade between tabs. Reuses motion variants."
```

---

## Task 4.7: SeriesHero + BändeList + SeriesSettings components

**Files:**
- Create: `packages/web/components/series/SeriesHero.tsx`
- Create: `packages/web/components/series/BändeList.tsx`
- Create: `packages/web/components/series/SeriesSettings.tsx`
- Test: corresponding tests

> **Note:** These are 3 components but all relatively simple. Implementer can split into 3 commits if preferred; bundled here for plan brevity. Each has its own test file.

- [ ] **Step 1: Write tests + implement each component**

```tsx
// packages/web/components/series/SeriesHero.tsx
"use client";
import { useTranslations } from "next-intl";
import type { Series } from "../../types/series";

export function SeriesHero({ series }: { series: Series }) {
  const t = useTranslations("series.workspace");
  return (
    <header className="series-hero">
      <div className="series-hero-badges">
        <span className="badge badge-series">📜 {t("badge_series")}</span>
        <span className="badge badge-status">{t(`status.${series.status}`)}</span>
      </div>
      <h1>{series.title}</h1>
      {series.subtitle && <p className="series-hero-subtitle">{series.subtitle}</p>}
      {series.description && <p className="series-hero-description">{series.description}</p>}
      <div className="series-hero-meta">
        {series.genre && <span><strong>{t("genre")}:</strong> {series.genre}</span>}
        {series.planned_novel_count && (
          <span><strong>{t("planned")}:</strong> {series.planned_novel_count}</span>
        )}
      </div>
    </header>
  );
}
```

```tsx
// packages/web/components/series/BändeList.tsx
"use client";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { seriesApi } from "../../lib/api/series";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { JoinPreviewDialog } from "./JoinPreviewDialog";

export function BändeList({ seriesId }: { seriesId: string }) {
  const t = useTranslations("series.bände");
  const qc = useQueryClient();
  const { data: novels } = useQuery({
    queryKey: ["series", seriesId, "novels"],
    queryFn: () => seriesApi.listNovels(seriesId),
  });
  const reorder = useMutation({
    mutationFn: (novelIds: string[]) => seriesApi.reorderNovels(seriesId, novelIds),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["series", seriesId, "novels"] }),
  });

  return (
    <div className="bände-list">
      <div className="bände-header">
        <h2>{t("title")}</h2>
        <AddNovelButton seriesId={seriesId} />
      </div>
      <ol className="bände-items">
        {novels?.map((novel, index) => (
          <li key={novel.id} className="bande-row">
            <span className="position-pill">{index + 1}</span>
            <Link href={`/novels/${novel.id}`} className="bande-title">
              {novel.title}
            </Link>
            <div className="bande-meta">
              <span className="badge">{novel.status}</span>
            </div>
            <BändeReorderButtons
              index={index}
              total={novels.length}
              onMove={(newIndex) => {
                const ids = [...novels.map((n) => n.id)];
                const [moved] = ids.splice(index, 1);
                ids.splice(newIndex, 0, moved);
                reorder.mutate(ids);
              }}
            />
          </li>
        ))}
      </ol>
    </div>
  );
}
```

```tsx
// packages/web/components/series/SeriesSettings.tsx
"use client";
import { useSeries } from "../../hooks/useSeries";
import { useUpdateSeries } from "../../hooks/useSeries";
import { useTranslations } from "next-intl";
// Standard form: title, subtitle, description, genre, writing_language,
// status (with transition enforcement shown in UI), planned_novel_count
// Implementer: use existing form patterns from novels settings.
// Settings includes a SeriesSettings subsection for author_voice
// (disabled in Spec 1, shown as "coming in Spec 3" placeholder).
```

- [ ] **Step 2: Implement + test each component**

(Follow TDD pattern: test → fail → impl → pass → commit. Three commits if preferred.)

- [ ] **Step 3: Commit (can be one commit or three)**

```bash
git add packages/web/components/series/
git commit -m "feat(web/series): add Hero, BändeList, Settings components

Spec 1 Slice 4 Task 4.7 — SeriesHero renders title/status/meta,
BändeList shows novels with position pills + reorder buttons,
SeriesSettings provides form for series metadata. Voice settings
section disabled in Spec 1 (Spec 3 fills)."
```

---

## Task 4.8: JoinPreviewDialog component

**Files:**
- Create: `packages/web/components/series/JoinPreviewDialog.tsx`
- Test: `packages/web/components/series/__tests__/JoinPreviewDialog.test.tsx`

> **Critical UX:** This dialog shows what would happen before apply. User sees the per-entry treatment list and confirms before changes are made.

- [ ] **Step 1: Write failing test**

```typescript
// packages/web/components/series/__tests__/JoinPreviewDialog.test.tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { JoinPreviewDialog } from "../JoinPreviewDialog";
import type { JoinPreview } from "../../../types/series";

describe("JoinPreviewDialog", () => {
  it("renders treatment list with reasons", () => {
    const preview: JoinPreview = {
      series_id: "s1", novel_id: "n1", canon_empty: true,
      treatments: [
        { entry_id: "e1", slug: "magic", entity_type: "system",
          current_scope: "novel", target_scope: "series",
          reason: "Entity type 'system' defaults to Canon" },
        { entry_id: "e2", slug: "harry", entity_type: "character",
          current_scope: "novel", target_scope: "novel",
          reason: "Entity type 'character' defaults to Novel-Overlay" },
      ],
    };
    render(
      <JoinPreviewDialog
        preview={preview}
        onApply={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    expect(screen.getByText("magic")).toBeInTheDocument();
    expect(screen.getByText(/defaults to Canon/)).toBeInTheDocument();
    expect(screen.getByText("harry")).toBeInTheDocument();
    expect(screen.getByText(/defaults to Novel-Overlay/)).toBeInTheDocument();
  });

  it("calls onApply when confirm button clicked", async () => {
    const onApply = vi.fn();
    const preview = { /* ... */ };
    render(<JoinPreviewDialog preview={preview} onApply={onApply} onCancel={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: /apply/i }));
    expect(onApply).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Implement dialog**

```tsx
// packages/web/components/series/JoinPreviewDialog.tsx
"use client";
import { useTranslations } from "next-intl";
import type { JoinPreview } from "../../types/series";
import { ConfirmDialog } from "../shared/ConfirmDialog";

interface Props {
  preview: JoinPreview;
  onApply: () => void;
  onCancel: () => void;
}

export function JoinPreviewDialog({ preview, onApply, onCancel }: Props) {
  const t = useTranslations("series.join");

  return (
    <ConfirmDialog
      title={t("preview_title")}
      description={
        preview.canon_empty
          ? t("canon_empty_explanation")
          : t("canon_nonempty_explanation")
      }
      confirmLabel={t("apply")}
      cancelLabel={t("cancel")}
      onConfirm={onApply}
      onCancel={onCancel}
    >
      <ul className="treatment-list">
        {preview.treatments.map((tr) => (
          <li key={tr.entry_id} className={`treatment treatment-${tr.target_scope}`}>
            <span className="treatment-slug">{tr.slug}</span>
            <span className="treatment-type">({tr.entity_type})</span>
            <span className="treatment-arrow">→</span>
            <span className={`treatment-target target-${tr.target_scope}`}>
              {t(`scope.${tr.target_scope}`)}
            </span>
            <span className="treatment-reason">{tr.reason}</span>
          </li>
        ))}
      </ul>
    </ConfirmDialog>
  );
}
```

- [ ] **Step 3: Run tests, verify pass**

- [ ] **Step 4: Commit**

```bash
git add packages/web/components/series/JoinPreviewDialog.tsx packages/web/components/series/__tests__/JoinPreviewDialog.test.tsx
git commit -m "feat(web/series): add JoinPreviewDialog (Policy α preview UI)

Spec 1 Slice 4 Task 4.8 — shows per-entry treatment list with reasons
before apply. User sees which entries become Canon vs stay Overlay,
plus Policy α explanation (canon empty vs non-empty). Confirms via
existing ConfirmDialog pattern."
```

---

## Task 4.9: i18n keys (en/de/fr) for Slice 4

**Files:**
- Create or extend: `packages/web/messages/en/series.json`
- Create or extend: `packages/web/messages/de/series.json`
- Create or extend: `packages/web/messages/fr/series.json`

> **Constraint:** All three locales must be updated simultaneously. No English fallback when de/fr exists.

- [ ] **Step 1: Write i18n parity test**

```typescript
// packages/web/messages/__tests__/i18n-parity.test.ts
import { describe, it, expect } from "vitest";
import en from "../en/series.json";
import de from "../de/series.json";
import fr from "../fr/series.json";

function flatten(obj: object, prefix = ""): string[] {
  return Object.entries(obj).flatMap(([k, v]) =>
    typeof v === "object" && v !== null ? flatten(v, `${prefix}${k}.`) : [`${prefix}${k}`],
  );
}

describe("Series i18n parity", () => {
  it("all three locales have the same keys", () => {
    const enKeys = new Set(flatten(en));
    const deKeys = new Set(flatten(de));
    const frKeys = new Set(flatten(fr));
    expect(deKeys).toEqual(enKeys);
    expect(frKeys).toEqual(enKeys);
  });
});
```

- [ ] **Step 2: Implement all three locale files**

```json
// packages/web/messages/en/series.json
{
  "dashboard": {
    "series": {
      "novel_count": "{count, plural, one {# novel} other {# novels}}",
      "status": {
        "draft": "Draft",
        "active": "Active",
        "completed": "Completed"
      },
      "new_series": "New Series"
    }
  },
  "series": {
    "workspace": {
      "badge_series": "Series",
      "status": {
        "draft": "Draft",
        "active": "Active",
        "completed": "Completed"
      },
      "genre": "Genre",
      "planned": "Planned novels",
      "tabs": {
        "bände": "Novels",
        "canon": "Series Canon",
        "settings": "Settings",
        "voice": "Voice"
      },
      "coming_in_spec_3": "coming in Spec 3"
    },
    "bände": {
      "title": "Novels in this Series",
      "add_novel": "Add Novel to Series",
      "move_up": "Move up",
      "move_down": "Move down",
      "empty": "No novels in this series yet."
    },
    "settings": {
      "title": "Series Settings",
      "voice_title": "Series Voice",
      "voice_coming_soon": "Series Voice will be available in Spec 3."
    },
    "canon": {
      "coming_in_slice_5": "Series Canon KB is being implemented in Slice 5."
    },
    "voice": {
      "title": "Series Voice",
      "coming_in_spec_3": "Series Voice Hierarchy will be implemented in Spec 3."
    },
    "join": {
      "preview_title": "Add Novel to Series",
      "canon_empty_explanation": "This series has no canon yet. The following entries will be promoted to Series-Canon based on entity-type defaults. You can adjust later.",
      "canon_nonempty_explanation": "This series already has canon. All your novel's entries will remain as Novel-Overlay. You can promote individual entries later.",
      "apply": "Apply",
      "cancel": "Cancel",
      "scope": {
        "series": "Series-Canon",
        "novel": "Novel-Overlay"
      }
    }
  }
}
```

```json
// packages/web/messages/de/series.json — German equivalent
{
  "dashboard": {
    "series": {
      "novel_count": "{count, plural, one {# Roman} other {# Romane}}",
      "status": {
        "draft": "Entwurf",
        "active": "Aktiv",
        "completed": "Abgeschlossen"
      },
      "new_series": "Neue Reihe"
    }
  },
  "series": {
    "workspace": {
      "badge_series": "Reihe",
      "status": {
        "draft": "Entwurf",
        "active": "Aktiv",
        "completed": "Abgeschlossen"
      },
      "genre": "Genre",
      "planned": "Geplante Romane",
      "tabs": {
        "bände": "Romane",
        "canon": "Reihen-Kanon",
        "settings": "Einstellungen",
        "voice": "Voice"
      },
      "coming_in_spec_3": "kommt in Spec 3"
    },
    "bände": {
      "title": "Romane in dieser Reihe",
      "add_novel": "Roman zur Reihe hinzufügen",
      "move_up": "Nach oben",
      "move_down": "Nach unten",
      "empty": "Keine Romane in dieser Reihe."
    },
    "settings": {
      "title": "Reihen-Einstellungen",
      "voice_title": "Reihen-Voice",
      "voice_coming_soon": "Reihen-Voice wird in Spec 3 verfügbar sein."
    },
    "canon": {
      "coming_in_slice_5": "Reihen-Kanon-KB wird in Slice 5 implementiert."
    },
    "voice": {
      "title": "Reihen-Voice",
      "coming_in_spec_3": "Voice-Hierarchie wird in Spec 3 implementiert."
    },
    "join": {
      "preview_title": "Roman zur Reihe hinzufügen",
      "canon_empty_explanation": "Diese Reihe hat noch keinen Kanon. Die folgenden Einträge werden anhand der Entity-Typ-Defaults zu Reihen-Kanon promoted. Später anpassbar.",
      "canon_nonempty_explanation": "Diese Reihe hat bereits Kanon. Alle Einträge deines Romans bleiben als Roman-Overlay. Du kannst einzelne Einträge später promoted.",
      "apply": "Anwenden",
      "cancel": "Abbrechen",
      "scope": {
        "series": "Reihen-Kanon",
        "novel": "Roman-Overlay"
      }
    }
  }
}
```

```json
// packages/web/messages/fr/series.json — French equivalent
{
  "dashboard": {
    "series": {
      "novel_count": "{count, plural, one {# roman} other {# romans}}",
      "status": {
        "draft": "Brouillon",
        "active": "Actif",
        "completed": "Terminé"
      },
      "new_series": "Nouvelle série"
    }
  },
  "series": {
    "workspace": {
      "badge_series": "Série",
      "status": {
        "draft": "Brouillon",
        "active": "Actif",
        "completed": "Terminé"
      },
      "genre": "Genre",
      "planned": "Romans prévus",
      "tabs": {
        "bände": "Romans",
        "canon": "Canon de la série",
        "settings": "Paramètres",
        "voice": "Voix"
      },
      "coming_in_spec_3": "à venir dans Spec 3"
    },
    "bände": {
      "title": "Romans dans cette série",
      "add_novel": "Ajouter un roman à la série",
      "move_up": "Monter",
      "move_down": "Descendre",
      "empty": "Aucun roman dans cette série."
    },
    "settings": {
      "title": "Paramètres de la série",
      "voice_title": "Voix de la série",
      "voice_coming_soon": "La voix de la série sera disponible dans Spec 3."
    },
    "canon": {
      "coming_in_slice_5": "Le Canon de la série sera implémenté dans Slice 5."
    },
    "voice": {
      "title": "Voix de la série",
      "coming_in_spec_3": "La hiérarchie des voix sera implémentée dans Spec 3."
    },
    "join": {
      "preview_title": "Ajouter un roman à la série",
      "canon_empty_explanation": "Cette série n'a pas encore de canon. Les entrées suivantes seront promues au canon de la série selon les valeurs par défaut de type d'entité. Ajustable ultérieurement.",
      "canon_nonempty_explanation": "Cette série a déjà un canon. Toutes les entrées de votre roman resteront comme Novel-Overlay. Vous pouvez promouvoir des entrées individuelles ultérieurement.",
      "apply": "Appliquer",
      "cancel": "Annuler",
      "scope": {
        "series": "Canon de série",
        "novel": "Overlay de roman"
      }
    }
  }
}
```

- [ ] **Step 3: Run i18n parity test**

```bash
cd packages/web && pnpm vitest run messages/__tests__/i18n-parity.test.ts
```

- [ ] **Step 4: Run reduced-motion regression test**

```bash
cd packages/web && pnpm vitest run components/shared/__tests__/MotionProvider.test.tsx
```

- [ ] **Step 5: Commit**

```bash
git add packages/web/messages/
git commit -m "feat(web/i18n): add Series namespaces (en/de/fr) — Slice 4

Spec 1 Slice 4 Task 4.9 — full i18n for dashboard.series, series.workspace,
series.bände, series.settings, series.canon, series.voice, series.join
namespaces. All three locales parity-checked by automated test."
```

---

## Slice 4 Self-Review Checklist

- [ ] All hooks tested (TanStack Query mocks)
- [ ] All components tested (Vitest + Testing Library)
- [ ] i18n parity test passes (en == de == fr keys)
- [ ] Reduced-motion regression test passes
- [ ] `pnpm vitest run` overall — all green
- [ ] `pnpm tsc --noEmit` — no type errors
- [ ] `pnpm lint` — no lint errors
- [ ] `pnpm test:e2e` (if Playwright tests exist for dashboard) — green
- [ ] `just check-ai-ux` — no AI-UX violations (no AI endpoints in this slice, but check)
- [ ] Storybook entries (if applicable)

## Slice 4 → Slice 5 Handoff

After Slice 4 merges, the Series-Workspace exists with all 4 tabs but the Canon tab is a placeholder. Slice 5 fills:
- Canon KB Tab UI (replacing placeholder)
- ScopeToggle component (integrated into existing Novel-scoped KBEditor)
- useCanonKB hook
- useKBScope hook
- Additional i18n keys for `kb.scope.*`
