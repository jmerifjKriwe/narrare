import { queryOptions } from "@tanstack/react-query";
import { createRoute, redirect } from "@tanstack/react-router";
import { lazy } from "react";

import { client } from "@shell/lib/api/client";
import { queryClient, refused } from "@shell/lib/query";
import { rootRoute } from "@shell/routes/__root";

// React.lazy keeps the face out of the shell's bundle: it loads as its own
// chunk when the route opens, and the shell root's Suspense boundary covers
// the gap.
const PromptsPage = lazy(async () => {
  const page = await import("./PromptsPage");
  return { default: page.PromptsPage };
});

/**
 * The setup gate the settings area's surfaces share with the shelf, the
 * workspace, the knowledge and the planning pages: an unconfigured instance
 * is handed to `/setup` before the page mounts. The check is the public
 * status endpoint asked directly — a capability never imports another
 * (rule 1), so the coordination is the cache key (`["setup", "status"]`,
 * the same entry setup's write invalidates), not an import.
 * `staleTime: Infinity` keeps a remount on the cached answer; a fresh load
 * asks anew. A non-ok answer throws to the root's error screen.
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
 * The Prompts surface (W8 Task 12) — the settings area's third page at
 * `/settings/prompts` (the hub chrome's third door, mounted in the same
 * commit as the surface behind it). The same global facts and the same
 * setup gate as the Allgemein and AI-Regeln routes: parented at the shell
 * root beside them, never under a book.
 */
const promptsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/settings/prompts",
  beforeLoad: async () => {
    const complete = await queryClient.ensureQueryData(setupStatusQueryOptions);
    if (!complete) throw redirect({ to: "/setup" });
  },
  component: PromptsPage,
});

// The capability route contract: every route this capability mounts under
// the shell root, as a const tuple. The route const stands on its own on
// purpose: a contextual type here degrades createRoute's inference to
// `any` paths, and with it the router's checked `to=` props.
export const routes = [promptsRoute] as const;
