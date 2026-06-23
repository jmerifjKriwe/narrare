import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SessionReconnectBanner } from "../SessionReconnectBanner";

const labels = {
  reconnectingLabel: "Reconnecting...",
  recoveredLabel: "Session recovered.",
  recoveryFailedLabel: "Recovery failed.",
  connectionLostLabel: "Connection lost.",
  preserveLocalCopyLabel: "Your local text has been preserved.",
  retryLabel: "Reconnect",
};

describe("SessionReconnectBanner", () => {
  it("renders nothing for idle recovery state", () => {
    const { container } = render(
      <SessionReconnectBanner recoveryState="idle" localProse="" onRetry={vi.fn()} {...labels} />,
    );

    expect(container).toBeEmptyDOMElement();
  });

  it("shows reconnecting copy", () => {
    render(
      <SessionReconnectBanner
        recoveryState="reconnecting"
        localProse=""
        onRetry={vi.fn()}
        {...labels}
      />,
    );

    expect(screen.getByText("Reconnecting...")).toBeDefined();
  });

  it("shows recovered copy", () => {
    render(
      <SessionReconnectBanner
        recoveryState="recovered"
        localProse=""
        onRetry={vi.fn()}
        {...labels}
      />,
    );

    expect(screen.getByText("Session recovered.")).toBeDefined();
  });

  it("shows failure copy, preserved prose, and retry action", () => {
    const onRetry = vi.fn();
    render(
      <SessionReconnectBanner
        recoveryState="failed"
        localProse="Preserved local prose"
        onRetry={onRetry}
        {...labels}
      />,
    );

    expect(screen.getByText("Recovery failed.")).toBeDefined();
    expect(screen.getByText("Your local text has been preserved.")).toBeDefined();
    expect(screen.getByText("Preserved local prose")).toBeDefined();

    fireEvent.click(screen.getByRole("button", { name: "Reconnect" }));

    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});
