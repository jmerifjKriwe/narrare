// @vitest-environment jsdom
/**
 * The setup status hook: the one fact the `/` gate reads. A 200 carries the
 * instance's state, cached under ["setup", "status"] — the state flips once
 * per instance, so the answer never goes stale on its own and a remount
 * reads the cache instead of asking again. The hook suspends while the
 * answer is in flight (the gate's loading state is the root boundary's bare
 * suspension); the provider below carries the same boundary the app's root
 * does. The client is mocked at its module boundary — the request itself is
 * the backend's and the E2E's to verify.
 */
import { QueryClientProvider } from "@tanstack/react-query";
import { createElement, Suspense, type ReactNode } from "react";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("@shell/lib/api/client", () => ({
  client: {
    GET: vi.fn(),
    POST: vi.fn(),
    PATCH: vi.fn(),
    PUT: vi.fn(),
    DELETE: vi.fn(),
  },
}));

import { client } from "@shell/lib/api/client";
import { queryClient } from "@shell/lib/query";

import { useSetupStatus } from "./useSetupStatus";

/** The client's methods as plain mocks; the real client's generics stay out. */
const api = client as unknown as Record<
  "GET" | "POST" | "PATCH" | "PUT" | "DELETE",
  ReturnType<typeof vi.fn>
>;

function ok(): Response {
  return new Response(null, { status: 200 });
}

/** The provider the app mounts everything under, plus the Suspense boundary
 *  the hook suspends against — the shell root's own boundary in the app. */
function wrapper({ children }: { children: ReactNode }) {
  return createElement(
    QueryClientProvider,
    { client: queryClient },
    createElement(Suspense, { fallback: null }, children),
  );
}

afterEach(() => {
  queryClient.clear();
  vi.clearAllMocks();
});

describe("useSetupStatus", () => {
  it("answers incomplete from a 200, cached under [\"setup\", \"status\"]", async () => {
    api.GET.mockResolvedValue({ data: { complete: false }, response: ok() });
    const hook = renderHook(() => useSetupStatus(), { wrapper });

    await waitFor(() => expect(hook.result.current.complete).toBe(false));
    expect(hook.result.current.isLoading).toBe(false);
    expect(api.GET).toHaveBeenCalledWith("/api/setup/status");
    // The key is part of the contract: the write that flips the state
    // invalidates it, and the gate reads no other question.
    expect(queryClient.getQueryState(["setup", "status"])?.status).toBe("success");
  });

  it("answers complete from a 200", async () => {
    api.GET.mockResolvedValue({ data: { complete: true }, response: ok() });
    const hook = renderHook(() => useSetupStatus(), { wrapper });

    await waitFor(() => expect(hook.result.current.complete).toBe(true));
    expect(hook.result.current.isLoading).toBe(false);
  });

  it("asks once per instance: a remount reads the cache, never stale", async () => {
    api.GET.mockResolvedValue({ data: { complete: false }, response: ok() });
    const first = renderHook(() => useSetupStatus(), { wrapper });
    await waitFor(() => expect(first.result.current.complete).toBe(false));
    first.unmount();

    const second = renderHook(() => useSetupStatus(), { wrapper });
    await waitFor(() => expect(second.result.current.complete).toBe(false));
    expect(api.GET).toHaveBeenCalledTimes(1);
  });
});
