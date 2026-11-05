// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, createRoute, createRouter, Outlet, RouterProvider } from "@tanstack/react-router";
import { act, cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { client } from "@shell/lib/api/client";
import { rootRoute } from "@shell/routes/__root";
import { EntitiesPanel } from "./EntitiesPanel";

vi.mock("@shell/lib/api/client", () => ({
  client: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn(), PUT: vi.fn(), DELETE: vi.fn() },
}));

const api = client as unknown as {
  GET: ReturnType<typeof vi.fn>;
  POST: ReturnType<typeof vi.fn>;
  PATCH: ReturnType<typeof vi.fn>;
};
const entity = (id: string, type: string, tags: string[] = []) => ({
  id, novel_id: "novel", name: id, type, description: null, aliases: [], tags,
  content: "",
  created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z",
});

function renderPanel() {
  const novel = createRoute({
    getParentRoute: () => rootRoute,
    path: "/novels/$id",
    component: Outlet,
  });
  const wissen = createRoute({
    getParentRoute: () => novel,
    path: "wissen",
    component: EntitiesPanel,
    validateSearch: (search: Record<string, unknown>) => ({ entity: search.entity as string | undefined }),
  });
  const router = createRouter({
    routeTree: rootRoute.addChildren([novel.addChildren([wissen])]),
    history: createMemoryHistory({ initialEntries: ["/novels/novel/wissen"] }),
  });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={queryClient}><RouterProvider router={router} /></QueryClientProvider>);
  return queryClient;
}

afterEach(() => { cleanup(); vi.clearAllMocks(); });

describe("EntitiesPanel filters", () => {
  it("clears selected type and tag after their last entity disappears", async () => {
    let entities = [entity("Aster", "character", ["myth"]), entity("Harbor", "location", ["coast"])];
    api.GET.mockImplementation(async (_path: string, options: { params?: { query?: { type?: string; tag?: string } } }) => {
      const { type, tag } = options?.params?.query ?? {};
      const filtered = entities.filter((item) => (!type || item.type === type) && (!tag || item.tags.includes(tag)));
      return { data: filtered, response: { ok: true } };
    });
    api.POST.mockResolvedValue({ data: [], response: { ok: true } });
    const queryClient = renderPanel();
    const user = userEvent.setup();

    await screen.findByText("Aster");
    const filter = screen.getByLabelText("Filter by type");
    const tagFilter = screen.getByLabelText("Filter by tag");
    await user.selectOptions(filter, "character");
    await screen.findByText("Aster");
    await user.selectOptions(tagFilter, "myth");
    await screen.findByText("Aster");

    entities = [entity("Harbor", "location", ["coast"])];
    await act(async () => {
      await queryClient.invalidateQueries({ queryKey: ["knowledge", "entities", "novel"] });
    });

    // The recovery is judged on the list, because that is the only place the
    // defect was visible: a select whose value matches no option reads back
    // as "" and displays its first option, so the stale state never shows in
    // the DOM. Harbor proves both filters fell away — either one left
    // standing would still narrow it out.
    expect(await screen.findByText("Harbor")).toBeTruthy();
    expect(screen.queryByText("No results")).toBeNull();
  });
});

describe("EntitiesPanel entity save", () => {
  it("keeps one PATCH per save while the request is pending", async () => {
    // The component-side pin (#313) that does not ride the E2E's route
    // hold: while the entity PATCH is held pending, the Save button stands
    // down and a second click sends no second request.
    const aster = entity("Aster", "character");
    api.GET.mockImplementation(async (path: string) => {
      if (path.includes("relations")) return { data: [], response: { ok: true } };
      return { data: [aster], response: { ok: true } };
    });
    let resolvePatch: (value: unknown) => void = () => undefined;
    api.PATCH.mockImplementation(() => new Promise((resolve) => { resolvePatch = resolve; }));
    renderPanel();
    // React-Aria's modal marks the page behind it pointer-events:none;
    // jsdom computes the inherited value, so user-event would silently
    // abort every click inside the open dialog. The pointer-events check
    // is off for this test's clicks — the disabled assertion below is the
    // thing under test, not the modal's overlay contract.
    const user = userEvent.setup({ pointerEventsCheck: 0 });

    // Select the entity and open its edit dialog.
    await user.click(await screen.findByRole("gridcell", { name: "Aster" }));
    await user.click(await screen.findByRole("button", { name: "Edit" }));
    const dialog = await screen.findByRole("dialog");
    await user.type(within(dialog).getByLabelText("Name"), " II");

    // Save once: the PATCH goes out and stays pending, the button stands
    // down. A second click is answered by the disabled button and the
    // handler's pending guard together: still exactly one PATCH.
    const save = within(dialog).getByRole("button", { name: "Save" }) as HTMLButtonElement;
    await user.click(save);
    await waitFor(() => expect(save.disabled).toBe(true));
    expect(api.PATCH).toHaveBeenCalledTimes(1);
    await user.click(save);
    expect(api.PATCH).toHaveBeenCalledTimes(1);

    // The request settles: the save closes its dialog, and no second
    // PATCH arrives behind the first.
    await act(async () => {
      resolvePatch({ data: { ...aster, name: "Aster II" }, response: { ok: true } });
    });
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(api.PATCH).toHaveBeenCalledTimes(1);
  });
});

