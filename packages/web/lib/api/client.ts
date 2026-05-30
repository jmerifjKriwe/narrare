/**
 * Narrare API client.
 *
 * Typed wrappers around all API endpoints.
 * Components never call fetch directly — always use these functions.
 *
 * Access token is stored in memory (not localStorage).
 * Refresh token is in an httpOnly cookie (set by server).
 */

import type {
  AIProvider,
  CascadePath,
  Chapter,
  ChapterSummary,
  ChatDoneEvent,
  ChatMetaEvent,
  CreateCustomToneRequest,
  CreateProviderRequest,
  CreateVolumeRequest,
  CustomTone,
  DemoProjectInfo,
  DiffResponse,
  KBTemplateDetail,
  KBTemplateDiff,
  KBTemplateInfo,
  KBTemplateUpdateInfo,
  NameGenerateRequest,
  NameGenerateResponse,
  Novel,
  NovelSummary,
  ProjectAiSettings,
  ProjectSettings,
  PromptDetail,
  PromptInfo,
  TokenLimitsResponse,
  TokenResponse,
  UpdateCustomToneRequest,
  UpdateInfo,
  UpdateProjectAiSettingsRequest,
  UpdateProviderRequest,
  UpdateTokenLimitsRequest,
  UpdateUserAiSettingsRequest,
  UpdateVolumeRequest,
  User,
  UserAiSettings,
  UserProvider,
  UserSettings,
  Volume,
  VolumeStats,
  WizardState,
} from "@/types";

// --- In-memory token storage (never localStorage — security) ---

let _accessToken: string | null = null;

export function setAccessToken(token: string): void {
  _accessToken = token;
  // Sync cookie for Next.js middleware (server-side route protection)
  if (typeof document !== "undefined") {
    // biome-ignore lint/suspicious/noDocumentCookie: cookie needed for Next.js middleware server-side route protection
    document.cookie = `narrare_auth=${token}; path=/; max-age=3600; samesite=lax`;
  }
}

export function clearAccessToken(): void {
  _accessToken = null;
  // Clear auth cookie
  if (typeof document !== "undefined") {
    // biome-ignore lint/suspicious/noDocumentCookie: clearing auth cookie for Next.js middleware
    document.cookie = "narrare_auth=; path=/; max-age=0";
  }
}

export function getAccessToken(): string | null {
  return _accessToken;
}

// --- Core fetch wrapper with auth + auto-refresh on 401 ---

let _isRefreshing = false;
let _refreshPromise: Promise<void> | null = null;

async function refreshAccessToken(): Promise<void> {
  if (_isRefreshing && _refreshPromise) return _refreshPromise;
  _isRefreshing = true;
  _refreshPromise = (async () => {
    try {
      // IMPORTANT: Must include Content-Type + empty body. The Next.js dev
      // proxy can hang on POST requests without Content-Type during page load
      // when the response takes more than a few seconds (e.g. cold DB start).
      // The httpOnly refresh cookie is sent via credentials: "include".
      const res = await fetch("/api/v1/auth/refresh", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: "{}",
      });
      if (!res.ok) throw new Error("Refresh failed");
      const data: TokenResponse = await res.json();
      setAccessToken(data.access_token);
    } finally {
      _isRefreshing = false;
      _refreshPromise = null;
    }
  })();
  return _refreshPromise;
}

/**
 * Log out on the server: POST to /api/v1/auth/logout to clear the httpOnly
 * refresh cookie. This uses raw fetch (not fetchApi) because there may be no
 * access token at the time of logout.
 */
export async function logoutApi(): Promise<void> {
  try {
    await fetch("/api/v1/auth/logout", {
      method: "POST",
      credentials: "include",
    });
  } catch {
    // Network error — ignore, we still clear local state
  }
}

export async function restoreSession(): Promise<boolean> {
  if (_accessToken) return true; // already have a valid token
  try {
    await refreshAccessToken();
    return true;
  } catch {
    return false;
  }
}

