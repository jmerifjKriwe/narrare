// @vitest-environment jsdom
/**
 * The inspector dock (W4 Tasks 11/20, W5 Tasks 1/2): the scene-centric
 * draft's round geometry — the atmosphere grid (#868), the disabled ⌘J
 * chip (#869) and layout tune (#881) — and the ONE real card: the cover
 * miniature with the book's own target, count and derived progress.
 * The draft's mock figures (85.000 / 3.384 / 4 %) never ship as data.
 *
 * W5 Task 2 retires the #866/#867 interims: the finding card and the
 * entity spotlight are gone — the knowledge region belongs to the
 * registry's matched dock face alone, and the header badge and the tab
 * badge read the real pending-findings count through the shell's query
 * seam (no neutral placeholder, no invented number).
 *
 * Task 20's pins that stand: every remaining interim's note speaks its
 * child issue's own language (the literals below, not a catalog echo),
 * the cover stands at the cover system's drafted miniature size (36×48,
 * cover-system.html Sektion 04 — the workspace draft's 48×64 chip is a
 * mock object, the cover system owns its sizes), and the dock speaks
 * du-tone in all three catalogs, never a German fallback.
 *
 * W5 Task 1's pins: the dock registry composes through the generated
 * table — one tab per row, the matched child route is the open state,
 * the knowledge region yields to the Outlet while the atmosphere and
 * cover slots stand. The harness mirrors the generated composition: a
 * workspace route hosting the dock, a child route at the registry's own
 * path standing in for the capability face (the face itself is pinned
 * in its own capability's tests).
 */
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, configure, fireEvent, render, screen, waitFor, within } from "@testing-library/react";

// Full-suite load: see WorkspacePage.test.tsx.
configure({ asyncUtilTimeout: 5000 });
import {
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
  Outlet,
  RouterProvider,
} from "@tanstack/react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@shell/lib/api/client", () => ({
  client: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn(), PUT: vi.fn(), DELETE: vi.fn() },
}));

import { client, type Finding, type Novel } from "@shell/lib/api/client";
import { docks } from "@shell/lib/generated/docks";
import { applyLocale } from "@shell/lib/locale";
import { queryClient } from "@shell/lib/query";
import { de, en, fr, merged } from "@shell/lib/test/catalogs";

import { InspectorDock } from "./InspectorDock";

const api = client as unknown as Record<"GET", ReturnType<typeof vi.fn>>;

// The dock foot's ⌘J chip and layout tune name their state, not a future
// release (#979).
const STATUS_NOTE = {
  en: "Not available yet.",
  de: "Noch nicht verfügbar.",
  fr: "Pas encore disponible.",
} as const;

const FUTURE_PROMISE =
  /build-out|aufbau|wave|welle|vague|appear|erschein|appara|coming soon|kommt mit|arrive avec|future|becomes available|later/i;

describe("the dock status notes speak to the reader", () => {
  it("are status-only in every catalog, never a future promise", () => {
    for (const locale of ["en", "de", "fr"] as const) {
      for (const key of [
        "writing.workspace.dock.soon",
        "writing.workspace.dock.layoutNote",
      ] as const) {
        const note = merged[locale][key];
        expect(note).toBe(STATUS_NOTE[locale]);
        expect(note).not.toMatch(FUTURE_PROMISE);
      }
    }
  });
});

function novelRow(overrides: Partial<Novel> = {}): Novel {
  return {
    id: "11111111-1111-1111-1111-111111111111",
    title: "Dead Signal",
    genre: "Science Fiction",
    blurb: null,
    author: "H. Calder",
    language: null,
    chapter_count: 2,
    word_count: 1855,
    created_at: "2026-11-01T10:00:00Z",
    updated_at: "2026-11-14T10:00:00Z",
    last_exported_at: null,
    status: "draft",
    series_title: null,
    series_volume: null,
    archived_at: null,
    target_words: 85000,
    ...overrides,
  };
}

function findingRow(overrides: Partial<Finding> = {}): Finding {
  return {
    id: "f1",
    novel_id: novelRow().id,
    summary: "Stationsbezeichnung uneinheitlich",
    detail: null,
    status: "pending",
    created_at: "2026-11-18T10:00:00Z",
    ...overrides,
  };
}

/** The findings answer the badge reads; the tests mutate it to model the
 *  queue the check filed. */
