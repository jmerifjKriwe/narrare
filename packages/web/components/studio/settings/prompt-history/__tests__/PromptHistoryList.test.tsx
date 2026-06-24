import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { PromptHistoryList } from "@/components/studio/settings/prompt-history/PromptHistoryList";
import type { PromptRevision } from "@/types";

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

describe("PromptHistoryList", () => {
  it("renders one row per revision with its source and a restore button", () => {
    const revisions = [
      revision("rev-2", { is_active: true, source: "edit" }),
      revision("rev-1", { source: "restore" }),
    ];
    render(
      <PromptHistoryList
        revisions={revisions}
        onRestore={() => {}}
        isRestorePending={false}
        restoringId={null}
      />,
    );

    // restore buttons rendered per row (active row excluded — it is already active)
    const restoreButtons = screen.getAllByRole("button", {
      name: "settings.prompts.promptHistory.restore",
    });
    expect(restoreButtons).toHaveLength(1);
  });

  it("shows the active badge on the currently-active revision", () => {
    render(
      <PromptHistoryList
        revisions={[revision("rev-2", { is_active: true })]}
        onRestore={() => {}}
        isRestorePending={false}
        restoringId={null}
      />,
    );
    expect(screen.getByText("settings.prompts.promptHistory.activeBadge")).toBeTruthy();
  });

  it("calls onRestore with the revision when its restore button is clicked", () => {
    const onRestore = vi.fn();
    const rev = revision("rev-1");
    render(
      <PromptHistoryList
        revisions={[rev]}
        onRestore={onRestore}
        isRestorePending={false}
        restoringId={null}
      />,
    );
    screen.getByRole("button", { name: "settings.prompts.promptHistory.restore" }).click();
    expect(onRestore).toHaveBeenCalledWith(rev);
  });

  it("disables the restore button and shows restoring label while pending", () => {
    render(
      <PromptHistoryList
        revisions={[revision("rev-1")]}
        onRestore={() => {}}
        isRestorePending
        restoringId="rev-1"
      />,
    );
    const btn = screen.getByRole("button", {
      name: "settings.prompts.promptHistory.restoring",
    });
    expect((btn as HTMLButtonElement).disabled).toBe(true);
  });
});
