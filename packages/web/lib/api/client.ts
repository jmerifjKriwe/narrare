/**
 * Narrare API client.
 *
 * Typed wrappers around all API endpoints.
 * Components never call fetch directly — always use these functions.
 *
 * Access token is stored in memory (not localStorage).
 * Refresh token is in an httpOnly cookie (set by server).
 */

import axios, { type AxiosError, type AxiosInstance } from "axios"
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
  AIProvider,
  DemoProjectInfo,
} from "@/types"

// In-memory token storage (never localStorage — security)
let _accessToken: string | null = null

export function setAccessToken(token: string): void {
  _accessToken = token
}

export function clearAccessToken(): void {
  _accessToken = null
}

export function getAccessToken(): string | null {
  return _accessToken
}

// Axios instance
const api: AxiosInstance = axios.create({
  baseURL: "/api/v1",
  headers: { "Content-Type": "application/json" },
  withCredentials: true, // send cookies for refresh token
})

// Attach access token to every request
api.interceptors.request.use((config) => {
  if (_accessToken) {
    config.headers.Authorization = `Bearer ${_accessToken}`
  }
  return config
})

// Auto-refresh on 401
api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as typeof error.config & { _retry?: boolean }
    if (error.response?.status === 401 && !original._retry) {
      original._retry = true
      try {
        const { data } = await axios.post<TokenResponse>(
          "/api/v1/auth/refresh",
          {},
          { withCredentials: true }
        )
        setAccessToken(data.access_token)
        original.headers!.Authorization = `Bearer ${data.access_token}`
        return api(original)
      } catch {
        clearAccessToken()
        window.location.href = "/login"
      }
    }
    return Promise.reject(error)
  }
)

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

export const authApi = {
  register: async (email: string, password: string, displayName = "") => {
    const { data } = await api.post<TokenResponse>("/auth/register", {
      email,
      password,
      display_name: displayName,
    })
    return data
  },

  login: async (email: string, password: string) => {
    const { data } = await api.post<TokenResponse>("/auth/login", { email, password })
    return data
  },

  me: async () => {
    const { data } = await api.get<User>("/auth/me")
    return data
  },
}

// ---------------------------------------------------------------------------
// Novels
// ---------------------------------------------------------------------------

export const novelsApi = {
  list: async () => {
    const { data } = await api.get<NovelSummary[]>("/novels")
    return data
  },

  get: async (novelId: string) => {
    const { data } = await api.get<Novel>(`/novels/${novelId}`)
    return data
  },

  create: async (payload: Partial<Novel>) => {
    const { data } = await api.post<Novel>("/novels", payload)
    return data
  },

  update: async (novelId: string, payload: Partial<Novel>) => {
    const { data } = await api.patch<Novel>(`/novels/${novelId}`, payload)
    return data
  },

  delete: async (novelId: string) => {
    await api.delete(`/novels/${novelId}`)
  },
}

// ---------------------------------------------------------------------------
// Chapters
// ---------------------------------------------------------------------------

export const chaptersApi = {
  list: async (novelId: string) => {
    const { data } = await api.get<ChapterSummary[]>(`/novels/${novelId}/chapters`)
    return data
  },

  get: async (novelId: string, chapterId: string) => {
    const { data } = await api.get<Chapter>(`/novels/${novelId}/chapters/${chapterId}`)
    return data
  },

  create: async (novelId: string, payload: { title?: string; content?: string }) => {
    const { data } = await api.post<Chapter>(`/novels/${novelId}/chapters`, payload)
    return data
  },

  updateContent: async (novelId: string, chapterId: string, content: string) => {
    const { data } = await api.put<Chapter>(
      `/novels/${novelId}/chapters/${chapterId}/content`,
      { content }
    )
    return data
  },

  updateMeta: async (novelId: string, chapterId: string, payload: Partial<Chapter>) => {
    const { data } = await api.patch<Chapter>(
      `/novels/${novelId}/chapters/${chapterId}`,
      payload
    )
    return data
  },

  reorder: async (novelId: string, chapterIds: string[]) => {
    const { data } = await api.post<ChapterSummary[]>(
      `/novels/${novelId}/chapters/reorder`,
      { chapter_ids: chapterIds }
    )
    return data
  },

  delete: async (novelId: string, chapterId: string) => {
    await api.delete(`/novels/${novelId}/chapters/${chapterId}`)
  },
}

// ---------------------------------------------------------------------------
// Settings
// ---------------------------------------------------------------------------

export const settingsApi = {
  getUser: async () => {
    const { data } = await api.get<UserSettings>("/settings/user")
    return data
  },

  updateUser: async (payload: Partial<UserSettings>) => {
    const { data } = await api.patch<UserSettings>("/settings/user", payload)
    return data
  },

  getProject: async (novelId: string) => {
    const { data } = await api.get<ProjectSettings>(`/settings/novels/${novelId}`)
    return data
  },

  updateProject: async (novelId: string, payload: Partial<ProjectSettings>) => {
    const { data } = await api.patch<ProjectSettings>(
      `/settings/novels/${novelId}`,
      payload
    )
    return data
  },
}

// ---------------------------------------------------------------------------
// Setup Wizard
// ---------------------------------------------------------------------------

export const setupApi = {
  validateStep1: async (data: {
    project_name: string
    language: string
    autosave_interval: number
  }) => {
    const { data: res } = await api.post("/setup/validate/step-1", data)
    return res
  },

  validateStep2: async (data: {
    title: string
    author?: string
    genre?: string
    logline?: string
    story_structure?: string
    tone?: string
  }) => {
    const { data: res } = await api.post("/setup/validate/step-2", data)
    return res
  },

  validateStep3: async (data: {
    starter: string
    import_path?: string | null
  }) => {
    const { data: res } = await api.post<{
      valid: boolean
      starter: string
      demo_info: DemoProjectInfo | null
    }>("/setup/validate/step-3", data)
    return res
  },

  validateStep4: async (data: {
    provider: AIProvider
    api_key: string
    model: string
    ollama_url?: string
  }) => {
    const { data: res } = await api.post("/setup/validate/step-4", data)
    return res
  },

  getProviderModels: async (
    provider: AIProvider,
    apiKey = "",
    ollamaUrl = "http://localhost:11434"
  ) => {
    const { data } = await api.get<{ provider: AIProvider; models: { id: string; name: string }[] }>(
      `/setup/providers/${provider}/models`,
      { params: { api_key: apiKey, ollama_url: ollamaUrl } }
    )
    return data
  },

  complete: async (state: WizardState) => {
    const { data } = await api.post<{ novel_id: string; redirect_to: string; message: string }>(
      "/setup/complete",
      { state }
    )
    return data
  },
}

// Type exports for external use
export interface AvailableModelsResponse {
  provider: AIProvider
  models: { id: string; name: string; context_window?: number }[]
}
