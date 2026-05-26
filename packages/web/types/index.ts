// Shared TypeScript types for the Narrare frontend

export interface User {
  id: string;
  email: string;
  display_name: string;
  is_active: boolean;
  is_verified: boolean;
  has_providers: boolean;
  created_at: string;
}

export interface Novel {
  id: string;
  title: string;
  author: string;
  genre: string;
  writing_language: string;
  tone: string;
  story_structure: string;
  logline: string;
  synopsis: string;
  is_demo: boolean;
  created_at: string;
  updated_at: string;
}

export interface NovelSummary {
  id: string;
  title: string;
  author: string;
  genre: string;
  writing_language: string;
  is_demo: boolean;
  updated_at: string;
}

export interface Chapter {
  id: string;
  novel_id: string;
  volume_id: string | null;
  title: string;
  content: string;
  summary: string;
  position: number;
  word_count: number;
  status: "draft" | "reviewed" | "final";
  pov_character_id: string;
  timeline_position: string;
  created_at: string;
  updated_at: string;
}

export interface ChapterSummary {
  id: string;
  novel_id: string;
  volume_id: string | null;
  title: string;
  position: number;
  word_count: number;
  status: "draft" | "reviewed" | "final";
  updated_at: string;
}

export interface Volume {
  id: string;
  novel_id: string;
  title: string;
  subtitle: string | null;
  description: string | null;
  word_count_target: number | null;
  is_default: boolean;
  position: number;
  created_at: string;
}

export interface VolumeStats {
  word_count: number;
  chapter_count: number;
  word_count_target: number | null;
  completion_percentage: number | null;
}

export interface CreateVolumeRequest {
  title: string;
  subtitle?: string | null;
  description?: string | null;
  word_count_target?: number | null;
}

export interface UpdateVolumeRequest {
  title?: string | null;
  subtitle?: string | null;
  description?: string | null;
  word_count_target?: number | null;
}

export interface UserSettings {
  user_id: string;
  display_name: string;
  ui_language: string;
  theme: "light" | "dark" | "system";
  updated_at: string;
}

