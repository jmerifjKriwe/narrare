/**
 * Settings APIs — user settings, project settings, AI settings, token limits.
 */

import type {
  AIProvider,
  CreateProviderRequest,
  ProjectAiSettings,
  ProjectSettings,
  TokenLimitsResponse,
  UpdateProjectAiSettingsRequest,
  UpdateProviderRequest,
  UpdateTokenLimitsRequest,
  UpdateUserAiSettingsRequest,
  UserAiSettings,
  UserProvider,
  UserSettings,
} from "@/types";
import { fetchApi } from "./core";

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

export interface TokenLimitsQuery {
  readonly provider?: string;
  readonly modelId?: string;
  readonly intent?: string;
}

function buildTokenLimitsPath(query?: TokenLimitsQuery): string {
  const params = new URLSearchParams();
  if (query?.provider) params.set("provider", query.provider);
  if (query?.modelId) params.set("model_id", query.modelId);
  if (query?.intent) params.set("intent", query.intent);
  const queryString = params.toString();
  return queryString ? `/settings/token-limits/?${queryString}` : "/settings/token-limits/";
}

// --- User & Project Settings ---

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
  getResolved: (query?: TokenLimitsQuery) =>
    fetchApi<TokenLimitsResponse>(buildTokenLimitsPath(query)),

  updateUser: (data: UpdateTokenLimitsRequest) =>
    fetchApi<void>("/settings/token-limits/user", {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  updateProject: (projectId: string, data: UpdateTokenLimitsRequest) =>
    fetchApi<void>(`/settings/token-limits/project/${projectId}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),
};
