/**
 * KB (Knowledge Base) API client.
 *
 * Typed wrappers around all KB entry and relationship endpoints.
 * Components never call fetch directly — always use these functions
 * via TanStack Query hooks from lib/hooks/useKB.ts.
 */

import { fetchApi } from "./client";

// --- KB Entry types ---

export type KBEntityType = "character" | "location" | "faction" | "object" | "system" | "timeline";

export type KBEntryStatus = "draft" | "reviewed" | "canon" | "deprecated";

export interface KBEntry {
  id: string;
  novel_id: string;
  entity_type: KBEntityType;
  name: string;
  slug: string;
  status: KBEntryStatus;
  tags: string[];
  metadata: Record<string, unknown>;
  body: string;
  template_version: string | null;
  created_at: string;
  updated_at: string;
}

export interface KBEntryListResponse {
  items: KBEntry[];
  total: number;
  page: number;
  page_size: number;
}

export interface KBEntryCreateRequest {
  entity_type: KBEntityType;
  name: string;
  body?: string;
  tags?: string[];
  status?: KBEntryStatus;
  metadata?: Record<string, unknown>;
}

export interface KBEntryUpdateRequest {
  name?: string;
  body?: string;
  tags?: string[];
  status?: KBEntryStatus;
  metadata?: Record<string, unknown>;
}

// --- KB Relationship types ---

export type KBRelationshipDirection = "directed" | "mutual";

export interface KBRelationship {
  id: string;
  source_id: string;
  target_id: string;
  rel_type: string;
  label: string | null;
  direction: KBRelationshipDirection;
  metadata: Record<string, unknown>;
  source_name?: string;
  target_name?: string;
  source_type?: string;
  target_type?: string;
  created_at: string;
  updated_at: string;
}

export interface KBRelationshipCreateRequest {
  source_id: string;
  target_id: string;
  rel_type: string;
  label?: string | null;
  direction?: KBRelationshipDirection;
  metadata?: Record<string, unknown>;
}

export interface KBInverseSuggestion {
  rel_type: string;
  inverse_rel_type: string;
  description: string;
}

// --- List query params ---

export interface KBEntryListParams {
  entity_type?: KBEntityType;
  tags?: string;
  page?: number;
  page_size?: number;
}

export interface KBSearchParams extends KBEntryListParams {
  q: string;
}

// --- API functions ---

export const kbApi = {
  // -- Entries --

  listEntries: (novelId: string, params?: KBEntryListParams) => {
    const searchParams = new URLSearchParams();
    if (params?.entity_type) searchParams.set("entity_type", params.entity_type);
    if (params?.tags) searchParams.set("tags", params.tags);
    if (params?.page) searchParams.set("page", String(params.page));
    if (params?.page_size) searchParams.set("page_size", String(params.page_size));
    const qs = searchParams.toString();
    return fetchApi<KBEntryListResponse>(`/novels/${novelId}/kb/entries${qs ? `?${qs}` : ""}`);
  },

  getEntry: (novelId: string, entryId: string) =>
    fetchApi<KBEntry>(`/novels/${novelId}/kb/entries/${entryId}`),

  createEntry: (novelId: string, data: KBEntryCreateRequest) =>
    fetchApi<KBEntry>(`/novels/${novelId}/kb/entries`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  updateEntry: (novelId: string, entryId: string, data: KBEntryUpdateRequest) =>
    fetchApi<KBEntry>(`/novels/${novelId}/kb/entries/${entryId}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  deleteEntry: (novelId: string, entryId: string) =>
    fetchApi<void>(`/novels/${novelId}/kb/entries/${entryId}`, { method: "DELETE" }),

  searchEntries: (novelId: string, params: KBSearchParams) => {
    const searchParams = new URLSearchParams();
    searchParams.set("q", params.q);
    if (params.entity_type) searchParams.set("entity_type", params.entity_type);
    if (params.tags) searchParams.set("tags", params.tags);
    if (params.page) searchParams.set("page", String(params.page));
    if (params.page_size) searchParams.set("page_size", String(params.page_size));
    return fetchApi<KBEntryListResponse>(
      `/novels/${novelId}/kb/entries/search?${searchParams.toString()}`,
    );
  },

  // -- Relationships --

  listRelationships: (novelId: string, entryId: string, direction?: string) => {
    const qs = direction ? `?direction=${direction}` : "";
    return fetchApi<KBRelationship[]>(
      `/novels/${novelId}/kb/entries/${entryId}/relationships${qs}`,
    );
  },

  createRelationship: (novelId: string, data: KBRelationshipCreateRequest) =>
    fetchApi<KBRelationship>(`/novels/${novelId}/kb/relationships`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  deleteRelationship: (novelId: string, relId: string) =>
    fetchApi<void>(`/novels/${novelId}/kb/relationships/${relId}`, { method: "DELETE" }),

  getInverseSuggestion: (novelId: string, relType: string) =>
    fetchApi<KBInverseSuggestion>(
      `/novels/${novelId}/kb/relationships/inverse-suggestion?rel_type=${encodeURIComponent(relType)}`,
    ),
};
