import { createRouter } from "@tanstack/react-router";

import { capabilityRoutes } from "./lib/generated/routes";
import { rootRoute } from "./routes/__root";

const routeTree = rootRoute.addChildren([
  // The generated capability route table: every route the app serves comes
  // from a capability's web/routes.tsx; the shell holds no hand-written
  // list of its own.
  ...capabilityRoutes,
]);

export const router = createRouter({ routeTree });

// Registers the router's route types globally: `to="/novels/$id"` with
// `params` is checked here, not at runtime.
declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
