import { createRoute, type AnyRoute } from "@tanstack/react-router";
import { lazy } from "react";

// React.lazy keeps the face out of the shell's bundle: it loads as its
// own chunk when the dock route opens, and the shell root's Suspense
// boundary covers the gap.
const KnowledgeDock = lazy(async () => {
  const panel = await import("./KnowledgeDock");
  return { default: panel.KnowledgeDock };
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

// The capability route contract: every route this capability mounts
// under the shell root, as a const tuple. The standalone surfaces (the
// lore graph, the dossiers, the sources archive) land with W5 Tasks
// 3/5/6; until then the capability mounts nothing under its own path —
// the dock is its first surface.
//
// The route consts stand on their own on purpose: a contextual type here
// degrades createRoute's inference to `any` paths, and with it the
// router's checked `to=` props.
export const routes = [] as const;
