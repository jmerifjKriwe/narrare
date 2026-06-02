/**
 * RewriteModeSelector tests — modal for selecting rewrite mode.
 *
 * Tests:
 * 1. Renders modal overlay with title
 * 2. Renders all mode buttons (tone, style, voice, fix, custom)
 * 3. Highlights selected mode
 * 4. Switches mode on click
 * 5. Renders tone options when tone mode selected
 * 6. Renders style options when style mode selected
 * 7. Renders voice input when voice mode selected
 * 8. Renders fix options when fix mode selected
 * 9. Renders custom instructions textarea when custom mode selected
 * 10. Calls onCancel when cancel button clicked
 * 11. Calls onGenerate with correct config
 * 12. Count selector buttons change count
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { RewriteModeSelector } from "@/components/studio/editor/RewriteModeSelector";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const defaultProps = {
  selectionLength: 100,
  onGenerate: vi.fn(),
  onCancel: vi.fn(),
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("RewriteModeSelector", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders modal overlay with title", () => {
    render(<RewriteModeSelector {...defaultProps} />);

    expect(screen.getByText("rewrite.title")).toBeDefined();
  });

  it("renders all five mode buttons", () => {
    render(<RewriteModeSelector {...defaultProps} />);

    expect(screen.getByText("rewrite.modeTone")).toBeDefined();
    expect(screen.getByText("rewrite.modeStyle")).toBeDefined();
    expect(screen.getByText("rewrite.modeVoice")).toBeDefined();
    expect(screen.getByText("rewrite.modeFix")).toBeDefined();
    expect(screen.getByText("rewrite.modeCustom")).toBeDefined();
  });

  it("renders tone options by default (tone mode selected initially)", () => {
    render(<RewriteModeSelector {...defaultProps} />);

    expect(screen.getByText("rewrite.toneOption")).toBeDefined();
    const select = screen.getByDisplayValue("rewrite.toneOptions.moredramatic");
    expect(select).toBeDefined();
  });

  it("switches to style mode on click", () => {
    render(<RewriteModeSelector {...defaultProps} />);

    fireEvent.click(screen.getByText("rewrite.modeStyle"));

    expect(screen.getByText("rewrite.styleOption")).toBeDefined();
  });

  it("switches to voice mode on click", () => {
    render(<RewriteModeSelector {...defaultProps} />);

    fireEvent.click(screen.getByText("rewrite.modeVoice"));

    expect(screen.getByText("rewrite.voiceCharacter")).toBeDefined();
    expect(screen.getByPlaceholderText("rewrite.voiceCharacterPlaceholder")).toBeDefined();
  });

  it("switches to fix mode on click", () => {
    render(<RewriteModeSelector {...defaultProps} />);

    fireEvent.click(screen.getByText("rewrite.modeFix"));

    expect(screen.getByText("rewrite.fixOption")).toBeDefined();
  });

  it("switches to custom mode on click", () => {
    render(<RewriteModeSelector {...defaultProps} />);

    fireEvent.click(screen.getByText("rewrite.modeCustom"));

    expect(screen.getByText("rewrite.customInstructions")).toBeDefined();
    expect(screen.getByPlaceholderText("rewrite.customInstructionsPlaceholder")).toBeDefined();
  });

  it("calls onCancel when cancel button clicked", () => {
    render(<RewriteModeSelector {...defaultProps} />);

    // There are two cancel buttons — footer and header
    const cancelButtons = screen.getAllByText("aiActions.stop");
    fireEvent.click(cancelButtons[0]);

    expect(defaultProps.onCancel).toHaveBeenCalled();
  });

  it("calls onCancel when X button clicked", () => {
    render(<RewriteModeSelector {...defaultProps} />);

    const closeButton = screen.getByLabelText("aiActions.stop");
    fireEvent.click(closeButton);

    expect(defaultProps.onCancel).toHaveBeenCalled();
  });

  it("calls onGenerate with tone config when generate clicked", () => {
    render(<RewriteModeSelector {...defaultProps} />);

    fireEvent.click(screen.getByText("rewrite.generate"));

    expect(defaultProps.onGenerate).toHaveBeenCalledWith({
      mode: "tone",
      option: "more dramatic",
      count: 1,
    });
  });

  it("calls onGenerate with custom instructions in custom mode", () => {
    render(<RewriteModeSelector {...defaultProps} />);

    // Switch to custom mode
    fireEvent.click(screen.getByText("rewrite.modeCustom"));

    // Type custom instructions
    const textarea = screen.getByPlaceholderText("rewrite.customInstructionsPlaceholder");
    fireEvent.change(textarea, { target: { value: "Make it sound like Shakespeare" } });

    // Click generate
    fireEvent.click(screen.getByText("rewrite.generate"));

    expect(defaultProps.onGenerate).toHaveBeenCalledWith(
      expect.objectContaining({
        mode: "custom",
        option: "custom",
        customInstructions: "Make it sound like Shakespeare",
      }),
    );
  });

  it("count selector buttons change count value", () => {
    render(<RewriteModeSelector {...defaultProps} />);

    // Click count 3
    fireEvent.click(screen.getByText("3"));

    // Click generate
    fireEvent.click(screen.getByText("rewrite.generate"));

    expect(defaultProps.onGenerate).toHaveBeenCalledWith(expect.objectContaining({ count: 3 }));
  });

  it("disables generate button when custom mode has no instructions", () => {
    render(<RewriteModeSelector {...defaultProps} />);

    fireEvent.click(screen.getByText("rewrite.modeCustom"));

    // Generate should be disabled since textarea is empty
    const generateBtn = screen.getByText("rewrite.generate").closest("button");
    expect(generateBtn?.disabled).toBe(true);
  });

  it("updates tone option when select changes", () => {
    render(<RewriteModeSelector {...defaultProps} />);

    const select = screen.getByDisplayValue("rewrite.toneOptions.moredramatic");
    fireEvent.change(select, { target: { value: "more subdued" } });

    fireEvent.click(screen.getByText("rewrite.generate"));

    expect(defaultProps.onGenerate).toHaveBeenCalledWith(
      expect.objectContaining({ option: "more subdued" }),
    );
  });
});
