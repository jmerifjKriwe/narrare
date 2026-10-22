import { QueryClient, useQuery, type UseQueryResult } from "@tanstack/react-query";

import { client } from "./api/client";

/**
 * The one query client. `retry: false` because the backend is a local
 * service: it is either up or the page reports the outage itself, and a
 * retry only delays that report. `staleTime: 30_000` because an answer is
 * recent enough for half a minute, so a remount reads the cache instead of
 * asking again.
 */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
      staleTime: 30_000,
    },
  },
});

/**
 * The stored settings row, as `{ locale }` — the same contract the boot
 * effect in the shell used to own: an answer carries the row's locale, an
 * unreachable service resolves to `locale: null`, and the browser's
 * language decides from there. The outage is an answer, not an error
 * state, so no consumer needs a fallback branch of its own.
 */
export function useSettingsQuery(): UseQueryResult<{ locale: string | null }> {
  return useQuery({
    queryKey: ["settings"],
    queryFn: async () => {
      try {
        const { data } = await client.GET("/api/settings");
        return { locale: data?.locale ?? null };
      } catch {
        return { locale: null };
      }
    },
  });
}
