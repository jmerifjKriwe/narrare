import type { KBEntityType } from "@/lib/api/kb";

export type KBMode = "detail" | "create" | "assist" | "analysis" | "consistency" | "graph" | "wiki";

export interface KBUrlState {
  type: KBEntityType | null;
  mode: KBMode;
  entryId: string | null;
  query: string;
}

const KB_TYPES = new Set<KBEntityType>([
  "character",
  "concept",
  "faction",
  "location",
  "object",
  "setting",
  "system",
  "timeline",
]);

const KB_MODES = new Set<KBMode>([
  "detail",
  "create",
  "assist",
  "analysis",
  "consistency",
  "graph",
  "wiki",
]);

export const EMPTY_KB_SEARCH_QUERY = "";

export function parseKBUrlState(searchParams: URLSearchParams): KBUrlState {
  const typeParam = searchParams.get("type");
  const modeParam = searchParams.get("mode");
  return {
    type: KB_TYPES.has(typeParam as KBEntityType) ? (typeParam as KBEntityType) : null,
    mode: KB_MODES.has(modeParam as KBMode) ? (modeParam as KBMode) : "detail",
    entryId: searchParams.get("entry"),
    query: searchParams.get("q") ?? EMPTY_KB_SEARCH_QUERY,
  };
}

export function serializeKBUrlState(state: KBUrlState): URLSearchParams {
  const params = new URLSearchParams();
  if (state.type) params.set("type", state.type);
  if (state.mode !== "detail") params.set("mode", state.mode);
  if (state.entryId) params.set("entry", state.entryId);
  if (state.query.trim().length > 0) params.set("q", state.query.trim());
  return params;
}
