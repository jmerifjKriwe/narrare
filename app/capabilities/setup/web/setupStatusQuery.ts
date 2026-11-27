import { queryOptions } from "@tanstack/react-query";

import { client } from "@shell/lib/api/client";
import { refused } from "@shell/lib/query";

/**
 * The one setup-status question, as shared query options. Two readers ask it
 * — the suspense hook the wizard's faces observe (`useSetupStatus`) and the
 * route loaders that gate `/setup` and the steps (`routes.tsx`) — and both
 * must land on the same cache entry, so the key, the freshness and the ask
 * live here once. The state flips once per instance, so `staleTime: Infinity`
 * keeps a remount (or a second loader) on the cached answer instead of asking
 * again; the provisioning write that flips the state invalidates
 * `["setup", "status"]` — the key is the seam, not either reader's business.
 * A fresh page load asks anew (the cache is empty), which is what keeps a
 * refresh after setup honest.
 *
 * A non-ok answer throws: an unreachable service is the root error screen's
 * fact, never a guessed welcome or a guessed shelf.
 */
export const setupStatusQueryOptions = queryOptions({
  queryKey: ["setup", "status"],
  staleTime: Infinity,
  queryFn: async () => {
    const { data, error, response } = await client.GET("/api/setup/status");
    if (!response.ok) {
      throw refused("setup status unavailable", response, error);
    }
    if (!data) {
      // A 2xx without a body is no refusal: the face's fallback names it.
      throw new Error(`setup status unavailable: ${response.status}`);
    }
    return data.complete;
  },
});
