/**
 * The AI-Regeln surface's query seams (W8 Task 9): the providers, the
 * presets, the models, the stored assignments and their writes — one file
 * beside the tasks and driver reads (`tasksQuery.ts`, `driverQuery.ts`),
 * the capability-local precedent: only this surface reads them, so they do
 * not join the shell's shared seam.
 *
 * Every key stands OUTSIDE the `["settings"]` prefix on purpose — the
 * profile row's writes invalidate that prefix, and a name or goal change
 * never moves the provider cascade. The keys ARE each other's invalidation
 * family: a model write invalidates the tasks and driver reads beside the
 * models, because the first model mints the default and every default moves
 * the cascade; an assignment write invalidates the stored rows beside the
 * tasks and driver reads, for the same reason. A provider write touches
 * providers alone — a provider without models answers nothing (the delete
 * guard proves it), so no cascade can move behind it.
 *
 * Reads are strict: a refusal or an outage throws, and the page answers
 * with its outage face and its retry — never dressed-up nulls. Writes
 * enrich the failure with the wire's status and detail, so the faces can
 * name the refusal families the backend answers with (the delete guard's
 * 409, the discovery's 502, the key store's 503).
 */
import { useMutation, useQuery, type UseMutationResult, type UseQueryResult } from "@tanstack/react-query";

import {
  client,
  type Assignment,
  type Model,
  type ModelTestResult,
  type Preset,
  type Provider,
  type ProviderCreated,
} from "@shell/lib/api/client";
import { queryClient } from "@shell/lib/query";

/** The wire's failure, enriched for the faces: the status picks the copy
 *  family, the detail carries the backend's own sentence (the guard's
 *  named models, the refused field's message). */
export type WireError = Error & { status?: number; detail?: unknown };

function enrich(cause: unknown, what: string): WireError {
  const failure = cause as { response?: Response; error?: { detail?: unknown } };
  const response = failure?.response;
  const detail = failure?.error?.detail;
  return Object.assign(new Error(`${what} refused: ${response?.status ?? "unknown"}`), {
    status: response?.status,
    detail,
  });
}

function invalidate(keys: string[][]): void {
  for (const key of keys) void queryClient.invalidateQueries({ queryKey: key });
}

/** The cascade family: every read the model and assignment writes move.
 *  The provider writes stand outside it — see the file comment. */
const CASCADE_KEYS: string[][] = [
  ["settings-models"],
  ["settings-assignments"],
  ["settings-tasks"],
  ["settings-driver"],
];

export function useProviders(): UseQueryResult<Provider[]> {
  return useQuery({
    queryKey: ["settings-providers"],
    refetchOnWindowFocus: false,
    queryFn: async () => {
      const { data, response } = await client.GET("/api/settings/providers");
      if (!response.ok || !data) throw new Error(`providers unavailable: ${response.status}`);
      return data;
    },
  });
}

export function usePresets(): UseQueryResult<Preset[]> {
  return useQuery({
    queryKey: ["settings-presets"],
    // The presets are the kernel table's frozen rows joined with the static
    // catalog — a settings visit never re-asks what cannot change.
    staleTime: Infinity,
    refetchOnWindowFocus: false,
    queryFn: async () => {
      const { data, response } = await client.GET("/api/settings/presets");
      if (!response.ok || !data) throw new Error(`presets unavailable: ${response.status}`);
      return data;
    },
  });
}

export function useModels(): UseQueryResult<Model[]> {
  return useQuery({
    queryKey: ["settings-models"],
    refetchOnWindowFocus: false,
    queryFn: async () => {
      const { data, response } = await client.GET("/api/settings/models");
      if (!response.ok || !data) throw new Error(`models unavailable: ${response.status}`);
      return data;
    },
  });
}

export function useAssignments(): UseQueryResult<Assignment[]> {
  return useQuery({
    queryKey: ["settings-assignments"],
    refetchOnWindowFocus: false,
    queryFn: async () => {
      const { data, response } = await client.GET("/api/settings/assignments");
      if (!response.ok || !data) throw new Error(`assignments unavailable: ${response.status}`);
      return data;
    },
  });
}

/** The provider create: the ONE response that carries the full key. The
 *  returned row is handed to the caller untouched — the key-once moment is
 *  the caller's face — and the list invalidation re-asks the mask. */
export function useCreateProvider(): UseMutationResult<
  ProviderCreated,
  WireError,
  {
    name: string;
    kind: string;
    base_url: string | null;
    models_url?: string | null;
    vendor?: string | null;
    api_key?: string | null;
  }
> {
  return useMutation({
    mutationFn: async (body) => {
      const { data, error, response } = await client.POST("/api/settings/providers", { body });
      if (!response.ok || !data) throw enrich({ response, error }, "provider create");
      return data;
    },
    onSuccess: () => {
      invalidate([["settings-providers"]]);
    },
  });
}

/** The provider patch: the kind is what the provider is — not editable;
 *  an absent or empty `api_key` keeps the stored one. */
export function useUpdateProvider(): UseMutationResult<
  Provider,
  WireError,
  { id: string; changes: { name?: string; base_url?: string | null; api_key?: string | null } }
