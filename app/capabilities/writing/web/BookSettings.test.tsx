// @vitest-environment jsdom
/**
 * The book-settings dialog (W4 Task 19; the atelier retired W7 Task 4) —
 * the round's dedicated `workspace-book-settings` draft ported onto the
 * shell's tokens: four sections (book & metadata, status & target, the
 * wizard's AI family, series), the explicit Speichern (the diff alone
 * rides the wire), the dirty-state rule the tree dialogs established, and
 * the modal discipline now shared through @shell/ui/modalKeys (#895).
 *
 * The fields read the REAL rows (novel + series — the settings row left
 * with the atelier section), the save round-trips through the novel PATCH
 * alone, the series create lands inline and selects itself, and the
 * inheritance note the new-book dialog carries is true: this surface edits
 * what setup bound. The profile's home is /settings: the retired atelier
 * section's door routes there at the profile section's address, held while
 * edits stand like every close path.
 */
import { cleanup, configure, fireEvent, render, screen, waitFor, within } from "@testing-library/react";

// Full-suite load: see WorkspacePage.test.tsx.
configure({ asyncUtilTimeout: 5000 });
import { QueryClientProvider } from "@tanstack/react-query";
import {
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
  Outlet,
  RouterProvider,
} from "@tanstack/react-router";
import { useCallback, useState, type ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@shell/lib/api/client", () => ({
  client: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn(), PUT: vi.fn(), DELETE: vi.fn() },
}));

import { client, type Novel, type Series } from "@shell/lib/api/client";
import { applyLocale } from "@shell/lib/locale";
import { queryClient } from "@shell/lib/query";
import { de } from "@shell/lib/test/catalogs";

import { BookSettings } from "./BookSettings";
import {
  formatGoalInput,
  genresFromNovel,
  joinGenresWithRest,
  parseVolume,
  parseWordGoal,
  seriesIdForTitle,
} from "./bookSettings";
import { TARGET_WORDS_MAX } from "./newBook";

const api = client as unknown as Record<"GET" | "POST" | "PATCH", ReturnType<typeof vi.fn>>;

/** The repo's plain assertions (no jest-dom): the input's value and the
 *  radio's checked state read through the DOM's own faces. */
function valueOf(el: HTMLElement): string {
  return (el as HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement).value;
}

function checked(el: HTMLElement): string | null {
  return el.getAttribute("aria-checked");
}

const NOVEL_ID = "11111111-1111-1111-1111-111111111111";

function novelRow(overrides: Partial<Novel> = {}): Novel {
  return {
    id: NOVEL_ID,
    title: "Dead Signal",
    genre: "Science Fiction & Speculative, Mystery & Noir",
    blurb: "Die Sensorenbatterie der Station Erebus schwieg seit drei Tagen.",
    author: "H. Calder",
    language: "de",
    chapter_count: 2,
    word_count: 15620,
    created_at: "2026-11-01T10:00:00Z",
    updated_at: "2026-11-14T10:00:00Z",
    last_exported_at: null,
    status: "draft",
    series_title: "Tiefsee-Chroniken",
    series_volume: 1,
    archived_at: null,
    target_words: 65000,
    author_typology: "plantser",
    dramatic_form: "three-act",
    ai_role: "coautor",
    canon_strictness: 3,
    ...overrides,
  };
}

const SERIES: Series[] = [
  { id: "se1", title: "Erebus-Expeditionen", created_at: "2026-11-01T10:00:00Z" },
  { id: "se2", title: "Tiefsee-Chroniken", created_at: "2026-11-02T10:00:00Z" },
];

function ok(): Response {
  return new Response(null, { status: 200 });
}

/** The opener the dialog returns focus to — the harness owns the open
 *  state the page owns: a close unmounts the dialog. The memory router
 *  carries a stub /settings face, so the profile door's landing is
 *  observable (path and hash). */
