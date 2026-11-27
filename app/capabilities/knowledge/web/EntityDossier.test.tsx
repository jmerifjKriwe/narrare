// @vitest-environment jsdom
/**
 * The entity dossier's editing affordances (W5 Task 4) — the shared detail
 * component the graph panel and the dossiers page mount. The edit/delete
 * footer doors, the quick-add relation and each relation card's edit/delete
 * now open the real CRUD dialogs (the disabled placeholders retired); the
 * invented fields (status, excerpts, bookmark/export, jump) stay honest
 * disabled gaps. The mutations fire the real client calls; a delete folds the
 * dossier (onClose) once the write lands. The relation card still selects the
 * other end — the affordances sit beside that door, never nested in it.
 */
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, configure, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@shell/lib/api/client", () => ({
  client: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn(), PUT: vi.fn(), DELETE: vi.fn() },
}));

import { client, type Entity, type Relation } from "@shell/lib/api/client";
import { applyLocale } from "@shell/lib/locale";
import { queryClient } from "@shell/lib/query";
import { de, merged } from "@shell/lib/test/catalogs";

import { EntityDossier } from "./EntityDossier";

// The bookmark and export doors name their state in title and aria-label,
// never a future wave (#979).
const STATUS_NOTE = {
  en: "Not available yet.",
  de: "Noch nicht verfügbar.",
  fr: "Pas encore disponible.",
} as const;

const FUTURE_PROMISE =
  /build-out|aufbau|wave|welle|vague|appear|erschein|appara|coming soon|kommt mit|arrive avec|future|becomes available|later/i;

describe("the bookmark and export notes speak to the reader", () => {
  it("are status-only in every catalog, never a future promise", () => {
    for (const locale of ["en", "de", "fr"] as const) {
      for (const key of [
        "knowledge.dossier.bookmarkNote",
        "knowledge.dossier.exportNote",
      ] as const) {
        const note = merged[locale][key];
        expect(note).toBe(STATUS_NOTE[locale]);
        expect(note).not.toMatch(FUTURE_PROMISE);
      }
    }
  });
});
const api = client as unknown as Record<"POST" | "PATCH" | "DELETE", ReturnType<typeof vi.fn>>;

configure({ asyncUtilTimeout: 5000 });

const NOVEL_ID = "11111111-1111-1111-1111-111111111111";

function ok(status = 200): Response {
  return new Response(null, { status });
}

function entityRow(overrides: Partial<Entity> & { id: string; name: string }): Entity {
  return {
    novel_id: NOVEL_ID,
    type: "character",
    aliases: [],
    tags: [],
    content: "",
    created_at: "2026-11-18T10:00:00Z",
    updated_at: "2026-11-18T10:00:00Z",
    ...overrides,
  };
}

const MAYA = entityRow({ id: "e1", name: "Dr. Maya Chen", content: "Leitende Bio-Physikerin." });
const ARIA = entityRow({ id: "e2", name: "ARIA" });
const STATION = entityRow({ id: "e3", name: "Station 7", type: "location" });
const ENTITIES = [MAYA, ARIA, STATION];

const R1: Relation = {
  id: "r1",
  from_entity_id: "e1",
  to_entity_id: "e2",
  relation_type: "ally_of",
  note: "Symbiotische Co-Pilotin.",
  created_at: "2026-11-18T10:00:00Z",
};
const R2: Relation = {
  id: "r2",
  from_entity_id: "e1",
  to_entity_id: "e3",
  relation_type: "located_in",
  note: null,
  created_at: "2026-11-18T10:00:00Z",
};

function dossierUi(
  relations: readonly Relation[],
  onClose: () => void = vi.fn(),
  onSelectEntity: (id: string) => void = vi.fn(),
) {
  return (
    <QueryClientProvider client={queryClient}>
      <EntityDossier
        entity={MAYA}
        relations={relations}
        entities={ENTITIES}
        onClose={onClose}
        onSelectEntity={onSelectEntity}
      />
    </QueryClientProvider>
  );
}

function mountDossier(onClose = vi.fn(), onSelectEntity = vi.fn()) {
  render(dossierUi([R1, R2], onClose, onSelectEntity));
  return { onClose, onSelectEntity };
}

beforeEach(() => {
  applyLocale("de");
  vi.stubGlobal("navigator", { language: "de-DE", languages: ["de-DE"] });
});

