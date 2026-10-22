import { createRouter } from "@tanstack/react-router";

import { capabilityRoutes } from "./lib/generated/routes";
import { rootRoute } from "./routes/__root";
import { indexRoute } from "./routes/index";
import { novelRoute } from "./routes/novels.$id";

const routeTree = rootRoute.addChildren([
  // The generated capability route table: every capability that owns a
  // web/routes.tsx mounts through here.
  ...capabilityRoutes,
  // Hand-listed until each capability owns its web/ folder.
  indexRoute,
  novelRoute,
]);

export const router = createRouter({ routeTree });

// Registers the router's route types globally: `to="/novels/$id"` with
// `params` is checked here, not at runtime.
declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
