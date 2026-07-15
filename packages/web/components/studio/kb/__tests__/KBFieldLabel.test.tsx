/**
 * KBFieldLabel tests — field label with required indicator and help tooltip.
 *
 * Tests:
 * 1. Renders the label text
 * 2. Renders required asterisk when required
 * 3. Does not render asterisk when not required
 * 4. Renders help tooltip (title) when helpText provided
 * 5. Does not render help tooltip when helpText omitted
 * 6. Renders as <span> when as="span"
 * 7. Applies custom className override
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { KBFieldLabel } from "@/components/studio/kb/KBFieldLabel";

describe("KBFieldLabel", () => {
  it("renders the label text", () => {
    render(<KBFieldLabel label="Full Name" />);

    expect(screen.getByText("Full Name")).toBeDefined();
  });

  it("renders required asterisk when required", () => {
    render(<KBFieldLabel label="Full Name" required />);

    expect(screen.getByText("*")).toBeDefined();
  });

  it("does not render asterisk when not required", () => {
    render(<KBFieldLabel label="Full Name" />);

    expect(screen.queryByText("*")).toBeNull();
  });

  it("renders help tooltip when helpText provided", () => {
    render(<KBFieldLabel label="Full Name" helpText="The character's full name" />);

    // The wrapping span carries the native tooltip via its title attribute.
    expect(screen.getByTitle("The character's full name")).toBeDefined();
  });

  it("does not render help tooltip when helpText omitted", () => {
    render(<KBFieldLabel label="Full Name" />);

    expect(screen.queryByTitle("The character's full name")).toBeNull();
  });

  it("renders as a span when as='span'", () => {
    const { container } = render(<KBFieldLabel as="span" label="Tags" />);

    // The rendered element is a <span>, not a <label>.
    expect(container.querySelector("label")).toBeNull();
    expect(container.querySelector("span")).not.toBeNull();
  });

  it("renders as a label with htmlFor by default", () => {
    const { container } = render(<KBFieldLabel htmlFor="my-input" label="Name" />);

    const label = container.querySelector("label");
    expect(label).not.toBeNull();
    expect(label?.getAttribute("for")).toBe("my-input");
  });

  it("applies custom className override", () => {
    const { container } = render(
      <KBFieldLabel label="Name" className="text-sm font-bold text-red-500" />,
    );

    expect(container.querySelector(".text-red-500")).not.toBeNull();
  });
});
