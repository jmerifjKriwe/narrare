/**
 * TanStack Query keys for the Notes domain (NOTES-001).
 *
 * Centralized (mirrors seriesKeys.ts / kbKeys.ts) so invalidations stay
 * consistent across hooks.
 *
 * Key shape:
 *   ["notes"]                    — list + wildcard prefix
 *   ["notes", "list", filters]   — filtered list
 *   ["notes", "detail", noteId]  — single note
 *   ["notes", "tags", q]         — tag autocomplete
 *   ["notes", "search", body]    — semantic search
 */

export const notesKeys = {
  all: ["notes"] as const,
  list: (filters?: object) => [...notesKeys.all, "list", filters ?? {}] as const,
  detail: (noteId: string) => [...notesKeys.all, "detail", noteId] as const,
  tags: (q?: string) => [...notesKeys.all, "tags", q ?? ""] as const,
  search: (body: object) => [...notesKeys.all, "search", body] as const,
};
