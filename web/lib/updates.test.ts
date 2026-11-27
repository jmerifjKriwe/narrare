// @vitest-environment jsdom
/**
 * The update check's web seam: the one fetch behind the shell's banner and
 * the hook's start check. The client is mocked at its module boundary — the
 * request itself is the backend's and the E2E's to verify — so these pins
 * hold the wire shape (the force flag), the answer, the refusal, and the
 * cache key the dismissal invalidates.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { createElement, type ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("./api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./api/client")>();
  return {
    ...actual,
    client: {
      GET: vi.fn(),
      POST: vi.fn(),
      PATCH: vi.fn(),
      PUT: vi.fn(),
      DELETE: vi.fn(),
    },
  };
});

import { client } from "./api/client";
import { ApiError, failureKey } from "./api/errors";
import { UPDATE_KEY, fetchUpdate, useUpdateCheck, type UpdateRead } from "./updates";

/** The client's methods as plain mocks; the real client's generics stay out. */
const api = client as unknown as Record<
  "GET" | "POST" | "PATCH" | "PUT" | "DELETE",
  ReturnType<typeof vi.fn>
>;

function ok(): Response {
  return new Response(null, { status: 200 });
}

const ANSWER: UpdateRead = {
  current_version: "0.5.0",
  latest_version: "v999.0.0",
  update_available: true,
  release_notes: "## Notes\n\n- new",
  release_url: "https://example.test/release",
  dismissed: false,
  checked_at: "2026-11-24T10:00:00Z",
};

function freshClient(): QueryClient {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } });
}

/** The app's own provider shape: one client, the hook's real defaults. */
function wrapperFor(queryClient: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return createElement(QueryClientProvider, { client: queryClient }, children);
  };
}

afterEach(() => {
  vi.clearAllMocks();
  Object.defineProperty(document, "visibilityState", { configurable: true, value: "visible" });
});

describe("fetchUpdate", () => {
  it("asks /api/updates with the force flag and answers the body", async () => {
    api.GET.mockResolvedValue({ data: ANSWER, response: ok() });

    await expect(fetchUpdate(true)).resolves.toEqual(ANSWER);

    expect(api.GET).toHaveBeenCalledWith("/api/updates", {
      params: { query: { force: true } },
    });
  });

  it("keeps a refusal as the failure it is — the status rides the error", async () => {
    api.GET.mockResolvedValue({
      data: undefined,
      response: new Response(null, { status: 503 }),
    });

    const failure = (await fetchUpdate(false).catch((error: unknown) => error)) as ApiError;
    expect(failure).toBeInstanceOf(ApiError);
    expect(failure.message).toContain("503");
    expect(failure.status).toBe(503);
    expect(failureKey(failure)).toBe("errors.server");
  });

  it("a 200 with no body is a failure too, never an empty update", async () => {
    api.GET.mockResolvedValue({ data: undefined, response: ok() });

    const failure = (await fetchUpdate(false).catch((error: unknown) => error)) as ApiError;
    expect(failure).toBeInstanceOf(ApiError);
    expect(failure.message).toContain("200");
    expect(failure.status).toBe(200);
    expect(failureKey(failure)).toBe("errors.refused");
  });
});

describe("useUpdateCheck — the start check, one cache entry", () => {
  it("runs the start ask with force=true and caches it under [\"updates\"]", async () => {
    api.GET.mockResolvedValue({ data: ANSWER, response: ok() });
    const queryClient = freshClient();

    const hook = renderHook(() => useUpdateCheck(), {
      wrapper: wrapperFor(queryClient),
    });

    await waitFor(() => expect(hook.result.current.data).toEqual(ANSWER));
    expect(api.GET).toHaveBeenCalledWith("/api/updates", {
      params: { query: { force: true } },
    });
    expect(queryClient.getQueryData(UPDATE_KEY)).toEqual(ANSWER);
  });

  it("a failed start check stays silent — the shell shows no invented update", async () => {
    api.GET.mockRejectedValueOnce(new Error("offline"));
    const queryClient = freshClient();

    const hook = renderHook(() => useUpdateCheck(), {
      wrapper: wrapperFor(queryClient),
    });

    // The failure is swallowed by the start check: no cache entry, no
    // observer error state, and the hook's data stays undefined.
    await waitFor(() => expect(api.GET).toHaveBeenCalledTimes(1));
    expect(queryClient.getQueryData(UPDATE_KEY)).toBeUndefined();
    expect(hook.result.current.data).toBeUndefined();
  });

  it("the hourly re-check skips while the tab is hidden", async () => {
    api.GET.mockResolvedValue({ data: ANSWER, response: ok() });
    const queryClient = freshClient();
    const intervals = vi.spyOn(window, "setInterval");

    const hook = renderHook(() => useUpdateCheck(), {
      wrapper: wrapperFor(queryClient),
    });
    await waitFor(() => expect(api.GET).toHaveBeenCalledTimes(1));

    // The registered interval is the hook's own tick; run it by hand so the
    // visibility rule is the thing under test, not an hour of waiting.
    const tick = intervals.mock.calls[0]?.[0] as unknown as () => void;
    expect(typeof tick).toBe("function");

    Object.defineProperty(document, "visibilityState", {
      configurable: true,
      value: "hidden",
    });
    act(() => tick());
    expect(api.GET).toHaveBeenCalledTimes(1);

    Object.defineProperty(document, "visibilityState", {
      configurable: true,
      value: "visible",
    });
    act(() => tick());
    await waitFor(() => expect(api.GET).toHaveBeenCalledTimes(2));

    hook.unmount();
    intervals.mockRestore();
  });
});
