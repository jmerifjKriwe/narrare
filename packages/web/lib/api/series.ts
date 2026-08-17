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
  SeriesConsistencyResult,
  SeriesCreate,
  SeriesDriftSnapshot,
  SeriesHistoryPreviewResponse,
  SeriesKBEntry,
  SeriesSettings,
  SeriesSettingsUpdate,
  SeriesSummary,
  SeriesUpdate,
  SeriesVoice,
  SeriesVoiceDriftResult,
  SeriesVoiceOverrideRequest,
  SeriesVoiceState,
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

  /** GET /series/{id}/settings/context-preview — live slider preview (C1). */
  getSettingsContextPreview: (seriesId: string) =>
    fetchApi<SeriesHistoryPreviewResponse>(`/series/${seriesId}/settings/context-preview`),

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
   * The path ``novelId`` is BOTH the routing anchor AND the overlay target
   * (mirrors the promote endpoint). The body carries only ``seriesId`` (the
   * canon's series) — there is no target id that could disagree with the path.
   */
  demoteToOverlay: (novelId: string, entryId: string, seriesId: string) =>
    fetchApi<NovelKBEntry>(`/novels/${novelId}/kb/${entryId}/demote`, {
      method: "POST",
      body: JSON.stringify({ series_id: seriesId }),
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

  // --- Series Voice Hierarchy (Spec 3 Tasks 5–6) ---
  // Mirrors apps/api/narrare/series/router_voice.py. Targets /series/{id}/voice.
  // The Delta-model foundation (ADR-078): one author-voice profile per series,
  // stored as SeriesSettings.author_voice. POST profiles a band (novel); PATCH
  // sets a manual override (validated server-side); DELETE nulls the column.

  /** POST /series/{id}/voice/profile — profile a novel's voice → store as series voice (200). */
  profileVoice: (seriesId: string, novelId: string) =>
    fetchApi<SeriesVoiceState>(`/series/${seriesId}/voice/profile`, {
      method: "POST",
      body: JSON.stringify({ novel_id: novelId }),
    }),

  /** GET /series/{id}/voice — fetch the series voice (author_voice may be null). */
  getVoice: (seriesId: string) => fetchApi<SeriesVoice>(`/series/${seriesId}/voice`),

  /** PATCH /series/{id}/voice — set a manual voice-profile override. */
  updateVoiceOverride: (seriesId: string, voice: SeriesVoiceOverrideRequest) =>
    fetchApi<SeriesVoice>(`/series/${seriesId}/voice`, {
      method: "PATCH",
      body: JSON.stringify(voice),
    }),

  /** DELETE /series/{id}/voice/override — clear the series voice (204). */
  clearVoiceOverride: (seriesId: string) =>
    fetchApi<void>(`/series/${seriesId}/voice/override`, { method: "DELETE" }),

  // --- Series Cross-Novel Drift (Spec 4 Tasks 2–3) ---
  // Mirrors apps/api/narrare/series/router_consistency.py +
  // router_voice_drift.py. Both checks persist their result as the band's latest drift snapshot (C2) and return it (HTTP 200); the
  // series id is the URL anchor, the band (novel) id rides in the request body
  // (the path-based verify_novel_in_owned_series dependency does not apply).

  /**
   * POST /series/{id}/consistency/check — check a band's chapter prose against
   * the series Canon KB. Returns the canon contradictions found (possibly empty
   * — no contradictions is a valid result). The result is persisted as the band's latest drift snapshot before it is returned.
   */
  checkSeriesConsistency: (seriesId: string, novelId: string) =>
    fetchApi<SeriesConsistencyResult>(`/series/${seriesId}/consistency/check`, {
      method: "POST",
      body: JSON.stringify({ novel_id: novelId }),
    }),

  /**
   * POST /series/{id}/voice-drift/check — analyse a band's narrator drift
   * against the series voice baseline. Reuses the novel-level response shape
   * (AuthorVoiceDriftResponse). The result is persisted as the band's latest drift snapshot before it is returned.
   */
  checkSeriesVoiceDrift: (seriesId: string, novelId: string) =>
    fetchApi<SeriesVoiceDriftResult>(`/series/${seriesId}/voice-drift/check`, {
      method: "POST",
      body: JSON.stringify({ novel_id: novelId }),
    }),

  /**
   * GET /series/{id}/consistency/{novelId} — the persisted drift snapshot
   * (SERIES-004 Slice 6 / C2): both check results as one document plus the
   * server-computed stale flag. `generated_at` is null when nothing was
   * persisted yet (200 with an all-null body — never an error).
   */
  getDriftSnapshot: (seriesId: string, novelId: string) =>
    fetchApi<SeriesDriftSnapshot>(`/series/${seriesId}/consistency/${novelId}`),
};
