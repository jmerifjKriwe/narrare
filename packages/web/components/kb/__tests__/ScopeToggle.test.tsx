/**
 * ScopeToggle component tests (Spec 1, Slice 5, Task 5.3).
 *
 * The toggle switches a KB entry between Series-Canon and Novel-Overlay scope.
 * It is hidden entirely when the novel is standalone (useNovelSeries → null) or
 * while the series is still resolving. When visible it shows two buttons
 * (Canon / Overlay); the inactive button opens a ConfirmDialog before calling
 * the promote / demote mutation.
 *
 * Conventions (mirrors SeriesSettings.test.tsx): the centralized setupTests.ts
 * mock returns i18n KEY STRINGS verbatim, so assertions check for keys.
 * useNovelSeries + useKBScope are mocked per-file so each test controls the
 * resolved series and the mutation fns.
 */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Series } from "@/types";

// --- Per-file mutable mock state (hoisted) -----------------------------------
const mock = vi.hoisted(() => ({
  series: {
    data: undefined as Series | null | undefined,
    isLoading: false,
  },
  promote: vi.fn(),
  promotePending: false,
  demote: vi.fn(),
  demotePending: false,
}));

vi.mock("@/lib/hooks/useNovelSeries", () => ({
  useNovelSeries: () => mock.series,
}));

vi.mock("@/lib/hooks/useKBScope", () => ({
  usePromoteToCanon: () => ({
    mutate: (...args: unknown[]) => mock.promote(...args),
    isPending: mock.promotePending,
  }),
  useDemoteToOverlay: () => ({
    mutate: (...args: unknown[]) => mock.demote(...args),
    isPending: mock.demotePending,
  }),
}));

import { ScopeToggle } from "@/components/kb/ScopeToggle";

const inSeries: Series = {
  id: "series-1",
  user_id: "user-1",
  title: "The Expanse",
  subtitle: null,
  description: null,
  genre: "sci-fi",
  writing_language: "en",
  status: "active",
  planned_novel_count: 9,
  novel_count: 2,
};

function resetState(): void {
  mock.series = { data: inSeries, isLoading: false };
  mock.promote = vi.fn();
  mock.promotePending = false;
  mock.demote = vi.fn();
  mock.demotePending = false;
}

describe("ScopeToggle", () => {
  beforeEach(() => {
    resetState();
  });

  it("renders nothing when the novel is standalone (no series)", () => {
    mock.series = { data: null, isLoading: false };
    const { container } = render(
      <ScopeToggle entry={{ id: "entry-1", scope: "novel" }} novelId="novel-1" />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing while the series is still loading", () => {
    mock.series = { data: undefined, isLoading: true };
    const { container } = render(
      <ScopeToggle entry={{ id: "entry-1", scope: "novel" }} novelId="novel-1" />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("renders the toggle when the novel belongs to a series", () => {
    render(<ScopeToggle entry={{ id: "entry-1", scope: "novel" }} novelId="novel-1" />);
    expect(screen.getByTestId("scope-toggle")).toBeDefined();
  });

  it("marks the Overlay button active when the entry scope is novel", () => {
    render(<ScopeToggle entry={{ id: "entry-1", scope: "novel" }} novelId="novel-1" />);
    expect(screen.getByTestId("scope-toggle-overlay").getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByTestId("scope-toggle-canon").getAttribute("aria-pressed")).toBe("false");
  });

  it("marks the Canon button active when the entry scope is series", () => {
    render(
      <ScopeToggle
        entry={{ id: "entry-1", scope: "series", series_id: "series-1" }}
        novelId="novel-1"
      />,
    );
    expect(screen.getByTestId("scope-toggle-canon").getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByTestId("scope-toggle-overlay").getAttribute("aria-pressed")).toBe("false");
  });

  it("opens a confirmation dialog when promoting (overlay → canon)", async () => {
    const user = userEvent.setup();
    render(<ScopeToggle entry={{ id: "entry-1", scope: "novel" }} novelId="novel-1" />);

    // No dialog before interaction.
    expect(screen.queryByTestId("confirm-dialog-confirm")).toBeNull();

    await user.click(screen.getByTestId("scope-toggle-canon"));
    expect(screen.getByTestId("confirm-dialog-confirm")).toBeDefined();
  });

  it("calls the promote mutation when the dialog is confirmed", async () => {
    const user = userEvent.setup();
    render(<ScopeToggle entry={{ id: "entry-1", scope: "novel" }} novelId="novel-1" />);

    await user.click(screen.getByTestId("scope-toggle-canon"));
    await user.click(screen.getByTestId("confirm-dialog-confirm"));

    expect(mock.promote).toHaveBeenCalledTimes(1);
  });

  it("does not promote when the dialog is cancelled", async () => {
    const user = userEvent.setup();
    render(<ScopeToggle entry={{ id: "entry-1", scope: "novel" }} novelId="novel-1" />);

    await user.click(screen.getByTestId("scope-toggle-canon"));
    await user.click(screen.getByTestId("confirm-dialog-cancel"));

    expect(mock.promote).not.toHaveBeenCalled();
  });

  it("calls the demote mutation when demoting (canon → overlay)", async () => {
    const user = userEvent.setup();
    render(
      <ScopeToggle
        entry={{ id: "entry-1", scope: "series", series_id: "series-1" }}
        novelId="novel-1"
      />,
    );

    await user.click(screen.getByTestId("scope-toggle-overlay"));
    await user.click(screen.getByTestId("confirm-dialog-confirm"));

    expect(mock.demote).toHaveBeenCalledTimes(1);
    // Demote routes via the current novel and targets it as the overlay home.
    // I-F3: an onSuccess callback closes the confirm dialog only on success.
    expect(mock.demote).toHaveBeenCalledWith(
      { novelId: "novel-1", targetNovelId: "novel-1" },
      expect.objectContaining({ onSuccess: expect.any(Function) }),
    );
  });

  it("disables both buttons while a mutation is pending", () => {
    mock.promotePending = true;
    render(<ScopeToggle entry={{ id: "entry-1", scope: "novel" }} novelId="novel-1" />);
    expect((screen.getByTestId("scope-toggle-canon") as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByTestId("scope-toggle-overlay") as HTMLButtonElement).disabled).toBe(true);
  });
});
