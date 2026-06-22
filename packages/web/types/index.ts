// Shared TypeScript types for the Narrare frontend
// Barrel file — re-exports all domain types for backward-compatible imports

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
  PromptInfo,
  PromptLiveTestStarted,
  PromptLiveTestStreamEvent,
  PromptPreview,
  PromptPreviewLanguage,
  PromptProvenance,
  PromptResetResult,
  PromptSecurity,
  PromptVariableMetadata,
  UpdateInfo,
} from "./prompts";
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
