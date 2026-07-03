import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import StudioLayout from "@/app/(studio)/layout";
import NovelLayout from "@/app/(studio)/novel/[id]/layout";
import WizardLayout from "@/app/(studio)/wizard/layout";
import DashboardPage from "@/app/page";

vi.mock("@tanstack/react-query", () => ({
  useQuery: () => ({ data: { id: "user-1" }, isError: false, isLoading: false }),
}));

vi.mock("@/lib/api/client", () => ({ authApi: { me: vi.fn() } }));
vi.mock("@/components/ui/toaster", () => ({ Toaster: () => <div data-testid="toaster" /> }));
vi.mock("@/components/ui/feature-tour", () => ({
  FeatureTour: () => <div data-testid="feature-tour" />,
}));
vi.mock("@/lib/config/feature-tour-steps", () => ({ FEATURE_TOUR_STEPS: [] }));
vi.mock("@/components/studio/DashboardView", () => ({
  DashboardView: () => <main data-testid="dashboard-shell">Dashboard</main>,
}));
vi.mock("@/components/studio/Sidebar", () => ({
  Sidebar: () => <aside data-testid="workspace-sidebar">Sidebar</aside>,
}));

describe("shell ownership", () => {
  it("dashboard route owns a dashboard shell without workspace sidebar", () => {
    render(<DashboardPage />);
    expect(screen.getByTestId("dashboard-shell")).toBeInTheDocument();
    expect(screen.queryByTestId("workspace-sidebar")).not.toBeInTheDocument();
  });

  it("studio auth boundary does not render workspace chrome by itself", () => {
    render(
      <StudioLayout>
        <div data-testid="studio-child" />
      </StudioLayout>,
    );
    expect(screen.getByTestId("studio-child")).toBeInTheDocument();
    expect(screen.queryByTestId("workspace-sidebar")).not.toBeInTheDocument();
  });

  it("wizard setup shell is auth-protected and not wrapped by sidebar", () => {
    render(
      <StudioLayout>
        <WizardLayout>
          <div data-testid="wizard-step" />
        </WizardLayout>
      </StudioLayout>,
    );
    expect(screen.getByTestId("wizard-step")).toBeInTheDocument();
    expect(screen.queryByTestId("workspace-sidebar")).not.toBeInTheDocument();
  });

  it("novel workspace route owns the sidebar shell", () => {
    render(
      <StudioLayout>
        <NovelLayout>
          <div data-testid="novel-child" />
        </NovelLayout>
      </StudioLayout>,
    );
    expect(screen.getByTestId("workspace-sidebar")).toBeInTheDocument();
    expect(screen.getByTestId("novel-child")).toBeInTheDocument();
  });
});
