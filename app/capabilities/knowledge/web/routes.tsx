import { queryOptions } from "@tanstack/react-query";
import { createRoute, redirect, type AnyRoute } from "@tanstack/react-router";
import { lazy } from "react";

import { client } from "@shell/lib/api/client";
import { queryClient } from "@shell/lib/query";
import { rootRoute } from "@shell/routes/__root";

// React.lazy keeps the face out of the shell's bundle: it loads as its
// own chunk when the dock route opens, and the shell root's Suspense
// boundary covers the gap.
const KnowledgeDock = lazy(async () => {
  const panel = await import("./KnowledgeDock");
  return { default: panel.KnowledgeDock };
});
const LoreGraphPage = lazy(async () => {
  const page = await import("./LoreGraphPage");
  return { default: page.LoreGraphPage };
});
const DossiersPage = lazy(async () => {
  const page = await import("./DossiersPage");
  return { default: page.DossiersPage };
});
const SourcesPage = lazy(async () => {
  const page = await import("./SourcesPage");
  return { default: page.SourcesPage };
});

/**
 * The setup gate the graph shares with the shelf and the workspace: an
 * unconfigured instance is handed to `/setup` before the page mounts. The
 * check is the public status endpoint asked directly — a capability never
 * imports another (rule 1), so the coordination is the cache key
 * (`["setup", "status"]`, the same entry setup's write invalidates), not an
 * import. `staleTime: Infinity` keeps a remount on the cached answer; a fresh
 * load asks anew. A non-ok answer throws to the root's error screen.
 */
const setupStatusQueryOptions = queryOptions({
  queryKey: ["setup", "status"],
  staleTime: Infinity,
  queryFn: async () => {
    const { data, response } = await client.GET("/api/setup/status");
    if (!response.ok || !data) {
      throw new Error(`setup status unavailable: ${response.status}`);
    }
    return data.complete;
  },
});

// The dock convention (scripts/generate_capabilities.py): routes for
// another capability's workspace, created as factories — this file never
// imports the workspace route (capabilities never import each other,
// rule 1); the generated table (web/lib/generated/routes.ts) passes the
// workspace route in, which is the one place the two sides meet. Path
// "knowledge" under /novels/$novelId mounts the face in the workspace's
// dock column (the InspectorDock renders the registry's tabs and the
// Outlet), and the generated dock registry picks the row up from this
// export alone — zero generator changes.
export const dockRoutes = [
  <Parent extends AnyRoute>(parent: Parent) =>
    createRoute({
      getParentRoute: () => parent,
      path: "knowledge",
      component: KnowledgeDock,
    }),
] as const;

/**
 * The lore graph (W5 Task 3) — the capability's first own addressable
 * surface. The dock already owns `/novels/$novelId/knowledge` (Tasks 1/2),
 * so the graph mounts one step deeper, at `/novels/$novelId/knowledge/graph`,
 * as a book-scoped page under the shell root — the setup capability's
 * addressable-step precedent (a full path literal parented at the root, not
 * a child of the workspace component, which renders its own columns and has
 * no page-level Outlet). The chrome resolves the active book from the
 * route's own `novelId` param on any book-scoped surface (chrome.ts), so the
 * graph wears the book's breadcrumb exactly as the workspace does.
 *
 * The `entity` search param is the dock chip's deep link: a chip navigates
 * here with its row's id, and the page opens that entity's dossier on arrival.
 */
const graphRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/novels/$novelId/knowledge/graph",
  beforeLoad: async () => {
    const complete = await queryClient.ensureQueryData(setupStatusQueryOptions);
    if (!complete) throw redirect({ to: "/setup" });
  },
  validateSearch: (search: Record<string, unknown>): { entity?: string; interview?: string } => {
    const next: { entity?: string; interview?: string } = {};
    const entity = search.entity;
    if (typeof entity === "string" && entity !== "") next.entity = entity;
    const interview = search.interview;
    if (typeof interview === "string" && interview !== "") next.interview = interview;
    return next;
  },
  component: LoreGraphPage,
});

/**
 * The dossiers page (W5 Task 5) — the graph's sibling browsing surface, the
 * same mount shape: a book-scoped page parented at the shell root (the dock
 * owns the bare `/novels/$novelId/knowledge` path), the same setup gate, and
 * the same `entity` search param so the two surfaces hand the selection to
 * each other through their subbar doors.
 */
const dossiersRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/novels/$novelId/knowledge/dossiers",
  beforeLoad: async () => {
    const complete = await queryClient.ensureQueryData(setupStatusQueryOptions);
    if (!complete) throw redirect({ to: "/setup" });
  },
  validateSearch: (search: Record<string, unknown>): { entity?: string } => {
    const entity = search.entity;
    return typeof entity === "string" && entity !== "" ? { entity } : {};
  },
  component: DossiersPage,
});

/**
 * The sources archive (W5 Task 6) — the graph's and the dossiers' third
 * sibling, the same mount shape: a book-scoped page parented at the shell
 * root (the dock owns the bare `/novels/$novelId/knowledge` path), the same
 * setup gate. No `entity` search param: the documents are the library's,
 * never an entity's (D8), so no selection travels the sibling doors into
 * this surface.
 */
const sourcesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/novels/$novelId/knowledge/sources",
  beforeLoad: async () => {
    const complete = await queryClient.ensureQueryData(setupStatusQueryOptions);
    if (!complete) throw redirect({ to: "/setup" });
  },
  component: SourcesPage,
});

// The capability route contract: every route this capability mounts
// under the shell root, as a const tuple. The dossiers (W5 Task 5) are the
// graph's sibling surface — the same book-scoped, root-parented shape, the
// same setup gate and `entity` deep-link param; the sources archive (W5
// Task 6) is the third sibling, library-scoped, no entity param.
//
// The route consts stand on their own on purpose: a contextual type here
// degrades createRoute's inference to `any` paths, and with it the
// router's checked `to=` props.
export const routes = [graphRoute, dossiersRoute, sourcesRoute] as const;
