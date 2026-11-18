// @vitest-environment jsdom
/**
 * The inspector dock (W4 Tasks 11/20): the scene-centric draft's round
 * geometry with honest neutrals — the finding card (INTERIM #866), the
 * entity spotlight (#867), the atmosphere grid (#868), the disabled ⌘J
 * chip (#869) and layout tune (#881) — and the ONE real card: the cover
 * miniature with the book's own target, count and derived progress.
 * The draft's mock figures (85.000 / 3.384 / 4 %) never ship as data.
 *
 * Task 20's pins: every interim's note speaks its child issue's own
 * language (the literals below, not a catalog echo), the cover stands at
 * the cover system's drafted miniature size (36×48, cover-system.html
 * Sektion 04 — the workspace draft's 48×64 chip is a mock object, the
 * cover system owns its sizes), and the dock speaks du-tone in all three
 * catalogs, never a German fallback.
 *
 * W5 Task 1's pins: the dock registry composes through the generated
 * table — one tab per row, the matched child route is the open state,
 * the knowledge region yields to the Outlet while the atmosphere and
 * cover slots stand. The harness mirrors the generated composition: a
 * workspace route hosting the dock, a child route at the registry's own
 * path standing in for the capability face (the face itself is pinned
 * in its own capability's tests).
 */
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
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

import type { Novel } from "@shell/lib/api/client";
import { catalogs } from "@shell/lib/generated/catalogs";
import { docks } from "@shell/lib/generated/docks";
import { applyLocale } from "@shell/lib/locale";

import { InspectorDock } from "./InspectorDock";

const de = catalogs.de;

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

/** The dock under a bare router root — the registry's tabs navigate and
 *  the Outlet reads the matched child, so the chrome needs the router
 *  context the workspace provides. The child route stands at the
 *  registry's own path: a drifted registry row would miss the match and
 *  fail the composition pins below. */
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
  render(<RouterProvider router={router} />);
  return router;
}

