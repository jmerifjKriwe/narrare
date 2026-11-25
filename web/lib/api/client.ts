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
/** One task's effective tier (the settings page's task face reads it):
 *  `kind` names the serving adapter — `fake` is the local driver, `audit`
 *  an audit-only key with no serving tier at all (`assignable: false`). */
export type TaskEffective = components["schemas"]["TaskEffectiveRead"];
/** The instance's driver kind as one word (the offline card's truth):
 *  `fake` while the local fake adapter serves every assignable task,
 *  `configured` once any provider adapter answers. */
export type Driver = components["schemas"]["DriverRead"];
/** One saved provider endpoint as every read shows it: the mask
 *  (`sk-…` plus the last four characters), never the key. */
export type Provider = components["schemas"]["ProviderRead"];
/** The provider create's one answer: the full key rides exactly once,
 *  `null` when nothing was stored (a local endpoint without one). */
export type ProviderCreated = components["schemas"]["ProviderCreated"];
/** One saved model as every read shows it: its provider named, no key
 *  anywhere, the `in_catalog`/`last_error_code` marks read-only facts. */
export type Model = components["schemas"]["ModelRead"];
/** One provider preset as the create form reads it: the endpoint facts,
 *  the vendor's catalog model ids and the snapshot's honesty date. */
export type Preset = components["schemas"]["PresetRead"];
/** One stored task assignment: the model and the output-profile choice. */
export type Assignment = components["schemas"]["AssignmentRead"];
/** What one model connection test found: it ran, and it either answered
 *  or named why. */
export type ModelTestResult = components["schemas"]["ModelTestResult"];
export type Entity = components["schemas"]["EntityRead"];
/** The create-by-hand POST body (W9): the entity's fields and the relation
 *  lines to place in the same transaction. The schema's defaults type
 *  `content` as required; the dialog always sends it. */
export type EntityCreate = components["schemas"]["EntityCreate"];
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
/** The assistant interview (W9): the session with its transcript and draft,
 *  a list row (no proposal), the door's create body and one turn's readback.
 *  The graph page's panel is the only surface in cut 1; chat owns the wire. */
export type AssistantSession = components["schemas"]["SessionDetail"];
export type AssistantSessionRead = components["schemas"]["SessionRead"];
export type AssistantSessionSummary = components["schemas"]["SessionSummary"];
export type AssistantSessionCreate = components["schemas"]["SessionCreate"];
export type AssistantTurnRead = components["schemas"]["TurnRead"];
export type AssistantTurnCreate = components["schemas"]["TurnCreate"];
export type AssistantTurnReadback = components["schemas"]["TurnReadback"];
export type Proposal = components["schemas"]["Proposal"];
export type ProposedRelation = components["schemas"]["ProposedRelation"];
/** The prompts surface's reads (W8 Task 12): the catalog row with its two
 *  override tiers' facts, the editor's detail, the provider-free preview
 *  and the saved diff. */
export type PromptSummary = components["schemas"]["PromptSummary"];
export type PromptDetail = components["schemas"]["PromptDetail"];
export type PromptDiff = components["schemas"]["PromptDiff"];
export type PromptPreview = components["schemas"]["PromptPreview"];

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
