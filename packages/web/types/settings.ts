// User & project settings, AI provider config, token limits

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