beforeEach(() => {
  applyLocale("de");
  vi.stubGlobal("navigator", { language: "de-DE", languages: ["de-DE"] });
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("the dock's neutral geometry", () => {
  it("the header names the consistency checker with the neutral badge", async () => {
    await renderDock();
    expect(screen.getByRole("heading", { name: de["writing.workspace.dock.title"] })).toBeTruthy();
  });

  it("the finding card stays neutral until the knowledge wave (#866)", async () => {
    await renderDock();
    const card = screen.getByTestId("dock-finding");
    expect(within(card).getByText(de["writing.workspace.dock.finding"])).toBeTruthy();
    expect(within(card).getByText(de["writing.workspace.dock.findingEmpty"])).toBeTruthy();
    expect(within(card).getByText(de["writing.workspace.dock.findingNote"])).toBeTruthy();
    expect(card.className).toContain("border-dashed");
  });

  it("the entity spotlight keeps its neutral fields and the disabled wiki door (#867)", async () => {
    await renderDock();
    const card = screen.getByTestId("dock-entity");
    for (const key of [
      "writing.workspace.dock.entityName",
      "writing.workspace.dock.entityFirst",
      "writing.workspace.dock.entityBinding",
    ] as const) {
      expect(within(card).getByText(de[key])).toBeTruthy();
    }
    const wiki = within(card).getByRole("button", { name: de["writing.workspace.dock.wiki"] });
    expect(wiki.hasAttribute("disabled")).toBe(true);
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

describe("the interim notes speak their child issue's own language", () => {
  // The literals are the issues' own words (#866, #881) — a catalog echo
  // would pass with any copy; these pin the note to the issue's language
  // so a drift in either home fails here.
  it("the finding card carries #866's neutral pair verbatim", async () => {
    await renderDock();
    const card = screen.getByTestId("dock-finding");
    expect(within(card).getByText("Keine offenen Brüche")).toBeTruthy();
    expect(within(card).getByText("Wird mit der Wissens-Welle aktiv")).toBeTruthy();
  });

  it("the layout tune's tooltip is the draft's own parenthetical (#881)", async () => {
    // workspace-scene-centric.html, dock foot: title="Workspace-Layout
    // (später verfügbar)" — the note rides lowercase inside the brackets,
    // exactly as the light draft draws it (the dark face is enabled and
    // loses per the archive convention).
    await renderDock();
    const layout = within(screen.getByTestId("dock-foot")).getByRole("button", {
      name: "Workspace-Layout",
    });
    expect(layout.getAttribute("title")).toBe("Workspace-Layout (später verfügbar)");
  });

  it("the ⌘J chip carries the „bald“ mark the issue names (#869)", async () => {
    await renderDock();
    const foot = screen.getByTestId("dock-foot");
    expect(within(foot).getByText("bald")).toBeTruthy();
    expect(within(foot).getByText("KI-Assistent")).toBeTruthy();
    expect(within(foot).getByText("⌘J")).toBeTruthy();
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
    // The interim neutrals stand while no dock child is matched.
    expect(screen.getByTestId("dock-finding")).toBeTruthy();
    expect(screen.getByTestId("dock-entity")).toBeTruthy();
  });

  it("opening the tab navigates to the dock route — the knowledge region yields to the Outlet", async () => {
    const router = await renderDock();
    const group = screen.getByRole("group", { name: de["writing.workspace.dock.tabs"] });
    fireEvent.click(within(group).getByRole("button", { name: de["knowledge.dockTitle"] }));
    // The matched child renders through the Outlet; the two knowledge
    // slots yield, the writing-owned slots stand (content, never slots).
    expect(await screen.findByTestId("dock-face-marker")).toBeTruthy();
    expect(screen.queryByTestId("dock-finding")).toBeNull();
    expect(screen.queryByTestId("dock-entity")).toBeNull();
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

  it("the pressed tab closes the dock — the interim neutrals return", async () => {
    const router = await renderDock();
    const group = screen.getByRole("group", { name: de["writing.workspace.dock.tabs"] });
    const tab = within(group).getByRole("button", { name: de["knowledge.dockTitle"] });
    fireEvent.click(tab);
    expect(await screen.findByTestId("dock-face-marker")).toBeTruthy();
    fireEvent.click(tab);
    await screen.findByTestId("dock-finding");
    expect(screen.queryByTestId("dock-face-marker")).toBeNull();
    expect(screen.getByTestId("dock-entity")).toBeTruthy();
    expect(tab.getAttribute("aria-pressed")).toBe("false");
    expect(router.state.location.pathname).toBe(`/novels/${novelRow().id}`);
  });

  it("the URL is the whole open state — a direct dock entry renders the face", async () => {
    const novel = novelRow();
    await renderDock(novel, `/novels/${novel.id}/${docks[0].path.split("/").pop() as string}`);
    expect(screen.getByTestId("dock-face-marker")).toBeTruthy();
    expect(screen.queryByTestId("dock-finding")).toBeNull();
    const group = screen.getByRole("group", { name: de["writing.workspace.dock.tabs"] });
    expect(
      within(group).getByRole("button", { name: de["knowledge.dockTitle"] }).getAttribute("aria-pressed"),
    ).toBe("true");
  });
});

describe("the dock speaks du-tone in every catalog — no German fallback", () => {
  it("the English face speaks the English catalog's own copy", async () => {
    applyLocale("en");
    const en = catalogs.en;
    await renderDock();
    expect(screen.getByRole("heading", { name: "Consistency Checker" })).toBeTruthy();
    const finding = screen.getByTestId("dock-finding");
    expect(within(finding).getByText("No open fractures")).toBeTruthy();
    expect(within(finding).getByText("Activates with the knowledge wave")).toBeTruthy();
    expect(within(screen.getByTestId("dock-entity")).getByRole("button", { name: "Open wiki" })).toBeTruthy();
    const foot = screen.getByTestId("dock-foot");
    expect(within(foot).getByText(en["writing.workspace.dock.soon"])).toBeTruthy();
    expect(within(foot).getByRole("button", { name: "Workspace layout" }).getAttribute("title")).toBe(
      "Workspace layout (available later)",
    );
    // The registry tab speaks the English catalog too.
    expect(
      within(screen.getByRole("group", { name: en["writing.workspace.dock.tabs"] })).getByRole("button", {
        name: en["knowledge.dockTitle"],
      }),
    ).toBeTruthy();
    // The German copy is absent — the face is translated, not fallen back.
    expect(screen.queryByText("Keine offenen Brüche")).toBeNull();
    expect(screen.queryByText("Konsistenz-Prüfer")).toBeNull();
  });

  it("the French face speaks the French catalog's own copy", async () => {
    applyLocale("fr");
    await renderDock();
    expect(screen.getByRole("heading", { name: "Vérificateur de cohérence" })).toBeTruthy();
    const finding = screen.getByTestId("dock-finding");
    expect(within(finding).getByText("Aucune fracture ouverte")).toBeTruthy();
    expect(within(finding).getByText("S'active avec la vague de connaissance")).toBeTruthy();
    expect(
      within(screen.getByTestId("dock-entity")).getByRole("button", { name: "Ouvrir le wiki" }),
    ).toBeTruthy();
    const foot = screen.getByTestId("dock-foot");
    expect(within(foot).getByText("bientôt")).toBeTruthy();
    expect(
      within(foot).getByRole("button", { name: "Disposition de l'espace" }).getAttribute("title"),
    ).toBe("Disposition de l'espace (disponible plus tard)");
    expect(screen.queryByText("Keine offenen Brüche")).toBeNull();
  });

  it("the three catalogs carry the dock's keys in parity, each translated", () => {
    // The global i18n gate pins whole-catalog parity; this pins the dock's
    // family specifically — every key present in all three, and the note
    // copy actually translated (a copied German string would pass parity).
    const keys = Object.keys(catalogs.de).filter((key) => key.startsWith("writing.workspace.dock."));
    expect(keys.length).toBeGreaterThan(0);
    for (const key of keys) {
      for (const locale of ["en", "fr"] as const) {
        expect(catalogs[locale][key as keyof typeof catalogs.en], `${locale}/${key}`).toBeTruthy();
      }
    }
    const translated = [
      "writing.workspace.dock.findingEmpty",
      "writing.workspace.dock.findingNote",
      "writing.workspace.dock.layoutNote",
      "writing.workspace.dock.title",
      "writing.workspace.dock.wiki",
    ] as const;
    for (const key of translated) {
      expect(catalogs.en[key], key).not.toBe(catalogs.de[key]);
      expect(catalogs.fr[key], key).not.toBe(catalogs.de[key]);
    }
  });
});
