/**
 * The tasks read (W7 Task 3's review fix): every known task key with the
 * tier that actually serves it. The settings surface's offline card reads
 * it for the backend's own truth — the card may claim „local fake driver
 * active" only while every assignable task answers `kind: "fake"`; a task
 * served by a configured provider hides the card, and an audit-only row
 * (kind `"audit"`, no serving tier, `assignable: false`) contradicts
 * nothing because no driver answers it at all.
 *
 * Capability-local (the setup gate's `setupStatusQuery` precedent): only
 * this surface reads it, so it does not join the shell's shared seam. The
 * key stands OUTSIDE the `["settings"]` prefix on purpose — the profile
 * row's writes invalidate that prefix, and a name or goal change never
 * moves the cascade. A refusal or an outage throws: the page hides the
 * card rather than claim a driver it could not see.
 */
import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import { client, type TaskEffective } from "@shell/lib/api/client";

export function useSettingsTasksQuery(): UseQueryResult<TaskEffective[]> {
  return useQuery({
    queryKey: ["settings-tasks"],
    refetchOnWindowFocus: false,
    queryFn: async () => {
      const { data, response } = await client.GET("/api/settings/tasks");
      if (!response.ok || !data) throw new Error(`tasks unavailable: ${response.status}`);
      return data;
    },
  });
}
