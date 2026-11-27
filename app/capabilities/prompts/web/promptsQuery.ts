/**
 * The prompts surface's query seams (W8 Task 12): the catalog list, the
 * editor's detail, the save and reset writes, the diff, and the live test's
 * SSE transport — one file beside the page, the capability-local precedent
 * (the AI-Regeln surface's `aiRulesQuery.ts`): only this surface reads them,
 * so they do not join the shell's shared seam.
 *
 * The query keys ARE each other's invalidation family under the `["prompts"]`
 * prefix: a save moves the catalog's marks beside the editor's detail, so the
 * whole prefix re-asks. A reset is narrower — it resets the exact detail entry
 * and refreshes the catalog/diff family, never a second detail read. Reads are
 * strict: a refusal or an outage throws, and the page answers with its outage
 * face and its retry — never dressed-up nulls. Writes enrich the failure with
 * the wire's status and body, so the faces can name the refusal families the
 * backend answers with (the save gate's 422 by reason).
 *
 * The live test rides `fetch`, not the typed client: openapi-fetch buffers
 * the whole answer before it parses, and the test's answer must arrive piece
 * by piece — the writing continuation's transport (W4), the same `readSse`
 * reader, the same frame grammar (one context frame, then deltas, then the
 * one terminal event). The pre-stream failures (409/429/502/503 and the
 * save gate's 422) are JSON answers, not SSE — named by their status.
 */
import { useIsMutating, useMutation, useQuery, type UseMutationResult, type UseQueryResult } from "@tanstack/react-query";

import {
  client,
  type PromptDetail,
  type PromptDiff,
  type PromptPreview,
  type PromptSummary,
} from "@shell/lib/api/client";
import { readSse } from "@shell/lib/api/sse";
import { queryClient } from "@shell/lib/query";

/** The wire's failure, enriched for the faces: the status picks the copy
 *  family, the body carries the backend's own refusal (the gate's
 *  `{reason, detail}` with its optional `line`/`name` fact, beside the
 *  framework's validation list). */
export type WireError = Error & { status?: number; body?: unknown };

function enrich(cause: unknown, what: string): WireError {
  const failure = cause as { response?: Response; error?: unknown };
  const response = failure?.response;
  return Object.assign(new Error(`${what} refused: ${response?.status ?? "unknown"}`), {
    status: response?.status,
    body: failure?.error,
  });
}

function invalidate(): void {
  void queryClient.invalidateQueries({ queryKey: ["prompts"] });
}

function invalidateCatalog(): void {
  void queryClient.invalidateQueries({ queryKey: ["prompts", "list"] });
  void queryClient.invalidateQueries({ queryKey: ["prompts", "diff"] });
}

/** One shared mutation identity: every mounted observer can see a reset
 *  pending, including an editor mounted after the original one unmounted. */
export const PROMPT_RESET_MUTATION_KEY = ["prompts", "reset"] as const;

function promptResetMutationKey(key: string | null, novelId: string | null) {
  return [...PROMPT_RESET_MUTATION_KEY, key, novelId] as const;
}

function promptResetRevisionQueryKey(key: string | null, novelId: string | null) {
  return ["prompts", "reset-revision", key, novelId] as const;
}

export function useResetPending(): boolean {
  return useIsMutating({ mutationKey: PROMPT_RESET_MUTATION_KEY }) > 0;
}

/** The latest successful reset for this exact editing scope. This tiny
 *  cache-only entry outlives MutationCache GC, so clearing an old mutation
 *  cannot roll the editor identity backward and discard an unsaved draft. */
export function useResetRevision(key: string | null, novelId: string | null): number {
  return useQuery({
    queryKey: promptResetRevisionQueryKey(key, novelId),
    initialData: 0,
    enabled: false,
    staleTime: Infinity,
    gcTime: Infinity,
  }).data;
}

function promptDetailQueryKey(key: string | null, novelId: string | null) {
  return ["prompts", "detail", key, novelId] as const;
}

function promptDetailScopeQueryKey(key: string | null, novelId: string | null) {
  // A global override is inherited by every novel detail for this key. A
  // novel reset, by contrast, owns only its one exact scope.
  return novelId === null
    ? (["prompts", "detail", key] as const)
    : promptDetailQueryKey(key, novelId);
}

/** The catalog list: one ask shape, the scope query always named. */
export function usePromptsList(novelId: string | null): UseQueryResult<PromptSummary[]> {
  return useQuery({
    queryKey: ["prompts", "list", novelId],
    refetchOnWindowFocus: false,
    queryFn: async () => {
      const { data, response } = await client.GET("/api/prompts", {
        params: { query: novelId ? { novel_id: novelId } : {} },
      });
      if (!response.ok || !data) throw new Error(`prompts unavailable: ${response.status}`);
      return data;
    },
  });
}

