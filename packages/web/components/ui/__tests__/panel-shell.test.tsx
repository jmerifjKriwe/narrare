/**
 * PanelShell primitive tests (Task 7).
 *
 * PanelShell is a SINGLE responsive shell: a bottom-sheet at narrow widths and
 * a static sidebar at the `lg` breakpoint, using one mounted element (not a
 * dual desktop/mobile render). The single-shell design is required because the
 * adopter (EditorRightPanelSlot → EditorPanelContent) renders panels that own
 * streaming hooks (e.g. useConsistencyStream); dual-mounting would run those
 * hooks twice. Presentation only (RULE-13).
 */
import { render, screen } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { PanelShell } from "@/components/ui/panel-shell";

describe("PanelShell", () => {
  it("renders a labelled region wired to an sr-only heading via titleId", () => {
    render(
      <PanelShell titleId="t1" dialogLabel="Inspector" onClose={() => {}}>
        <p>Panel body</p>
      </PanelShell>,
    );
    const region = screen.getByRole("region", { name: "Inspector" });
    expect(region).toHaveAttribute("aria-labelledby", "t1");
    const heading = screen.getByRole("heading", { name: "Inspector" });
    expect(heading).toHaveAttribute("id", "t1");
    expect(heading.className).toContain("sr-only");
  });

  it("renders exactly one mounted shell with the children", () => {
    render(
      <PanelShell titleId="t1" dialogLabel="Inspector" onClose={() => {}}>
        <p>Panel body</p>
      </PanelShell>,
    );
    // Single shell — one region, children rendered once (no duplicate mounts).
    expect(screen.getAllByRole("region")).toHaveLength(1);
    expect(screen.getByText("Panel body")).toBeDefined();
  });

  it("renders nothing when open is false", () => {
    render(
      <PanelShell titleId="t1" dialogLabel="Inspector" open={false} onClose={() => {}}>
        <p>Panel body</p>
      </PanelShell>,
    );
    expect(screen.queryByRole("region")).not.toBeInTheDocument();
  });

  it("applies the responsive single-shell classes (mobile sheet + desktop sidebar)", () => {
    render(
      <PanelShell titleId="t1" dialogLabel="Inspector" onClose={() => {}}>
        <p>body</p>
      </PanelShell>,
    );
    const region = screen.getByRole("region");
    expect(region.className).toContain("fixed");
    expect(region.className).toContain("lg:static");
    expect(region.className).toContain("lg:w-96");
    expect(region.className).toContain("lg:flex");
  });

  it("places the dividing border on the configured side", () => {
    const { rerender } = render(
      <PanelShell titleId="t1" dialogLabel="Inspector" side="right" onClose={() => {}}>
        <p>body</p>
      </PanelShell>,
    );
    const right = screen.getByRole("region").className;
    expect(right).toContain("lg:border-l");
    expect(right).not.toContain("lg:border-l-0");
    rerender(
      <PanelShell titleId="t1" dialogLabel="Inspector" side="left" onClose={() => {}}>
        <p>body</p>
      </PanelShell>,
    );
    const left = screen.getByRole("region").className;
    expect(left).toContain("lg:border-r");
    expect(left).not.toContain("lg:border-r-0");
  });

  it("calls onClose when Escape is pressed", async () => {
    const onClose = vi.fn();
    render(
      <PanelShell titleId="t1" dialogLabel="Inspector" onClose={onClose}>
        <button type="button">Inside</button>
      </PanelShell>,
    );
    await userEvent.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("forwards the optional testId to the shell element", () => {
    render(
      <PanelShell titleId="t1" dialogLabel="Inspector" testId="my-panel" onClose={() => {}}>
        <p>body</p>
      </PanelShell>,
    );
    expect(screen.getByTestId("my-panel")).toBeDefined();
  });
});