let findingQueue: Finding[];

/** The dock under a bare router root — the registry's tabs navigate and
 *  the Outlet reads the matched child, so the chrome needs the router
 *  context the workspace provides. The child route stands at the
 *  registry's own path: a drifted registry row would miss the match and
 *  fail the composition pins below. The query provider carries the
 *  badge's findings read (the shell's seam, the workspace's own). */
const harnessRoot = createRootRoute({ component: () => <Outlet /> });

async function renderDock(novel: Novel = novelRow(), entry?: string) {
  const workspace = createRoute({
    getParentRoute: () => harnessRoot,
    path: "/novels/$novelId",
    component: () => <InspectorDock novel={novel} />,
  });
  const dockChildren = docks.map((dock) =>
    createRoute({
      getParentRoute: () => workspace,
      // The registry's path is the full route id under the root; the
      // child's own segment is its last piece.
      path: dock.path.split("/").pop() as string,
      component: () => <div data-testid="dock-face-marker">{dock.id} face</div>,
    }),
  );
  const router = createRouter({
    routeTree: harnessRoot.addChildren([workspace.addChildren(dockChildren)]),
    history: createMemoryHistory({ initialEntries: [entry ?? `/novels/${novel.id}`] }),
  });
  await router.load();
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return router;
}

beforeEach(() => {
  applyLocale("de");
  vi.stubGlobal("navigator", { language: "de-DE", languages: ["de-DE"] });
  findingQueue = [findingRow()];
  api.GET.mockImplementation(async (path: string) => {
    if (path === "/api/knowledge/novels/{novel_id}/findings") {
      return { data: findingQueue, response: new Response(null, { status: 200 }) };
    }
    throw new Error(`unexpected GET: ${path}`);
  });
});

