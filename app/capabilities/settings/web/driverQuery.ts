/**
 * The driver read (W8 Task 5): the instance's driver kind as one backend
 * word — `fake` while every assignable task's serving tier is the local
 * fake adapter, `configured` once any provider adapter answers. The
 * settings surface's offline card reads it for the backend's own truth
 * instead of inferring across the task cascade: the card stands only on
 * `fake`, and a refusal or an outage throws — the page hides the card
 * rather than claim a driver it could not see.
 *
 * Capability-local (the setup gate's `setupStatusQuery` precedent, the
 * tasks seam's twin): only this surface reads it, so it does not join the
 * shell's shared seam. The key stands OUTSIDE the `["settings"]` prefix on
 * purpose — the profile row's writes invalidate that prefix, and a name or
 * goal change never moves the cascade.
 */
import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import { client, type Driver } from "@shell/lib/api/client";

export function useDriver(): UseQueryResult<Driver> {
  return useQuery({
    queryKey: ["settings-driver"],
    refetchOnWindowFocus: false,
    queryFn: async () => {
      const { data, response } = await client.GET("/api/settings/driver");
      if (!response.ok || !data) throw new Error(`driver unavailable: ${response.status}`);
      return data;
    },
  });
}
