import { queryOptions } from "@tanstack/react-query";
import { createRoute, redirect } from "@tanstack/react-router";
import { lazy } from "react";

import { client } from "@shell/lib/api/client";
import { queryClient } from "@shell/lib/query";
import { rootRoute } from "@shell/routes/__root";

// React.lazy keeps the page out of the shell's bundle: it loads as its own
// chunk, and the shell root's Suspense boundary covers the gap.
const ShelfPage = lazy(async () => {
  const page = await import("./ShelfPage");
  return { default: page.ShelfPage };
});

/**
 * The one fact the shelf's door reads: whether this instance has been set
 * up. `GET /api/setup/status` is a public endpoint, so the writing capability
 * asks it directly — a capability never imports another, and setup's own
 * status hook stays its own. The coordination is the cache key, not an
 * import: `["setup", "status"]` is the same key setup's provisioning write
 * invalidates when the instance flips complete, so this gate and setup's
 * inverse gate read one answer. The state flips once per instance, so
 * `staleTime: Infinity` keeps a remount on the cached answer; a fresh page
 * load asks anew (the cache is empty), which is what makes a refresh after
 * setup land on the shelf, never on a remembered redirect. A non-ok answer
 * throws to the root's error screen — never a guessed shelf or welcome.
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

const homeRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  // The `/` gate after the W3 handover: the shelf once the instance is set
  // up, a redirect to setup's welcome (`/setup`) while it is not. The check
  // lives in beforeLoad — the router's load-time redirect mechanism, the same
  // shape setup's inverse gate uses — so an unconfigured instance is handed
  // to `/setup` before the shelf ever mounts. The ask suspends the route
  // while its answer is in flight (the root boundary holds the gap, nothing
  // invented), and every fresh load asks anew.
  beforeLoad: async () => {
    const complete = await queryClient.ensureQueryData(setupStatusQueryOptions);
    if (!complete) throw redirect({ to: "/setup" });
  },
  component: ShelfPage,
});

// The capability route contract: every route this capability mounts under the
// shell root, as a const tuple. The generated table (web/lib/generated/
// routes.ts) imports this array; a capability without this file mounts
// nothing.
//
// The route consts stand on their own on purpose: a contextual type here
// (a `Route[]` annotation or satisfies) degrades createRoute's inference to
// `any` paths, and with it the router's checked `to=` props.
export const routes = [homeRoute] as const;