export async function fetchApi<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `/api/v1${endpoint}`;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((options.headers as Record<string, string>) ?? {}),
  };
  if (_accessToken) headers.Authorization = `Bearer ${_accessToken}`;

  const response = await fetch(url, { ...options, headers, credentials: "include" });

  if (response.status === 401) {
    if (endpoint === "/auth/refresh") {
      clearAccessToken();
      if (typeof window !== "undefined" && window.location.pathname !== "/login") {
        window.location.href = "/login";
      }
      throw new Error("Session expired");
    }
    // Auth endpoints: 401 means "wrong credentials", not "session expired"
    if (endpoint === "/auth/login" || endpoint === "/auth/register") {
      const err = await response.json().catch(() => ({ detail: response.statusText }));
      if (typeof err.detail === "string") {
        throw new Error(err.detail);
      }
      if (Array.isArray(err.detail)) {
        const messages = err.detail.map((e: { msg?: string }) => e.msg).filter(Boolean);
        throw new Error(messages.join("; ") || `HTTP ${response.status}`);
      }
      throw new Error(`HTTP ${response.status}`);
    }
    try {
      await refreshAccessToken();
      headers.Authorization = `Bearer ${_accessToken}`;
      const retry = await fetch(url, { ...options, headers, credentials: "include" });
      if (!retry.ok) throw new Error(`HTTP ${retry.status}`);
      if (retry.status === 204) return undefined as T;
      return retry.json() as Promise<T>;
    } catch {
      clearAccessToken();
      window.location.href = "/login";
      throw new Error("Session expired");
    }
  }

  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: response.statusText }));
    if (typeof err.detail === "string") {
      throw new Error(err.detail);
    }
    if (Array.isArray(err.detail)) {
      const messages = err.detail.map((e: { msg?: string }) => e.msg).filter(Boolean);
      throw new Error(messages.join("; ") || `HTTP ${response.status}`);
    }
    throw new Error(`HTTP ${response.status}`);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

// --- Auth ---

export const authApi = {
  register: (email: string, password: string, displayName = "") =>
    fetchApi<TokenResponse>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password, display_name: displayName }),
    }),

  login: (email: string, password: string) =>
    fetchApi<TokenResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  me: () => fetchApi<User>("/auth/me"),
};

// --- Novels ---

export const novelsApi = {
  list: () => fetchApi<NovelSummary[]>("/novels"),
  get: (novelId: string) => fetchApi<Novel>(`/novels/${novelId}`),
  create: (payload: Partial<Novel>) =>
    fetchApi<Novel>("/novels", { method: "POST", body: JSON.stringify(payload) }),
  update: (novelId: string, payload: Partial<Novel>) =>
    fetchApi<Novel>(`/novels/${novelId}`, { method: "PATCH", body: JSON.stringify(payload) }),
  delete: (novelId: string) => fetchApi<void>(`/novels/${novelId}`, { method: "DELETE" }),
};

// --- Chapters ---

