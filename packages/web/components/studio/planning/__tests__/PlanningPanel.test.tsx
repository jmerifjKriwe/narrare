import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PlanningPanel } from "../PlanningPanel";

const mocks = vi.hoisted(() => {
  const state = { storyboardOpen: false };
  return {
    routerPush: vi.fn(),
    routerReplace: vi.fn(),
    searchParams: new URLSearchParams(),
    state,
    toggleStoryboard: vi.fn(() => {
      state.storyboardOpen = !state.storyboardOpen;
    }),
  };
});

vi.mock("next-intl", () => ({
  useTranslations: () => (key: string) => key,
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mocks.routerPush, replace: mocks.routerReplace }),
  usePathname: () => "/novel/novel-1",
  useSearchParams: () => mocks.searchParams,
}));

vi.mock("@/lib/stores/editorStore", () => ({
  useEditorStore: (
    selector: (state: { storyboardOpen: boolean; toggleStoryboard: () => void }) => unknown,
  ) =>
    selector({
      storyboardOpen: mocks.state.storyboardOpen,
      toggleStoryboard: mocks.toggleStoryboard,
    }),
}));

vi.mock("../StoryboardPanel", () => ({
  StoryboardPanel: () => <section data-testid="storyboard-panel" />,
}));

vi.mock("../timeline/TimelinePanel", () => ({
  TimelinePanel: () => <section data-testid="timeline-panel" />,
}));

vi.mock("../CharacterArcPanel", () => ({
  CharacterArcPanel: () => <section data-testid="character-arc-panel" />,
}));

describe("PlanningPanel URL state", () => {
  beforeEach(() => {
    mocks.routerPush.mockClear();
    mocks.routerReplace.mockClear();
    mocks.toggleStoryboard.mockClear();
    mocks.searchParams = new URLSearchParams();
    mocks.state.storyboardOpen = false;
  });

  it("opens from planning=1 and renders the requested tab", () => {
    mocks.searchParams = new URLSearchParams("planning=1&planningTab=timeline");

    render(<PlanningPanel novelId="novel-1" />);

    expect(mocks.toggleStoryboard).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId("timeline-panel")).toBeInTheDocument();
  });

  it("pushes URL state when opening from the collapsed button", () => {
    render(<PlanningPanel novelId="novel-1" />);

    fireEvent.click(screen.getByRole("button", { name: /storyboard.title/i }));

    expect(mocks.routerPush).toHaveBeenCalledWith("/novel/novel-1?planning=1", { scroll: false });
  });

  it("pushes selected tab while keeping planning open", () => {
    mocks.state.storyboardOpen = true;
    mocks.searchParams = new URLSearchParams("planning=1");
    render(<PlanningPanel novelId="novel-1" />);

    fireEvent.click(screen.getByRole("button", { name: "title" }));

    expect(mocks.routerPush).toHaveBeenCalledWith(
      "/novel/novel-1?planning=1&planningTab=timeline",
      {
        scroll: false,
      },
    );
  });
});