> {
  return useMutation({
    mutationFn: async ({ id, changes }) => {
      const { data, error, response } = await client.PATCH("/api/settings/providers/{provider_id}", {
        params: { path: { provider_id: id } },
        body: changes,
      });
      if (!response.ok || !data) throw enrich({ response, error }, "provider update");
      return data;
    },
    onSuccess: () => {
      invalidate([["settings-providers"]]);
    },
  });
}

export function useDeleteProvider(): UseMutationResult<void, WireError, { id: string }> {
  return useMutation({
    mutationFn: async ({ id }) => {
      const { error, response } = await client.DELETE("/api/settings/providers/{provider_id}", {
        params: { path: { provider_id: id } },
      });
      if (!response.ok) throw enrich({ response, error }, "provider delete");
    },
    onSuccess: () => {
      // The guard refuses a delete a model still points at, so no cascade
      // can move behind a landed 204 — providers alone move.
      invalidate([["settings-providers"]]);
    },
  });
}

export function useCreateModel(): UseMutationResult<
  Model,
  WireError,
  { name: string; provider_id: string; model: string }
> {
  return useMutation({
    mutationFn: async (body) => {
      const { data, error, response } = await client.POST("/api/settings/models", { body });
      if (!response.ok || !data) throw enrich({ response, error }, "model create");
      return data;
    },
    onSuccess: () => {
      // The first model mints the default: the cascade moves on every
      // create, so the whole family re-asks.
      invalidate(CASCADE_KEYS);
    },
  });
}

export function useSetDefaultModel(): UseMutationResult<Model, WireError, { id: string }> {
  return useMutation({
    mutationFn: async ({ id }) => {
      const { data, error, response } = await client.PATCH("/api/settings/models/{model_id}", {
        params: { path: { model_id: id } },
        body: { is_default: true },
      });
      if (!response.ok || !data) throw enrich({ response, error }, "default handover");
      return data;
    },
    onSuccess: () => {
      invalidate(CASCADE_KEYS);
    },
  });
}

export function useDeleteModel(): UseMutationResult<void, WireError, { id: string }> {
  return useMutation({
    mutationFn: async ({ id }) => {
      const { error, response } = await client.DELETE("/api/settings/models/{model_id}", {
        params: { path: { model_id: id } },
      });
      if (!response.ok) throw enrich({ response, error }, "model delete");
    },
    onSuccess: () => {
      // The delete cascades the model's assignments at the database — the
      // affected tasks fall back down the resolution cascade, so the whole
      // family re-asks.
      invalidate(CASCADE_KEYS);
    },
  });
}

/** One cheap completion through the model's provider, audited as
 *  `settings.test`. The answer is never an HTTP refusal — the test ran, and
 *  the 200 carries ok/error/latency. The write invalidates the models read:
 *  the audit row's mark (a later success clears a standing failure) lives
 *  there. */
export function useTestModel(): UseMutationResult<
  ModelTestResult,
  WireError,
  { id: string }
> {
  return useMutation({
    mutationFn: async ({ id }) => {
      const { data, error, response } = await client.POST("/api/settings/models/{model_id}/test", {
        params: { path: { model_id: id } },
      });
      if (!response.ok || !data) throw enrich({ response, error }, "model test");
      return data;
    },
    onSuccess: () => {
      invalidate([["settings-models"]]);
    },
  });
}

/** The discovery ask: the provider's own list URL, plain httpx behind the
 *  API. The named refusals: 409 (a fake has no endpoint), 502 (the endpoint
 *  did not answer, or its key is gone), 404 (no such provider of the
 *  user's). */
export function useProviderModels(): UseMutationResult<string[], WireError, { id: string }> {
  return useMutation({
    mutationFn: async ({ id }) => {
      const { data, error, response } = await client.GET("/api/settings/providers/{provider_id}/models", {
        params: { path: { provider_id: id } },
      });
      if (!response.ok || !data) throw enrich({ response, error }, "model discovery");
      return data;
    },
  });
}

/** One assignment's write: the model (or the cascade floor with `null`) and
 *  the output profile — a vocabulary name, or the custom choice as its own
 *  number. The PUT is whole: the caller carries BOTH fields on every save,
 *  because the column has no two-state semantics — an omitted profile
 *  states `balanced` by that fact. */
export function useAssignTask(): UseMutationResult<
  Assignment,
  WireError,
  { taskKey: string; profileId: string | null; outputProfile?: string | number }
> {
  return useMutation({
    mutationFn: async ({ taskKey, profileId, outputProfile }) => {
      const body: { profile_id: string | null; output_profile?: string | number } = {
        profile_id: profileId,
      };
      if (outputProfile !== undefined) body.output_profile = outputProfile;
      const { data, error, response } = await client.PUT("/api/settings/assignments/{task_key}", {
        params: { path: { task_key: taskKey } },
        body,
      });
      if (!response.ok || !data) throw enrich({ response, error }, "assignment");
      return data;
    },
    onSuccess: () => {
      invalidate(CASCADE_KEYS);
    },
  });
}