/** One key as the editor shows it, for the editing scope: the bundled
 *  source, the legend, the override in force, the effective source. */
async function fetchPromptDetail(key: string, novelId: string | null): Promise<PromptDetail> {
  // The scope ask always names its query: an empty one is the global
  // tier, a novel id the novel's — one shape to assert on.
  const { data, response } = await client.GET("/api/prompts/{key}", {
    params: { path: { key }, query: novelId ? { novel_id: novelId } : {} },
  });
  if (!response.ok || !data) throw new Error(`prompt unavailable: ${response.status}`);
  return data;
}

export function usePromptDetail(
  key: string | null,
  novelId: string | null,
): UseQueryResult<PromptDetail> {
  return useQuery({
    queryKey: promptDetailQueryKey(key, novelId),
    refetchOnWindowFocus: false,
    enabled: key !== null,
    queryFn: () => fetchPromptDetail(key as string, novelId),
  });
}

/** The saved tiers side by side: the bundled template against the override
 *  in force for the scope. Asked only while the panel stands open. */
export function usePromptDiff(
  key: string | null,
  novelId: string | null,
  open: boolean,
): UseQueryResult<PromptDiff> {
  return useQuery({
    queryKey: ["prompts", "diff", key, novelId],
    refetchOnWindowFocus: false,
    enabled: key !== null && open,
    queryFn: async () => {
      const { data, response } = await client.GET("/api/prompts/{key}/diff", {
        params: { path: { key: key as string }, query: novelId ? { novel_id: novelId } : {} },
      });
      if (!response.ok || !data) throw new Error(`diff unavailable: ${response.status}`);
      return data;
    },
  });
}

/** One override write. `novelId` null saves the global tier; the fresh
 *  detail answers and the whole `["prompts"]` family re-asks (the catalog's
 *  mark moves with the landed write). */
export function useSavePrompt(): UseMutationResult<
  PromptDetail,
  WireError,
  { key: string; content: string; novelId: string | null }
> {
  return useMutation({
    mutationFn: async ({ key, content, novelId }) => {
      const { data, response, error } = await client.PUT("/api/prompts/{key}", {
        params: { path: { key } },
        body: { content, novel_id: novelId },
      });
      if (!response.ok || !data) throw enrich({ response, error }, "prompt save");
      return data;
    },
    onSuccess: invalidate,
  });
}

/** The scope's override reset (the other tier untouched). The successful
 *  DELETE resets the scope's detail entries at hook level and lets active
 *  observers fetch inherited detail once. A global reset covers every novel
 *  detail for that prompt key; a novel reset covers only its exact entry.
 *  The editor never owns that completion, so unmounting cannot lose it or
 *  leave a stale cache behind. */
export function useResetPrompt(
  key: string | null,
  novelId: string | null,
): UseMutationResult<
  void,
  WireError,
  { key: string; novelId: string | null }
> {
  return useMutation({
    mutationKey: promptResetMutationKey(key, novelId),
    mutationFn: async ({ key, novelId }) => {
      const { response, error } = await client.DELETE("/api/prompts/{key}", {
        params: { path: { key }, query: novelId ? { novel_id: novelId } : {} },
      });
      if (!response.ok) throw enrich({ response, error }, "prompt reset");
    },
    onSuccess: async (_data, { key, novelId }) => {
      const queryKey = promptDetailScopeQueryKey(key, novelId);
      const exact = novelId !== null;
      try {
        // A detail refetch that began before the DELETE must not win after
        // it. Cancel first, then reset notifies active observers and refetches
        // them once; inactive inheriting novel entries become unset.
        await queryClient.cancelQueries({ queryKey, exact });
        await queryClient.resetQueries({ queryKey, exact });
      } finally {
        // The DELETE committed even if the fresh detail read is down. Its
        // completion still advances the cache-only editor revision; the
        // detail query's own error owns the page's outage/retry face.
        queryClient.setQueryData<number>(
          promptResetRevisionQueryKey(key, novelId),
          (current) => (current ?? 0) + 1,
        );
        invalidateCatalog();
      }
    },
  });
}

/** The provider-free render: the editor draft (absent body = the saved
 *  effective) at sample scope. A render refusal is the named 422; a
 *  contract failure rides the 200 as a diagnostic. */
export function usePreviewPrompt(): UseMutationResult<
  PromptPreview,
  WireError,
  { key: string; novelId: string | null; draft: string | null }
