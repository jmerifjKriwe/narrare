/** Canonical TanStack Query keys for adaptive state (ADR-069 Decision 15).
 *  Every adaptive query/mutation shares the `["adaptive-context", projectId]` root
 *  so a single invalidation propagates to the indicator, dashboard, and panel. */
export const adaptiveKeys = {
  all: ["adaptive-context"] as const,
  context: (projectId: string) => ["adaptive-context", projectId] as const,
  snapshots: (projectId: string) => ["adaptive-context", projectId, "snapshots"] as const,
};
