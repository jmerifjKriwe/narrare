import createClient from "openapi-fetch";

import type { components, paths } from "./schema";

/** One origin: the Next.js shell forwards /api to the FastAPI process. */
export const client = createClient<paths>({ baseUrl: "" });

export type Novel = components["schemas"]["NovelRead"];
export type NovelCreate = components["schemas"]["NovelCreate"];
export type Chapter = components["schemas"]["ChapterRead"];
export type KnowledgeDocument = components["schemas"]["DocumentRead"];
export type Hit = components["schemas"]["SearchHit"];
export type Job = components["schemas"]["JobRead"];
export type Entity = components["schemas"]["EntityRead"];
export type Suggestion = components["schemas"]["SuggestionRead"];

/**
 * The one failure the UI can name a fix for: the corpus was embedded by a
 * different model than the configured one. The server sends it as a machine-
 * readable detail code; the UI localizes by that code.
 */
export function isModelChange(error: unknown): boolean {
  return (
    (error as { detail?: { code?: string } } | null | undefined)?.detail?.code ===
    "embedding-mismatch"
  );
}
