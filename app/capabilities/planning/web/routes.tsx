import { queryOptions } from "@tanstack/react-query";
import { createRoute, redirect } from "@tanstack/react-router";
import { lazy } from "react";

import { client } from "@shell/lib/api/client";
import { queryClient, refused } from "@shell/lib/query";
import { rootRoute } from "@shell/routes/__root";

// React.lazy keeps each face out of the shell's bundle: it loads as its
// own chunk when the route opens, and the shell root's Suspense
// boundary covers the gap.
const TimelinePage = lazy(async () => {
  const page = await import("./TimelinePage");
  return { default: page.TimelinePage };
});

const StoryboardPage = lazy(async () => {
  const page = await import("./StoryboardPage");
  return { default: page.StoryboardPage };
});

const CausalityPage = lazy(async () => {
  const page = await import("./CausalityPage");
  return { default: page.CausalityPage };
});

/**
 * The setup gate the planning surfaces share with the shelf, the workspace
 * and the knowledge pages: an unconfigured instance is handed to `/setup`
 * before the page mounts. The check is the public status endpoint asked
 * directly — a capability never imports another (rule 1), so the
 * coordination is the cache key (`["setup", "status"]`, the same entry
 * setup's write invalidates), not an import. `staleTime: Infinity` keeps
 * a remount on the cached answer; a fresh load asks anew. A non-ok
 * answer throws to the root's error screen.
 */
const setupStatusQueryOptions = queryOptions({
  queryKey: ["setup", "status"],
  staleTime: Infinity,
  queryFn: async () => {
    const { data, error, response } = await client.GET("/api/setup/status");
    if (!response.ok) {
      throw refused("setup status unavailable", response, error);
    }
    if (!data) {
      // A 2xx without a body is no refusal: the face's fallback names it.
      throw new Error(`setup status unavailable: ${response.status}`);
    }
    return data.complete;
  },
});

/**
 * The chronology (W6 Task 3) — the planning capability's first addressable
 * surface, a book-scoped page parented at the shell root (the knowledge
 * graph's precedent: a full path literal, not a child of the workspace
 * component, which renders its own columns and has no page-level Outlet).
 * The chrome resolves the active book from the route's own `novelId` param
 * on any book-scoped surface (chrome.ts), so the chronology wears the
 * book's breadcrumb exactly as the workspace does.
 */
const timelineRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/novels/$novelId/planning/timeline",
  beforeLoad: async () => {
    const complete = await queryClient.ensureQueryData(setupStatusQueryOptions);
    if (!complete) throw redirect({ to: "/setup" });
  },
  component: TimelinePage,
});

/**
 * The storyboard's surface (W6 Task 4): the planning capability's second
 * addressable page — the structure switcher over the five real ids, the
 * staged chapter columns, the stage assignment PUT, the remap's two-step
 * contract and the scene drill-in with its stale-version conflict face.
 */
const storyboardRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/novels/$novelId/planning/storyboard",
  beforeLoad: async () => {
    const complete = await queryClient.ensureQueryData(setupStatusQueryOptions);
    if (!complete) throw redirect({ to: "/setup" });
  },
  component: StoryboardPage,
});

/**
 * The causality strip's address (W6 Task 5): the same mount shape as its
 * siblings; the waiting face retired when the surface landed.
 */
const causalityRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/novels/$novelId/planning/causality",
  beforeLoad: async () => {
    const complete = await queryClient.ensureQueryData(setupStatusQueryOptions);
    if (!complete) throw redirect({ to: "/setup" });
  },
  component: CausalityPage,
});

// The capability route contract: every route this capability mounts under
// the shell root, as a const tuple. The route consts stand on their own
// on purpose: a contextual type here degrades createRoute's inference to
// `any` paths, and with it the router's checked `to=` props.
export const routes = [timelineRoute, storyboardRoute, causalityRoute] as const;