function renderWithOpener(makeUi: (openerId: string, onClose: () => void) => ReactNode) {
  function Harness() {
    const [open, setOpen] = useState(true);
    const close = useCallback(() => setOpen(false), []);
    return (
      <div>
        <button type="button" id="opener">
          opener
        </button>
        {open && makeUi("opener", close)}
      </div>
    );
  }
  const rootRoute = createRootRoute({
    component: () => (
      <>
        <Harness />
        <Outlet />
      </>
    ),
  });
  const settingsRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/settings",
    component: () => <p>settings</p>,
  });
  const router = createRouter({
    routeTree: rootRoute.addChildren([settingsRoute]),
    history: createMemoryHistory({ initialEntries: ["/"] }),
  });
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return router;
}

function mockReads(series: Series[] = SERIES) {
  // No /api/settings ask: the settings row left with the atelier section —
  // a read here would be the retired surface's corpse.
  api.GET.mockImplementation(async (path: string) => {
    if (path === "/api/writing/series") return { data: series, response: ok() };
    throw new Error(`unexpected GET: ${path}`);
  });
}

function mockWrites() {
  // No /api/settings write: the settings PATCH left with the atelier — a
  // call here is the retired save path's corpse, and it fails loudly.
  api.PATCH.mockImplementation(async (path: string, init?: { body?: Record<string, unknown> }) => {
    if (path === "/api/writing/novels/{novel_id}") {
      return { data: { ...novelRow(), ...(init?.body ?? {}) }, response: ok() };
    }
    throw new Error(`unexpected PATCH: ${path}`);
  });
  api.POST.mockImplementation(async (path: string, init?: { body?: { title?: string } }) => {
    if (path === "/api/writing/series") {
      return { data: { id: "se3", title: init?.body?.title ?? "", created_at: "2026-11-18T10:00:00Z" }, response: ok() };
    }
    throw new Error(`unexpected POST: ${path}`);
  });
}

async function openDialog(novel: Novel = novelRow()) {
  mockReads();
  mockWrites();
  const router = renderWithOpener((openerId, onClose) => <BookSettings novel={novel} openerId={openerId} onClose={onClose} />);
  await screen.findByLabelText(de["writing.settings.titleLabel"]);
  return router;
}

beforeEach(() => {
  applyLocale("de");
  vi.stubGlobal("navigator", { language: "de-DE", languages: ["de-DE"] });
});

