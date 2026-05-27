/**
 * SystemTimeouts tests — timeout configuration inputs.
 *
 * Tests:
 * 1. Renders all three timeout inputs
 * 2. Renders labels for each input
 * 3. Calls onChange with correct values
 * 4. Ignores NaN input
 * 5. Ignores values below minimum
 * 6. Disables inputs when disabled=true
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SystemTimeouts } from "@/components/studio/settings/SystemTimeouts";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const defaultProps = {
  wsTimeout: 120,
  retryMaxAttempts: 3,
  retryBaseDelay: 1.0,
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

  it("renders retry attempts input with label", () => {
    render(<SystemTimeouts {...defaultProps} />);

    expect(screen.getByText("settings.ai.systemTimeouts.retryAttempts")).toBeDefined();
    expect(screen.getByDisplayValue("3")).toBeDefined();
  });

  it("renders retry delay input with label", () => {
    render(<SystemTimeouts {...defaultProps} />);

    expect(screen.getByText("settings.ai.systemTimeouts.retryDelay")).toBeDefined();
    expect(screen.getByDisplayValue("1")).toBeDefined();
  });

  it("calls onChange when ws timeout changes", () => {
    const onChange = vi.fn();
    render(<SystemTimeouts {...defaultProps} onChange={onChange} />);

    const inputs = screen.getAllByRole("spinbutton");
    fireEvent.change(inputs[0], { target: { value: "180" } });

    expect(onChange).toHaveBeenCalledWith({ ws_timeout: 180 });
  });

  it("calls onChange when retry attempts changes", () => {
    const onChange = vi.fn();
    render(<SystemTimeouts {...defaultProps} onChange={onChange} />);

    const inputs = screen.getAllByRole("spinbutton");
    fireEvent.change(inputs[1], { target: { value: "5" } });

    expect(onChange).toHaveBeenCalledWith({ retry_max_attempts: 5 });
  });

  it("calls onChange when retry delay changes", () => {
    const onChange = vi.fn();
    render(<SystemTimeouts {...defaultProps} onChange={onChange} />);

    const inputs = screen.getAllByRole("spinbutton");
    fireEvent.change(inputs[2], { target: { value: "2.5" } });

    expect(onChange).toHaveBeenCalledWith({ retry_base_delay: 2.5 });
  });

  it("ignores NaN input", () => {
    const onChange = vi.fn();
    render(<SystemTimeouts {...defaultProps} onChange={onChange} />);

    const inputs = screen.getAllByRole("spinbutton");
    fireEvent.change(inputs[0], { target: { value: "abc" } });

    expect(onChange).not.toHaveBeenCalled();
  });

  it("ignores ws timeout below minimum (60)", () => {
    const onChange = vi.fn();
    render(<SystemTimeouts {...defaultProps} onChange={onChange} />);

    const inputs = screen.getAllByRole("spinbutton");
    fireEvent.change(inputs[0], { target: { value: "30" } });

    expect(onChange).not.toHaveBeenCalled();
  });

  it("ignores retry attempts outside range", () => {
    const onChange = vi.fn();
    render(<SystemTimeouts {...defaultProps} onChange={onChange} />);

    const inputs = screen.getAllByRole("spinbutton");
    fireEvent.change(inputs[1], { target: { value: "15" } });

    expect(onChange).not.toHaveBeenCalled();
  });

  it("disables all inputs when disabled=true", () => {
    render(<SystemTimeouts {...defaultProps} disabled />);

    const inputs = screen.getAllByRole("spinbutton");
    for (const input of inputs) {
      expect(input).toHaveProperty("disabled", true);
    }
  });

  it("renders hint text for ws timeout", () => {
    render(<SystemTimeouts {...defaultProps} />);

    expect(screen.getByText("settings.ai.systemTimeouts.wsTimeoutHint")).toBeDefined();
  });

  it("renders hint text for retry delay", () => {
    render(<SystemTimeouts {...defaultProps} />);

    expect(screen.getByText("settings.ai.systemTimeouts.retryDelayHint")).toBeDefined();
  });
});