export const chaptersApi = {
  list: (novelId: string, volumeId?: string | null) => {
    const params = volumeId ? `?volume_id=${volumeId}` : "";
    return fetchApi<ChapterSummary[]>(`/novels/${novelId}/chapters${params}`);
  },
  get: (novelId: string, chapterId: string) =>
    fetchApi<Chapter>(`/novels/${novelId}/chapters/${chapterId}`),
  create: (novelId: string, payload: { title?: string; content?: string; volume_id?: string }) =>
    fetchApi<Chapter>(`/novels/${novelId}/chapters`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateContent: (novelId: string, chapterId: string, content: string) =>
    fetchApi<Chapter>(`/novels/${novelId}/chapters/${chapterId}/content`, {
      method: "PUT",
      body: JSON.stringify({ content }),
    }),
  updateMeta: (novelId: string, chapterId: string, payload: Partial<Chapter>) =>
    fetchApi<Chapter>(`/novels/${novelId}/chapters/${chapterId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  reorder: (novelId: string, chapterIds: string[]) =>
    fetchApi<ChapterSummary[]>(`/novels/${novelId}/chapters/reorder`, {
      method: "POST",
      body: JSON.stringify({ chapter_ids: chapterIds }),
    }),
  delete: (novelId: string, chapterId: string) =>
    fetchApi<void>(`/novels/${novelId}/chapters/${chapterId}`, { method: "DELETE" }),
};

// --- Volumes ---

export const volumesApi = {
  list: (novelId: string) => fetchApi<Volume[]>(`/novels/${novelId}/volumes`),
  create: (novelId: string, payload: CreateVolumeRequest) =>
    fetchApi<Volume>(`/novels/${novelId}/volumes`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  update: (novelId: string, volumeId: string, payload: UpdateVolumeRequest) =>
    fetchApi<Volume>(`/novels/${novelId}/volumes/${volumeId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  delete: (novelId: string, volumeId: string) =>
    fetchApi<void>(`/novels/${novelId}/volumes/${volumeId}`, { method: "DELETE" }),
  getStats: (novelId: string, volumeId: string) =>
    fetchApi<VolumeStats>(`/novels/${novelId}/volumes/${volumeId}/stats`),
  reorder: (novelId: string, volumeIds: string[]) =>
    fetchApi<Volume[]>(`/novels/${novelId}/volumes/reorder`, {
      method: "PATCH",
      body: JSON.stringify({ volume_ids: volumeIds }),
    }),
};

// --- Settings ---

export const settingsApi = {
  getUser: () => fetchApi<UserSettings>("/settings/user"),
  updateUser: (payload: Partial<UserSettings>) =>
    fetchApi<UserSettings>("/settings/user", { method: "PATCH", body: JSON.stringify(payload) }),
  getProject: (novelId: string) => fetchApi<ProjectSettings>(`/settings/novels/${novelId}`),
  updateProject: (novelId: string, payload: Partial<ProjectSettings>) =>
    fetchApi<ProjectSettings>(`/settings/novels/${novelId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
};

// --- Setup Wizard ---

export const setupApi = {
  validateStep1: (data: {
    project_name: string;
    writing_language: string;
    autosave_interval: number;
  }) =>
    fetchApi<{ valid: boolean }>("/setup/validate/step-1", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  validateStep2: (data: {
    title: string;
    author?: string;
    genre?: string;
    logline?: string;
    story_structure?: string;
    tone?: string;
  }) =>
    fetchApi<{ valid: boolean }>("/setup/validate/step-2", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  validateStep3: (data: { starter: string; import_path?: string | null }) =>
    fetchApi<{ valid: boolean; starter: string; demo_info: DemoProjectInfo | null }>(
      "/setup/validate/step-3",
      { method: "POST", body: JSON.stringify(data) },
    ),

  validateStep4: (data: {
    provider: AIProvider;
    api_key: string;
    model: string;
    ollama_url?: string;
    zai_endpoint?: string;
  }) =>
    fetchApi<{ valid: boolean }>("/setup/validate/step-4", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  getProviderModels: (provider: AIProvider, apiKey = "", ollamaUrl = "http://localhost:11434") => {
    const params = new URLSearchParams({ api_key: apiKey, ollama_url: ollamaUrl });
    return fetchApi<{ provider: AIProvider; models: { id: string; name: string }[] }>(
      `/setup/providers/${provider}/models?${params.toString()}`,
    );
  },

  complete: (state: WizardState) =>
    fetchApi<{ novel_id: string; redirect_to: string; message: string }>("/setup/complete", {
      method: "POST",
      body: JSON.stringify({ state }),
    }),
};

// Type exports for external use
export interface AvailableModelsResponse {
  provider: AIProvider;
  models: { id: string; name: string; context_window?: number }[];
}

export interface ModelRefreshResponse {
  status: "ok" | "error";
  new_models: string[];
  removed_models: string[];
  total_models: number;
  cached_at: string;
  message?: string;
}

// --- AI Settings ---

export const aiSettingsApi = {
  // Provider CRUD
  listProviders: () => fetchApi<UserProvider[]>("/settings/ai/providers"),
  createProvider: (data: CreateProviderRequest) =>
    fetchApi<UserProvider>("/settings/ai/providers", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  updateProvider: (id: string, data: UpdateProviderRequest) =>
    fetchApi<UserProvider>(`/settings/ai/providers/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  deleteProvider: (id: string) =>
    fetchApi<void>(`/settings/ai/providers/${id}`, { method: "DELETE" }),

  // User AI Settings
  getUserSettings: () => fetchApi<UserAiSettings>("/settings/ai"),
  updateUserSettings: (data: UpdateUserAiSettingsRequest) =>
    fetchApi<UserAiSettings>("/settings/ai", {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  // Project AI Settings
  getProjectSettings: (novelId: string) =>
    fetchApi<ProjectAiSettings>(`/settings/ai/novels/${novelId}`),
  updateProjectSettings: (novelId: string, data: UpdateProjectAiSettingsRequest) =>
    fetchApi<ProjectAiSettings>(`/settings/ai/novels/${novelId}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  // Live model retrieval (uses stored API key from DB)
  getProviderModels: (providerId: string) =>
    fetchApi<AvailableModelsResponse>(`/settings/ai/providers/${providerId}/models`),

  // Refresh model data from models.dev
  refreshModels: () =>
    fetchApi<ModelRefreshResponse>("/settings/models/refresh", { method: "POST" }),
};

// --- Token Limits ---

export const tokenLimitsApi = {
  getResolved: () => fetchApi<TokenLimitsResponse>("/settings/token-limits/"),

  updateUser: (data: UpdateTokenLimitsRequest) =>
    fetchApi<TokenLimitsResponse>("/settings/token-limits/user", {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  updateProject: (projectId: string, data: UpdateTokenLimitsRequest) =>
    fetchApi<TokenLimitsResponse>(`/settings/token-limits/project/${projectId}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),
};

// --- Prompts ---

export const promptsApi = {
  list: (category?: string) =>
    fetchApi<PromptInfo[]>(`/prompts${category ? `?category=${category}` : ""}`),

  get: (id: string) => fetchApi<PromptDetail>(`/prompts/${id}`),

  save: (id: string, content: string) =>
    fetchApi<void>(`/prompts/${id}`, {
      method: "PUT",
      body: JSON.stringify({ content }),
    }),

  reset: (id: string) => fetchApi<void>(`/prompts/${id}/override`, { method: "DELETE" }),

  cascade: (id: string) => fetchApi<CascadePath[]>(`/prompts/${id}/cascade`),

  updates: () => fetchApi<UpdateInfo[]>("/prompts/updates"),

  diff: (id: string) => fetchApi<DiffResponse>(`/prompts/${id}/diff`),
};

// --- KB Templates ---

export const templatesApi = {
  list: (novelId: string) => fetchApi<KBTemplateInfo[]>(`/novels/${novelId}/kb/templates`),

  get: (novelId: string, entityType: string) =>
    fetchApi<KBTemplateDetail>(`/novels/${novelId}/kb/templates/${entityType}`),

  save: (novelId: string, entityType: string, content: string, basedOnVersion?: string) =>
    fetchApi<void>(`/novels/${novelId}/kb/templates/${entityType}`, {
      method: "POST",
      body: JSON.stringify({ content, based_on_version: basedOnVersion }),
    }),

  reset: (novelId: string, entityType: string) =>
    fetchApi<void>(`/novels/${novelId}/kb/templates/${entityType}`, { method: "DELETE" }),

  updates: (novelId: string) =>
    fetchApi<KBTemplateUpdateInfo[]>(`/novels/${novelId}/kb/templates/updates`),

  diff: (novelId: string, entityType: string) =>
    fetchApi<KBTemplateDiff>(`/novels/${novelId}/kb/templates/${entityType}/diff`),
};

// --- Generation ---

export const generationApi = {
  generateNames: (request: NameGenerateRequest) =>
    fetchApi<NameGenerateResponse>("/generation/names", {
      method: "POST",
      body: JSON.stringify(request),
    }),
};

// --- Chat (ADR-024 Free-Form Chat) ---

export const chatApi = {
  /**
   * Stream a free-form chat message via SSE.
   *
   * POST /api/v1/chat with SSE response.
   * Event types: meta, token, done.
   * Follows the same SSE pattern as coauthor.ts / generation.ts.
   */
  streamChat: async (
    body: { project_id: string; message: string; conversation_id?: string | null },
    callbacks: {
      onMeta: (meta: ChatMetaEvent) => void;
      onToken: (text: string) => void;
      onDone: (done: ChatDoneEvent) => void;
      onError: (error: Error) => void;
    },
    signal?: AbortSignal,
  ): Promise<void> => {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    };
    const token = getAccessToken();
    if (token) headers.Authorization = `Bearer ${token}`;

    try {
      const response = await fetch("/api/v1/chat", {
        method: "POST",
        headers,
        credentials: "include",
        body: JSON.stringify(body),
        signal,
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);

      const reader = response.body?.getReader();
      if (!reader) throw new Error("No response body");

      const decoder = new TextDecoder();
      let buffer = "";
      let currentEvent = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          // Track SSE event type
          if (line.startsWith("event: ")) {
            currentEvent = line.slice(7).trim();
            continue;
          }

          if (line.startsWith("data: ")) {
            const data = line.slice(6);
            if (data === "[DONE]") return;

            try {
              const parsed = JSON.parse(data) as Record<string, unknown>;

              if (currentEvent === "meta" || parsed.conversation_id) {
                callbacks.onMeta(parsed as unknown as ChatMetaEvent);
              } else if (currentEvent === "token" || parsed.type === "token") {
                callbacks.onToken(parsed.text as string);
              } else if (currentEvent === "done" || parsed.type === "done") {
                callbacks.onDone(parsed as unknown as ChatDoneEvent);
              }
            } catch {
              // Skip malformed JSON
            }

            currentEvent = "";
          }
        }
      }
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      callbacks.onError(error instanceof Error ? error : new Error(String(error)));
    }
  },
};

// --- Custom Tones ---

export const tonesApi = {
  list: () => fetchApi<CustomTone[]>("/settings/user/tones"),

  create: (data: CreateCustomToneRequest) =>
    fetchApi<CustomTone>("/settings/user/tones", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  update: (id: string, data: UpdateCustomToneRequest) =>
    fetchApi<CustomTone>(`/settings/user/tones/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  delete: (id: string) => fetchApi<void>(`/settings/user/tones/${id}`, { method: "DELETE" }),
};
