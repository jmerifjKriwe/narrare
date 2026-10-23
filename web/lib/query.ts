import {
  QueryClient,
  useMutation,
  useQuery,
  type UseMutationResult,
  type UseQueryResult,
} from "@tanstack/react-query";

import { client, type Novel, type NovelCreate } from "./api/client";

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
    // No refetch on window focus: a focus refetch while the service is down
    // would erase the locale adopted at boot. The row changes only through
    // the switcher, which invalidates this key itself.
    refetchOnWindowFocus: false,
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

/**
 * The library list, cached under the writing capability's `["novels"]` key.
 * An answer that is not ok throws, so the cache holds either the list or
 * the failure — never a half-current list.
 */
export function useNovelsQuery(): UseQueryResult<Novel[]> {
  return useQuery({
    queryKey: ["novels"],
    queryFn: async () => {
      const { data, response } = await client.GET("/api/writing/novels");
      if (!response.ok) throw new Error(`novels unavailable: ${response.status}`);
      return data ?? [];
    },
  });
}

/**
 * Creating a novel: the first mutation under the spec 5.10 convention. The
 * write invalidates `["novels"]` instead of patching the cached list by
 * hand, so every view of the key refetches from the row that changed. The
 * list updates when that refetch lands; the caller's own state (the form)
 * does not wait for it.
 */
export function useCreateNovel(): UseMutationResult<Novel, Error, NovelCreate> {
  return useMutation({
    mutationFn: async (input: NovelCreate) => {
      const { data, response } = await client.POST("/api/writing/novels", { body: input });
      if (!response.ok || !data) throw new Error(`create refused: ${response.status}`);
      return data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["novels"] });
    },
  });
}
