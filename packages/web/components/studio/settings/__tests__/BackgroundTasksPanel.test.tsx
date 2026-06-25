/**
 * Tests for BackgroundTasksPanel (INFRA-007).
 *
 * The tasks API module is mocked so we control the status payload; a real
 * QueryClientProvider backs the data hook. The global next-intl mock
 * (setupTests.ts) returns message keys verbatim, so translated strings appear
 * as their key paths (e.g. "backgroundTasks.brokerStatus.started").
 *
 * ``useQuery`` is wrapped (via importOriginal) so its real behaviour is
 * preserved while letting us assert on the polling options.
 */
import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@tanstack/react-query", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@tanstack/react-query")>();
  return {
    ...actual,
    // Wrap the real hook so the component still works, but calls are recorded.
    useQuery: vi.fn(actual.useQuery),
  };
});

vi.mock("@/lib/api/client", () => ({
  tasksApi: {
    getStatus: vi.fn(),
  },
}));

import { BackgroundTasksPanel } from "@/components/studio/settings/BackgroundTasksPanel";
import type { TaskStatus } from "@/lib/api/client";
import { tasksApi } from "@/lib/api/client";

const mockUseQuery = vi.mocked(useQuery);
const mockGetStatus = tasksApi.getStatus as ReturnType<typeof vi.fn>;

const started: TaskStatus = {
  broker_started: true,
  is_worker_process: false,
  registered_task_count: 7,
  registered_tasks: [
    "embed_source",
    "process_feedback_memory",
    "run_preference_analysis",
    "wiki_generate_chapter",
    "wiki_generate_entity",
    "wiki_mark_all_stale",
    "wiki_refresh_summary",
  ],
};

const stopped: TaskStatus = {
  ...started,
  broker_started: false,
  is_worker_process: true,
};

function renderWithClient(ui: ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0, staleTime: 0, refetchInterval: false },
    },
  });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

describe("BackgroundTasksPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetStatus.mockResolvedValue(started);
  });
  afterEach(() => cleanup());

  it("renders the loading state before data resolves", () => {
    // Never-resolving promise keeps the query pending.
    mockGetStatus.mockReturnValue(new Promise(() => {}));
    renderWithClient(<BackgroundTasksPanel />);
    expect(screen.getByRole("status")).toBeTruthy();
  });

  it("renders the error state when the status fetch fails", async () => {
    mockGetStatus.mockRejectedValueOnce(new Error("boom"));
    renderWithClient(<BackgroundTasksPanel />);
    expect(await screen.findByText("backgroundTasks.loadFailed")).toBeTruthy();
    expect(screen.getByRole("alert")).toBeTruthy();
  });

  it("shows the running badge and task count once loaded", async () => {
    renderWithClient(<BackgroundTasksPanel />);
    await waitFor(() => expect(mockGetStatus).toHaveBeenCalled());
    expect(await screen.findByText("backgroundTasks.brokerStatus.started")).toBeTruthy();
    expect(screen.getByText("backgroundTasks.taskCount")).toBeTruthy();
    expect(screen.queryByText("backgroundTasks.brokerStatus.stopped")).toBeNull();
  });

  it("shows the stopped badge when the broker is not running", async () => {
    mockGetStatus.mockResolvedValue(stopped);
    renderWithClient(<BackgroundTasksPanel />);
    expect(await screen.findByText("backgroundTasks.brokerStatus.stopped")).toBeTruthy();
    expect(screen.queryByText("backgroundTasks.brokerStatus.started")).toBeNull();
  });

  it("lists every registered task with a friendly label and raw code name", async () => {
    renderWithClient(<BackgroundTasksPanel />);
    await waitFor(() => expect(mockGetStatus).toHaveBeenCalled());
    // Friendly label (translated key) for a known task…
    expect(await screen.findByText("backgroundTasks.taskName.embed_source")).toBeTruthy();
    // …plus the raw task name rendered as a code element.
    expect(screen.getByText("embed_source")).toBeTruthy();
    expect(screen.getByText("wiki_refresh_summary")).toBeTruthy();
    expect(screen.getByText("backgroundTasks.refreshInterval")).toBeTruthy();
  });

  it("falls back to the raw task name for unknown tasks", async () => {
    mockGetStatus.mockResolvedValue({
      ...started,
      registered_task_count: 1,
      registered_tasks: ["some_future_task"],
    });
    renderWithClient(<BackgroundTasksPanel />);
    // Unknown task has no friendly key → raw name is shown (label + code).
    expect((await screen.findAllByText("some_future_task")).length).toBeGreaterThanOrEqual(1);
    expect(screen.queryByText("backgroundTasks.taskName.some_future_task")).toBeNull();
  });

  it("renders the empty state when no tasks are registered", async () => {
    mockGetStatus.mockResolvedValue({
      ...started,
      registered_task_count: 0,
      registered_tasks: [],
    });
    renderWithClient(<BackgroundTasksPanel />);
    expect(await screen.findByText("backgroundTasks.noTasks")).toBeTruthy();
  });

  it("configures the status query to auto-refresh every 10 seconds", async () => {
    renderWithClient(<BackgroundTasksPanel />);
    await waitFor(() => expect(mockGetStatus).toHaveBeenCalled());
    expect(mockUseQuery).toHaveBeenCalledWith(
      expect.objectContaining({
        queryKey: ["tasks", "status"],
        refetchInterval: 10_000,
      }),
    );
  });
});
