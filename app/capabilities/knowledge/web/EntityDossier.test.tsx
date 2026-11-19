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
import { catalogs } from "@shell/lib/generated/catalogs";
import { applyLocale } from "@shell/lib/locale";
import { queryClient } from "@shell/lib/query";

import { EntityDossier } from "./EntityDossier";

const de = catalogs.de;
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

function mountDossier(onClose = vi.fn(), onSelectEntity = vi.fn()) {
  render(
    <QueryClientProvider client={queryClient}>
      <EntityDossier
        entity={MAYA}
        relations={[R1, R2]}
        entities={ENTITIES}
        onClose={onClose}
        onSelectEntity={onSelectEntity}
      />
    </QueryClientProvider>,
  );
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
});

describe("the invented fields stay honest disabled gaps", () => {
  it("bookmark and export remain disabled with their notes", () => {
    mountDossier();
    const bookmark = screen.getByRole("button", { name: new RegExp(de["knowledge.dossier.bookmark"]) });
    expect((bookmark as HTMLButtonElement).disabled).toBe(true);
    const exportDoor = screen.getByRole("button", { name: new RegExp(de["knowledge.dossier.export"]) });
    expect((exportDoor as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByText(de["knowledge.dossier.excerptsGap"])).toBeTruthy();
  });
});
