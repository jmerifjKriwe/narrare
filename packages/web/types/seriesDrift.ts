/**
 * GET /api/v1/series/{id}/consistency/{novelId} response (SERIES-004 Slice 6 / C2).
 *
 * The persisted latest-wins drift snapshot for one band, fetched as ONE
 * document. RULE-17 contract parity: mirrors
 * ``apps/api/narrare/series/series_drift_schemas.SeriesDriftSnapshotResponse``
 * — snake_case preserved, the sections reuse the run-result mirrors from
 * ./series (the stored JSON serializes those models; no re-shaping).
 * ``generated_at`` is an ISO string (or null when nothing is persisted);
 * ``stale`` is true when the band's chapter texts changed since the last
 * completed write (server-side fingerprint comparison).
 */
import type { SeriesConsistencyResult, SeriesVoiceDriftResult } from "./series";

export interface SeriesDriftSnapshot {
  series_id: string;
  novel_id: string;
  /** ISO timestamp of the last completed write (either check); null = none. */
  generated_at: string | null;
  /** True when the band's texts changed after the persisted results. */
  stale: boolean;
  /** Persisted canon-contradiction result (null when never run). */
  consistency: SeriesConsistencyResult | null;
  /** Persisted series-voice-drift result (null when never run). */
  voice_drift: SeriesVoiceDriftResult | null;
}
