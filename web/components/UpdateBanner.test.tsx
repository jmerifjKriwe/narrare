// @vitest-environment jsdom
/**
 * The shell's update surfaces: the persistent banner under the topbar, the
 * start toast, and the release-notes modal. The shell's own hook is mocked to
 * read the query cache (the test seeds the start answer), so the dismissal's
 * `setQueryData` is what hides the strip — the production path, not a local
 * flag. The API client is mocked at its module boundary; catalogs are real.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { createElement, type ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../lib/updates", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/updates")>();
  const { useQuery } = await import("@tanstack/react-query");
  return {
    ...actual,
    // The start ask is the app's; here the cache is the only source, so a test
    // seeds the answer and a dismissal's setQueryData re-renders the banner.
    useUpdateCheck: () =>
      useQuery({
        queryKey: actual.UPDATE_KEY,
        queryFn: () => Promise.reject(new Error("the test seeds the cache")),
        enabled: false,
        staleTime: Infinity,
      }),
  };
});

vi.mock("../lib/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/api/client")>();
  return {
    ...actual,
    client: {
      GET: vi.fn(),
      POST: vi.fn(),
      PATCH: vi.fn(),
      PUT: vi.fn(),
      DELETE: vi.fn(),
    },
  };
});

import { client } from "../lib/api/client";
import { applyLocale } from "../lib/locale";
import { UPDATE_KEY, type UpdateRead } from "../lib/updates";
import { resetAnnouncedUpdates, UpdateBanner } from "./UpdateBanner";

/** The client's methods as plain mocks; the real client's generics stay out. */
const api = client as unknown as Record<
  "GET" | "POST" | "PATCH" | "PUT" | "DELETE",
  ReturnType<typeof vi.fn>
>;

function ok(): Response {
  return new Response(null, { status: 200 });
}

const AVAILABLE: UpdateRead = {
  current_version: "0.5.0",
  latest_version: "v999.0.0",
  update_available: true,
  release_notes:
    "# Die Neuerungen\n\n## Notes\n\n- Der Banner zeigt neue Versionen.\n\nEin **Satz** mit `code`.\n\n<script>alert(1)</script>",
  release_url: "https://example.test/release",
  dismissed: false,
  checked_at: "2026-11-24T10:00:00Z",
};

const UNAVAILABLE: UpdateRead = {
  ...AVAILABLE,
  update_available: false,
  latest_version: null,
  release_notes: null,
  release_url: null,
};

const DISMISSED: UpdateRead = {
  ...AVAILABLE,
  update_available: false,
  dismissed: true,
};

/**
 * Render the banner over a fresh cache. No answer seeds nothing — the pending
 * / failed face the start check shows. The `main` element is the shell's one
 * landmark (`ChromeFrame`), the focus fallback when a dismissed strip takes its
 * opener with it.
 */
function renderBanner(answer?: UpdateRead) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  if (answer !== undefined) queryClient.setQueryData(UPDATE_KEY, answer);
  const wrapper = ({ children }: { children: ReactNode }) =>
    createElement(
      QueryClientProvider,
      { client: queryClient },
      createElement("main", { id: "main", tabIndex: 0 }),
      children,
    );
  const view = render(createElement(UpdateBanner), { wrapper });
  return { queryClient, ...view };
}

async function openNotes(): Promise<HTMLElement> {
  fireEvent.click(screen.getByRole("button", { name: "Release notes" }));
  return screen.findByRole("dialog");
}

beforeEach(() => {
  applyLocale("en");
  resetAnnouncedUpdates();
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  vi.useRealTimers();
  applyLocale(null);
});

describe("UpdateBanner — the persistent strip", () => {
  it("renders nothing while the check is pending or failed", () => {
    renderBanner();

    expect(screen.queryByTestId("update-banner")).toBeNull();
    expect(screen.queryByTestId("update-toast")).toBeNull();
    expect(screen.queryByText(/is available/)).toBeNull();
  });

  it("stands silent when no newer release is available", () => {
    renderBanner(UNAVAILABLE);

    expect(screen.queryByTestId("update-banner")).toBeNull();
    expect(screen.queryByTestId("update-toast")).toBeNull();
    expect(screen.queryByText(/is available/)).toBeNull();
  });

  it("names the version and opens the notes from its door", async () => {
    renderBanner(AVAILABLE);

    const banner = screen.getByTestId("update-banner");
    // The strip is not a live region: the toast alone announces availability.
    expect(banner.getAttribute("role")).toBeNull();
    expect(banner.getAttribute("aria-live")).toBeNull();
    expect(within(banner).getByText("Narrare v999.0.0 is available")).toBeTruthy();
    expect(within(banner).getByRole("button", { name: "Release notes" })).toBeTruthy();
    expect(within(banner).getByRole("button", { name: "Later" })).toBeTruthy();

    const dialog = await openNotes();
    expect(dialog.getAttribute("aria-modal")).toBe("true");
    expect(within(dialog).getByRole("heading", { name: "What changed in v999.0.0" })).toBeTruthy();
  });

  it("Later defers the strip for this page load, without a wire write", () => {
    renderBanner(AVAILABLE);

    fireEvent.click(screen.getByRole("button", { name: "Later" }));

    expect(screen.queryByTestId("update-banner")).toBeNull();
    expect(screen.queryByTestId("update-toast")).toBeNull();
    expect(api.POST).not.toHaveBeenCalled();
  });
});

