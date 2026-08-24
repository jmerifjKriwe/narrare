/**
 * QuickCapture tests (NOTES-001 §7): provider shortcut opens the panel,
 * capture creates a note and toasts with the scratchpad link, save resets.
 *
 * Beyond the brief's four cases: Escape closes (this panel owns its own
 * listener — unlike NotesChatDrawer it hosts no ChatPanel), the shortcut
 * TOGGLES, the text field autofocuses on open, the POST body carries the
 * captured draft, the toast action navigates to /scratchpad, and a failed
 * save toasts an error while the panel stays open (state coverage).
 *
 * Harness notes (mirrors NoteEditor.test.tsx conventions):
 * - setupTests provides NO global QueryClientProvider — the provider is
 *   rendered inside a fresh one because the panel mounts useCreateNote.
 * - sonner is mocked at file level (toast.success/error spy); the toast
 *   action's onClick is invoked directly to assert its navigation.
 * - next/navigation is re-mocked locally to capture router.push.
 * - The centralized next-intl mock returns KEY STRINGS verbatim, so toast
 *   labels assert as "quickCapture.*" keys.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { toast } from "sonner";
import { describe, expect, it, vi } from "vitest";
import { server } from "@/mocks/server";
import { QuickCaptureProvider, useQuickCapture } from "../QuickCaptureProvider";

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

const routerPush = vi.hoisted(() => vi.fn());
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: routerPush,
    replace: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
  }),
  useParams: () => ({}),
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => "/",
}));

function OpenButton() {
  const { open } = useQuickCapture();
  return (
    <button type="button" data-testid="qc-open" onClick={open}>
      open
    </button>
  );
}

function renderProvider(children: React.ReactElement = <OpenButton />) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <QuickCaptureProvider>{children}</QuickCaptureProvider>
    </QueryClientProvider>,
  );
}

const createdNote = {
  id: "n1",
  title: null,
  content: "thought",
  note_type: "idea",
  tags: [],
  novel_id: null,
  series_id: null,
  created_at: "2026-08-21T00:00:00Z",
  updated_at: "2026-08-21T00:00:00Z",
};

describe("QuickCapture", () => {
  it("opens via the Ctrl/Cmd+Shift+U shortcut", () => {
    renderProvider();
    fireEvent.keyDown(window, { metaKey: true, shiftKey: true, key: "U" });
    expect(screen.getByTestId("quick-capture-panel")).toBeInTheDocument();
  });

  it("does not open on unrelated combos", () => {
    renderProvider();
    fireEvent.keyDown(window, { metaKey: true, shiftKey: true, key: "N" });
    fireEvent.keyDown(window, { metaKey: true, key: "u" });
    fireEvent.keyDown(window, { ctrlKey: true, shiftKey: true, key: "u" });
    expect(screen.queryByTestId("quick-capture-panel")).not.toBeInTheDocument();
  });

  it("toggles closed when the shortcut fires again", () => {
    renderProvider();
    fireEvent.keyDown(window, { metaKey: true, shiftKey: true, key: "U" });
    expect(screen.getByTestId("quick-capture-panel")).toBeInTheDocument();
    fireEvent.keyDown(window, { metaKey: true, shiftKey: true, key: "U" });
    expect(screen.queryByTestId("quick-capture-panel")).not.toBeInTheDocument();
  });

  it("keeps the context value referentially stable across provider re-renders", () => {
    // Regression (P-FE1): the inline `{ open }` value re-created the context
    // object on every provider render, so isOpen transitions re-rendered ALL
    // useQuickCapture consumers needlessly. With the memoized value, a
    // consumer must render exactly once and keep the same object identity.
    const seen: ReturnType<typeof useQuickCapture>[] = [];
    let renders = 0;
    function Probe() {
      renders += 1;
      seen.push(useQuickCapture());
      return null;
    }
    renderProvider(<Probe />);
    fireEvent.keyDown(window, { metaKey: true, shiftKey: true, key: "U" });
    expect(screen.getByTestId("quick-capture-panel")).toBeInTheDocument();
    expect(renders).toBe(1);
    expect(seen[seen.length - 1]).toBe(seen[0]);
  });

  it("closes on Escape and autofocuses the text field on open", () => {
    renderProvider();
    fireEvent.click(screen.getByTestId("qc-open"));
    expect(screen.getByTestId("qc-text")).toHaveFocus();
    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.queryByTestId("quick-capture-panel")).not.toBeInTheDocument();
  });

  it("labels the close button as closing the capture, not opening it (a11y)", () => {
    renderProvider();
    fireEvent.click(screen.getByTestId("qc-open"));
    expect(screen.getByTestId("qc-close")).toHaveAccessibleName("quickCapture.close");
  });

  it("captures a note and toasts success", async () => {
    let captured: Record<string, unknown> | undefined;
    server.use(
      http.post("*/api/v1/notes", async ({ request }) => {
        captured = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(createdNote, { status: 201 });
      }),
    );
    renderProvider();
    fireEvent.click(screen.getByTestId("qc-open"));
    fireEvent.change(screen.getByTestId("qc-text"), { target: { value: "thought" } });
    fireEvent.click(screen.getByTestId("qc-save"));
    await waitFor(() => expect(toast.success).toHaveBeenCalled());
    expect(captured).toMatchObject({
      title: null,
      content: "thought",
      note_type: "idea",
      tags: [],
    });
    // Panel resets and closes after a successful capture.
    await waitFor(() =>
      expect(screen.queryByTestId("quick-capture-panel")).not.toBeInTheDocument(),
    );
  });

  it("toast action opens the scratchpad", async () => {
    server.use(http.post("*/api/v1/notes", () => HttpResponse.json(createdNote, { status: 201 })));
    renderProvider();
    fireEvent.click(screen.getByTestId("qc-open"));
    fireEvent.change(screen.getByTestId("qc-text"), { target: { value: "thought" } });
    fireEvent.click(screen.getByTestId("qc-save"));
    await waitFor(() => expect(toast.success).toHaveBeenCalled());
    const options = vi.mocked(toast.success).mock.calls[0]?.[1];
    expect(options?.action).toMatchObject({ label: "quickCapture.openInScratchpad" });
    // sonner types `action` as Action | ReactNode; our toast always builds
    // the Action shape — the cast plus toDefined fail loudly if that breaks.
    const action = options?.action as { onClick: () => void } | undefined;
    expect(action).toBeDefined();
    action?.onClick();
    expect(routerPush).toHaveBeenCalledWith("/scratchpad");
  });

  it("keeps the panel open when saving an empty thought", () => {
    renderProvider();
    fireEvent.click(screen.getByTestId("qc-open"));
    fireEvent.click(screen.getByTestId("qc-save"));
    expect(screen.getByTestId("quick-capture-panel")).toBeInTheDocument();
  });

  it("toasts an error and stays open when the create fails", async () => {
    server.use(http.post("*/api/v1/notes", () => new HttpResponse(null, { status: 500 })));
    renderProvider();
    fireEvent.click(screen.getByTestId("qc-open"));
    fireEvent.change(screen.getByTestId("qc-text"), { target: { value: "thought" } });
    fireEvent.click(screen.getByTestId("qc-save"));
    await waitFor(() => expect(toast.error).toHaveBeenCalled());
    expect(screen.getByTestId("quick-capture-panel")).toBeInTheDocument();
  });
});
