/**
 * Timeline event types — mirrors backend schemas (RULE-17).
 *
 * All field names use snake_case to match the Python API exactly.
 * Components never call fetch directly — use TanStack Query hooks
 * from lib/hooks/useTimeline.ts.
 */

// --- Enums (string literal types matching Python StrEnum values) ---

export type TimelineEventType =
  | "plot_point"
  | "character_event"
  | "world_event"
  | "flashback"
  | "flashforward"
  | "birth"
  | "death"
  | "battle"
  | "journey"
  | "other";

export type TimelineEventSource = "manual" | "ai_analysis" | "extracted";

// --- Entity References ---

export interface CharacterRef {
  id: string;
  name: string;
}

export interface LocationRef {
  id: string;
  name: string;
}

// --- Timeline Event CRUD ---

export interface TimelineEvent {
  id: string;
  novel_id: string;
  event_name: string;
  description: string;
  event_type: TimelineEventType;
  timestamp_raw: string;
  timestamp_normalized: string;
  temporal_order: number | null;
  chapter_id: string | null;
  character_refs: CharacterRef[];
  location_ref: LocationRef | null;
  causes: string;
  consequences: string;
  source: TimelineEventSource;
  confidence: number | null;
  is_confirmed: boolean;
  created_at: string;
  updated_at: string;
}

export interface TimelineEventCreateRequest {
  event_name: string;
  description?: string;
  event_type?: TimelineEventType;
  timestamp_raw?: string;
  timestamp_normalized?: string;
  temporal_order?: number | null;
  chapter_id?: string | null;
  character_refs?: CharacterRef[];
  location_ref?: LocationRef | null;
  causes?: string;
  consequences?: string;
}

export interface TimelineEventUpdateRequest {
  event_name?: string;
  description?: string;
  event_type?: TimelineEventType;
  timestamp_raw?: string;
  timestamp_normalized?: string;
  temporal_order?: number | null;
  chapter_id?: string | null;
  character_refs?: CharacterRef[];
  location_ref?: LocationRef | null;
  causes?: string;
  consequences?: string;
}

// --- AI Analysis (existing endpoint) ---

export interface TimelineAnalysisEvent {
  event_name: string;
  description: string;
  timestamp: string;
  chapter_reference: string;
  characters_involved: string[];
  location: string;
  causes: string[];
  consequences: string[];
}

export interface TimelineAnalysis {
  timeline_events: TimelineAnalysisEvent[];
  temporal_conflicts: string[];
  coverage_gaps: string[];
  overall_assessment: string;
}

// --- Filters ---

export interface TimelineFilters {
  event_type?: TimelineEventType;
  chapter_id?: string;
  source?: TimelineEventSource;
  is_confirmed?: boolean;
}
