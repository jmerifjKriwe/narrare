/**
 * scene_plan editor panel wiring (PLAN-001 spec §8.2).
 *
 * Integration-level assertion that the wiring contract holds: the
 * `scene_plan` right-panel id renders {@link ScenePlanPanel} with the active
 * chapter threaded in and a panel-scoped onClose. The panel's own behaviour
 * (list, inline edits, save, planner navigation) is owned by
 * ScenePlanPanel.test.tsx — here the panel is stubbed to keep this test
 * focused on the EditorPanelContent switch case.
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { EditorPanelContent } from "../EditorPanelContent";

vi.mock("../../editor/ScenePlanPanel", () => ({
  ScenePlanPanel: ({
    novelId,
    chapterId,
    onClose,
  }: {
    novelId: string;
    chapterId: string;
    onClose: () => void;
  }) => (
    <div data-testid="scene-plan-panel">
      <span data-testid="spp-novel">{novelId}</span>
      <span data-testid="spp-chapter">{chapterId}</span>
      <button type="button" onClick={onClose}>
        close
      </button>
    </div>
  ),
}));

const panelBaseProps = {
  novelId: "novel-1",
  activeChapterId: "ch-1",
  content: "<p>x</p>",
  editor: null,
  chapter: undefined,
  chapters: [],
  sessionStartWordCount: 0,
  volumeStats: undefined,
  wordCount: 1,
  charCount: 1,
  paragraphCount: 1,
  sessionMode: "interactive_session" as const,
  handleSessionClose: vi.fn(),
  handleDraftAccepted: vi.fn(),
  handleStartSession: vi.fn(),
  closePanel: vi.fn(),
};

describe("scene_plan panel wiring", () => {
  it("renders ScenePlanPanel when active with chapter + scoped onClose", () => {
    const closePanel = vi.fn();
    render(
      <EditorPanelContent {...panelBaseProps} activePanel="scene_plan" closePanel={closePanel} />,
    );

    expect(screen.getByTestId("scene-plan-panel")).toBeDefined();
    expect(screen.getByTestId("spp-novel").textContent).toBe("novel-1");
    expect(screen.getByTestId("spp-chapter").textContent).toBe("ch-1");

    screen.getByText("close").click();
    expect(closePanel).toHaveBeenCalledWith("scene_plan");
  });
});
