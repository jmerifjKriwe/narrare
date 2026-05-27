/**
 * GhostTextConfig tests — toolbar control for Ghost Text extension.
 *
 * Tests:
 * 1. Renders toggle button with label
 * 2. Toggle button is pressed by default (enabled)
 * 3. Calls handleToggle to disable on click
 * 4. Shows delay slider when enabled
 * 5. Hides delay slider when disabled
 * 6. Updates delay on slider change
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { GhostTextConfig } from "@/components/studio/editor/GhostTextConfig";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mockSetEnabled = vi.fn();
const mockSetDelay = vi.fn();

function createMockEditor(enabled = true, delay = 800) {
  return {
    isDestroyed: false,
    storage: {
      ghostText: {
        enabled,
        delay,
        setEnabled: mockSetEnabled,
        setDelay: mockSetDelay,
      },
    },
  };
}

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: (key: string) => store[key] ?? null,
    setItem: (key: string, value: string) => {
      store[key] = value;
    },
    clear: () => {
      store = {};
    },
  };
})();

Object.defineProperty(window, "localStorage", { value: localStorageMock });

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("GhostTextConfig", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorageMock.clear();
  });

  it("renders toggle button with label", () => {
    render(<GhostTextConfig editor={null} />);

    expect(screen.getByText("ghostTextToggle")).toBeDefined();
  });

  it("renders fieldset with aria-label", () => {
    render(<GhostTextConfig editor={null} />);

    const fieldset = screen.getByText("ghostTextToggle").closest("fieldset");
    expect(fieldset?.getAttribute("aria-label")).toBe("ghostTextToggle");
  });

  it("returns null when editor is null (renders nothing but toggle)", () => {
    render(<GhostTextConfig editor={null} />);

    // Component still renders the UI but sync effect skips
    expect(screen.getByText("ghostTextToggle")).toBeDefined();
  });

  it("shows delay slider when enabled", () => {
    // Default state: enabled=true
    render(<GhostTextConfig editor={null} />);

    expect(screen.getByText("ghostTextDelay")).toBeDefined();
    expect(screen.getByLabelText("ghostTextDelay")).toBeDefined();
  });

  it("toggles enabled state on button click", () => {
    render(<GhostTextConfig editor={null} />);

    const toggleBtn = screen.getByText("ghostTextToggle").closest("button")!;
    expect(toggleBtn.getAttribute("aria-pressed")).toBe("true");

    fireEvent.click(toggleBtn);

    // After click, should be false
    expect(toggleBtn.getAttribute("aria-pressed")).toBe("false");
  });

  it("hides delay slider when disabled", () => {
    render(<GhostTextConfig editor={null} />);

    const toggleBtn = screen.getByText("ghostTextToggle").closest("button")!;
    fireEvent.click(toggleBtn); // disable

    expect(screen.queryByText("ghostTextDelay")).toBeNull();
  });

  it("syncs enabled state to editor storage", () => {
    const editor = createMockEditor();
    render(<GhostTextConfig editor={editor as unknown as never} />);

    expect(mockSetEnabled).toHaveBeenCalledWith(true);
  });

  it("syncs delay state to editor storage", () => {
    const editor = createMockEditor();
    render(<GhostTextConfig editor={editor as unknown as never} />);

    expect(mockSetDelay).toHaveBeenCalledWith(800);
  });

  it("updates delay on slider change", () => {
    render(<GhostTextConfig editor={null} />);

    const slider = screen.getByLabelText("ghostTextDelay");
    fireEvent.change(slider, { target: { value: "1200" } });

    // Verify localStorage was updated
    expect(localStorageMock.getItem("ghostText.delay")).toBe("1200");
  });

  it("persists toggle state in localStorage", () => {
    render(<GhostTextConfig editor={null} />);

    const toggleBtn = screen.getByText("ghostTextToggle").closest("button")!;
    fireEvent.click(toggleBtn); // disable

    expect(localStorageMock.getItem("ghostText.enabled")).toBe("false");
  });
});
