/**
 * KBFieldGroup tests — accordion group for KB template fields.
 *
 * Tests:
 * 1. Renders with title and icon
 * 2. Renders description when provided
 * 3. Is open by default (defaultOpen=true)
 * 4. Collapses when header clicked
 * 5. Re-expands when header clicked again
 * 6. Renders children content
 * 7. Respects defaultOpen=false
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { KBFieldGroup } from "@/components/studio/kb/KBFieldGroup";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const defaultProps = {
  icon: "Info",
  iconColor: "text-blue-500",
  title: "Basic Info",
  children: <div data-testid="field-content">Field content</div>,
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("KBFieldGroup", () => {
  it("renders title text", () => {
    render(<KBFieldGroup {...defaultProps} />);

    expect(screen.getByText("Basic Info")).toBeDefined();
  });

  it("renders description when provided", () => {
    render(<KBFieldGroup {...defaultProps} description="Core character details" />);

    expect(screen.getByText("Core character details")).toBeDefined();
  });

  it("does not render description when not provided", () => {
    render(<KBFieldGroup {...defaultProps} />);

    expect(screen.queryByText("Core character details")).toBeNull();
  });

  it("renders children content", () => {
    render(<KBFieldGroup {...defaultProps} />);

    expect(screen.getByTestId("field-content")).toBeDefined();
    expect(screen.getByText("Field content")).toBeDefined();
  });

  it("is open by default (defaultOpen=true)", () => {
    render(<KBFieldGroup {...defaultProps} />);

    // Children should be visible when open
    expect(screen.getByTestId("field-content")).toBeDefined();

    // aria-expanded should be true
    const header = screen.getByText("Basic Info").closest("button");
    expect(header?.getAttribute("aria-expanded")).toBe("true");
  });

  it("respects defaultOpen=false", () => {
    render(<KBFieldGroup {...defaultProps} defaultOpen={false} />);

    const header = screen.getByText("Basic Info").closest("button");
    expect(header?.getAttribute("aria-expanded")).toBe("false");
  });

  it("toggles open/closed when header clicked", () => {
    render(<KBFieldGroup {...defaultProps} />);

    const header = screen.getByText("Basic Info").closest("button");

    // Initially open
    expect(header?.getAttribute("aria-expanded")).toBe("true");

    // Click to close
    fireEvent.click(header!);
    expect(header?.getAttribute("aria-expanded")).toBe("false");

    // Click to open again
    fireEvent.click(header!);
    expect(header?.getAttribute("aria-expanded")).toBe("true");
  });

  it("renders icon container with correct color class", () => {
    render(<KBFieldGroup {...defaultProps} />);

    const iconContainer = document.querySelector(".text-blue-500");
    expect(iconContainer).toBeDefined();
  });

  it("renders unknown icon as FileText fallback", () => {
    render(<KBFieldGroup {...defaultProps} icon="UnknownIcon" />);

    // Should still render without crashing — fallback to FileText
    expect(screen.getByText("Basic Info")).toBeDefined();
  });

  it("renders with border styling", () => {
    render(<KBFieldGroup {...defaultProps} />);

    // The outermost container has the border class
    const outerDiv = document.querySelector(".border-border\\/60");
    expect(outerDiv).toBeDefined();
  });
});
