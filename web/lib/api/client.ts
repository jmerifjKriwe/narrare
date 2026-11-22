import createClient from "openapi-fetch";

import type { components, paths } from "./schema";

/** One origin: FastAPI serves the built SPA, and the relative base keeps /api there. */
export const client = createClient<paths>({ baseUrl: "" });

export type Novel = components["schemas"]["NovelRead"];
export type NovelCreate = components["schemas"]["NovelCreate"];
/** The novel PATCH body (W4 Task 19): only the carried fields change, a
 *  carried null clears — the server's `model_fields_set` contract. */
export type NovelChanges = components["schemas"]["NovelUpdate"];
export type Series = components["schemas"]["SeriesRead"];
export type Activity = components["schemas"]["ActivityRead"];
export type ActivityPoint = components["schemas"]["ActivityPoint"];
export type SetupResult = components["schemas"]["SetupResult"];
export type Chapter = components["schemas"]["ChapterRead"];
/** Writing's prose scene (W4 §5). The generated schema prefixes both
 *  capabilities' SceneRead — writing's and planning's — because the bare
 *  name collides (#890's decision: the prefixed generated names stand, the
 *  UI types against the clean alias, the same pattern every row here uses).
 *  Planning's ScenePlan read keeps its prefixed name until its own wave
 *  types against it. */
export type Scene = components["schemas"]["app__capabilities__writing__schemas__SceneRead"];
export type Storyboard = components["schemas"]["StoryboardRead"];
export type StoryboardStage = components["schemas"]["StoryboardStageRead"];
/** One chapter's storyboard row (W6): the effective stage, where the stage
 *  came from, and how closely the writing follows the plan. */
export type StoryboardChapter = components["schemas"]["StoryboardChapterRead"];
/** The structure change's two-step answer (W6): the preview and the confirm
 *  agree chapter by chapter — `mapping` carries every move. */
export type RemapRead = components["schemas"]["RemapRead"];
/** One scene of the aggregate PUT (W6): ids the client mints for new
 *  scenes, and the writer-facing fields — the timestamps stay the
 *  server's own. */
export type SceneUpsert = components["schemas"]["SceneUpsert"];
export type KnowledgeDocument = components["schemas"]["DocumentRead"];
export type Hit = components["schemas"]["SearchHit"];
export type Job = components["schemas"]["JobRead"];
/** One task's effective tier (the settings page's driver card reads it):
 *  `kind` names the serving adapter — `fake` is the local driver, `audit`
 *  an audit-only key with no serving tier at all (`assignable: false`). */
export type TaskEffective = components["schemas"]["TaskEffectiveRead"];
export type Entity = components["schemas"]["EntityRead"];
export type Suggestion = components["schemas"]["SuggestionRead"];
export type Relation = components["schemas"]["RelationRead"];
export type Accept = components["schemas"]["AcceptRead"];
export type Finding = components["schemas"]["FindingRead"];
/** Planning's timeline event row (W6): the free-text date, the manual
 *  position (null = unordered, listed last) and the free-text character
 *  names — no KB linkage in this slice. */
export type TimelineEvent = components["schemas"]["TimelineEventRead"];
export type TimelineEventCreate = components["schemas"]["TimelineEventCreate"];
/** The PUT body's generated shape: the server honors sent-vs-absent
 *  (`model_fields_set`), but the serialized schema types the defaulted
 *  fields as required — the client's all-optional mirror
 *  (`TimelineEventChanges` in query.ts) is the honest edit surface. */
export type TimelineEventUpdate = components["schemas"]["TimelineEventUpdate"];
/** Planning's scene aggregate (W6): one chapter's scenes in position
 *  order, with the chapter's stamp as the version a drill-in compares. */
export type SceneAggregate = components["schemas"]["SceneAggregateRead"];

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
