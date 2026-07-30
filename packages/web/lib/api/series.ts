/**
 * Series API client.
 *
 * Typed wrappers around all Series endpoints shipped in Slice 3
 * (apps/api/narrare/series/router.py + router_novels.py): CRUD, novels-in-series
 * (join preview/apply, list, reorder, remove), and settings.
 *
 * Follows the established Narrare pattern: every call goes through `fetchApi`
 * from ./core (auth-token injection, 401 auto-refresh, `/api/v1` prefixing,
 * unified error parsing). Components/hooks import this — never `fetch` directly.
 */

import type {
  JoinPreview,
  JoinResult,
  NovelSummary,
  Series,
  SeriesCreate,
  SeriesSettings,
  SeriesSettingsUpdate,
  SeriesSummary,
  SeriesUpdate,
} from "@/types";
import { fetchApi } from "./core";

// --- Series CRUD ---

export const seriesApi = {
  list: () => fetchApi<SeriesSummary[]>("/series"),
  get: (seriesId: string) => fetchApi<Series>(`/series/${seriesId}`),
  create: (body: SeriesCreate) =>
    fetchApi<Series>("/series", { method: "POST", body: JSON.stringify(body) }),
  update: (seriesId: string, body: SeriesUpdate) =>
    fetchApi<Series>(`/series/${seriesId}`, { method: "PATCH", body: JSON.stringify(body) }),
  delete: (seriesId: string) => fetchApi<void>(`/series/${seriesId}`, { method: "DELETE" }),

  // --- Novels in series (join flow) ---

  /** GET /series/{id}/novels — ordered by series_position. */
  listNovels: (seriesId: string) => fetchApi<NovelSummary[]>(`/series/${seriesId}/novels`),

  /** POST /series/{id}/novels — preview (Policy alpha; does NOT mutate). */
  previewJoin: (seriesId: string, novelId: string) =>
    fetchApi<JoinPreview>(`/series/${seriesId}/novels`, {
      method: "POST",
      body: JSON.stringify({ novel_id: novelId }),
    }),

  /** POST /series/{id}/novels/{novelId}/apply — executes the join (1-based slot). */
  applyJoin: (seriesId: string, novelId: string, position: number) =>
    fetchApi<JoinResult>(`/series/${seriesId}/novels/${novelId}/apply`, {
      method: "POST",
      body: JSON.stringify({ position }),
    }),

  /** DELETE /series/{id}/novels/{novelId} — back to standalone (204). */
  removeNovel: (seriesId: string, novelId: string) =>
    fetchApi<void>(`/series/${seriesId}/novels/${novelId}`, { method: "DELETE" }),

  /** PATCH /series/{id}/novels/reorder — full ordered id list (204). */
  reorderNovels: (seriesId: string, novelIds: string[]) =>
    fetchApi<void>(`/series/${seriesId}/novels/reorder`, {
      method: "PATCH",
      body: JSON.stringify({ novel_ids: novelIds }),
    }),

  // --- Settings ---

  getSettings: (seriesId: string) => fetchApi<SeriesSettings>(`/series/${seriesId}/settings`),
  updateSettings: (seriesId: string, body: SeriesSettingsUpdate) =>
    fetchApi<SeriesSettings>(`/series/${seriesId}/settings`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
};
