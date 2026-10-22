import { createRouter } from "@tanstack/react-router";

import { rootRoute } from "./routes/__root";
import { chatRoute } from "./routes/chat";
import { indexRoute } from "./routes/index";
import { knowledgeRoute } from "./routes/knowledge";
import { novelRoute } from "./routes/novels.$id";
import { setupRoute } from "./routes/setup";

const routeTree = rootRoute.addChildren([
  indexRoute,
  novelRoute,
  knowledgeRoute,
  chatRoute,
  setupRoute,
]);

export const router = createRouter({ routeTree });

// Registers the router's route types globally: `to="/novels/$id"` with
// `params` is checked here, not at runtime.
declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
