// Shared TypeScript types for the Narrare frontend

export interface User {
  id: string;
  email: string;
  display_name: string;
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
}

export interface Novel {
  id: string;
  title: string;
  author: string;
  genre: string;
  language: string;
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
  language: string;
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
  position: number;
  created_at: string;
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
  | "dramatic"
  | "humorous"
  | "suspenseful"
  | "contemplative"
  | "romantic"
  | "dark"
  | "adventurous";

export interface ProviderModel {
  id: string;
  name: string;
  context_window: number | null;
  supports_streaming: boolean;
}

export interface DemoProjectInfo {
  id: StarterContent;
  title: string;
  language: string;
  genre: string;
  chapter_count: number;
  character_count: number;
  word_count: number;
  description: string;
}

export interface WizardState {
  // Step 1
  project_name: string;
  language: string;
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
}

// API error shape
export interface ApiError {
  detail: string;
  code?: string;
}

// Save status for editor
export type SaveStatus = "idle" | "saving" | "saved" | "error";
