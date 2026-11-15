import { useSuspenseQuery } from "@tanstack/react-query";

import { setupStatusQueryOptions } from "./setupStatusQuery";

/**
 * Whether this instance has been set up — the one fact the wizard's faces
 * observe (the provisioning step reads it so the 409's invalidation refetches
 * while the step still watches). The question itself lives in
 * `setupStatusQueryOptions`, shared with the route loaders so the hook and
 * the gates read one cache entry; the key is the seam, not this hook's
 * business.
 *
 * A suspense query on purpose: the loading state is the root's bare
 * suspension. While the answer is in flight the hook throws the fetch
 * promise and the shell root's Suspense boundary holds the gap — nothing
 * invented; a failed answer throws to the root's error screen instead of
 * dressing an unreachable service up as welcome or landing. `isLoading`
 * rides along for consumers that want the flag; under the boundary it is
 * only ever read once the answer stands.
 */
export function useSetupStatus(): { complete: boolean; isLoading: boolean } {
  const query = useSuspenseQuery(setupStatusQueryOptions);
  return { complete: query.data, isLoading: query.isLoading };
}
