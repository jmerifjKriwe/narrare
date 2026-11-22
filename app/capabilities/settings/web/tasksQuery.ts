/**
 * The tasks read (W8 Task 8 extends it): every known task key with the
 * tier that actually serves it. The settings surface's task face renders
 * it — the backend's own cascade truth, one row per known key. The
 * offline card no longer infers its claim from these rows; it reads the
 * driver read (`useDriver`, W8 Task 5), the same resolution reduced to
 * one word.
 *
 * Capability-local (the setup gate's `setupStatusQuery` precedent): only
 * this surface reads it, so it does not join the shell's shared seam. The
 * key stands OUTSIDE the `["settings"]` prefix on purpose — the profile
 * row's writes invalidate that prefix, and a name or goal change never
 * moves the cascade. A refusal or an outage throws: the face never
 * renders rows the wire did not answer.
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