afterEach(() => {
  cleanup();
  queryClient.clear();
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

describe("the footer's edit and delete doors are live", () => {
  it("edit opens the prefilled edit dialog and save fires the real PATCH", async () => {
    api.PATCH.mockResolvedValue({ data: MAYA, response: ok() });
    mountDossier();
    const edit = screen.getByRole("button", { name: de["knowledge.dossier.edit"] });
    expect((edit as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(edit);
    const dialog = await screen.findByRole("dialog");
    expect((within(dialog).getByLabelText(de["knowledge.crud.nameLabel"]) as HTMLInputElement).value).toBe("Dr. Maya Chen");
    fireEvent.change(within(dialog).getByLabelText(de["knowledge.crud.nameLabel"]), { target: { value: "Maya" } });
    fireEvent.click(within(dialog).getByRole("button", { name: de["knowledge.crud.save"] }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(api.PATCH).toHaveBeenCalledWith("/api/knowledge/entities/{entity_id}", {
      params: { path: { entity_id: "e1" } },
      body: { name: "Maya", type: "character", content: "Leitende Bio-Physikerin." },
    });
  });

  it("delete opens the confirm with the real relation count and folds the dossier on success", async () => {
    api.DELETE.mockResolvedValue({ data: undefined, response: ok(204) });
    const { onClose } = mountDossier();
    fireEvent.click(document.getElementById("dossier-delete") as HTMLElement);
    const confirm = await screen.findByRole("alertdialog");
    expect(within(confirm).getByText(/2 Relationen/)).toBeTruthy();
    fireEvent.click(within(confirm).getByRole("button", { name: de["knowledge.crud.deleteConfirm"] }));
    await waitFor(() => expect(screen.queryByRole("alertdialog")).toBeNull());
    expect(api.DELETE).toHaveBeenCalledWith("/api/knowledge/entities/{entity_id}", {
      params: { path: { entity_id: "e1" } },
    });
    expect(onClose).toHaveBeenCalled();
  });

  it("jump stays an honest disabled gap", () => {
    mountDossier();
    const jump = screen.getByRole("button", { name: new RegExp(de["knowledge.dossier.jump"]) });
    expect((jump as HTMLButtonElement).disabled).toBe(true);
  });

  it("an entity delete lands focus on the dossier container, not the body (review fix)", async () => {
    api.DELETE.mockResolvedValue({ data: undefined, response: ok(204) });
    // onClose is a spy here, so the dossier survives the fold — its container
    // is the focus survivor (the graph passes its own page when it folds).
    mountDossier();
    fireEvent.click(document.getElementById("dossier-delete") as HTMLElement);
    const confirm = await screen.findByRole("alertdialog");
    fireEvent.click(within(confirm).getByRole("button", { name: de["knowledge.crud.deleteConfirm"] }));
    await waitFor(() => {
      expect(screen.queryByRole("alertdialog")).toBeNull();
      expect(document.activeElement).toBe(document.getElementById("entity-dossier"));
    });
  });
});

describe("the quick-add relation door is live", () => {
  it("opens the create dialog with the entity as the fixed from", async () => {
    api.POST.mockResolvedValue({ data: R1, response: ok(201) });
    mountDossier();
    fireEvent.click(document.getElementById("dossier-add-relation") as HTMLElement);
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(de["knowledge.crud.addRelationTitle"])).toBeTruthy();
    // From is fixed (no from select).
    expect(within(dialog).queryByLabelText(de["knowledge.crud.fromLabel"])).toBeNull();
    fireEvent.change(within(dialog).getByLabelText(de["knowledge.crud.toLabel"]), { target: { value: "e2" } });
    fireEvent.change(within(dialog).getByLabelText(de["knowledge.crud.relationTypeLabel"]), { target: { value: "ally_of" } });
    fireEvent.click(within(dialog).getByRole("button", { name: de["knowledge.crud.save"] }));
    await waitFor(() => expect(api.POST).toHaveBeenCalled());
    expect(api.POST.mock.calls[0][1].params.path.entity_id).toBe("e1");
  });
});

describe("each relation card carries edit and delete beside the select door", () => {
  it("the card's main door still selects the other end", () => {
    const { onSelectEntity } = mountDossier();
    fireEvent.click(screen.getByText("ARIA"));
    expect(onSelectEntity).toHaveBeenCalledWith("e2");
  });

  it("edit opens the relation edit dialog prefilled; save fires the real PATCH", async () => {
    api.PATCH.mockResolvedValue({ data: R1, response: ok() });
    mountDossier();
    fireEvent.click(document.getElementById("dossier-relation-edit-r1") as HTMLElement);
    const dialog = await screen.findByRole("dialog");
    expect((within(dialog).getByLabelText(de["knowledge.crud.relationTypeLabel"]) as HTMLInputElement).value).toBe(
      de["knowledge.relation.ally_of"],
    );
    fireEvent.change(within(dialog).getByLabelText(de["knowledge.crud.relationTypeLabel"]), { target: { value: "enemy_of" } });
    fireEvent.click(within(dialog).getByRole("button", { name: de["knowledge.crud.save"] }));
    await waitFor(() => expect(api.PATCH).toHaveBeenCalled());
    expect(api.PATCH.mock.calls[0][0]).toBe("/api/knowledge/relations/{relation_id}");
    expect(api.PATCH.mock.calls[0][1].params.path.relation_id).toBe("r1");
  });

  it("delete opens the relation confirm and fires the real DELETE on the edge", async () => {
    api.DELETE.mockResolvedValue({ data: undefined, response: ok(204) });
    mountDossier();
    fireEvent.click(document.getElementById("dossier-relation-delete-r2") as HTMLElement);
    const confirm = await screen.findByRole("alertdialog");
    expect(within(confirm).getByText(/Station 7/)).toBeTruthy();
    fireEvent.click(within(confirm).getByRole("button", { name: de["knowledge.crud.deleteConfirm"] }));
    await waitFor(() => expect(api.DELETE).toHaveBeenCalled());
    expect(api.DELETE).toHaveBeenCalledWith("/api/knowledge/relations/{relation_id}", {
      params: { path: { relation_id: "r2" } },
    });
  });

  it("the affordances are not nested inside the select button (valid HTML)", () => {
    mountDossier();
    const edit = document.getElementById("dossier-relation-edit-r1") as HTMLElement;
    // The affordance is a button itself; it must not sit INSIDE another button.
    expect(edit.parentElement?.closest("button")).toBeNull();
  });

  it("the edit/delete affordances name the other end — distinguishable per card (review fix)", () => {
    mountDossier();
    const editR1 = document.getElementById("dossier-relation-edit-r1");
    const editR2 = document.getElementById("dossier-relation-edit-r2");
    expect(editR1?.getAttribute("aria-label")).toContain("ARIA");
    expect(editR2?.getAttribute("aria-label")).toContain("Station 7");
    expect(editR1?.getAttribute("aria-label")).not.toBe(editR2?.getAttribute("aria-label"));
    expect(document.getElementById("dossier-relation-delete-r1")?.getAttribute("aria-label")).toContain("ARIA");
    expect(document.getElementById("dossier-relation-delete-r2")?.getAttribute("aria-label")).toContain("Station 7");
  });

  it("a relation delete lands focus on the relations list, not the body (review fix)", async () => {
    api.DELETE.mockResolvedValue({ data: undefined, response: ok(204) });
    mountDossier();
    fireEvent.click(document.getElementById("dossier-relation-delete-r2") as HTMLElement);
    const confirm = await screen.findByRole("alertdialog");
    fireEvent.click(within(confirm).getByRole("button", { name: de["knowledge.crud.deleteConfirm"] }));
    await waitFor(() => {
      expect(screen.queryByRole("alertdialog")).toBeNull();
      expect(document.activeElement).toBe(document.getElementById("dossier-relations"));
    });
  });

  it("deleting the LAST relation keeps focus off the body — the dossier aside survives the emptied list (#910)", async () => {
    api.DELETE.mockResolvedValue({ data: undefined, response: ok(204) });
    // One edge: deleting it empties the list, whose unmount would otherwise
    // drop activeElement to the body once the invalidation settles.
    const view = render(dossierUi([R1]));
    fireEvent.click(document.getElementById("dossier-relation-delete-r1") as HTMLElement);
    const confirm = await screen.findByRole("alertdialog");
    fireEvent.click(within(confirm).getByRole("button", { name: de["knowledge.crud.deleteConfirm"] }));
    // The write landed: focus sits on the surviving container, not on the
    // list the refetch is about to retire.
    await waitFor(() => {
      expect(screen.queryByRole("alertdialog")).toBeNull();
      expect(document.activeElement).toBe(document.getElementById("entity-dossier"));
    });
    // The invalidation settles: the emptied list unmounts (the empty-state
    // paragraph replaces it) — the survivor must be one that survives THIS.
    view.rerender(dossierUi([]));
    expect(document.getElementById("dossier-relations")).toBeNull();
    expect(document.activeElement).toBe(document.getElementById("entity-dossier"));
  });
});

describe("the invented fields stay honest disabled gaps", () => {
  it("bookmark and export remain disabled with their notes", () => {
    mountDossier();
    // Both doors carry the same status note, so anchor the full accessible
    // name instead of the shared note regex.
    const bookmark = screen.getByRole("button", {
      name: `${de["knowledge.dossier.bookmark"]} (${de["knowledge.dossier.bookmarkNote"]})`,
    });
    expect((bookmark as HTMLButtonElement).disabled).toBe(true);
    expect(bookmark.getAttribute("title")).toContain(de["knowledge.dossier.bookmarkNote"]);
    expect(bookmark.getAttribute("aria-label")).toContain(de["knowledge.dossier.bookmarkNote"]);
    const exportDoor = screen.getByRole("button", {
      name: `${de["knowledge.dossier.export"]} (${de["knowledge.dossier.exportNote"]})`,
    });
    expect((exportDoor as HTMLButtonElement).disabled).toBe(true);
    expect(exportDoor.getAttribute("title")).toContain(de["knowledge.dossier.exportNote"]);
    expect(exportDoor.getAttribute("aria-label")).toContain(de["knowledge.dossier.exportNote"]);
    expect(screen.getByText(de["knowledge.dossier.excerptsGap"])).toBeTruthy();
    // The jump door's tooltip carries the same status note — no dead promise.
    const jump = screen.getByRole("button", {
      name: `${de["knowledge.dossier.jump"]} (${de["knowledge.dossier.jumpNote"]})`,
    });
    expect((jump as HTMLButtonElement).disabled).toBe(true);
    expect(jump.getAttribute("title")).toContain(de["knowledge.dossier.jumpNote"]);
  });
});
