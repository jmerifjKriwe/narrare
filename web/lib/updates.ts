/**
 * The update check's web seam: one cache entry, the start ask and the hourly
 * re-check. The shell owns this module (rule 1) — the banner, the toast and
 * the release-notes dialog consume it, and the kernel serves the answer.
 *
 * The check is a convenience, never a gate: a failure is swallowed by the
 * start and interval asks, so the shell simply shows nothing. The observer
 * query carries the cache back to React (`enabled: false` — it never fetches
 * on its own; `fetchQuery` is what asks), which keeps the start check the
 * only first request.
 */
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import { client } from "./api/client";
import type { components } from "./api/schema";

export type UpdateRead = components["schemas"]["UpdateRead"];
export const UPDATE_KEY = ["updates"] as const;

export async function fetchUpdate(force: boolean): Promise<UpdateRead> {
  const { data, response } = await client.GET("/api/updates", {
    params: { query: { force } },
  });
  if (!response.ok || data === undefined) {
    throw new Error(`update check failed: ${response.status}`);
  }
  return data;
}

/** Swallow a failed background check: offline is an answer, not an error. */
function silent(promise: Promise<UpdateRead>): void {
  void promise.catch(() => undefined);
}

export function useUpdateCheck() {
  const queryClient = useQueryClient();
  // The observer re-renders when fetchQuery writes the cache; it does not
  // fetch on its own, so the start check below is the only first request.
  const query = useQuery({
    queryKey: UPDATE_KEY,
    queryFn: () => fetchUpdate(false),
    enabled: false,
    staleTime: Infinity,
    retry: false,
  });
  useEffect(() => {
    silent(
      queryClient.fetchQuery({
        queryKey: UPDATE_KEY,
        queryFn: () => fetchUpdate(true),
        staleTime: 0,
      }),
    );
    const id = window.setInterval(() => {
      if (document.visibilityState === "visible") {
        silent(
          queryClient.fetchQuery({
            queryKey: UPDATE_KEY,
            queryFn: () => fetchUpdate(false),
            staleTime: 0,
          }),
        );
      }
    }, 60 * 60 * 1000);
    return () => window.clearInterval(id);
  }, [queryClient]);
  return query;
}
