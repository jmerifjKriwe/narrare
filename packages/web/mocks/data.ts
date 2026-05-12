import type {
  Chapter,
  ChapterSummary,
  Novel,
  NovelSummary,
  ProjectSettings,
  TokenResponse,
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
    title: "Test Novel",
    author: "",
    genre: "",
    language: "en",
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
    title: "Test Novel",
    author: "",
    genre: "",
    language: "en",
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
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

export function createWizardState(overrides: Partial<WizardState> = {}): WizardState {
  return {
    project_name: "Test Project",
    language: "en",
    autosave_interval: 30,
    title: "Test Novel",
    author: "Test Author",
    genre: "fantasy",
    logline: "A test logline",
    story_structure: "three_act",
    tone: "dramatic",
    starter: "blank",
    import_path: null,
    provider: "openai",
    api_key: "test-api-key",
    model: "gpt-4o",
    ollama_url: "http://localhost:11434",
    ...overrides,
  };
}
