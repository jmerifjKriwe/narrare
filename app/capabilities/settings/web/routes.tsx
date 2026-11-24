import { queryOptions } from "@tanstack/react-query";
import { createRoute, redirect } from "@tanstack/react-router";
import { lazy } from "react";

import { client } from "@shell/lib/api/client";
import { queryClient } from "@shell/lib/query";
import { rootRoute } from "@shell/routes/__root";

// React.lazy keeps the face out of the shell's bundle: it loads as its own
// chunk when the route opens, and the shell root's Suspense boundary covers
// the gap.
const SettingsPage = lazy(async () => {
  const page = await import("./SettingsPage");
  return { default: page.SettingsPage };
});
const AiRulesPage = lazy(async () => {
  const page = await import("./ai-rules/AiRulesPage");
  return { default: page.AiRulesPage };
});

/**
 * The setup gate the settings surface shares with the shelf, the workspace,
 * the knowledge and the planning pages: an unconfigured instance is handed
 * to `/setup` before the page mounts. The check is the public status endpoint
 * asked directly — a capability never imports another (rule 1), so the
 * coordination is the cache key (`["setup", "status"]`, the same entry
 * setup's write invalidates), not an import. `staleTime: Infinity` keeps a
 * remount on the cached answer; a fresh load asks anew. A non-ok answer
 * throws to the root's error screen.
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

/**
 * The Allgemein surface (W7 Task 3) — the settings capability's first
 * addressable page, global by the capability's own facts (`path: /settings`,
* `nav: false` — a control in the shell, not a destination): parented at the
 * shell root beside the app root, never under a book. The chrome stays; the
 * gear door in the rail and the user-block menu's Einstellungen row are the
 * drafted doors onto it.
 */
const settingsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/settings",
  beforeLoad: async () => {
    const complete = await queryClient.ensureQueryData(setupStatusQueryOptions);
    if (!complete) throw redirect({ to: "/setup" });
  },
  component: SettingsPage,
});

/**
 * The AI-Regeln surface (W8 Task 9) — the hub's second page at
 * `/settings/ai-regeln`, the same global facts and the same setup gate as
 * the Allgemein route: a child shape beside it under the shell root, never
 * under a book.
 */
const aiRulesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/settings/ai-regeln",
  beforeLoad: async () => {
    const complete = await queryClient.ensureQueryData(setupStatusQueryOptions);
    if (!complete) throw redirect({ to: "/setup" });
  },
  component: AiRulesPage,
});

// The capability route contract: every route this capability mounts under
// the shell root, as a const tuple. The route consts stand on their own
// on purpose: a contextual type here degrades createRoute's inference to
// `any` paths, and with it the router's checked `to=` props.
export const routes = [settingsRoute, aiRulesRoute] as const;