> {
  return useMutation({
    mutationFn: async ({ key, novelId, draft }) => {
      const { data, response, error } = await client.POST("/api/prompts/{key}/preview", {
        params: { path: { key }, query: novelId ? { novel_id: novelId } : {} },
        // Absent body: the saved effective is the source under preview —
        // the key stays present, spelled undefined, so the wire shape is
        // assertable ("with/without draft" is one call shape).
        body: draft === null ? undefined : { content: draft },
      });
      if (!response.ok || !data) throw enrich({ response, error }, "prompt preview");
      return data;
    },
  });
}

/** The context frame's payload: what the test rode — the source mode, the
 *  provider kind (the fake's honest mark among it), the scope, the facts. */
export interface LiveTestContext {
  key: string;
  source: string;
  provider: string;
  novel_id: string | null;
  facts: Record<string, string>;
}

/** How the live test's progress reaches the editor's faces. */
export interface LiveTestSink {
  context(context: LiveTestContext): void;
  delta(text: string): void;
  done(): void;
  /** A coded pre-stream face (409/429/502/503) or a mid-stream error frame;
   *  `retryAfter` rides the 429's header, and `status` the pre-stream
   *  answer's HTTP status (a coded 502 is still a provider failure, while a
   *  mid-stream frame has no status to tell it by). */
  error(code: string, retryAfter?: number, status?: number): void;
  /** The save gate's 422: the refusal body rides for the family face. */
  refused(body: unknown): void;
  /** The coded faces' transport-level shapes: a non-SSE answer that is none
   *  of the above, and the call that never reached the server. */
  failed(status: number): void;
  network(): void;
}

/** One live-test ask over the writing continuation's transport. The body
 *  carries the editor draft (`null` = the saved effective) and the scope;
 *  the answer streams frame by frame into the sink. */
export async function startLiveTest(
  key: string,
  body: { content: string | null; novel_id: string | null },
  signal: AbortSignal,
  sink: LiveTestSink,
): Promise<void> {
  let response: Response;
  try {
    // Fixed same-origin base + the registry's closed key set, concatenated
    // (never interpolated) — one path segment, no SSRF-shaped template.
    // SSRF false positive: the base is a constant relative path and the key
    // a backend-owned registry name — no user-controlled URL (PR #901's
    // Codacy round, the continuation's own spelling).
    response = await fetch("/api/prompts/" + encodeURIComponent(key) + "/live-test", {
      // nosemgrep: Semgrep_rules_lgpl_javascript_ssrf_rule-node-ssrf
      method: "POST",
      signal,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch (cause) {
    if (!signal.aborted) sink.network();
    void cause;
    return;
  }
  if (signal.aborted) return;
  if (!response.ok || response.body === null) {
    // The pre-stream failures are JSON answers, not a stream — read the
    // body, release the connection.
    const raw = await response.text().catch(() => "");
    if (signal.aborted) return;
    let body: unknown = null;
    try {
      body = raw === "" ? null : JSON.parse(raw);
    } catch {
      body = null;
    }
    if (response.status === 422) {
      sink.refused(body);
      return;
    }
    const coded = (body as { detail?: { code?: unknown } } | null)?.detail;
    const code = typeof coded?.code === "string" ? coded.code : null;
    if (code !== null) {
      const retryAfter = response.headers.get("Retry-After");
      sink.error(
        code,
        retryAfter === null ? undefined : Number.parseInt(retryAfter, 10) || undefined,
        response.status,
      );
      return;
    }
    void response.body?.cancel();
    sink.failed(response.status);
    return;
  }
  try {
    for await (const frame of readSse(response.body)) {
      if (signal.aborted) return;
      if (frame.event === "done") {
        sink.done();
        return;
      }
      if (frame.event === "error") {
        let code = "unknown";
        try {
          const payload = JSON.parse(frame.data) as { code?: unknown };
          if (typeof payload.code === "string") code = payload.code;
        } catch {
          // The frame's payload is the contract's own JSON; a broken one
          // names itself unknown.
        }
        sink.error(code);
        return;
      }
      let payload: { context?: unknown; delta?: unknown } | null = null;
      try {
        payload = JSON.parse(frame.data) as { context?: unknown; delta?: unknown };
      } catch {
        payload = null;
      }
      if (payload !== null && isContext(payload.context)) {
        sink.context(payload.context);
        continue;
      }
      if (payload !== null && typeof payload.delta === "string") {
        sink.delta(payload.delta);
      }
    }
    if (!signal.aborted) sink.error("interrupted");
  } catch {
    if (!signal.aborted) sink.error("network");
  }
}

function isContext(value: unknown): value is LiveTestContext {
  if (typeof value !== "object" || value === null) return false;
  const candidate = value as Partial<LiveTestContext>;
  return (
    typeof candidate.key === "string" &&
    typeof candidate.source === "string" &&
    typeof candidate.provider === "string" &&
    typeof candidate.facts === "object" &&
    candidate.facts !== null
  );
}