describe("EntitiesPanel relation edit refusals", () => {
  it("names the duplicate 409 inside the inline edit form and clears it on leaving", async () => {
    // The edit-side pin (#309 + the round-1 fix): a 409 on a retyped edge
    // answers inside the inline editor's own Notice — not the shared
    // section-bottom wording — and leaving that editor, by cancel or by
    // another editor opening, takes the words with it.
    const aster = entity("Aster", "character");
    const harbor = entity("Harbor", "location");
    const edge = (id: string, type: string) => ({
      id,
      from_entity_id: aster.id,
      to_entity_id: harbor.id,
      relation_type: type,
      note: null,
      created_at: "2026-01-01T00:00:00Z",
    });
    const edges = [edge("edge-ally", "ally_of"), edge("edge-enemy", "enemy_of")];
    api.GET.mockImplementation(async (path: string) => {
      if (path.includes("relations")) return { data: edges, response: { ok: true } };
      return { data: [aster, harbor], response: { ok: true } };
    });
    // The 409: the retyped pair is one the tables already hold.
    api.PATCH.mockResolvedValue({ response: { ok: false, status: 409 } });
    renderPanel();
    const user = userEvent.setup({ pointerEventsCheck: 0 });

    // Select Aster and open its edit dialog.
    await user.click(await screen.findByRole("gridcell", { name: "Aster" }));
    await user.click(await screen.findByRole("button", { name: "Edit" }));
    await screen.findByRole("dialog");

    // Open the enemy edge's row editor from its own table row.
    const enemyRow = await screen.findByRole("row", { name: /Enemy of/ });
    await user.click(within(enemyRow).getByRole("button", { name: "Edit relation" }));
    const editForm = await screen.findByRole("form", { name: "Edit the relation" });

    // Retype the box to the ally label — a pair the backend already
    // holds. While the box has a match under the cursor, React-Aria
    // hides the page outside the listbox (the popover's own contract),
    // so the pick is made from the list itself: it sets the text and
    // closes the listbox, returning the form's words to the tree.
    const typeBox = within(editForm).getByLabelText("Relation type");
    await user.clear(typeBox);
    await user.type(typeBox, "Ally");
    await user.click(await screen.findByRole("option", { name: "Ally of" }));
    expect(within(editForm).getByLabelText("Relation type")).toHaveProperty("value", "Ally of");
    await user.click(within(editForm).getByRole("button", { name: "Save" }));

    // The refusal names itself in the inline form: within the form, and
    // nowhere at the section bottom.
    expect(within(editForm).getByText("This relation already exists.")).toBeTruthy();

    // Switch editors without leaving the first: the ally row's editor
    // opens over the standing duplicate — and carries no words from it.
    // Its box is prefilled with the edge it edits, not the stale form.
    const allyRow = screen.getByRole("row", { name: /Ally of/ });
    await user.click(within(allyRow).getByRole("button", { name: "Edit relation" }));
    const allyForm = await screen.findByRole("form", { name: "Edit the relation" });
    expect(screen.queryByText("This relation already exists.")).toBeNull();
    expect(within(allyForm).getByLabelText("Relation type")).toHaveProperty("value", "Ally of");

    // Cancel: the form and its words leave together.
    await user.click(within(allyForm).getByRole("button", { name: "Cancel" }));
    await waitFor(() =>
      expect(screen.queryByRole("form", { name: "Edit the relation" })).toBeNull(),
    );
    expect(screen.queryByText("This relation already exists.")).toBeNull();

    // A later editor opens clean too: what the leaving editor owed went
    // with it — nothing is standing to be re-shown.
    await user.click(within(enemyRow).getByRole("button", { name: "Edit relation" }));
    const enemyForm = await screen.findByRole("form", { name: "Edit the relation" });
    expect(screen.queryByText("This relation already exists.")).toBeNull();
    expect(within(enemyForm).getByLabelText("Relation type")).toHaveProperty("value", "Enemy of");

    // Clean up: leave the inline editor, then the dialog.
    await user.click(within(enemyForm).getByRole("button", { name: "Cancel" }));
    await user.click(await screen.findByRole("button", { name: "Cancel" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });
});
