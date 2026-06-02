/**
 * Toast notification system tests.
 *
 * Tests:
 * 1. Toaster component renders without errors
 * 2. toast.success is callable
 * 3. toast.error is callable
 * 4. toast.info is callable
 * 5. toast.warning is callable
 * 6. Actionable toast renders action button
 */

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { toast } from "sonner";
import { afterEach, describe, expect, it } from "vitest";
import { Toaster } from "@/components/ui/toaster";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function renderToaster() {
  return render(<Toaster />);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("Toast System", () => {
  afterEach(() => {
    cleanup();
    toast.dismiss();
  });

  it("renders the Toaster component without errors", () => {
    const { container } = renderToaster();
    // sonner renders into a <ol> with [data-sonner-toaster] or just renders a list
    // In jsdom it may use a different container — just verify no crash
    expect(container).toBeTruthy();
  });

  it("displays a success toast", async () => {
    renderToaster();
    toast.success("Operation succeeded");

    await waitFor(() => {
      expect(screen.getByText("Operation succeeded")).toBeTruthy();
    });
  });

  it("displays an error toast", async () => {
    renderToaster();
    toast.error("Something went wrong");

    await waitFor(() => {
      expect(screen.getByText("Something went wrong")).toBeTruthy();
    });
  });

  it("displays an info toast", async () => {
    renderToaster();
    toast.info("FYI");

    await waitFor(() => {
      expect(screen.getByText("FYI")).toBeTruthy();
    });
  });

  it("displays a warning toast", async () => {
    renderToaster();
    toast.warning("Heads up");

    await waitFor(() => {
      expect(screen.getByText("Heads up")).toBeTruthy();
    });
  });

  it("displays actionable toast with a button", async () => {
    renderToaster();
    toast.error("Upload failed", {
      action: { label: "Retry", onClick: () => {} },
    });

    await waitFor(() => {
      expect(screen.getByText("Upload failed")).toBeTruthy();
      expect(screen.getByText("Retry")).toBeTruthy();
    });
  });
});
