import { createRoute, type AnyRoute } from "@tanstack/react-router";
import { lazy } from "react";

import { rootRoute } from "@shell/routes/__root";

// React.lazy keeps each surface out of the shell's bundle: the capability
// loads as its own chunk, and the shell root's Suspense boundary covers the gap.
const ChatPage = lazy(async () => {
  const page = await import("./ChatPage");
  return { default: page.ChatPage };
});

const ChatDock = lazy(async () => {
  const panel = await import("./dock");
  return { default: panel.ChatDock };
});

const chatRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/chat",
  component: ChatPage,
});

// The dock convention: routes for another capability's workspace, created as
// factories — this file never imports the workspace route (capabilities never
// import each other); the generated table (web/lib/generated/routes.ts) passes
// the workspace route in, which is the one place the two sides meet. Path
// "chat" under /novels/$id mounts the panel beside the editor.
export const dockRoutes = [
  <Parent extends AnyRoute>(parent: Parent) =>
    createRoute({
      getParentRoute: () => parent,
      path: "chat",
      component: ChatDock,
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
export const routes = [chatRoute] as const;
