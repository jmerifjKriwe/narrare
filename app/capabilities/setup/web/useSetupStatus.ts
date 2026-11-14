import { useSuspenseQuery } from "@tanstack/react-query";

import { client } from "@shell/lib/api/client";

/**
 * Whether this instance has been set up — the one fact the `/` gate reads.
 * The state flips once per instance, so the answer never goes stale on its
 * own: `staleTime: Infinity` keeps a remount on the cached answer instead of
 * asking again, and the write that flips the state invalidates
 * `["setup", "status"]` — the key is the seam, not this hook's business.
 *
 * A suspense query on purpose: the gate's loading state is the root's bare
 * suspension. While the answer is in flight the hook throws the fetch
 * promise and the shell root's Suspense boundary holds the gap — nothing
 * invented; a failed answer throws to the root's error screen instead of
 * dressing an unreachable service up as welcome or landing. `isLoading`
 * rides along for consumers that want the flag; under the boundary it is
 * only ever read once the answer stands.
 */
export function useSetupStatus(): { complete: boolean; isLoading: boolean } {
  const query = useSuspenseQuery({
    queryKey: ["setup", "status"],
    staleTime: Infinity,
    queryFn: async () => {
      const { data, response } = await client.GET("/api/setup/status");
      if (!response.ok || !data) {
        throw new Error(`setup status unavailable: ${response.status}`);
      }
      return data.complete;
    },
  });
  return { complete: query.data, isLoading: query.isLoading };
}
