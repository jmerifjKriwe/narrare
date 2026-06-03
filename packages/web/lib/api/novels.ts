/**
 * Novels, Chapters, and Volumes APIs.
 */

import type {
  Chapter,
  ChapterSummary,
  CreateVolumeRequest,
  Novel,
  NovelSummary,
  UpdateVolumeRequest,
  Volume,
  VolumeStats,
} from "@/types";
import { fetchApi } from "./core";

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