afterEach(() => {
  cleanup();
  queryClient.clear();
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

describe("the pure model", () => {
  it("parseWordGoal reads the locale's separators and the column's bounds", () => {
    expect(parseWordGoal("65.000")).toBe(65000);
    expect(parseWordGoal("65,000")).toBe(65000);
    expect(parseWordGoal("65 000")).toBe(65000);
    expect(parseWordGoal("70000")).toBe(70000);
    expect(parseWordGoal("")).toBeNull();
    expect(parseWordGoal("   ")).toBeNull();
    expect(parseWordGoal("0")).toBe("invalid");
    expect(parseWordGoal("-5")).toBe("invalid");
    expect(parseWordGoal("abc")).toBe("invalid");
    expect(parseWordGoal(String(TARGET_WORDS_MAX))).toBe(TARGET_WORDS_MAX);
    expect(parseWordGoal(String(TARGET_WORDS_MAX + 1))).toBe("invalid");
  });

  it("formatGoalInput opens on the grouped figure, the unset on empty", () => {
    expect(formatGoalInput(65000)).toBe("65.000");
    expect(formatGoalInput(null)).toBe("");
  });

  it("the genre pills round-trip the joined string without losing free text", () => {
    const { pills, rest } = genresFromNovel("Science Fiction & Speculative, Mystery & Noir");
    expect(pills).toEqual(["Science Fiction & Speculative", "Mystery & Noir"]);
    expect(rest).toBe("");
    expect(joinGenresWithRest(pills, rest)).toBe("Science Fiction & Speculative, Mystery & Noir");

    const custom = genresFromNovel("Mystery & Noir, Eigene Gattung");
    expect(custom.pills).toEqual(["Mystery & Noir"]);
    expect(custom.rest).toBe("Eigene Gattung");
    expect(joinGenresWithRest(custom.pills, custom.rest)).toBe("Mystery & Noir, Eigene Gattung");
    expect(joinGenresWithRest([], "")).toBeNull();
    expect(genresFromNovel(null)).toEqual({ pills: [], rest: "" });
  });

  it("the series select resolves the link by the joined title", () => {
    expect(seriesIdForTitle(SERIES, "Tiefsee-Chroniken")).toBe("se2");
    expect(seriesIdForTitle(SERIES, null)).toBeNull();
    expect(seriesIdForTitle(SERIES, "Gone")).toBeNull();
  });

  it("parseVolume counts from one, empty is the unset, the column's ceiling holds", () => {
    expect(parseVolume("1")).toBe(1);
    expect(parseVolume("12")).toBe(12);
    expect(parseVolume("")).toBeNull();
    expect(parseVolume("0")).toBe("invalid");
    expect(parseVolume("I")).toBe("invalid");
    expect(parseVolume("2147483647")).toBe(2147483647);
    expect(parseVolume("2147483648")).toBe("invalid");
  });
});

describe("the fields read the real rows", () => {
  it("opens on the novel's metadata and the wizard answers — no settings row ask", async () => {
    await openDialog();
    expect(valueOf(screen.getByLabelText(de["writing.settings.titleLabel"]))).toBe("Dead Signal");
    expect(valueOf(screen.getByLabelText(de["writing.settings.authorLabel"]))).toBe("H. Calder");
    expect(valueOf(screen.getByLabelText(de["writing.settings.blurbLabel"]))).toBe(
      "Die Sensorenbatterie der Station Erebus schwieg seit drei Tagen.",
    );
    // The draft's grouped figure — the input opens on the locale's face.
    expect(valueOf(screen.getByLabelText(de["writing.settings.targetLabel"]))).toBe("65.000");

    // The settings row left with the atelier section (W7): the dialog asks
    // the series list alone — a settings read here would be the corpse.
    const asked = api.GET.mock.calls.map((call) => call[0]);
    expect(asked).toEqual(["/api/writing/series"]);

    // The retired section's door stands in its place: the note names the
    // profile's home, the action carries the walk.
    expect(screen.getByText(de["writing.settings.profileDoor.note"])).toBeTruthy();
    expect(
      screen.getByRole("button", { name: de["writing.settings.profileDoor.action"] }),
    ).toBeTruthy();

    // The segments and radio families read the stored answers.
    expect(checked(screen.getByRole("radio", { name: "Entwurf" }))).toBe("true");
    expect(checked(screen.getByRole("radio", { name: "DE" }))).toBe("true");
    expect(checked(screen.getByRole("radio", { name: "Plantser" }))).toBe("true");
    expect(checked(screen.getByRole("radio", { name: de["writing.settings.roleCoautorLabel"] }))).toBe("true");
    expect(valueOf(screen.getByRole("slider", { name: de["writing.settings.canonLabel"] }))).toBe("3");
    expect(screen.getByText(de["writing.settings.canonBadgeNamed"].replace("{n}", "3").replace("{name}", de["writing.settings.canonBalanced"]))).toBeTruthy();

    // The genre pills: the two known parts selected, the rest offered.
    const scifi = screen.getByRole("button", { name: de["writing.shelf.dialog.genre.scifi"] });
    expect(scifi.getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByRole("button", { name: de["writing.shelf.dialog.genre.mystery"] }).getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByRole("button", { name: de["writing.shelf.dialog.genre.historical"] }).getAttribute("aria-pressed")).toBe("false");

    // The series select carries the link and the volume.
    expect(valueOf(screen.getByLabelText(de["writing.settings.seriesLabel"]))).toBe("se2");
    expect(valueOf(screen.getByLabelText(de["writing.settings.volumeLabel"]))).toBe("1");

    // The progress line is the book's own count against its target.
    expect(screen.getByText(de["writing.settings.targetWritten"].replace("{count, number}", "15.620"))).toBeTruthy();
    expect(screen.getByText(de["writing.settings.targetPercent"].replace("{percent}", "24"))).toBeTruthy();

    // The header chip names the book; the footer note stands verbatim.
    expect(screen.getByText(de["writing.settings.inheritance"])).toBeTruthy();
  });

  it("the manuscript segment offers the registry's languages in its order", async () => {
    await openDialog();
    const segment = screen.getByRole("radiogroup", { name: de["writing.settings.languageLabel"] });
    const options = within(segment).getAllByRole("radio");
    expect(options.map((option) => option.textContent)).toEqual(["DE", "EN", "FR"]);
  });

  it("an unset book keeps the honest neutrals — no goal, no status, no series", async () => {
    await openDialog(
      novelRow({
        status: null,
        target_words: null,
        series_title: null,
        series_volume: null,
        author_typology: null,
        dramatic_form: null,
        ai_role: null,
        canon_strictness: null,
        language: null,
        genre: null,
        author: null,
      }),
    );
    expect(valueOf(screen.getByLabelText(de["writing.settings.targetLabel"]))).toBe("");
    expect(screen.getByText(de["writing.shelf.noTarget"])).toBeTruthy();
    expect(valueOf(screen.getByLabelText(de["writing.settings.seriesLabel"]))).toBe("");
    expect(checked(screen.getByRole("radio", { name: "Entwurf" }))).toBe("false");
    expect(screen.getByText(de["writing.settings.canonUnset"])).toBeTruthy();
    expect(valueOf(screen.getByLabelText(de["writing.settings.formLabel"]))).toBe("");
  });
});

describe("the save round-trip", () => {
  it("carries the novel diff alone — untouched fields never ride the wire", async () => {
    await openDialog();
    fireEvent.change(screen.getByLabelText(de["writing.settings.titleLabel"]), { target: { value: "Dead Signal II" } });
    fireEvent.change(screen.getByLabelText(de["writing.settings.targetLabel"]), { target: { value: "70.000" } });
    fireEvent.click(screen.getByRole("radio", { name: "Überarbeitung" }));
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.crud.save"] }));

    await waitFor(() => expect(api.PATCH).toHaveBeenCalledTimes(1));
    expect(api.PATCH.mock.calls[0][0]).toBe("/api/writing/novels/{novel_id}");
    expect(api.PATCH.mock.calls[0][1].body).toEqual({
      title: "Dead Signal II",
      target_words: 70000,
      status: "revision",
    });
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  it("the save carries the novel diff alone — no settings write rides this surface", async () => {
    await openDialog();
    fireEvent.change(screen.getByLabelText(de["writing.settings.titleLabel"]), { target: { value: "Dead Signal II" } });
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.crud.save"] }));

    await waitFor(() => expect(api.PATCH).toHaveBeenCalledTimes(1));
    expect(api.PATCH.mock.calls[0][0]).toBe("/api/writing/novels/{novel_id}");
    expect(api.PATCH.mock.calls[0][1].body).toEqual({ title: "Dead Signal II" });
    // The settings PATCH left with the atelier section (W7): the profile's
    // home is /settings, and no second write family stands here.
    expect(api.PATCH.mock.calls.every((call) => call[0] !== "/api/settings")).toBe(true);
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  it("a cleared target carries null — the honest unset, not a zero", async () => {
    await openDialog();
    fireEvent.change(screen.getByLabelText(de["writing.settings.targetLabel"]), { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.crud.save"] }));

    await waitFor(() => expect(api.PATCH).toHaveBeenCalledTimes(1));
    expect(api.PATCH.mock.calls[0][0]).toBe("/api/writing/novels/{novel_id}");
    expect(api.PATCH.mock.calls[0][1].body).toEqual({ target_words: null });
    expect(api.PATCH.mock.calls.every((call) => call[0] !== "/api/settings")).toBe(true);
  });

  it("an empty author clears to null on the book's level", async () => {
    await openDialog();
    fireEvent.change(screen.getByLabelText(de["writing.settings.authorLabel"]), { target: { value: "  " } });
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.crud.save"] }));
    await waitFor(() => expect(api.PATCH).toHaveBeenCalledTimes(1));
    expect(api.PATCH.mock.calls[0][1].body).toEqual({ author: null });
  });

  it("a pristine save closes without a wire ask", async () => {
    await openDialog();
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.crud.save"] }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(api.PATCH).not.toHaveBeenCalled();
  });

  it("the wizard answers ride the patch when changed", async () => {
    await openDialog();
    fireEvent.click(screen.getByRole("radio", { name: "Plotter" }));
    fireEvent.click(screen.getByRole("radio", { name: de["writing.settings.roleLektorLabel"] }));
    fireEvent.change(screen.getByRole("slider", { name: de["writing.settings.canonLabel"] }), { target: { value: "5" } });
    fireEvent.change(screen.getByLabelText(de["writing.settings.formLabel"]), { target: { value: "five-act" } });
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.crud.save"] }));

    await waitFor(() => expect(api.PATCH).toHaveBeenCalledTimes(1));
    expect(api.PATCH.mock.calls[0][1].body).toEqual({
      author_typology: "plotter",
      ai_role: "lektor",
      canon_strictness: 5,
      dramatic_form: "five-act",
    });
  });
});

describe("the series section", () => {
  it("creates a series inline and selects it — the link rides the save", async () => {
    await openDialog();
    fireEvent.click(screen.getByRole("button", { name: de["writing.settings.seriesCreate"] }));
    const nameInput = screen.getByLabelText(de["writing.settings.seriesCreateLabel"]);
    fireEvent.change(nameInput, { target: { value: "Neue Chroniken" } });
    fireEvent.click(screen.getByRole("button", { name: de["writing.settings.seriesCreateConfirm"] }));

    await waitFor(() => expect(api.POST).toHaveBeenCalledTimes(1));
    expect(api.POST.mock.calls[0][1].body).toEqual({ title: "Neue Chroniken" });
    // The fresh row is selected at once; the list refetch carries it.
    await waitFor(() => expect(valueOf(screen.getByLabelText(de["writing.settings.seriesLabel"]))).toBe("se3"));

    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.crud.save"] }));
    await waitFor(() => expect(api.PATCH).toHaveBeenCalledTimes(1));
    expect(api.PATCH.mock.calls[0][1].body).toEqual({ series_id: "se3" });
  });

  it("linking another series carries the id and the volume together", async () => {
    await openDialog();
    fireEvent.change(screen.getByLabelText(de["writing.settings.seriesLabel"]), { target: { value: "se1" } });
    fireEvent.change(screen.getByLabelText(de["writing.settings.volumeLabel"]), { target: { value: "3" } });
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.crud.save"] }));
    await waitFor(() => expect(api.PATCH).toHaveBeenCalledTimes(1));
    expect(api.PATCH.mock.calls[0][1].body).toEqual({ series_id: "se1", series_volume: 3 });
  });

  it("unlinking takes the volume with it — the number belongs to the link", async () => {
    await openDialog();
    fireEvent.change(screen.getByLabelText(de["writing.settings.seriesLabel"]), { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.crud.save"] }));
    await waitFor(() => expect(api.PATCH).toHaveBeenCalledTimes(1));
    expect(api.PATCH.mock.calls[0][1].body).toEqual({ series_id: null, series_volume: null });
  });

  it("a duplicate name answers with its own note — the link stands unchanged", async () => {
    await openDialog();
    api.POST.mockResolvedValueOnce({ data: undefined, response: new Response(null, { status: 409 }) });
    fireEvent.click(screen.getByRole("button", { name: de["writing.settings.seriesCreate"] }));
    fireEvent.change(screen.getByLabelText(de["writing.settings.seriesCreateLabel"]), {
      target: { value: "Tiefsee-Chroniken" },
    });
    fireEvent.click(screen.getByRole("button", { name: de["writing.settings.seriesCreateConfirm"] }));
    expect(await screen.findByText(de["writing.settings.seriesDuplicate"])).toBeTruthy();
    expect(valueOf(screen.getByLabelText(de["writing.settings.seriesLabel"]))).toBe("se2");
  });

  it("Speichern waits for the inline create — one write family at a time", async () => {
    await openDialog();
    // The node reference stays valid while its label flips to the busy
    // face — the guard is the disabled state, not the name.
    const save = screen.getByRole("button", { name: de["writing.workspace.crud.save"] }) as HTMLButtonElement;
    let settleCreate: (answer: unknown) => void = () => {};
    api.POST.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          settleCreate = resolve;
        }),
    );
    fireEvent.click(screen.getByRole("button", { name: de["writing.settings.seriesCreate"] }));
    fireEvent.change(screen.getByLabelText(de["writing.settings.seriesCreateLabel"]), {
      target: { value: "Neue Chroniken" },
    });
    fireEvent.click(screen.getByRole("button", { name: de["writing.settings.seriesCreateConfirm"] }));
    await waitFor(() => expect(save.disabled).toBe(true));
    settleCreate({
      data: { id: "se3", title: "Neue Chroniken", created_at: "2026-11-18T10:00:00Z" },
      response: ok(),
    });
    await waitFor(() => expect(save.disabled).toBe(false));
  });
});

describe("the refusals stay client-side before the wire", () => {
  it("an empty title is refused by name — no PATCH runs", async () => {
    await openDialog();
    fireEvent.change(screen.getByLabelText(de["writing.settings.titleLabel"]), { target: { value: "   " } });
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.crud.save"] }));
    expect(await screen.findByText(de["writing.settings.titleRequired"])).toBeTruthy();
    expect(api.PATCH).not.toHaveBeenCalled();
  });

  it("a goal outside the bounds is refused — the field names itself", async () => {
    await openDialog();
    fireEvent.change(screen.getByLabelText(de["writing.settings.targetLabel"]), { target: { value: "0" } });
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.crud.save"] }));
    expect(await screen.findByText(de["writing.settings.targetInvalid"])).toBeTruthy();
    expect(api.PATCH).not.toHaveBeenCalled();
  });

  it("a volume without a number is refused", async () => {
    await openDialog();
    fireEvent.change(screen.getByLabelText(de["writing.settings.volumeLabel"]), { target: { value: "I" } });
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.crud.save"] }));
    expect(await screen.findByText(de["writing.settings.volumeInvalid"])).toBeTruthy();
    expect(api.PATCH).not.toHaveBeenCalled();
  });

  it("a volume beyond the column's ceiling is refused before the wire", async () => {
    await openDialog();
    fireEvent.change(screen.getByLabelText(de["writing.settings.volumeLabel"]), { target: { value: "2147483648" } });
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.crud.save"] }));
    expect(await screen.findByText(de["writing.settings.volumeInvalid"])).toBeTruthy();
    expect(api.PATCH).not.toHaveBeenCalled();
  });
});

describe("a refused save keeps the answers", () => {
  it("the error line stands, the retry re-runs the very ask", async () => {
    await openDialog();
    api.PATCH.mockResolvedValueOnce({ data: undefined, response: new Response(null, { status: 500 }) });
    fireEvent.change(screen.getByLabelText(de["writing.settings.titleLabel"]), { target: { value: "Neu" } });
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.crud.save"] }));

    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(screen.getByText(de["writing.settings.error"])).toBeTruthy();
    expect(valueOf(screen.getByLabelText(de["writing.settings.titleLabel"]))).toBe("Neu");
    expect(screen.queryByRole("dialog")).not.toBeNull();

    fireEvent.click(screen.getByRole("button", { name: de["writing.shelf.error.retry"] }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(api.PATCH).toHaveBeenCalledTimes(2);
  });
});

describe("the modal discipline", () => {
  it("focus lands on the title field; every close returns it to the opener", async () => {
    await openDialog();
    expect(document.activeElement).toBe(screen.getByLabelText(de["writing.settings.titleLabel"]));
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.crud.cancel"] }));
    await waitFor(() => expect(document.activeElement).toBe(screen.getByRole("button", { name: "opener" })));
  });

  it("Tab wraps inside the panel at both ends", async () => {
    await openDialog();
    const panel = screen.getByRole("dialog");
    const focusables = Array.from(
      panel.querySelectorAll<HTMLElement>(
        'button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])',
      ),
    );
    const first = focusables[0];
    const last = focusables[focusables.length - 1];
    last.focus();
    fireEvent.keyDown(document, { key: "Tab" });
    expect(document.activeElement).toBe(first);
    fireEvent.keyDown(document, { key: "Tab", shiftKey: true });
    expect(document.activeElement).toBe(last);
  });

  it("pristine: Escape and the scrim close; dirty: both are held and the cross waits", async () => {
    await openDialog();
    // Pristine — Escape closes.
    fireEvent.keyDown(document, { key: "Escape" });
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());

    // Reopen dirty — Escape holds, the scrim holds, Fertig is unavailable.
    await openDialog();
    fireEvent.change(screen.getByLabelText(de["writing.settings.titleLabel"]), { target: { value: "Anders" } });
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog")).not.toBeNull();
    const done = screen.getByRole("button", { name: `${de["writing.settings.close"]} (${de["writing.workspace.crud.close"]})` });
    expect(done.hasAttribute("disabled")).toBe(true);
    // Abbrechen still answers — the named discard.
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.crud.cancel"] }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  it("a returned field is pristine again — the comparison, not a latch", async () => {
    await openDialog();
    const title = screen.getByLabelText(de["writing.settings.titleLabel"]);
    fireEvent.change(title, { target: { value: "Anders" } });
    fireEvent.change(title, { target: { value: "Dead Signal" } });
    fireEvent.keyDown(document, { key: "Escape" });
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  it("the dialog is labelled and modal, the radio families are groups", async () => {
    await openDialog();
    const panel = screen.getByRole("dialog");
    expect(panel.getAttribute("aria-modal")).toBe("true");
    expect(panel.getAttribute("aria-labelledby")).toBeTruthy();
    expect(screen.getByRole("radiogroup", { name: de["writing.settings.statusLabel"] })).toBeTruthy();
    expect(screen.getByRole("radiogroup", { name: de["writing.settings.languageLabel"] })).toBeTruthy();
    expect(screen.getByRole("radiogroup", { name: de["writing.settings.typologyLabel"] })).toBeTruthy();
    expect(screen.getByRole("radiogroup", { name: de["writing.settings.roleLabel"] })).toBeTruthy();
  });
});

describe("the profile's door (W7)", () => {
  it("the atelier's fields are gone — the dialog's textboxes are the book's own", async () => {
    await openDialog();
    // The retired section left no corpse: title, author, target and volume
    // are the dialog's only text inputs (the blurb is the textarea).
    const textboxes = screen.getByRole("dialog").querySelectorAll("input[type=text]");
    expect(textboxes.length).toBe(4);
  });

  it("the door routes to /settings at the profile section's address, the dialog closed", async () => {
    const router = await openDialog();
    fireEvent.click(screen.getByRole("button", { name: de["writing.settings.profileDoor.action"] }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/settings"));
    expect(router.state.location.hash).toBe("profil-sektion");
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(screen.getByText("settings")).toBeTruthy();
  });

  it("the door answers the dirty rule both ways — enabled clean, held while edits stand", async () => {
    await openDialog();
    const door = screen.getByRole("button", { name: de["writing.settings.profileDoor.action"] }) as HTMLButtonElement;
    // The clean dialog answers: the door is a live choice at rest.
    expect(door.disabled).toBe(false);
    // Any typed change holds it — only Abbrechen and Speichern answer.
    fireEvent.change(screen.getByLabelText(de["writing.settings.titleLabel"]), { target: { value: "Anders" } });
    expect(door.disabled).toBe(true);
    // And back: the reverted field is pristine again, the door answers.
    fireEvent.change(screen.getByLabelText(de["writing.settings.titleLabel"]), { target: { value: "Dead Signal" } });
    expect(door.disabled).toBe(false);
  });

  it("the door's section is named for the scan — the short label, not the sentence", async () => {
    await openDialog();
    // A named section is a region: its accessible name is the scannable
    // word („Profil"), the note stays the visible secondary text.
    expect(screen.getByRole("region", { name: de["writing.settings.profileDoor.label"] })).toBeTruthy();
    expect(screen.getByText(de["writing.settings.profileDoor.note"])).toBeTruthy();
  });
});
