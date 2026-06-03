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
