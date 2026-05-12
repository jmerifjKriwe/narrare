import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Button } from "./Button";

describe("Button", () => {
  it("should render with text content", () => {
    render(<Button>Click me</Button>);

    const button = screen.getByRole("button", { name: "Click me" });
    expect(button).toBeInTheDocument();
  });

  it("should handle click events", async () => {
    const user = userEvent.setup();
    const handleClick = vi.fn();

    render(<Button onClick={handleClick}>Click me</Button>);

    await user.click(screen.getByRole("button", { name: "Click me" }));

    expect(handleClick).toHaveBeenCalledOnce();
  });

  it("should be disabled when disabled prop is true", () => {
    render(<Button disabled>Disabled</Button>);

    const button = screen.getByRole("button", { name: "Disabled" });
    expect(button).toBeDisabled();
  });

  it("should be disabled when loading prop is true", () => {
    render(<Button loading>Loading</Button>);

    const button = screen.getByRole("button");
    expect(button).toBeDisabled();
  });

  it("should show spinner when loading", () => {
    render(<Button loading>Save</Button>);

    const spinner = screen.getByRole("button").querySelector('[class*="animate-spin"]');
    expect(spinner).toBeInTheDocument();
  });

  it("should not call onClick when disabled", async () => {
    const user = userEvent.setup();
    const handleClick = vi.fn();

    render(
      <Button disabled onClick={handleClick}>
        Nope
      </Button>,
    );

    await user.click(screen.getByRole("button"));
    expect(handleClick).not.toHaveBeenCalled();
  });

  it("should render with different variant classes", () => {
    const { rerender } = render(<Button variant="secondary">Secondary</Button>);

    expect(screen.getByRole("button").className).toContain("bg-secondary");

    rerender(<Button variant="danger">Danger</Button>);
    expect(screen.getByRole("button").className).toContain("bg-destructive");

    rerender(<Button variant="ghost">Ghost</Button>);
    expect(screen.getByRole("button").className).toContain("hover:bg-muted");
  });

  it("should render with different size classes", () => {
    const { rerender } = render(<Button size="sm">Small</Button>);

    expect(screen.getByRole("button").className).toContain("px-3");

    rerender(<Button size="lg">Large</Button>);
    expect(screen.getByRole("button").className).toContain("px-6");
  });

  it("should apply default variant as primary", () => {
    render(<Button>Default</Button>);

    expect(screen.getByRole("button").className).toContain("bg-primary");
  });
});
