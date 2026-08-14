/**
 * Narrare API client — barrel file.
 *
 * Re-exports all API functions and types from domain-specific modules.
 * Components should import from here or from "@/lib/api/client" (which re-exports this).
 */

export { adaptiveApi } from "./adaptive";
export { authApi } from "./auth";
export { chatApi } from "./chat";
export {
  clearAccessToken,
  fetchApi,
  fetchApiRaw,
  getAccessToken,
  logoutApi,
  restoreSession,
  setAccessToken,
} from "./core";
export type { DialogueCoachStreamHandlers } from "./dialogue-coach-stream";
export { streamDialogueCoach } from "./dialogue-coach-stream";
export type { DownloadedArtifact } from "./export";
export { exportApi, parseArtifactToken } from "./export";
export type {
  ContextMeta,
  ExtendLength,
  ExtendRequest,
  ExtendStreamEvent,
  GenerateRequest,
  GenerationChunk,
  GenerationMode,
  RewriteAlternative,
  RewriteConfig,
  RewriteMode,
  RewriteRequest,
  SessionResponse,
} from "./generation";
export {
  generationApi,
  parseAlternatives,
  streamExtend,
  streamGeneration,
  streamRewrite,
  WritingSessionSocket,
  writingApi,
} from "./generation";
export { chaptersApi, novelsApi, volumesApi } from "./novels";
export { promptsApi, streamPromptLiveTest, templatesApi } from "./prompts";
export { seriesApi } from "./series";
export type { AvailableModelsResponse, ModelRefreshResponse } from "./settings";
export { aiSettingsApi, settingsApi, tokenLimitsApi } from "./settings";
export { setupApi } from "./setup";
export { tonesApi } from "./tones";
