/**
 * Tests for PromptHistoryPanel (CR-AUFG-07-19).
 *
 * The panel orchestrates the data hook + list + compare + confirm dialogs. The
 * API module is mocked so we control list/compare/restore/clear behaviour; a
 * real QueryClientProvider backs the hook (mirrors usePromptHistory.test.tsx).
 * The global next-intl mock (setupTests.ts) returns message keys verbatim.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
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

import { PromptHistoryPanel } from "@/components/studio/settings/prompt-history/PromptHistoryPanel";
import { promptsApi } from "@/lib/api/prompts";
import type { PromptRevision } from "@/types";

const mockList = promptsApi.listHistory as ReturnType<typeof vi.fn>;
const mockCompare = promptsApi.compareRevisions as ReturnType<typeof vi.fn>;
const mockRestore = promptsApi.restoreRevision as ReturnType<typeof vi.fn>;
const mockClear = promptsApi.clearHistory as ReturnType<typeof vi.fn>;

const PROMPT_ID = "writing/en/new_chapter";
const EXPAND = "settings.prompts.promptHistory.expand";
const RESTORE = "settings.prompts.promptHistory.restore";
const CLEAR = "settings.prompts.promptHistory.clear";

function revision(id: string, active = false): PromptRevision {
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

function listResponse(revisions: PromptRevision[]) {
  return {
    prompt_id: PROMPT_ID,
    scope: "project",
    total: revisions.length,
    limit: 50,
    offset: 0,
    revisions,
  };
}

function renderWithClient(ui: ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } },
  });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

async function expand() {
  fireEvent.click(screen.getByRole("button", { name: new RegExp(EXPAND) }));
}

describe("PromptHistoryPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Single non-active revision → exactly one enabled "restore" button.
    mockList.mockResolvedValue(listResponse([revision("rev-1")]));
    mockCompare.mockResolvedValue({
      prompt_id: PROMPT_ID,
      from_id: "rev-1",
      to_id: "rev-2",
      from_source: "edit",
      to_source: "edit",
      from_content: "alpha",
      to_content: "beta",
    });
    mockRestore.mockResolvedValue({
      prompt_id: PROMPT_ID,
      restored_revision: revision("rev-3"),
      active_content: "content-rev-3",
      previous_active_hash: "rev-2",
    });
    mockClear.mockResolvedValue({ prompt_id: PROMPT_ID, scope: "project", deleted_count: 2 });
  });

  afterEach(() => cleanup());

  it("is collapsed by default and renders no revision rows", () => {
    renderWithClient(<PromptHistoryPanel promptId={PROMPT_ID} />);
    expect(screen.getByRole("button", { name: new RegExp(EXPAND) })).toBeTruthy();
    // Collapsed → list is not mounted → no restore buttons.
    expect(screen.queryAllByRole("button", { name: RESTORE })).toHaveLength(0);
  });

  it("renders the revision list, count, and clear button once expanded", async () => {
    renderWithClient(<PromptHistoryPanel promptId={PROMPT_ID} />);
    await expand();
    await waitFor(() => expect(mockList).toHaveBeenCalledWith(PROMPT_ID));
    // Restore button for the single non-active revision.
    expect(screen.getByRole("button", { name: RESTORE })).toBeTruthy();
    expect(screen.getByRole("button", { name: CLEAR })).toBeTruthy();
    expect(screen.getByText("settings.prompts.promptHistory.count")).toBeTruthy();
  });

  it("shows the empty state when there are no revisions", async () => {
    mockList.mockResolvedValue(listResponse([]));
    renderWithClient(<PromptHistoryPanel promptId={PROMPT_ID} />);
    await expand();
    expect(await screen.findByText("settings.prompts.promptHistory.empty")).toBeTruthy();
    expect(screen.getByText("settings.prompts.promptHistory.emptyHint")).toBeTruthy();
  });

  it("shows the loading state while the list is fetching", async () => {
    // Never-resolving promise keeps the query pending.
    mockList.mockReturnValue(new Promise(() => {}));
    renderWithClient(<PromptHistoryPanel promptId={PROMPT_ID} />);
    await expand();
    expect(await screen.findByText("settings.prompts.promptHistory.loading")).toBeTruthy();
  });

  it("shows the error state and retries on demand", async () => {
    mockList.mockRejectedValueOnce(new Error("boom"));
    renderWithClient(<PromptHistoryPanel promptId={PROMPT_ID} />);
    await expand();
    expect(await screen.findByText("settings.prompts.promptHistory.loadFailed")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "settings.prompts.promptHistory.retry" }));
    await waitFor(() => expect(mockList.mock.calls.length).toBeGreaterThanOrEqual(2));
  });

  it("restore flow: confirm dialog gates the restore API call and fires onRestored", async () => {
    const onRestored = vi.fn();
    renderWithClient(<PromptHistoryPanel promptId={PROMPT_ID} onRestored={onRestored} />);
    await expand();

    // One non-active revision → one list restore button.
    fireEvent.click(await screen.findByRole("button", { name: RESTORE }));

    // Confirm dialog opens.
    const dialog = await screen.findByRole("alertdialog");
    fireEvent.click(within(dialog).getByRole("button", { name: RESTORE }));

    await waitFor(() => expect(mockRestore).toHaveBeenCalledWith(PROMPT_ID, "rev-1"));
    await waitFor(() => expect(onRestored).toHaveBeenCalledTimes(1));
  });

  it("restore flow: cancelling the dialog does not call the API", async () => {
    renderWithClient(<PromptHistoryPanel promptId={PROMPT_ID} />);
    await expand();
    fireEvent.click(await screen.findByRole("button", { name: RESTORE }));

    const dialog = await screen.findByRole("alertdialog");
    // Cancel button is the non-confirm button inside the dialog (the next-intl
    // mock returns the bare key "cancel" for useTranslations("common")("cancel")).
    fireEvent.click(within(dialog).getByRole("button", { name: "cancel" }));

    await waitFor(() => expect(screen.queryByRole("alertdialog")).toBeNull());
    expect(mockRestore).not.toHaveBeenCalled();
  });

  it("clear flow: confirm dialog gates the clear API call and fires onCleared", async () => {
    const onCleared = vi.fn();
    renderWithClient(<PromptHistoryPanel promptId={PROMPT_ID} onCleared={onCleared} />);
    await expand();

    fireEvent.click(await screen.findByRole("button", { name: CLEAR }));
    const dialog = await screen.findByRole("alertdialog");
    fireEvent.click(within(dialog).getByRole("button", { name: CLEAR }));

    await waitFor(() => expect(mockClear).toHaveBeenCalledWith(PROMPT_ID));
    await waitFor(() => expect(onCleared).toHaveBeenCalledTimes(1));
  });
});
