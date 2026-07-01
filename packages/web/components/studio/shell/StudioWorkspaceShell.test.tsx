import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { StudioWorkspaceShell } from "./StudioWorkspaceShell";

vi.mock("next-intl", () => ({
  useTranslations: () => (key: string) => key,
}));

vi.mock("@/components/studio/Sidebar", () => ({
  Sidebar: ({
    variant = "desktop",
    onClose,
  }: {
    variant?: "desktop" | "drawer";
    onClose?: () => void;
  }) => (
    <nav aria-label="sidebar.navigation" data-testid={`sidebar-${variant}`}>
      <button type="button" onClick={onClose}>
        close drawer
      </button>
    </nav>
  ),
}));

vi.mock("@/components/ui/toaster", () => ({
  Toaster: () => <div data-testid="toaster" />,
}));

vi.mock("@/components/ui/feature-tour", () => ({
  FeatureTour: () => <div data-testid="feature-tour" />,
}));

vi.mock("@/lib/config/feature-tour-steps", () => ({
  FEATURE_TOUR_STEPS: [],
}));

describe("StudioWorkspaceShell", () => {
  it("renders desktop sidebar, workspace main landmark, toaster, and feature tour", () => {
    render(
      <StudioWorkspaceShell>
        <div data-testid="workspace-child" />
      </StudioWorkspaceShell>,
    );

    expect(screen.getByTestId("sidebar-desktop")).toBeInTheDocument();
    expect(screen.getByRole("main", { name: "shell.workspaceMain" })).toContainElement(
      screen.getByTestId("workspace-child"),
    );
    expect(screen.getByTestId("toaster")).toBeInTheDocument();
    expect(screen.getByTestId("feature-tour")).toBeInTheDocument();
  });

  it("opens the mobile drawer from the menu button and closes it from the drawer callback", () => {
    render(<StudioWorkspaceShell>workspace</StudioWorkspaceShell>);

    fireEvent.click(screen.getByRole("button", { name: "sidebar.openMenu" }));
    expect(screen.getByRole("dialog", { name: "sidebar.navigation" })).toBeInTheDocument();
    expect(screen.getByTestId("sidebar-drawer")).toBeInTheDocument();

    fireEvent.click(
      within(screen.getByTestId("sidebar-drawer")).getByRole("button", { name: "close drawer" }),
    );
    expect(screen.queryByRole("dialog", { name: "sidebar.navigation" })).not.toBeInTheDocument();
  });

  it("closes the mobile drawer on Escape", () => {
    render(<StudioWorkspaceShell>workspace</StudioWorkspaceShell>);

    fireEvent.click(screen.getByRole("button", { name: "sidebar.openMenu" }));
    fireEvent.keyDown(window, { key: "Escape" });

    expect(screen.queryByRole("dialog", { name: "sidebar.navigation" })).not.toBeInTheDocument();
  });
});
