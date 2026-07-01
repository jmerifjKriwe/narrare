/**
 * SystemTimeouts tests — WebSocket timeout configuration input.
 *
 * Only the WebSocket idle timeout is user-configurable; the former retry
 * controls were a false surface removed end-to-end per ADR-060.
 *
 * Tests:
 * 1. Renders the ws timeout input with its label
 * 2. Calls onChange with the rounded value when ws timeout changes
 * 3. Ignores NaN input
 * 4. Ignores values below the 60-second minimum
 * 5. Disables the input when disabled=true
 * 6. Renders the ws timeout hint text
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SystemTimeouts } from "@/components/studio/settings/SystemTimeouts";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const defaultProps = {
  wsTimeout: 120,
  onChange: vi.fn(),
  disabled: false,
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("SystemTimeouts", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders ws timeout input with label", () => {
    render(<SystemTimeouts {...defaultProps} />);

    expect(screen.getByText("settings.ai.systemTimeouts.wsTimeout")).toBeDefined();
    expect(screen.getByDisplayValue("120")).toBeDefined();
  });

  it("renders exactly one configurable timeout input", () => {
    render(<SystemTimeouts {...defaultProps} />);

    // The retry inputs were removed (ADR-060); only ws_timeout remains.
    expect(screen.getAllByRole("spinbutton")).toHaveLength(1);
  });

  it("calls onChange when ws timeout changes", () => {
    const onChange = vi.fn();
    render(<SystemTimeouts {...defaultProps} onChange={onChange} />);

    const input = screen.getByDisplayValue("120");
    fireEvent.change(input, { target: { value: "180" } });

    expect(onChange).toHaveBeenCalledWith({ ws_timeout: 180 });
  });

  it("rounds fractional ws timeout to an integer", () => {
    const onChange = vi.fn();
    render(<SystemTimeouts {...defaultProps} onChange={onChange} />);

    const input = screen.getByDisplayValue("120");
    fireEvent.change(input, { target: { value: "150.7" } });

    expect(onChange).toHaveBeenCalledWith({ ws_timeout: 151 });
  });

  it("ignores NaN input", () => {
    const onChange = vi.fn();
    render(<SystemTimeouts {...defaultProps} onChange={onChange} />);

    const input = screen.getByDisplayValue("120");
    fireEvent.change(input, { target: { value: "abc" } });

    expect(onChange).not.toHaveBeenCalled();
  });

  it("ignores ws timeout below minimum (60)", () => {
    const onChange = vi.fn();
    render(<SystemTimeouts {...defaultProps} onChange={onChange} />);

    const input = screen.getByDisplayValue("120");
    fireEvent.change(input, { target: { value: "30" } });

    expect(onChange).not.toHaveBeenCalled();
  });

  it("disables the input when disabled=true", () => {
    render(<SystemTimeouts {...defaultProps} disabled />);

    const input = screen.getByDisplayValue("120");
    expect(input).toHaveProperty("disabled", true);
  });

  it("renders hint text for ws timeout", () => {
    render(<SystemTimeouts {...defaultProps} />);

    expect(screen.getByText("settings.ai.systemTimeouts.wsTimeoutHint")).toBeDefined();
  });
});
