/**
 * Tests for usePromptHistory (CR-AUFG-07-19).
 *
 * Data layer for the Prompt History panel: TanStack Query for the revision
 * list + compare, and mutations for restore / clear. The API module is mocked
 * so the hook is tested in isolation (mirrors useKB.test.tsx).
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/prompts", () => ({
  promptsApi: {
    listHistory: vi.fn(),
    compareRevisions: vi.fn(),
    restoreRevision: vi.fn(),
    clearHistory: vi.fn(),
  },
}));

import { usePromptHistory } from "@/components/studio/settings/prompt-history/usePromptHistory";
import { promptsApi } from "@/lib/api/prompts";

const mockList = promptsApi.listHistory as ReturnType<typeof vi.fn>;
const mockCompare = promptsApi.compareRevisions as ReturnType<typeof vi.fn>;
const mockRestore = promptsApi.restoreRevision as ReturnType<typeof vi.fn>;
const mockClear = promptsApi.clearHistory as ReturnType<typeof vi.fn>;

const PROMPT_ID = "writing/en/new_chapter";

function revision(id: string, active = false) {
  return {
    id,
    prompt_id: PROMPT_ID,
    scope: "project",
    content: `content-${id}`,
    content_hash: id,
    actor_id: null,
    source: "edit",
    change_reason: null,
    restored_from_id: null,
    created_at: "2026-06-20T10:00:00Z",
    is_active: active,
  };
}

function listResponse() {
  return {
    prompt_id: PROMPT_ID,
    scope: "project",
    total: 2,
    limit: 50,
    offset: 0,
    revisions: [revision("rev-2", true), revision("rev-1")],
  };
}

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

describe("usePromptHistory", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockList.mockResolvedValue(listResponse());
    mockCompare.mockResolvedValue({
      prompt_id: PROMPT_ID,
      from_id: "rev-1",
      to_id: "rev-2",
      from_source: "edit",
      to_source: "edit",
      from_content: "old",
      to_content: "new",
    });
    mockRestore.mockResolvedValue({
      prompt_id: PROMPT_ID,
      restored_revision: revision("rev-3"),
      active_content: "content-rev-3",
      previous_active_hash: "rev-2",
    });
    mockClear.mockResolvedValue({
      prompt_id: PROMPT_ID,
      scope: "project",
      deleted_count: 2,
    });
  });

  afterEach(() => cleanup());

  it("loads the revision list on mount", async () => {
    const { result } = renderHook(() => usePromptHistory(PROMPT_ID), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.list.isSuccess).toBe(true));
    expect(mockList).toHaveBeenCalledWith(PROMPT_ID);
    expect(result.current.list.data?.revisions).toHaveLength(2);
  });

  it("does not run the compare query until both fromId and toId are set", async () => {
    const { result } = renderHook(() => usePromptHistory(PROMPT_ID), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.list.isSuccess).toBe(true));
    expect(result.current.compare.fetchStatus).toBe("idle");
    expect(mockCompare).not.toHaveBeenCalled();

    result.current.setFromId("rev-1");
    expect(mockCompare).not.toHaveBeenCalled();

    result.current.setToId("rev-2");
    await waitFor(() => expect(mockCompare).toHaveBeenCalledWith(PROMPT_ID, "rev-1", "rev-2"));
  });

  it("restoreRevision calls the API, records the id, and refreshes the list + onRestored", async () => {
    const onRestored = vi.fn();
    const { result } = renderHook(() => usePromptHistory(PROMPT_ID, { onRestored }), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.list.isSuccess).toBe(true));

    await result.current.restoreMutation.mutateAsync("rev-1");

    expect(mockRestore).toHaveBeenCalledWith(PROMPT_ID, "rev-1");
    await waitFor(() => expect(result.current.lastRestoredRevisionId).toBe("rev-3"));
    expect(onRestored).toHaveBeenCalledTimes(1);
    // list refetched after restore
    await waitFor(() => expect(mockList.mock.calls.length).toBeGreaterThanOrEqual(2));
  });

  it("clearHistory calls the API and refreshes the list + onCleared", async () => {
    const onCleared = vi.fn();
    const { result } = renderHook(() => usePromptHistory(PROMPT_ID, { onCleared }), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.list.isSuccess).toBe(true));

    await result.current.clearMutation.mutateAsync();

    expect(mockClear).toHaveBeenCalledWith(PROMPT_ID);
    expect(onCleared).toHaveBeenCalledTimes(1);
    await waitFor(() => expect(mockList.mock.calls.length).toBeGreaterThanOrEqual(2));
  });
});
