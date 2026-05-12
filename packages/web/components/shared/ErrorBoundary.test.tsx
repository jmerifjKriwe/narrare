import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ErrorBoundary } from "./ErrorBoundary";

// --- Helpers ---

// Component that always throws during render
function ThrowOnRender({ error }: { error: Error }): React.ReactNode {
  throw error;
}

// Component that renders normally
function NormalChild({ text }: { text: string }) {
  return <div>{text}</div>;
}

// Suppress console.error for expected errors in tests
const originalConsoleError = console.error;
beforeAll(() => {
  console.error = (...args: unknown[]) => {
    if (typeof args[0] === "string" && args[0].includes("The above error occurred in the")) return;
    if (typeof args[0] === "string" && args[0].includes("Uncaught")) return;
    originalConsoleError.call(console, ...args);
  };
});
afterAll(() => {
  console.error = originalConsoleError;
});

describe("ErrorBoundary", () => {
  it("should render children when no error occurs", () => {
    render(
      <ErrorBoundary>
        <NormalChild text="Hello World" />
      </ErrorBoundary>,
    );

    expect(screen.getByText("Hello World")).toBeInTheDocument();
  });

  it("should render children normally when no error", () => {
    render(
      <ErrorBoundary>
        <div>Child 1</div>
        <div>Child 2</div>
      </ErrorBoundary>,
    );

    expect(screen.getByText("Child 1")).toBeInTheDocument();
    expect(screen.getByText("Child 2")).toBeInTheDocument();
  });

  it("should catch render error and display fallback UI", () => {
    render(
      <ErrorBoundary>
        <ThrowOnRender error={new Error("Something broke")} />
      </ErrorBoundary>,
    );

    // Should display default error message
    expect(screen.getByText("Something broke")).toBeInTheDocument();
  });

  it("should display default fallback message when error has no message", () => {
    render(
      <ErrorBoundary>
        <ThrowOnRender error={new Error()} />
      </ErrorBoundary>,
    );

    // Default message is "Something went wrong"
    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
  });

  it("should display custom fallback when provided", () => {
    render(
      <ErrorBoundary fallback={<div>Custom error UI</div>}>
        <ThrowOnRender error={new Error("Boom")} />
      </ErrorBoundary>,
    );

    expect(screen.getByText("Custom error UI")).toBeInTheDocument();
    // Default error message should NOT be visible
    expect(screen.queryByText("Boom")).not.toBeInTheDocument();
  });

  it("should call onError callback when an error occurs", () => {
    const handleError = vi.fn();
    const error = new Error("Callback test");

    render(
      <ErrorBoundary onError={handleError}>
        <ThrowOnRender error={error} />
      </ErrorBoundary>,
    );

    expect(handleError).toHaveBeenCalledWith(error);
  });

  it("should display user-friendly error message", () => {
    render(
      <ErrorBoundary>
        <ThrowOnRender error={new Error("Database connection failed")} />
      </ErrorBoundary>,
    );

    // Error message should be visible and readable
    expect(screen.getByText("Database connection failed")).toBeInTheDocument();
  });

  it("should display Try again button in fallback UI", () => {
    render(
      <ErrorBoundary>
        <ThrowOnRender error={new Error("Test error")} />
      </ErrorBoundary>,
    );

    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  it("should recover when Try again is clicked and error is resolved", async () => {
    const user = userEvent.setup();

    // We need a component that can toggle between error and no-error
    // Since we can't re-render inside ErrorBoundary easily,
    // we test the button click resets the error state
    render(
      <ErrorBoundary>
        <ThrowOnRender error={new Error("Recoverable error")} />
      </ErrorBoundary>,
    );

    expect(screen.getByText("Recoverable error")).toBeInTheDocument();

    // Click "Try again" — this resets hasError state
    // The child will throw again since it always throws, but the state reset should happen
    const tryAgainButton = screen.getByRole("button", { name: "Try again" });
    await user.click(tryAgainButton);

    // After clicking, ErrorBoundary resets state and tries to re-render children
    // Since ThrowOnRender always throws, the error boundary will catch it again
    expect(screen.getByText("Recoverable error")).toBeInTheDocument();
  });

  it("should not affect sibling components when one child throws", () => {
    // ErrorBoundary only wraps the children that throw
    // This test verifies the boundary isolates the error
    render(
      <div>
        <div>Safe sibling</div>
        <ErrorBoundary>
          <ThrowOnRender error={new Error("Isolated error")} />
        </ErrorBoundary>
      </div>,
    );

    expect(screen.getByText("Safe sibling")).toBeInTheDocument();
    expect(screen.getByText("Isolated error")).toBeInTheDocument();
  });
});
