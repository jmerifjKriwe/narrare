// Prompt Override types

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
