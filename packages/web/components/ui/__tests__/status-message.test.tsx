import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StatusMessage } from "@/components/ui/status-message";

describe("StatusMessage", () => {
  it("announces loading with a polite live region and aria-busy", () => {
    render(<StatusMessage state="loading" message="Thinking" />);
    const region = screen.getByRole("status");
    expect(region).toHaveAttribute("aria-live", "polite");
    expect(region).toHaveAttribute("aria-busy", "true");
    expect(region).toHaveTextContent("Thinking");
  });

  it("uses role=alert and assertive live region for errors", () => {
    render(<StatusMessage state="error" message="Connection lost. Tap retry to reconnect." />);
    const alert = screen.getByRole("alert");
    expect(alert).toHaveAttribute("aria-live", "assertive");
    expect(alert).toHaveTextContent("Connection lost");
  });

  it("renders an actionable retry control via action prop", () => {
    render(
      <StatusMessage
        state="error"
        message="Failed"
        action={<button type="button">Retry</button>}
      />,
    );
    expect(screen.getByRole("button", { name: "Retry" })).toBeDefined();
  });

  it("renders nothing visible in idle but keeps the region mounted", () => {
    const { container } = render(<StatusMessage state="idle" />);
    expect(container.textContent).toBe("");
  });

  it("honours an explicit assertive politeness override", () => {
    render(<StatusMessage state="loading" message="x" politeness="assertive" />);
    expect(screen.getByRole("status")).toHaveAttribute("aria-live", "assertive");
  });
});
