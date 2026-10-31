import { createRoute, type AnyRoute } from "@tanstack/react-router";
import { lazy } from "react";

// React.lazy keeps the page out of the shell's bundle: the capability loads
// as its own chunk, and the shell root's Suspense boundary covers the gap.
const PromptsPage = lazy(async () => {
  const page = await import("./PromptsPage");
  return { default: page.PromptsPage };
});

// The settings host contract: routes for another capability's settings area,
// created as factories — this file never imports the settings route
// (capabilities never import each other); the generated table (web/lib/
// generated/routes.ts) passes the settings route in, which is the one place
// the two sides meet. Path "prompts" under /settings mounts the page inside
// the area's frame; the registry row (web/lib/generated/settingsPages.ts)
// carries the same path to the hub card and the cluster nav.
export const settingsRoutes = [
  <Parent extends AnyRoute>(parent: Parent) =>
    createRoute({
      getParentRoute: () => parent,
      path: "prompts",
      component: PromptsPage,
    }),
] as const;

// The capability route contract: every route this capability mounts under the
// shell root, as a const tuple. The generated table (web/lib/generated/
// routes.ts) imports this array; a capability without this file mounts
// nothing. This capability mounts nothing at the root: the page lives in the
// settings area, so the tuple is empty and the export stands only for the
// generated import.
export const routes = [] as const;
