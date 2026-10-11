// Shared TypeScript types for the Narrare frontend
// Barrel file — re-exports all domain types for backward-compatible imports

export type {
  AdaptiveContextResponse,
  AdaptiveSettingsResponse,
  AdaptiveSnapshotItem,
  AdaptiveSnapshotsResponse,
  AdaptiveSourceSummary,
  AdaptiveToggleInput,
  AdaptiveWeightsInput,
  AdaptiveWeightsResponse,
} from "./adaptive";
export type {
  ApiError,
  TokenResponse,
  User,
  WsTicket,
} from "./auth";
export type {
  ChatDoneEvent,
  ChatMetaEvent,
} from "./chat";
export type {
  DialogueAlternative,
  DialogueCoachMode,
  DialogueCoachRequest,
  DialogueCoachResponse,
  DialogueCoachStreamEvent,
  DialogueIssue,
} from "./dialogueCoach";
export type {
  Artifact,
  EpubOptions,
  ExportFormat,
  ExportJob,
  ExportJobStatus,
  ExportOptions,
  ExportRequest,
  FormatAvailability,
  MarkdownOptions,
  MirroredMargins,
  PaperSize,
  PdfOptions,
} from "./export";
export type {
  AnalyzeRequest,
  AnalyzeResponse,
  FeedbackAction,
  FeedbackRequest,
  FeedbackResponse,
  FeedbackSourceType,
  PreferenceProfile,
  ResetResponse,
} from "./feedback";
export type {
  Gender,
  GeneratedName,
  NameGenerateRequest,
  NameGenerateResponse,
  NameType,
  SaveStatus,
} from "./generation";
// Project Import (SETUP-003) — RULE-17 mirror of apps/api/narrare/importing/schemas.py
export type {
  ImportCommitAdjustments,
  ImportCommitChapterInfo,
  ImportCommitResponse,
  ImportMergeOperation,
  ImportOpsState,
  ImportPreviewItem,
  ImportPreviewResponse,
  ImportSelection,
  ImportSplitCandidate,
  ImportSplitOperation,
} from "./importing";
export type {
  KBTemplate,
  KBTemplateDetail,
  KBTemplateDiff,
  KBTemplateField,
  KBTemplateFieldGroup,
  KBTemplateInfo,
  KBTemplateMeta,
  KBTemplateSection,
  KBTemplateUpdateInfo,
} from "./kb";
// Scratchpad notes (NOTES-001)
export type {
  Note,
  NoteCreate,
  NoteListParams,
  NoteSearchHit,
  NoteSearchMode,
  NoteSearchRequest,
  NoteSearchResponse,
  NoteTagsResponse,
  NoteTypeKey,
  NoteUpdate,
} from "./notes";
export { NOTE_TYPE_KEYS, noteDisplayTitle } from "./notes";
export type {
  Chapter,
  ChapterSummary,
  CreateVolumeRequest,
  Novel,
  NovelSummary,
  UpdateVolumeRequest,
  Volume,
  VolumeStats,
} from "./novel";
export type {
  ChapterInStoryboard,
  OutlineResponse,
  OutlineUpdateRequest,
  RemapPreviewItem,
  RemapResponse,
  SceneDraftRequest,
  SceneDraftResponse,
  ScenePlan,
  ScenePlanAggregate,
  ScenePlanSaveRequest,
  ScenePresence,
  SceneProposal,
  SceneRef,
  SceneRefineRequest,
  SceneRefineResponse,
  SceneStatus,
  StoryboardResponse,
  StoryboardStageResponse,
  SyncStatus,
  SyncStatusResponse,
} from "./planning";
export type {
  CascadePath,
  DiffResponse,
  LiveTestRequest,
  PreviewRequest,
  PromptDetail,
  PromptDiagnostic,
  PromptDiagnosticKind,
  PromptHistoryClearedResponse,
  PromptHistoryListResponse,
  PromptHistoryScope,
  PromptInfo,
  PromptLiveTestStarted,
  PromptLiveTestStreamEvent,
  PromptPreview,
  PromptPreviewLanguage,
  PromptProvenance,
  PromptResetResult,
  PromptRevision,
  PromptRevisionCompareResponse,
  PromptRevisionRestoredResponse,
  PromptSecurity,
  PromptVariableMetadata,
  UpdateInfo,
} from "./prompts";
export { PROMPT_HISTORY_ACTIVE_TOKEN } from "./prompts";
export type {
  BandSummary,
  BandSummaryOverrideRequest,
  CanonConflict,
  CanonConflictSeverity,
  CanonEntryCreate,
  CanonEntryUpdate,
  JoinEntryTreatment,
  JoinPreview,
  JoinReasonCode,
  JoinResult,
  KBScope,
  NovelKBEntry,
  ScopedKBEntry,
  Series,
  SeriesConsistencyResult,
  SeriesCreate,
  SeriesKBEntry,
  SeriesSettings,
  SeriesSettingsUpdate,
  SeriesStatus,
  SeriesSummary,
  SeriesUpdate,
  SeriesVoice,
  SeriesVoiceAnalysis,
  SeriesVoiceDriftResult,
  SeriesVoiceOverrideRequest,
  SeriesVoiceProfile,
  SeriesVoiceState,
} from "./series";
export type {
  SeriesHistoryPreviewEntry,
  SeriesHistoryPreviewResponse,
} from "./seriesContextPreview";
export type { SeriesDriftSnapshot } from "./seriesDrift";
export type {
  BudgetMode,
  CalibrationMetadata,
  CalibrationStatus,
  ContextTier,
  CreateProviderRequest,
  IntentCategory,
  ModelOverride,
  ProjectAiSettings,
  ProjectSettings,
  SuitabilityIssue,
  SuitabilityMetadata,
  SuitabilitySeverity,
  TokenLimitProfile,
  TokenLimitsCatalog,
  TokenLimitsResponse,
  TokenProfilePreset,
  TokenUsage,
  UpdateProjectAiSettingsRequest,
  UpdateProviderRequest,
  UpdateTokenLimitsRequest,
  UpdateUserAiSettingsRequest,
  UserAiSettings,
  UserProvider,
  UserSettings,
  WritingGoals,
} from "./settings";
export type {
  CreateCustomToneRequest,
  CustomTone,
  UpdateCustomToneRequest,
} from "./tones";
export type {
  AIProvider,
  DemoProjectInfo,
  ModelCatalogProvenance,
  ModelCatalogSource,
  ProviderModel,
  StarterContent,
  StoryStructure,
  StoryTone,
  WizardState,
} from "./wizard";

// ---------------------------------------------------------------------------
// Timeline types (re-exported from dedicated module for convenience)
// ---------------------------------------------------------------------------

export type {
  CharacterRef,
  LocationRef,
  TimelineAnalysis,
  TimelineAnalysisEvent,
  TimelineEvent,
  TimelineEventCreateRequest,
  TimelineEventSource,
  TimelineEventType,
  TimelineEventUpdateRequest,
  TimelineFilters,
} from "./timeline";
