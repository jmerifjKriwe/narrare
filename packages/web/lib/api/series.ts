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
  BandSummary,
  CanonEntryCreate,
  CanonEntryUpdate,
  JoinPreview,
  JoinResult,
  NovelKBEntry,
  NovelSummary,
  Series,
  SeriesCreate,
  SeriesKBEntry,
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

  // --- Series-Canon KB CRUD (Slice 5) ---
  // Mirrors apps/api/narrare/kb/router_canon.py. Targets /series/{id}/kb.

  /** GET /series/{id}/kb — all Series-Canon entries for the series. */
  listCanonKB: (seriesId: string) => fetchApi<SeriesKBEntry[]>(`/series/${seriesId}/kb`),

  /** POST /series/{id}/kb — create a Series-Canon entry (201). */
  createCanonEntry: (seriesId: string, body: CanonEntryCreate) =>
    fetchApi<SeriesKBEntry>(`/series/${seriesId}/kb`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  /** PATCH /series/{id}/kb/{entryId} — update a Series-Canon entry. */
  updateCanonEntry: (seriesId: string, entryId: string, body: CanonEntryUpdate) =>
    fetchApi<SeriesKBEntry>(`/series/${seriesId}/kb/${entryId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),

  /** DELETE /series/{id}/kb/{entryId} — delete a Series-Canon entry (204). */
  deleteCanonEntry: (seriesId: string, entryId: string) =>
    fetchApi<void>(`/series/${seriesId}/kb/${entryId}`, { method: "DELETE" }),

  // --- KB scope toggle (Slice 5) ---
  // Mirrors apps/api/narrare/kb/router_scope.py.

  /** POST /novels/{novelId}/kb/{entryId}/promote — Novel-Overlay → Series-Canon. */
  promoteToCanon: (novelId: string, entryId: string) =>
    fetchApi<SeriesKBEntry>(`/novels/${novelId}/kb/${entryId}/promote`, { method: "POST" }),

  /**
   * POST /novels/{novelId}/kb/{entryId}/demote — Series-Canon → Novel-Overlay.
   *
   * The path ``novelId`` is the routing anchor; ``seriesId`` and ``targetNovelId``
   * (the novel the canon entry becomes an overlay of) ride in the request body.
   */
  demoteToOverlay: (novelId: string, entryId: string, seriesId: string, targetNovelId: string) =>
    fetchApi<NovelKBEntry>(`/novels/${novelId}/kb/${entryId}/demote`, {
      method: "POST",
      body: JSON.stringify({ series_id: seriesId, target_novel_id: targetNovelId }),
    }),

  // --- Band summaries (Spec 2 Task 4 / Task 8) ---
  // Mirrors apps/api/narrare/series/router_band_summary.py. One summary row
  // per novel; override takes precedence at SeriesHistoryTier assembly time.

  /** GET /series/{id}/novels/{novelId}/band-summary — existing summary (404 if none). */
  getBandSummary: (seriesId: string, novelId: string) =>
    fetchApi<BandSummary>(`/series/${seriesId}/novels/${novelId}/band-summary`),

  /** POST /series/{id}/novels/{novelId}/band-summary — trigger (re)generation (upsert). */
  generateBandSummary: (seriesId: string, novelId: string) =>
    fetchApi<BandSummary>(`/series/${seriesId}/novels/${novelId}/band-summary`, {
      method: "POST",
    }),

  /** PATCH /series/{id}/novels/{novelId}/band-summary — set the user override. */
  updateBandSummaryOverride: (seriesId: string, novelId: string, override: string) =>
    fetchApi<BandSummary>(`/series/${seriesId}/novels/${novelId}/band-summary`, {
      method: "PATCH",
      body: JSON.stringify({ override }),
    }),

  /** DELETE /series/{id}/novels/{novelId}/band-summary/override — clear override (204). */
  clearBandSummaryOverride: (seriesId: string, novelId: string) =>
    fetchApi<void>(`/series/${seriesId}/novels/${novelId}/band-summary/override`, {
      method: "DELETE",
    }),
};
