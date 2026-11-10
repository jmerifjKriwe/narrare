import { createRoute, type AnyRoute } from "@tanstack/react-router";
import { lazy } from "react";

import { rootRoute } from "@shell/routes/__root";

// React.lazy keeps the page and the dock out of the shell's bundle: the
// capability loads as its own chunk, and the shell root's Suspense boundary
// covers the gap.
const PlanningPage = lazy(async () => {
  const page = await import("./PlanningPage");
  return { default: page.PlanningPage };
});

const SceneDock = lazy(async () => {
  const panel = await import("./SceneDock");
  return { default: panel.SceneDock };
});

// The landing canvas: the novel's timeline as a full page under the Planen
// rail entry. The novel arrives as `?novel=` (the graph's sibling: tolerant
// in, absent means the picker); the dock's routes below parent at the
// workspace instead, so the canvas and the dock never share an address.
const planningRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/planning",
  component: PlanningPage,
  validateSearch: (search: { novel?: unknown }): { novel?: string } => {
    return {
      ...(typeof search.novel === "string" && search.novel !== ""
        ? { novel: search.novel }
        : {}),
    };
  },
});

// The dock convention: routes for another capability's workspace, created as
// factories — this file never imports the workspace route (capabilities
// never import each other); the generated table (web/lib/generated/routes.ts)
// passes the workspace route in, which is the one place the two sides meet.
// Path "planning" under /novels/$id mounts the scene plans beside the
// editor, and the generated dock registry picks the row up from this export
// alone. The dock carries no search of its own: the chapter it edits is the
// workspace's own param, read from the parent route — the editor's chapter,
// never a second address.
export const dockRoutes = [
  <Parent extends AnyRoute>(parent: Parent) =>
    createRoute({
      getParentRoute: () => parent,
      path: "planning",
      component: SceneDock,
    }),
] as const;

// The capability route contract: every route this capability mounts under the
// shell root, as a const tuple. The generated table (web/lib/generated/
// routes.ts) imports this array; a capability without this file mounts
// nothing.
//
// The route const stands on its own on purpose: a contextual type here
// (a `Route[]` annotation or satisfies) degrades createRoute's inference to
// `any` paths, and with it the router's checked `to=` props.
export const routes = [planningRoute] as const;
