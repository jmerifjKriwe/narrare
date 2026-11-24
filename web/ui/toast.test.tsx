// @vitest-environment jsdom
/**
 * The shell's toast: one polite confirmation, present only while it is
 * worth reading, gone on its own. The live region stays mounted empty from
 * the first paint, so a screen reader hears the message when it lands.
 */
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ToastProvider, useToast } from "./toast";

function Opener({ messages }: { messages: readonly string[] }) {
  const toast = useToast();
  return (
    <>
      {messages.map((message) => (
        <button key={message} type="button" onClick={() => toast.show(message)}>
          {message}
        </button>
      ))}
    </>
  );
}

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe("ToastProvider", () => {
  it("shows the message in a polite live region and dismisses itself", () => {
    vi.useFakeTimers();
    render(
      <ToastProvider>
        <Opener messages={["Entität angelegt · 2 Beziehungen verknüpft"]} />
      </ToastProvider>,
    );
    const region = screen.getByTestId("toast-region");
    expect(region.getAttribute("aria-live")).toBe("polite");
    expect(region.textContent).toBe("");

    fireEvent.click(screen.getByRole("button", { name: "Entität angelegt · 2 Beziehungen verknüpft" }));
    expect(screen.getByTestId("toast").textContent).toContain(
      "Entität angelegt · 2 Beziehungen verknüpft",
    );

    act(() => {
      vi.advanceTimersByTime(6000);
    });
    expect(screen.queryByTestId("toast")).toBeNull();
  });

  it("replaces a standing message instead of stacking a queue", () => {
    render(
      <ToastProvider>
        <Opener messages={["erste", "zweite"]} />
      </ToastProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: "erste" }));
    fireEvent.click(screen.getByRole("button", { name: "zweite" }));
    expect(screen.getAllByTestId("toast")).toHaveLength(1);
    expect(screen.getByTestId("toast").textContent).toContain("zweite");
  });
});
