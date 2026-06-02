/**
 * Connection-lost handler tests — hook + banner component.
 *
 * Tests:
 * 1. useConnectionLost: initial state is not lost
 * 2. useConnectionLost: markConnectionLost sets isConnectionLost true
 * 3. useConnectionLost: clearError resets to false
 * 4. useConnectionLost: retry clears state and calls onRetry
 * 5. ConnectionLostBanner: renders default i18n message
 * 6. ConnectionLostBanner: renders custom message
 * 7. ConnectionLostBanner: retry button fires onRetry
 */

import { act, cleanup, fireEvent, render, renderHook, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ConnectionLostBanner } from "@/components/ui/connection-lost-banner";
import { useConnectionLost } from "@/lib/hooks/use-connection-lost";

// ---------------------------------------------------------------------------
// Hook tests
// ---------------------------------------------------------------------------

describe("useConnectionLost", () => {
  afterEach(() => {
    cleanup();
  });

  it("starts with isConnectionLost false", () => {
    const { result } = renderHook(() => useConnectionLost({ onRetry: vi.fn() }));
    expect(result.current.isConnectionLost).toBe(false);
  });

  it("markConnectionLost sets isConnectionLost to true", () => {
    const { result } = renderHook(() => useConnectionLost({ onRetry: vi.fn() }));
    act(() => {
      result.current.markConnectionLost();
    });
    expect(result.current.isConnectionLost).toBe(true);
  });

  it("clearError resets isConnectionLost to false", () => {
    const { result } = renderHook(() => useConnectionLost({ onRetry: vi.fn() }));
    act(() => {
      result.current.markConnectionLost();
    });
    expect(result.current.isConnectionLost).toBe(true);
    act(() => {
      result.current.clearError();
    });
    expect(result.current.isConnectionLost).toBe(false);
  });

  it("retry clears state and calls onRetry", () => {
    const onRetry = vi.fn();
    const { result } = renderHook(() => useConnectionLost({ onRetry }));
    act(() => {
      result.current.markConnectionLost();
    });
    expect(result.current.isConnectionLost).toBe(true);
    act(() => {
      result.current.retry();
    });
    expect(result.current.isConnectionLost).toBe(false);
    expect(onRetry).toHaveBeenCalledOnce();
  });
});

// ---------------------------------------------------------------------------
// Banner component tests
// ---------------------------------------------------------------------------

describe("ConnectionLostBanner", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders default i18n connectionLost message", () => {
    render(<ConnectionLostBanner onRetry={vi.fn()} />);
    // next-intl mock returns the key as text
    expect(screen.getByText("connectionLost")).toBeTruthy();
  });

  it("renders a custom message when provided", () => {
    render(<ConnectionLostBanner onRetry={vi.fn()} message="Custom error" />);
    expect(screen.getByText("Custom error")).toBeTruthy();
  });

  it("renders retry button with i18n label", () => {
    render(<ConnectionLostBanner onRetry={vi.fn()} />);
    // next-intl mock returns the key as text
    expect(screen.getByText("connectionLostRetry")).toBeTruthy();
  });

  it("fires onRetry when retry button is clicked", () => {
    const onRetry = vi.fn();
    render(<ConnectionLostBanner onRetry={onRetry} />);
    fireEvent.click(screen.getByText("connectionLostRetry"));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("has role='alert' for accessibility", () => {
    render(<ConnectionLostBanner onRetry={vi.fn()} />);
    expect(screen.getByRole("alert")).toBeTruthy();
  });
});
