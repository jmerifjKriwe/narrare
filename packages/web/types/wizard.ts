// Setup Wizard types

import type { AIProvider } from "@/lib/providers.generated";

// AIProvider is generated from the provider catalog SSOT (ADR-099); this module
// re-exports it rather than declaring a second copy (RULE-17). The import binds
// the name locally for `WizardState` below; the re-export keeps `@/types`
// handing out the same union.
export type { AIProvider };

export type StarterContent = "blank" | "demo_fantasy" | "demo_scifi" | "demo_german" | "import";

export type StoryStructure =
  | "three_act"
  | "five_act"
  | "heros_journey"
  | "save_the_cat"
  | "seven_point";

export type StoryTone =
  | "balanced"
  | "dramatic"
  | "humorous"
  | "suspenseful"
  | "contemplative"
  | "romantic"
  | "dark"
  | "adventurous"
  | "quiet";

export interface ProviderModel {
  id: string;
  name: string;
  context_window: number | null;
  supports_streaming: boolean;
}

/**
 * Where a model catalog list came from — mirrors the backend
 * `ModelCatalogProvenance.source` (setup/constants.py: LIVE_CATALOG_SOURCE /
 * FALLBACK_CATALOG_SOURCE). The UI uses this to flag a stale/offline list.
 */
export type ModelCatalogSource = "live" | "bundled-fallback";

/**
 * Provenance metadata for an AvailableModelsResponse — RULE-17 contract match
 * with the backend `ModelCatalogProvenance` Pydantic model
 * (apps/api/narrare/setup/provider_schemas.py).
 *
 * - `source === "live"`: models fetched in real time, `last_reviewed` is null.
 * - `source === "bundled-fallback"`: offline static fallback list;
 *   `last_reviewed` is the ISO date the fallback was last refreshed.
 */
export interface ModelCatalogProvenance {
  source: ModelCatalogSource;
  last_reviewed: string | null;
}

export interface DemoProjectInfo {
  id: StarterContent;
  title: string;
  writing_language: string;
  genre: string;
  chapter_count: number;
  character_count: number;
  word_count: number;
  description: string;
  /** Author name from demo metadata — used to prefill wizard Step 3 */
  author: string;
  /** One-sentence story summary from demo metadata */
  logline: string;
  /** Point of view from demo metadata */
  pov: string;
  /** Tags from demo metadata */
  tags: string[];
}

export interface WizardState {
  // Step 1
  project_name: string;
  writing_language: string;
  autosave_interval: number;
  // Step 2
  title: string;
  author: string;
  genre: string;
  logline: string;
  story_structure: StoryStructure;
  tone: StoryTone;
  // Step 3
  starter: StarterContent;
  // Step 4
  provider: AIProvider;
  api_key: string;
  model: string;
  ollama_url: string;
  zai_endpoint?: string;
  // Provider skip flag — true when Step 4 was skipped
  skip_provider?: boolean;
}
