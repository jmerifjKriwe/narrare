import { createRoute, type AnyRoute } from "@tanstack/react-router";
import { lazy } from "react";

// React.lazy keeps the dock out of the shell's bundle: the capability loads
// as its own chunk, and the shell root's Suspense boundary covers the gap.
const SceneDock = lazy(async () => {
  const panel = await import("./SceneDock");
  return { default: panel.SceneDock };
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
// nothing. Planning owns no page of its own — the dock is its whole web
// surface — so the tuple is empty, and the spread in the generated table
// contributes no route.
//
// The route const stands on its own on purpose: a contextual type here
// (a `Route[]` annotation or satisfies) degrades createRoute's inference to
// `any` paths, and with it the router's checked `to=` props.
export const routes = [] as const;
