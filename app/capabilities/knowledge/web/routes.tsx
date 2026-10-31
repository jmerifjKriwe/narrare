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
      // The selected entity is URL state, the workspace's chapter param's
      // sibling: a link opens the dock on the entity it names (the palette's
      // deep links ride this contract). Tolerant in, like the parent's own
      // params: accepted as any non-empty string — an id is never a number,
      // so the parser's typing cannot mangle it — and judged against the
      // novel's own rows in the panel, where a dead id degrades to no
      // selection instead of erroring here. Absent is the ordinary dock:
      // nothing selected, and nothing writes that absence back.
      // The param lives on the dock route, not the workspace — only an open
      // dock reads it. Closing the dock does not strip it: a navigation's
      // search is carried whole, and each matched route's validateSearch
      // writes onto it, so a param no writer removed rides along — inert
      // while the dock is unmounted, and the selection restores when the
      // dock opens again. While the dock is open both outputs merge in the
      // URL: the entity and the chapter name different things and never
      // collide.
      validateSearch: (search: { entity?: unknown }): { entity?: string } => {
        return {
          ...(typeof search.entity === "string" && search.entity !== ""
            ? { entity: search.entity }
            : {}),
        };
      },
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
