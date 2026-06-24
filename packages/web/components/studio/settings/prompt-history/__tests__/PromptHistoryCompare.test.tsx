/**
 * Tests for PromptHistoryCompare (CR-AUFG-07-19).
 *
 * Presentational from/to selector + shared AIDiffView. Owns no data, so no
 * QueryClientProvider is required. The global next-intl mock (setupTests.ts)
 * returns the message key verbatim — assertions use those keys.
 */
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { PromptHistoryCompare } from "@/components/studio/settings/prompt-history/PromptHistoryCompare";
import type { PromptRevision, PromptRevisionCompareResponse } from "@/types";

const FROM_LABEL = "settings.prompts.promptHistory.fromLabel";
const TO_LABEL = "settings.prompts.promptHistory.toLabel";
const ACTIVE_OPTION = "settings.prompts.promptHistory.activeOption";

function revision(id: string, overrides: Partial<PromptRevision> = {}): PromptRevision {
  return {
    id,
    prompt_id: "writing/en/new_chapter",
    scope: "project",
    content: `content-${id}`,
    content_hash: id,
    actor_id: null,
    source: "edit",
    change_reason: null,
    restored_from_id: null,
    created_at: "2026-06-20T10:00:00Z",
    is_active: false,
    ...overrides,
  };
}

function compare(
  overrides: Partial<PromptRevisionCompareResponse> = {},
): PromptRevisionCompareResponse {
  // Distinct tokens with no common prefix/suffix so diff-match-patch keeps
  // each side as a whole segment (robust textContent assertions).
  return {
    prompt_id: "writing/en/new_chapter",
    from_id: "rev-1",
    to_id: "rev-2",
    from_source: "edit",
    to_source: "edit",
    from_content: "foo",
    to_content: "bar",
    ...overrides,
  };
}

describe("PromptHistoryCompare", () => {
  it("renders the compare title and hint", () => {
    const { container } = render(
      <PromptHistoryCompare
        revisions={[revision("rev-1")]}
        fromId={null}
        toId={null}
        onFromChange={() => {}}
        onToChange={() => {}}
        compare={undefined}
        isLoading={false}
        isError={false}
      />,
    );
    expect(screen.getByText("settings.prompts.promptHistory.compareTitle")).toBeTruthy();
    expect(screen.getByText("settings.prompts.promptHistory.compareHint")).toBeTruthy();
    // Nothing selected → no diff/loading/error surfaces.
    expect(container.textContent).not.toContain("alpha content");
  });

  it("renders an Active override option plus one option per revision in each select", () => {
    render(
      <PromptHistoryCompare
        revisions={[revision("rev-1"), revision("rev-2")]}
        fromId={null}
        toId={null}
        onFromChange={() => {}}
        onToChange={() => {}}
        compare={undefined}
        isLoading={false}
        isError={false}
      />,
    );

    const fromSelect = screen.getByRole("combobox", { name: FROM_LABEL });
    const toSelect = screen.getByRole("combobox", { name: TO_LABEL });

    // Each select exposes: placeholder + active + 2 revisions = 4 options.
    expect(fromSelect).toBeTruthy();
    expect(toSelect).toBeTruthy();
    expect(fromSelect.querySelectorAll("option")).toHaveLength(4);
    // The active pseudo-revision uses PROMPT_HISTORY_ACTIVE_TOKEN ("active").
    expect(fromSelect.querySelector(`option[value="active"]`)?.textContent).toBe(ACTIVE_OPTION);
    expect(fromSelect.querySelector(`option[value="rev-1"]`)).toBeTruthy();
  });

  it("calls onFromChange / onToChange when a selection is made", () => {
    const onFromChange = vi.fn();
    const onToChange = vi.fn();
    render(
      <PromptHistoryCompare
        revisions={[revision("rev-1")]}
        fromId={null}
        toId={null}
        onFromChange={onFromChange}
        onToChange={onToChange}
        compare={undefined}
        isLoading={false}
        isError={false}
      />,
    );

    fireEvent.change(screen.getByRole("combobox", { name: FROM_LABEL }), {
      target: { value: "active" },
    });
    fireEvent.change(screen.getByRole("combobox", { name: TO_LABEL }), {
      target: { value: "rev-1" },
    });

    expect(onFromChange).toHaveBeenCalledWith("active");
    expect(onToChange).toHaveBeenCalledWith("rev-1");
  });

  it("shows the loading indicator when both are selected and isLoading", () => {
    render(
      <PromptHistoryCompare
        revisions={[revision("rev-1")]}
        fromId="active"
        toId="rev-1"
        onFromChange={() => {}}
        onToChange={() => {}}
        compare={undefined}
        isLoading
        isError={false}
      />,
    );
    expect(screen.getByText("settings.prompts.promptHistory.compareLoading")).toBeTruthy();
  });

  it("shows an error alert when the compare query failed", () => {
    render(
      <PromptHistoryCompare
        revisions={[revision("rev-1")]}
        fromId="active"
        toId="rev-1"
        onFromChange={() => {}}
        onToChange={() => {}}
        compare={undefined}
        isLoading={false}
        isError
      />,
    );
    expect(screen.getByRole("alert").textContent).toContain(
      "settings.prompts.promptHistory.compareFailed",
    );
  });

  it("renders the shared AIDiffView with the compared content", () => {
    const { container } = render(
      <PromptHistoryCompare
        revisions={[revision("rev-1")]}
        fromId="rev-1"
        toId="rev-2"
        onFromChange={() => {}}
        onToChange={() => {}}
        compare={compare()}
        isLoading={false}
        isError={false}
      />,
    );
    // The diff surfaces both sides of the comparison.
    expect(container.textContent).toContain("foo");
    expect(container.textContent).toContain("bar");
  });
});
