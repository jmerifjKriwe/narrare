import type { KBEntryListParams, KBSearchParams } from "@/lib/api/kb";

export const kbKeys = {
  all: (novelId: string) => ["kb", novelId] as const,
  entries: (novelId: string) => [...kbKeys.all(novelId), "entries"] as const,
  entriesList: (novelId: string, params?: KBEntryListParams) =>
    [...kbKeys.entries(novelId), params] as const,
  entry: (novelId: string, entryId: string) => [...kbKeys.entries(novelId), entryId] as const,
  search: (novelId: string, params: KBSearchParams) =>
    [...kbKeys.all(novelId), "search", params] as const,
  relationships: (novelId: string, entryId: string) =>
    [...kbKeys.all(novelId), "relationships", entryId] as const,
  inverseSuggestion: (novelId: string, relType: string) =>
    [...kbKeys.all(novelId), "inverse", relType] as const,
  templates: (novelId: string) => [...kbKeys.all(novelId), "templates"] as const,
  template: (novelId: string, entityType: string) =>
    [...kbKeys.templates(novelId), entityType] as const,
  references: (novelId: string, text: string) =>
    [...kbKeys.all(novelId), "references", text] as const,
  autocomplete: (novelId: string, query: string) =>
    [...kbKeys.all(novelId), "autocomplete", query] as const,
  dismissedFindings: (novelId: string) => [...kbKeys.all(novelId), "dismissed"] as const,
};
