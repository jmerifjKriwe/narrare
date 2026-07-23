import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Badge } from "@/components/ui/badge";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";

describe("shadcn primitives render", () => {
  it("Badge renders children", () => {
    render(<Badge>medium</Badge>);
    expect(screen.getByText("medium")).toBeInTheDocument();
  });

  it("Badge applies the default variant and forwards className", () => {
    render(<Badge className="tier-marker">high</Badge>);
    const badge = screen.getByText("high");
    expect(badge.className).toContain("bg-primary");
    expect(badge.className).toContain("tier-marker");
  });

  it("Badge applies the secondary variant", () => {
    render(<Badge variant="secondary">low</Badge>);
    expect(screen.getByText("low").className).toContain("bg-secondary");
  });

  it("Slider is labelled", () => {
    render(<Slider defaultValue={[0.5]} max={1} step={0.01} aria-label="preference weight" />);
    expect(screen.getByRole("slider", { name: "preference weight" })).toBeInTheDocument();
  });

  it("Slider forwards className to the root element", () => {
    const { container } = render(
      <Slider
        defaultValue={[0.5]}
        max={1}
        step={0.01}
        aria-label="weight"
        className="weight-control"
      />,
    );
    expect(container.querySelector(".weight-control")).not.toBeNull();
  });

  it("Switch toggles", () => {
    render(<Switch aria-label="adaptive toggle" />);
    expect(screen.getByRole("switch", { name: "adaptive toggle" })).toBeInTheDocument();
  });

  it("Switch reflects aria-checked from Radix when defaultChecked", () => {
    render(<Switch aria-label="adaptive toggle" defaultChecked />);
    expect(screen.getByRole("switch", { name: "adaptive toggle" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
  });
});