afterEach(() => {
  cleanup();
  queryClient.clear();
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

describe("the dock's geometry after the knowledge retirement", () => {
  it("the header names the consistency checker", async () => {
    await renderDock();
    expect(screen.getByRole("heading", { name: de["writing.workspace.dock.title"] })).toBeTruthy();
  });

  it("the knowledge region stands empty until a dock opens — #866/#867 retired", async () => {
    await renderDock();
    // The interim cards are gone: no dashed finding placeholder, no
    // neutral spotlight, no „Wissens-Welle" promise — the wave is here,
    // and its content lives behind the registry's tab.
    expect(screen.queryByTestId("dock-finding")).toBeNull();
    expect(screen.queryByTestId("dock-entity")).toBeNull();
    expect(screen.queryByText("Wird mit der Wissens-Welle aktiv")).toBeNull();
    expect(screen.queryByText("Wiki öffnen")).toBeNull();
    // The writing-owned slots stand — content replaced, never slots.
    expect(screen.getByTestId("dock-atmosphere")).toBeTruthy();
    expect(screen.getByTestId("dock-cover")).toBeTruthy();
    expect(screen.getByTestId("dock-foot")).toBeTruthy();
  });

  it("the atmosphere grid keeps its neutral values — no mock scene label (#868)", async () => {
    await renderDock();
    const card = screen.getByTestId("dock-atmosphere");
    expect(within(card).getByText(de["writing.workspace.dock.light"])).toBeTruthy();
    expect(within(card).getByText(de["writing.workspace.dock.acoustics"])).toBeTruthy();
    expect(screen.queryByText("Permafrost Station 7")).toBeNull();
  });

  it("the foot's ⌘J chip and layout tune stay disabled with their marks (#869, #881)", async () => {
    await renderDock();
    const foot = screen.getByTestId("dock-foot");
    const assistant = within(foot).getByText(de["writing.workspace.dock.assistant"]);
    expect(assistant.closest("[aria-disabled='true']")).not.toBeNull();
    expect(within(foot).getByText(de["writing.workspace.dock.soon"])).toBeTruthy();
    const layout = within(foot).getByRole("button", { name: de["writing.workspace.dock.layout"] });
    expect(layout.hasAttribute("disabled")).toBe(true);
    expect(layout.getAttribute("title")).toContain(de["writing.workspace.dock.layoutNote"]);
  });
});

describe("the badges read the real queue (#866 retired)", () => {
  it("the header badge counts the pending findings — the checker's own number", async () => {
    findingQueue = [findingRow(), findingRow({ id: "f2" })];
    await renderDock();
    const badge = await screen.findByTestId("dock-findings-badge");
    await waitFor(() => expect(badge.textContent).toBe("2"));
    expect(badge.getAttribute("aria-label")).toBe("2 offene Befunde");
    expect(badge.className).toContain("text-warning");
    // The ask carries the novel and the pending question.
    const call = api.GET.mock.calls.find(([path]) => path === "/api/knowledge/novels/{novel_id}/findings");
    expect(call?.[1]).toEqual({
      params: { path: { novel_id: novelRow().id }, query: { status: "pending" } },
    });
  });

  it("the tab badge shows the count — and only when there is one", async () => {
    findingQueue = [findingRow(), findingRow({ id: "f2" })];
    await renderDock();
    const group = screen.getByRole("group", { name: de["writing.workspace.dock.tabs"] });
    const tab = within(group).getByRole("button", { name: de["knowledge.dockTitle"] });
    const badge = await within(tab).findByTestId("dock-tab-badge");
    expect(badge.textContent).toBe("2");
    // The badge is the draft's warning circle; it never renames the tab.
    expect(badge.getAttribute("aria-hidden")).toBe("true");
    expect(badge.className).toContain("bg-warning");
  });

  it("an empty queue reads zero — no tab badge, no invented alert", async () => {
    findingQueue = [];
    await renderDock();
    const badge = await screen.findByTestId("dock-findings-badge");
    await waitFor(() => expect(badge.textContent).toBe("0"));
    expect(badge.className).toContain("text-muted");
    expect(screen.queryByTestId("dock-tab-badge")).toBeNull();
  });

  it("a pending ask keeps the badge neutral — no invented count", async () => {
    let resolveFindings: (value: { data: Finding[]; response: Response }) => void = () => {};
    api.GET.mockImplementation(
      (path: string) =>
        new Promise((resolve) => {
          if (path === "/api/knowledge/novels/{novel_id}/findings") resolveFindings = resolve;
        }),
    );
    await renderDock();
    const badge = await screen.findByTestId("dock-findings-badge");
    expect(badge.textContent).toBe("—");
    expect(screen.queryByTestId("dock-tab-badge")).toBeNull();
    resolveFindings({ data: [findingRow()], response: new Response(null, { status: 200 }) });
    await waitFor(() => expect(badge.textContent).toBe("1"));
  });

  it("an unavailable queue keeps the badge neutral — the face names the outage", async () => {
    api.GET.mockImplementation(async () => ({
      data: undefined,
      response: new Response(null, { status: 500 }),
    }));
    await renderDock();
    const badge = await screen.findByTestId("dock-findings-badge");
    // The error settles; the badge never invents a number from a failure.
    await waitFor(() => expect(badge.textContent).toBe("—"));
    expect(screen.queryByTestId("dock-tab-badge")).toBeNull();
  });
});

describe("the remaining interims speak their child issue's own language", () => {
  // These pin the canonical status copy in the draft's geometry, so a drift
  // in either home fails here.
  it("the layout tune's tooltip keeps the draft's parenthetical (#881)", async () => {
    // workspace-scene-centric.html, dock foot: the layout title keeps its
    // bracketed note. The copy is now the canonical status note, not a
    // future promise (#979).
    await renderDock();
    const layout = within(screen.getByTestId("dock-foot")).getByRole("button", {
      name: "Workspace-Layout",
    });
    expect(layout.getAttribute("title")).toBe("Workspace-Layout (Noch nicht verfügbar.)");
  });

  it("the ⌘J chip carries the status mark and keeps its shortcut name (#869)", async () => {
    await renderDock();
    const foot = screen.getByTestId("dock-foot");
    expect(within(foot).getByText("Noch nicht verfügbar.")).toBeTruthy();
    expect(within(foot).getByText("KI-Assistent")).toBeTruthy();
    // The keycap's accessible name keeps the command modifier; the visible
    // ink is the app's SVG plus the bundled mono J, and no U+2318 text.
    const keycap = within(foot).getByRole("img", { name: "⌘J" });
    expect(keycap.tagName).toBe("KBD");
    const command = keycap.querySelector("svg");
    expect(command).toBeTruthy();
    expect(command?.getAttribute("aria-hidden")).toBe("true");
    expect(keycap.textContent).toBe("J");
    expect(foot.textContent).not.toContain("⌘");
  });
});

describe("the cover miniature — the dock's one real card", () => {
  it("renders the cover system's miniature with the book's own figures", async () => {
    await renderDock();
    const card = screen.getByTestId("dock-cover");
    // The cover system's monogram — the real object, never the draft's chip.
    expect(within(card).getByText("DS")).toBeTruthy();
    expect(within(card).getByText("Dead Signal")).toBeTruthy();
    expect(within(card).getByText(/85\.000/)).toBeTruthy();
    expect(within(card).getByText(/1\.855/)).toBeTruthy();
    // 1855 / 85000 = 2.18 % — floored, the shelf's own rule.
    expect(within(card).getByText("2 % Gesamt")).toBeTruthy();
  });

  it("a missing target keeps the honest neutral — no percent, empty track", async () => {
    await renderDock(novelRow({ target_words: null }));
    const card = screen.getByTestId("dock-cover");
    expect(within(card).queryByText(/Gesamt/)).toBeNull();
    expect(within(card).getByText(/1\.855/)).toBeTruthy();
  });

  it("the progress never overflows the track — a finished book reads 100", async () => {
    await renderDock(novelRow({ word_count: 90000 }));
    const card = screen.getByTestId("dock-cover");
    expect(within(card).getByText("100 % Gesamt")).toBeTruthy();
  });

  it("stands at the cover system's drafted miniature size — 36×48, monogram alone", async () => {
    // cover-system.html Sektion 04 pins the miniature at 36 × 48 px with
    // the monogram alone; the workspace draft's 48×64 chip is a mock
    // object, the cover system owns its sizes (Task 11's recorded
    // deviation). The procedural cover renders, never the draft's chip.
    await renderDock();
    const card = screen.getByTestId("dock-cover");
    const cover = card.querySelector("[data-channel]");
    expect(cover).not.toBeNull();
    expect((cover as HTMLElement).style.width).toBe("36px");
    expect((cover as HTMLElement).style.height).toBe("48px");
    // The miniature keeps only the monogram — no eyebrow, no author line.
    expect(within(cover as HTMLElement).getByText("DS")).toBeTruthy();
    expect(within(cover as HTMLElement).queryByText("H. Calder")).toBeNull();
    expect(within(cover as HTMLElement).queryByText(/Science Fiction/)).toBeNull();
  });
});

describe("the dock registry composition (W5 Task 1)", () => {
  it("the registry's tab stands on the default face — named, unpressed", async () => {
    await renderDock();
    const group = screen.getByRole("group", { name: de["writing.workspace.dock.tabs"] });
    const tab = within(group).getByRole("button", { name: de["knowledge.dockTitle"] });
    expect(tab.getAttribute("aria-pressed")).toBe("false");
    // The knowledge region stands empty while no dock child is matched —
    // the interims retired; the writing-owned slots stand.
    expect(screen.queryByTestId("dock-finding")).toBeNull();
    expect(screen.queryByTestId("dock-entity")).toBeNull();
    expect(screen.getByTestId("dock-atmosphere")).toBeTruthy();
  });

  it("opening the tab navigates to the dock route — the knowledge region yields to the Outlet", async () => {
    const router = await renderDock();
    const group = screen.getByRole("group", { name: de["writing.workspace.dock.tabs"] });
    fireEvent.click(within(group).getByRole("button", { name: de["knowledge.dockTitle"] }));
    // The matched child renders through the Outlet; the writing-owned
    // slots stand (content, never slots).
    expect(await screen.findByTestId("dock-face-marker")).toBeTruthy();
    expect(screen.getByTestId("dock-atmosphere")).toBeTruthy();
    expect(screen.getByTestId("dock-cover")).toBeTruthy();
    expect(screen.getByTestId("dock-foot")).toBeTruthy();
    // The URL is the open state — the registry row's own path.
    expect(router.state.location.pathname).toBe(
      `/novels/${novelRow().id}/${docks[0].path.split("/").pop() as string}`,
    );
    expect(
      within(group).getByRole("button", { name: de["knowledge.dockTitle"] }).getAttribute("aria-pressed"),
    ).toBe("true");
  });

  it("the pressed tab closes the dock — the knowledge region empties again", async () => {
    const router = await renderDock();
    const group = screen.getByRole("group", { name: de["writing.workspace.dock.tabs"] });
    const tab = within(group).getByRole("button", { name: de["knowledge.dockTitle"] });
    fireEvent.click(tab);
    expect(await screen.findByTestId("dock-face-marker")).toBeTruthy();
    fireEvent.click(tab);
    await waitFor(() => expect(screen.queryByTestId("dock-face-marker")).toBeNull());
    expect(screen.queryByTestId("dock-finding")).toBeNull();
    expect(screen.getByTestId("dock-atmosphere")).toBeTruthy();
    expect(tab.getAttribute("aria-pressed")).toBe("false");
    expect(router.state.location.pathname).toBe(`/novels/${novelRow().id}`);
  });

  it("the URL is the whole open state — a direct dock entry renders the face", async () => {
    const novel = novelRow();
    await renderDock(novel, `/novels/${novel.id}/${docks[0].path.split("/").pop() as string}`);
    expect(screen.getByTestId("dock-face-marker")).toBeTruthy();
    const group = screen.getByRole("group", { name: de["writing.workspace.dock.tabs"] });
    expect(
      within(group).getByRole("button", { name: de["knowledge.dockTitle"] }).getAttribute("aria-pressed"),
    ).toBe("true");
  });
});

describe("the dock speaks du-tone in every catalog — no German fallback", () => {
  it("the English face speaks the English catalog's own copy", async () => {
    applyLocale("en");
    await renderDock();
    expect(screen.getByRole("heading", { name: "Consistency Checker" })).toBeTruthy();
    // The badge speaks the English plural — the checker's real count.
    const badge = await screen.findByTestId("dock-findings-badge");
    await waitFor(() => expect(badge.getAttribute("aria-label")).toBe("1 open finding"));
    const foot = screen.getByTestId("dock-foot");
    expect(within(foot).getByText(en["writing.workspace.dock.soon"])).toBeTruthy();
    expect(within(foot).getByRole("button", { name: "Workspace layout" }).getAttribute("title")).toBe(
      "Workspace layout (Not available yet.)",
    );
    // The registry tab speaks the English catalog too.
    expect(
      within(screen.getByRole("group", { name: en["writing.workspace.dock.tabs"] })).getByRole("button", {
        name: en["knowledge.dockTitle"],
      }),
    ).toBeTruthy();
    // The German copy is absent — the face is translated, not fallen back.
    expect(screen.queryByText("Konsistenz-Prüfer")).toBeNull();
    expect(screen.queryByText("Noch nicht verfügbar.")).toBeNull();
  });

  it("the French face speaks the French catalog's own copy", async () => {
    applyLocale("fr");
    await renderDock();
    expect(screen.getByRole("heading", { name: "Vérificateur de cohérence" })).toBeTruthy();
    const badge = await screen.findByTestId("dock-findings-badge");
    await waitFor(() => expect(badge.getAttribute("aria-label")).toBe("1 constat ouvert"));
    const foot = screen.getByTestId("dock-foot");
    expect(within(foot).getByText("Pas encore disponible.")).toBeTruthy();
    expect(
      within(foot).getByRole("button", { name: "Disposition de l'espace" }).getAttribute("title"),
    ).toBe("Disposition de l'espace (Pas encore disponible.)");
    expect(screen.queryByText("Konsistenz-Prüfer")).toBeNull();
  });

  it("the three catalogs carry the dock's keys in parity, each translated", () => {
    // The global i18n gate pins whole-catalog parity; this pins the dock's
    // family specifically — every key present in all three, and the note
    // copy actually translated (a copied German string would pass parity).
    const keys = Object.keys(de).filter((key) => key.startsWith("writing.workspace.dock."));
    expect(keys.length).toBeGreaterThan(0);
    for (const key of keys) {
      for (const locale of ["en", "fr"] as const) {
        expect(merged[locale][key as keyof typeof en], `${locale}/${key}`).toBeTruthy();
      }
    }
    const translated = [
      "writing.workspace.dock.layoutNote",
      "writing.workspace.dock.tabs",
      "writing.workspace.dock.title",
    ] as const;
    for (const key of translated) {
      expect(en[key], key).not.toBe(de[key]);
      expect(fr[key], key).not.toBe(de[key]);
    }
  });
});
