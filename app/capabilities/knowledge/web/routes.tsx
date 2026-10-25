import { createRoute, type AnyRoute } from "@tanstack/react-router";
import { lazy } from "react";

import { rootRoute } from "@shell/routes/__root";

// React.lazy keeps the page out of the shell's bundle: the capability loads
// as its own chunk, and the shell root's Suspense boundary covers the gap.
const KnowledgePage = lazy(async () => {
  const page = await import("./KnowledgePage");
  return { default: page.KnowledgePage };
});

const KnowledgeDock = lazy(async () => {
  const panel = await import("./dock");
  return { default: panel.KnowledgeDock };
});

const knowledgeRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/knowledge",
  component: KnowledgePage,
});

// The dock convention: routes for another capability's workspace, created as
// factories — this file never imports the workspace route (capabilities
// never import each other); the generated table (web/lib/generated/routes.ts)
// passes the workspace route in, which is the one place the two sides meet.
// Path "wissen" under /novels/$id mounts the dock beside the editor, and
// the generated dock registry picks the row up from this export alone.
export const dockRoutes = [
  <Parent extends AnyRoute>(parent: Parent) =>
    createRoute({
      getParentRoute: () => parent,
      path: "wissen",
      component: KnowledgeDock,
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
export const routes = [knowledgeRoute] as const;
