import { HttpResponse, http } from "msw";

/**
 * Planning defaults (PLAN-001). The generation panel fetches the chapter's
 * scene-plan aggregate on mount, so a default empty-aggregate GET keeps the
 * "all endpoints handled" MSW invariant for suites that render it without
 * caring about scenes. Seeded scenes: override per test via `server.use`.
 */
export const handlers = [
  http.get("*/api/v1/planning/scenes/:novelId/:chapterId", async () =>
    HttpResponse.json({ chapter_id: "", scenes: [], version_updated_at: "" }),
  ),
];
