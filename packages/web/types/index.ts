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
  OutlineBeat,
  OutlineResponse,
  OutlineUpdateRequest,
  RemapPreviewItem,
  RemapResponse,
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
  SeriesCreate,
  SeriesKBEntry,
  SeriesSettings,
  SeriesSettingsUpdate,
  SeriesStatus,
  SeriesSummary,
  SeriesUpdate,
} from "./series";
export type {
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
