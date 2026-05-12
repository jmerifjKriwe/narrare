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
  Chapter,
  ChapterSummary,
  DemoProjectInfo,
  Novel,
  NovelSummary,
  ProjectSettings,
  TokenResponse,
  User,
  UserSettings,
  WizardState,
} from "@/types";

// --- In-memory token storage (never localStorage — security) ---

let _accessToken: string | null = null;

export function setAccessToken(token: string): void {
  _accessToken = token;
}

export function clearAccessToken(): void {
  _accessToken = null;
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
      const res = await fetch("/api/v1/auth/refresh", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
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

async function fetchApi<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
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
      window.location.href = "/login";
      throw new Error("Session expired");
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
    throw new Error(err.detail || `HTTP ${response.status}`);
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
  list: (novelId: string) => fetchApi<ChapterSummary[]>(`/novels/${novelId}/chapters`),
  get: (novelId: string, chapterId: string) =>
    fetchApi<Chapter>(`/novels/${novelId}/chapters/${chapterId}`),
  create: (novelId: string, payload: { title?: string; content?: string }) =>
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
  validateStep1: (data: { project_name: string; language: string; autosave_interval: number }) =>
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
