import type {
  Chapter,
  ChapterSummary,
  GeneratedName,
  NameGenerateResponse,
  Novel,
  NovelSummary,
  ProjectSettings,
  PromptDetail,
  PromptInfo,
  TokenResponse,
  UpdateInfo,
  User,
  UserSettings,
  WizardState,
} from "@/types";

// ---------------------------------------------------------------------------
// Factory functions for test data
// ---------------------------------------------------------------------------

export function createUser(overrides: Partial<User> = {}): User {
  return {
    id: "test-user-id",
    email: "test@example.com",
    display_name: "Test User",
    is_active: true,
    is_verified: true,
    has_providers: false,
    created_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

export function createTokenResponse(overrides: Partial<TokenResponse> = {}): TokenResponse {
  return {
    access_token: "test-access-token",
    refresh_token: "test-refresh-token",
    token_type: "bearer",
    expires_in: 3600,
    ...overrides,
  };
}

export function createNovel(overrides: Partial<Novel> = {}): Novel {
  return {
    id: "test-novel-id",
    series_id: null,
    title: "Test Novel",
    author: "",
    genre: "",
    writing_language: "en",
    tone: "",
    story_structure: "three_act",
    logline: "",
    synopsis: "",
    is_demo: false,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

export function createNovelSummary(overrides: Partial<NovelSummary> = {}): NovelSummary {
  return {
    id: "test-novel-id",
    series_id: null,
    title: "Test Novel",
    author: "",
    genre: "",
    writing_language: "en",
    is_demo: false,
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

export function createChapter(overrides: Partial<Chapter> = {}): Chapter {
  return {
    id: "test-chapter-id",
    novel_id: "test-novel-id",
    volume_id: null,
    title: "Test Chapter",
    content: "",
    summary: "",
    position: 0,
    word_count: 0,
    status: "draft",
    pov_character_id: "",
    timeline_position: "",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

export function createChapterSummary(overrides: Partial<ChapterSummary> = {}): ChapterSummary {
  return {
    id: "test-chapter-id",
    novel_id: "test-novel-id",
    volume_id: null,
    title: "Test Chapter",
    position: 0,
    word_count: 0,
    status: "draft",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

export function createUserSettings(overrides: Partial<UserSettings> = {}): UserSettings {
  return {
    user_id: "test-user-id",
    display_name: "Test User",
    ui_language: "en",
    theme: "system",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

export function createProjectSettings(overrides: Partial<ProjectSettings> = {}): ProjectSettings {
  return {
    novel_id: "test-novel-id",
    autosave_interval: 30,
    default_language: "en",
    ai_provider: "openai",
    ai_model: "gpt-4o",
    model_overrides: "",
    use_series_voice: true,
    // STATS-001: the GET always serializes this (null when unset) — loose on
    // the read side; narrow with parseTargetWords before use.
    writing_goals: null,
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

export function createWizardState(overrides: Partial<WizardState> = {}): WizardState {
  return {
    project_name: "Test Project",
    writing_language: "en",
    autosave_interval: 30,
    title: "Test Novel",
    author: "Test Author",
    genre: "fantasy",
    logline: "A test logline",
    story_structure: "three_act",
    tone: "dramatic",
    starter: "blank",
    provider: "openai",
    api_key: "test-api-key",
    model: "gpt-4o",
    ollama_url: "http://localhost:11434",
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Prompt Override factories
// ---------------------------------------------------------------------------

export function createPromptInfo(overrides: Partial<PromptInfo> = {}): PromptInfo {
  return {
    prompt_id: "write-extend-en",
    name: "Write / Extend",
    category: "writing",
    language: "en",
    source: "bundled",
    has_override: false,
    prompt_version: "1.0.0",
    is_overridden: false,
    ...overrides,
  };
}

export function createPromptDetail(overrides: Partial<PromptDetail> = {}): PromptDetail {
  return {
    prompt_id: "write-extend-en",
    content: "You are a helpful writing assistant.",
    base_content: "You are a helpful writing assistant.",
    source: "bundled",
    is_overridden: false,
    variables: ["text", "language"],
    metadata: { version: "1.0.0" },
    ...overrides,
  };
}

export function createUpdateInfo(overrides: Partial<UpdateInfo> = {}): UpdateInfo {
  return {
    prompt_id: "analyse-sentiment-en",
    override_version: "1.0.0",
    current_bundled_version: "1.1.0",
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Name Generation factories
// ---------------------------------------------------------------------------

export function createGeneratedName(overrides: Partial<GeneratedName> = {}): GeneratedName {
  return {
    name: "Aelindra",
    pronunciation: "AY-lin-dra",
    meaning: "Starlight wanderer",
    type: "character",
    name_style: "fantasy",
    is_duplicate: false,
    confidence: 0.92,
    ...overrides,
  };
}

export function createNameGenerateResponse(
  overrides: Partial<NameGenerateResponse> = {},
): NameGenerateResponse {
  return {
    names: [createGeneratedName()],
    count: 1,
    name_style: "fantasy",
    name_type: "character",
    ...overrides,
  };
}
