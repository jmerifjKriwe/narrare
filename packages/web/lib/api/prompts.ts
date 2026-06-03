/**
 * Prompts and KB Templates APIs.
 */

import type {
  CascadePath,
  DiffResponse,
  KBTemplateDetail,
  KBTemplateDiff,
  KBTemplateInfo,
  KBTemplateUpdateInfo,
  PromptDetail,
  PromptInfo,
  UpdateInfo,
} from "@/types";
import { fetchApi } from "./core";

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