export interface ProjectSettings {
  novel_id: string;
  autosave_interval: number;
  default_language: string;
  ai_provider: string;
  ai_model: string;
  model_overrides: string;
  updated_at: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

// Setup Wizard types
export type AIProvider =
  | "anthropic"
  | "openai"
  | "google"
  | "groq"
  | "ollama"
  | "openrouter"
  | "zai";

export type StarterContent = "blank" | "demo_fantasy" | "demo_scifi" | "demo_german" | "import";

export type StoryStructure =
  | "three_act"
  | "five_act"
  | "heros_journey"
  | "save_the_cat"
  | "seven_point";

export type StoryTone =
  | "balanced"
  | "dramatic"
  | "humorous"
  | "suspenseful"
  | "contemplative"
  | "romantic"
  | "dark"
  | "adventurous"
  | "quiet";

export interface ProviderModel {
  id: string;
  name: string;
  context_window: number | null;
  supports_streaming: boolean;
}

export interface DemoProjectInfo {
  id: StarterContent;
  title: string;
  writing_language: string;
  genre: string;
  chapter_count: number;
  character_count: number;
  word_count: number;
  description: string;
  /** Author name from demo metadata — used to prefill wizard Step 3 */
  author: string;
  /** One-sentence story summary from demo metadata */
  logline: string;
  /** Point of view from demo metadata */
  pov: string;
  /** Tags from demo metadata */
  tags: string[];
}

export interface WizardState {
  // Step 1
  project_name: string;
  writing_language: string;
  autosave_interval: number;
  // Step 2
  title: string;
  author: string;
  genre: string;
  logline: string;
  story_structure: StoryStructure;
  tone: StoryTone;
  // Step 3
  starter: StarterContent;
  import_path: string | null;
  // Step 4
  provider: AIProvider;
  api_key: string;
  model: string;
  ollama_url: string;
  zai_endpoint?: string;
  // Provider skip flag — true when Step 4 was skipped
  skip_provider?: boolean;
}

// API error shape
export interface ApiError {
  detail: string;
  code?: string;
}

// Save status for editor
export type SaveStatus = "idle" | "saving" | "saved" | "error";

// ---------------------------------------------------------------------------
// AI Provider & Settings types
// ---------------------------------------------------------------------------

export interface UserProvider {
  id: string;
  provider_name: string;
  has_api_key: boolean;
  api_key_last4: string;
  base_url: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CreateProviderRequest {
  provider_name: string;
  api_key: string;
  base_url?: string | null;
}

export interface UpdateProviderRequest {
  api_key?: string;
  base_url?: string | null;
  is_active?: boolean;
}

export type IntentCategory =
  | "writing"
  | "analysis"
  | "kb"
  | "planning"
  | "extraction"
  | "chat"
  | "research";

export type TokenLimitProfile = "quick" | "balanced" | "long_texts" | "custom";

export interface ModelOverride {
  provider_id: string;
  model_id: string;
}

/** Tier names for context budget allocation. */
export type ContextTier = "immediate" | "recent" | "kb_referenced" | "kb_suggested" | "pinned";

/** Resolved token limits from all layers (user → project → env → code). */
export interface TokenLimitsResponse {
  output_limit: number;
  token_profile: TokenLimitProfile;
  tier_percentages: Record<ContextTier, number>;
  ws_timeout: number;
  retry_max_attempts: number;
  retry_base_delay: number;
}

/** Partial update for token limit overrides. */
export interface UpdateTokenLimitsRequest {
  output_limit?: number;
  token_profile?: TokenLimitProfile;
  tier_percentages?: Partial<Record<ContextTier, number>>;
  ws_timeout?: number;
  retry_max_attempts?: number;
  retry_base_delay?: number;
}

export interface UserAiSettings {
  user_id: string;
  default_provider_id: string | null;
  default_model: string;
  category_overrides: Record<string, ModelOverride>;
  intent_overrides: Record<string, ModelOverride>;
  updated_at: string;
}

export interface UpdateUserAiSettingsRequest {
  default_provider_id?: string | null;
  default_model?: string;
  category_overrides?: Record<string, ModelOverride>;
  intent_overrides?: Record<string, ModelOverride>;
}

export interface ProjectAiSettings {
  novel_id: string;
  category_overrides: Record<string, ModelOverride>;
  intent_overrides: Record<string, ModelOverride>;
  updated_at: string;
}

export interface UpdateProjectAiSettingsRequest {
  category_overrides?: Record<string, ModelOverride>;
  intent_overrides?: Record<string, ModelOverride>;
}

export interface TokenUsage {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}

// ---------------------------------------------------------------------------
// Prompt Override types
// ---------------------------------------------------------------------------

export interface PromptInfo {
  prompt_id: string;
  name: string;
  category: string;
  language: string;
  source: string;
  has_override: boolean;
  prompt_version: string;
  is_overridden: boolean;
}

export interface PromptDetail {
  prompt_id: string;
  content: string;
  base_content: string;
  source: string;
  is_overridden: boolean;
  variables: string[];
  metadata: Record<string, unknown>;
}

export interface CascadePath {
  level: string;
  path: string;
  exists: boolean;
}

export interface UpdateInfo {
  prompt_id: string;
  override_version: string;
  current_bundled_version: string;
}

export interface DiffResponse {
  prompt_id: string;
  override_content: string;
  bundled_content: string;
}

// ---------------------------------------------------------------------------
// Name Generation types
// ---------------------------------------------------------------------------

export type NameType = "character" | "place" | "organization" | "item";
export type Gender = "male" | "female" | "neutral" | "any";

export interface NameGenerateRequest {
  project_id: string;
  name_type: NameType;
  name_style: string;
  count: number;
  gender: Gender;
  explanation_language: string;
}

export interface GeneratedName {
  name: string;
  pronunciation: string | null;
  meaning: string | null;
  type: string;
  name_style: string;
  is_duplicate: boolean;
  confidence: number;
}

export interface NameGenerateResponse {
  names: GeneratedName[];
  count: number;
  name_style: string;
  name_type: string;
}

// ---------------------------------------------------------------------------
// KB Template types
// ---------------------------------------------------------------------------

export interface KBTemplateField {
  name: string;
  field_type: string;
  required: boolean;
  description: string;
}

export interface KBTemplateSection {
  name: string;
  label_key: string;
  description_key: string;
  order: number;
}

export interface KBTemplateFieldGroup {
  name: string;
  label_key: string;
  description_key: string;
  fields: KBTemplateField[];
  order: number;
}

export interface KBTemplateMeta {
  template_type: string;
  template_version: string;
  schema_version: string;
}

export interface KBTemplate {
  meta: KBTemplateMeta;
  fields: KBTemplateField[];
  field_groups: KBTemplateFieldGroup[];
  sections: KBTemplateSection[];
  body: string;
}

export interface KBTemplateInfo {
  entity_type: string;
  scope: string;
  schema_version: string;
  has_override: boolean;
  has_update: boolean;
}

export interface KBTemplateDetail {
  entity_type: string;
  scope: string;
  content: string;
  base_content: string | null;
  schema_version: string;
  based_on_version: string | null;
  is_overridden: boolean;
}

export interface KBTemplateUpdateInfo {
  entity_type: string;
  override_version: string | null;
  current_bundled_version: string | null;
}

export interface KBTemplateDiff {
  entity_type: string;
  override_content: string;
  bundled_content: string;
}

// ---------------------------------------------------------------------------
// Planning / Storyboard types
// ---------------------------------------------------------------------------

export type SyncStatus = "empty" | "planned" | "on_track" | "deviated" | "completed";

export interface ChapterInStoryboard {
  chapter_id: string;
  title: string;
  word_count: number;
  sync_status: SyncStatus;
  position: number;
}

export interface StoryboardStageResponse {
  stage_id: string;
  stage_name: string;
  chapters: ChapterInStoryboard[];
}

export interface StoryboardResponse {
  structure_type: string;
  stages: StoryboardStageResponse[];
}

export interface SyncStatusResponse {
  chapter_id: string;
  status: SyncStatus;
}

export interface OutlineBeat {
  title: string;
  description: string;
  completed: boolean;
}

export interface OutlineResponse {
  id: string;
  chapter_id: string;
  stage_assignment: string;
  planned_beats: OutlineBeat[];
  outline_notes: string;
  created_at: string;
  updated_at: string;
}

export interface OutlineUpdateRequest {
  stage_assignment?: string;
  planned_beats?: OutlineBeat[];
  outline_notes?: string;
}

export interface RemapPreviewItem {
  chapter_id: string;
  chapter_title: string;
  old_stage: string;
  new_stage: string;
  ai_confidence?: number;
  ai_suggested_stage?: string;
}

export interface RemapResponse {
  new_structure: string;
  remapped: RemapPreviewItem[];
  ai_confidence?: number;
  confirmed: boolean;
}

// ---------------------------------------------------------------------------
// Custom Tone types
// ---------------------------------------------------------------------------

export interface CustomTone {
  id: string;
  name: string;
  instructions: string;
}

export interface CreateCustomToneRequest {
  name: string;
  instructions: string;
}

export interface UpdateCustomToneRequest {
  name?: string;
  instructions?: string;
}

// ---------------------------------------------------------------------------
// Memory / Feedback / Learning types
// ---------------------------------------------------------------------------

export type FeedbackAction = "accept" | "reject" | "modify";

export interface FeedbackRequest {
  action: FeedbackAction;
  suggestion_id: string;
  intent: string;
  suggestion_text: string;
  modification?: string | null;
  rating?: number | null;
  context?: Record<string, unknown> | null;
  project_id: string;
  chapter_id?: string | null;
  genre?: string | null;
  mode?: string | null;
}

export interface FeedbackResponse {
  id: string;
  action: string;
  created_at: string;
}

export interface PreferenceProfile {
  user_id: string;
  project_id: string;
  event_count: number;
  confidence: number;
  style: Record<string, string>;
  content: Record<string, string>;
  constraints: string[];
  last_updated: string;
}

export interface ResetResponse {
  message: string;
  deleted_count: number;
}

export interface AnalyzeRequest {
  project_id: string;
}

export interface AnalyzeResponse {
  id: string;
  user_id: string;
  project_id: string;
  confidence: number;
  summary: string;
  style_patterns: string[];
  content_patterns: string[];
  avoidance_patterns: string[];
  event_count_at_analysis: number;
  created_at: string;
  updated_at: string;
}
