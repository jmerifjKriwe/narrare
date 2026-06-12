import { handlers as authHandlers } from "./auth";
import { handlers as generationHandlers } from "./generation";
import { handlers as kbHandlers } from "./kb";
import { handlers as kbSessionsHandlers } from "./kb-sessions";
import { handlers as novelsHandlers } from "./novels";
import { handlers as settingsHandlers } from "./settings";
import { handlers as wikiHandlers } from "./wiki";

export const handlers = [
  ...authHandlers,
  ...novelsHandlers,
  ...kbHandlers,
  ...settingsHandlers,
  ...kbSessionsHandlers,
  ...generationHandlers,
  ...wikiHandlers,
];
