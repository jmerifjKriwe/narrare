// @vitest-environment jsdom
/**
 * The shell's toast: one polite confirmation, present only while it is
 * worth reading, gone on its own. The live region stays mounted empty from
 * the first paint, so a screen reader hears the message when it lands.
 */
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { catalogs } from "@shell/lib/generated/catalogs";
import { applyLocale } from "@shell/lib/locale";

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

beforeEach(() => {
  applyLocale("de");
});

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

  it("keeps a replacement message paused while the pointer stays on it", () => {
    vi.useFakeTimers();
    render(
      <ToastProvider>
        <Opener messages={["erste", "zweite"]} />
      </ToastProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: "erste" }));
    const toast = screen.getByTestId("toast");
    fireEvent.mouseEnter(toast);

    act(() => {
      vi.advanceTimersByTime(5000);
    });
    // The replacement lands under the pointer: no new mouseenter follows.
    fireEvent.click(screen.getByRole("button", { name: "zweite" }));
    act(() => {
      vi.advanceTimersByTime(60_000);
    });
    expect(screen.getByTestId("toast").textContent).toContain("zweite");

    // The fresh lifetime starts only once the pointer actually leaves.
    fireEvent.mouseLeave(screen.getByTestId("toast"));
    act(() => {
      vi.advanceTimersByTime(5999);
    });
    expect(screen.getByTestId("toast")).toBeTruthy();
    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(screen.queryByTestId("toast")).toBeNull();
  });

  it("a message shown right after a dismissal starts paused while the pointer stays", () => {
    vi.useFakeTimers();
    render(
      <ToastProvider>
        <Opener messages={["erste", "zweite"]} />
      </ToastProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: "erste" }));
    fireEvent.mouseEnter(screen.getByTestId("toast"));

    // Dismiss while the pointer rests on the toast's area: the close button
    // goes with the toast, so no mouseleave can follow until a new one mounts.
    fireEvent.click(screen.getByRole("button", { name: catalogs.de["shell.toast.dismiss"] }));
    expect(screen.queryByTestId("toast")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "zweite" }));
    act(() => {
      vi.advanceTimersByTime(60_000);
    });
    expect(screen.getByTestId("toast").textContent).toContain("zweite");

    // The fresh lifetime starts only when the pointer actually leaves.
    fireEvent.mouseLeave(screen.getByTestId("toast"));
    act(() => {
      vi.advanceTimersByTime(5999);
    });
    expect(screen.getByTestId("toast")).toBeTruthy();
    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(screen.queryByTestId("toast")).toBeNull();
  });

  it("pauses on hover and resumes when the pointer leaves", () => {
    vi.useFakeTimers();
    render(
      <ToastProvider>
        <Opener messages={["Meldung"]} />
      </ToastProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Meldung" }));
    const toast = screen.getByTestId("toast");

    act(() => {
      vi.advanceTimersByTime(5000);
    });
    fireEvent.mouseEnter(toast);
    act(() => {
      vi.advanceTimersByTime(10_000);
    });
    expect(screen.getByTestId("toast")).toBeTruthy();

    // The remaining second resumes only after both hover and focus leave.
    fireEvent.mouseLeave(toast);
    act(() => {
      vi.advanceTimersByTime(999);
    });
    expect(screen.getByTestId("toast")).toBeTruthy();
    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(screen.queryByTestId("toast")).toBeNull();
  });

  it("pauses while a control inside it has focus", () => {
    vi.useFakeTimers();
    render(
      <ToastProvider>
        <Opener messages={["Meldung"]} />
      </ToastProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Meldung" }));
    const close = screen.getByRole("button", { name: catalogs.de["shell.toast.dismiss"] });

    act(() => {
      vi.advanceTimersByTime(2000);
    });
    fireEvent.focus(close);
    act(() => {
      vi.advanceTimersByTime(10_000);
    });
    expect(screen.getByTestId("toast")).toBeTruthy();

    // Four seconds remained; the clock restarts at the leave.
    fireEvent.blur(close);
    act(() => {
      vi.advanceTimersByTime(3999);
    });
    expect(screen.getByTestId("toast")).toBeTruthy();
    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(screen.queryByTestId("toast")).toBeNull();
  });

  it("gives the close control a 24 px hit area without growing the icon", () => {
    render(
      <ToastProvider>
        <Opener messages={["Meldung"]} />
      </ToastProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Meldung" }));
    const close = screen.getByRole("button", { name: catalogs.de["shell.toast.dismiss"] });

    // jsdom lays nothing out, so the box is asserted as the class contract:
    // h-6/w-6 are 24 CSS px on the shell's 16 px root (WCAG 2.2 2.5.8).
    expect(close.className.split(/\s+/)).toEqual(
      expect.arrayContaining(["h-6", "w-6", "items-center", "justify-center"]),
    );
    // The glyph's own visual size is unchanged at 12 px.
    const icon = close.querySelector("svg");
    expect(icon?.getAttribute("width")).toBe("12");
    expect(icon?.getAttribute("height")).toBe("12");
  });

  it("dismisses at once from its named close button and leaves no timer", () => {
    vi.useFakeTimers();
    render(
      <ToastProvider>
        <Opener messages={["Meldung"]} />
      </ToastProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Meldung" }));
    fireEvent.click(screen.getByRole("button", { name: catalogs.de["shell.toast.dismiss"] }));
    expect(screen.queryByTestId("toast")).toBeNull();
    expect(vi.getTimerCount()).toBe(0);

    // No leaked timer can resurrect it.
    act(() => {
      vi.advanceTimersByTime(6000);
    });
    expect(screen.queryByTestId("toast")).toBeNull();
  });

  it("clears its timer on unmount", () => {
    vi.useFakeTimers();
    const { unmount } = render(
      <ToastProvider>
        <Opener messages={["Meldung"]} />
      </ToastProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Meldung" }));
    expect(vi.getTimerCount()).toBeGreaterThan(0);
    unmount();
    expect(vi.getTimerCount()).toBe(0);
  });
});
