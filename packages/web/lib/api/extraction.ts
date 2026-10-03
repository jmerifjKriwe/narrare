/**
 * Extraction API client — KB entity extraction from chapters.
 *
 * REST-only endpoints (no SSE). The extraction agent runs
 * synchronously and returns structured results.
 *
 * Architecture:
 * - extractChapter: POST → ExtractionOutput (results + analysis_notes)
 * - applyExtraction: POST → ApplyExtractionResponse (created + updated entries)
 */

import { fetchApi } from "./client";

// --- Types ---

export type ExtractionItemType = "new_entity" | "update_entity" | "relationship" | "conflict";

export interface ExtractionItem {
  item_type: ExtractionItemType;
  entity_type: string | null;
  name: string;
  confidence: number;
  source_text: string;
  proposed_content: Record<string, unknown> | null;
  target_entity_id: string | null;
  conflict_description: string | null;
  relationship_type: string | null;
  related_entity_name: string | null;
}

export interface ExtractionOutput {
  results: ExtractionItem[];
  analysis_notes: string;
}

export interface ApplyExtractionItem {
  item_type: ExtractionItemType;
  name: string;
  entity_type: string | null;
  proposed_content: Record<string, unknown> | null;
  target_entity_id: string | null;
  relationship_type: string | null;
  related_entity_name: string | null;
  source_text: string;
}

export interface ApplyExtractionEntryResult {
  id: string;
  name: string;
  entity_type: string;
}

export interface ApplyExtractionResponse {
  created_entries: ApplyExtractionEntryResult[];
  updated_entries: ApplyExtractionEntryResult[];
}

// --- API functions ---

export const extractionApi = {
  /** Run extraction agent on a chapter. Returns structured results. */
  extractChapter: (novelId: string, chapterId: string, signal?: AbortSignal) =>
    fetchApi<ExtractionOutput>(`/novels/${novelId}/kb/extract/${chapterId}`, {
      method: "POST",
      signal,
    }),

  /**
   * Apply selected extraction items to the Knowledge Base.
   *
   * `chapterId` (optional, F2 Task 6 / ADR-085 provenance) records the
   * source chapter on the written KB entries; existing two-arg callers
   * stay unchanged. Note the signature: `chapterId` precedes `signal`.
   */
  applyExtraction: (
    novelId: string,
    items: ApplyExtractionItem[],
    chapterId?: string,
    signal?: AbortSignal,
  ) =>
    fetchApi<ApplyExtractionResponse>(`/novels/${novelId}/kb/extract/apply`, {
      method: "POST",
      body: JSON.stringify({ items, ...(chapterId ? { chapter_id: chapterId } : {}) }),
      signal,
    }),
};