describe("UpdateBanner — the start toast", () => {
  it("announces once with role=status and clears after its moment", () => {
    vi.useFakeTimers();
    renderBanner(AVAILABLE);

    const toast = screen.getByTestId("update-toast");
    expect(toast.getAttribute("role")).toBe("status");
    expect(toast.getAttribute("aria-live")).toBe("polite");
    expect(toast.textContent).toContain("A newer release is available — v999.0.0");

    act(() => {
      vi.advanceTimersByTime(8000);
    });
    expect(screen.queryByTestId("update-toast")).toBeNull();
    // The banner is the standing surface; the notice's exit does not take it.
    expect(screen.getByTestId("update-banner")).toBeTruthy();
  });

  it("does not replay for a version it already announced, even after a remount", () => {
    vi.useFakeTimers();
    const first = renderBanner(AVAILABLE);
    expect(screen.getByTestId("update-toast")).toBeTruthy();
    act(() => {
      vi.advanceTimersByTime(8000);
    });
    first.unmount();

    renderBanner(AVAILABLE);

    expect(screen.queryByTestId("update-toast")).toBeNull();
  });
});

describe("ReleaseNotesDialog — the markdown and the two answers", () => {
  it("renders the release markdown through the components map, escaping raw HTML", async () => {
    renderBanner(AVAILABLE);
    const dialog = await openNotes();

    // The h1 becomes the panel's second-level heading, the h2 the next one.
    expect(within(dialog).getByRole("heading", { name: "Die Neuerungen" })).toBeTruthy();
    expect(within(dialog).getByRole("heading", { name: "Notes" })).toBeTruthy();
    expect(within(dialog).getByText("Der Banner zeigt neue Versionen.")).toBeTruthy();
    expect(within(dialog).getByText("Satz")).toBeTruthy();
    expect(within(dialog).getByText("code")).toBeTruthy();
    const link = within(dialog).getByRole("link", { name: "Open the release on GitHub" });
    expect(link.getAttribute("href")).toBe("https://example.test/release");

    // The security boundary: Markdown's raw HTML is text, never a live node.
    expect(dialog.querySelector("script")).toBeNull();
    expect(dialog.textContent).toContain("<script>");
  });

  it("renders an image in the release body as a link, never an <img>", async () => {
    renderBanner({
      ...AVAILABLE,
      release_notes: "![A screenshot](https://example.test/shot.png)",
    });
    const dialog = await openNotes();

    // No auto-fetch: the modal must not request a third-party URL on open.
    expect(dialog.querySelector("img")).toBeNull();
    const link = within(dialog).getByRole("link", { name: "A screenshot" });
    expect(link.getAttribute("href")).toBe("https://example.test/shot.png");
    expect(link.getAttribute("rel")).toBe("noreferrer");
  });

  it("says so when the release has no body", async () => {
    renderBanner({ ...AVAILABLE, release_notes: null });
    const dialog = await openNotes();

    expect(within(dialog).getByText("No release notes were provided.")).toBeTruthy();
  });

  it("Ignore this version posts the version, caches the answer and closes the strip", async () => {
    const { queryClient } = renderBanner(AVAILABLE);
    api.POST.mockResolvedValue({ data: DISMISSED, response: ok() });
    const dialog = await openNotes();

    fireEvent.click(within(dialog).getByRole("button", { name: "Ignore this version" }));

    await waitFor(() =>
      expect(api.POST).toHaveBeenCalledWith("/api/updates/dismiss", {
        body: { version: "v999.0.0" },
      }),
    );
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    await waitFor(() => expect(screen.queryByTestId("update-banner")).toBeNull());
    expect(screen.queryByTestId("update-toast")).toBeNull();
    expect(queryClient.getQueryData(UPDATE_KEY)).toEqual(DISMISSED);
    // The dismissed strip took its opener with it: focus lands on the shell's
    // main landmark, never on <body>. The cleanup is a passive effect, so the
    // focus can land a beat after the dialog leaves the DOM.
    await waitFor(() =>
      expect(document.activeElement).toBe(document.getElementById("main")),
    );
  });

  it("a refused dismissal keeps the strip and the cached answer", async () => {
    const { queryClient } = renderBanner(AVAILABLE);
    api.POST.mockRejectedValue(new Error("offline"));
    const dialog = await openNotes();

    fireEvent.click(within(dialog).getByRole("button", { name: "Ignore this version" }));

    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(screen.getByTestId("update-banner")).toBeTruthy();
    expect(screen.getByText("Narrare v999.0.0 is available")).toBeTruthy();
    expect(queryClient.getQueryData(UPDATE_KEY)).toEqual(AVAILABLE);
    // The opener survived, so focus returns to it (the cleanup is passive).
    await waitFor(() =>
      expect(document.activeElement).toBe(screen.getByRole("button", { name: "Release notes" })),
    );
  });

  it("Escape closes the modal and returns focus to its opener", async () => {
    renderBanner(AVAILABLE);
    const opener = screen.getByRole("button", { name: "Release notes" });
    fireEvent.click(opener);
    expect(screen.getByRole("dialog")).toBeTruthy();

    fireEvent.keyDown(document, { key: "Escape" });

    expect(screen.queryByRole("dialog")).toBeNull();
    await waitFor(() => expect(document.activeElement).toBe(opener));
  });

  it("a press on the scrim closes the modal", async () => {
    renderBanner(AVAILABLE);
    await openNotes();

    // The scrim is the only control named Close outside the panel: the panel
    // holds the other two, in its header and its footer.
    const scrim = screen
      .getAllByRole("button", { name: "Close" })
      .find((button) => button.closest("[role='dialog']") === null);
    expect(scrim).toBeDefined();
    fireEvent.click(scrim as HTMLElement);

    expect(screen.queryByRole("dialog")).toBeNull();
  });
});
