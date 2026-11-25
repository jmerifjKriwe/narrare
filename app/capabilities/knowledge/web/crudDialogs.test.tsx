// @vitest-environment jsdom
/**
 * The knowledge CRUD dialogs (W5 Task 4) — the editing layer the graph and
 * the dossiers mount, on the modal discipline the writing dialogs speak
 * (`@shell/ui/modalKeys`): the trap and the wrap shared, the Escape answer
 * each dialog's own (forms hold while dirty or busy, the destructive confirms
 * cancel unless busy), focus lands on the first answer and returns to the
 * opener on every close. The mutations fire the REAL client calls (the client
 * mocked at its module boundary, the house pattern); a refusal keeps the
 * answers and names the loss-free error with a retry, a 409 on an edge names
 * the duplicate it is. The merge names source → target and the loss before it
 * happens. The hand-made create (W9) is the same frame: a name and a type
 * gate the save, a duplicate name is a notice, and a relation row the save
 * will drop is counted rather than lost. The face speaks du-tone in all
 * three catalogs.
 */
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, configure, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { useState, type ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@shell/lib/api/client", () => ({
  client: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn(), PUT: vi.fn(), DELETE: vi.fn() },
}));

import { client, type Entity, type Relation } from "@shell/lib/api/client";
import { catalogs } from "@shell/lib/generated/catalogs";
import { applyLocale } from "@shell/lib/locale";
import { queryClient } from "@shell/lib/query";

import {
  CreateRelationDialog,
  DeleteEntityDialog,
  DeleteRelationDialog,
  EditEntityDialog,
  EditRelationDialog,
  MergeDialog,
} from "./crudDialogs";

const de = catalogs.de;
const api = client as unknown as Record<"GET" | "POST" | "PATCH" | "DELETE", ReturnType<typeof vi.fn>>;

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
const ARIA = entityRow({ id: "e2", name: "ARIA", content: "Autonome Schiffs-KI." });
const STATION = entityRow({ id: "e3", name: "Station 7", type: "location" });
const ENTITIES = [MAYA, ARIA, STATION];

function relationRow(overrides: Partial<Relation> & { id: string }): Relation {
  return {
    from_entity_id: "e1",
    to_entity_id: "e2",
    relation_type: "ally_of",
    note: null,
    created_at: "2026-11-18T10:00:00Z",
    ...overrides,
  };
}

const R1 = relationRow({ id: "r1", relation_type: "ally_of", note: "Symbiotische Co-Pilotin." });

/** An opener button plus the dialog it opens; closing unmounts the dialog so
 *  the focus-return contract can be read off the opener. */
function harness(dialog: (close: () => void) => ReactNode, openerId = "opener") {
  return function Harness() {
    const [open, setOpen] = useState(false);
    return (
      <>
        <button id={openerId} type="button" onClick={() => setOpen(true)}>
          opener
        </button>
        {open && dialog(() => setOpen(false))}
      </>
    );
  };
}

function mount(Harness: () => ReactNode) {
  render(
    <QueryClientProvider client={queryClient}>
      <Harness />
    </QueryClientProvider>,
  );
}

function openDialog() {
  fireEvent.click(screen.getByText("opener"));
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

describe("EditEntityDialog", () => {
  const harnessEdit = harness((close) => <EditEntityDialog entity={MAYA} openerId="opener" onClose={close} />);

  it("opens prefilled with the row's name, type and description; focus on the name", () => {
    mount(harnessEdit);
    openDialog();
    const name = screen.getByLabelText(de["knowledge.crud.nameLabel"]) as HTMLInputElement;
    expect(name.value).toBe("Dr. Maya Chen");
    expect(document.activeElement).toBe(name);
    const type = screen.getByLabelText(de["knowledge.crud.typeLabel"]) as HTMLSelectElement;
    expect(type.value).toBe("character");
    // The type box offers the real eight, no invented type.
    expect(type.querySelectorAll("option")).toHaveLength(8);
    const desc = screen.getByLabelText(de["knowledge.crud.descriptionLabel"]) as HTMLTextAreaElement;
    expect(desc.value).toBe("Leitende Bio-Physikerin.");
  });

  it("a blank name is refused before the wire — the required guard", () => {
    mount(harnessEdit);
    openDialog();
    fireEvent.change(screen.getByLabelText(de["knowledge.crud.nameLabel"]), { target: { value: "   " } });
    fireEvent.click(screen.getByRole("button", { name: de["knowledge.crud.save"] }));
    expect(screen.getByText(de["knowledge.crud.nameRequired"])).toBeTruthy();
    expect(api.PATCH).not.toHaveBeenCalled();
  });

  it("save fires the real PATCH with the carried fields and closes on success", async () => {
    api.PATCH.mockResolvedValue({ data: { ...MAYA, name: "Maya" }, response: ok() });
    mount(harnessEdit);
    openDialog();
    fireEvent.change(screen.getByLabelText(de["knowledge.crud.nameLabel"]), { target: { value: "Maya" } });
    fireEvent.change(screen.getByLabelText(de["knowledge.crud.typeLabel"]), { target: { value: "location" } });
    fireEvent.click(screen.getByRole("button", { name: de["knowledge.crud.save"] }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(api.PATCH).toHaveBeenCalledWith("/api/knowledge/entities/{entity_id}", {
      params: { path: { entity_id: "e1" } },
      body: { name: "Maya", type: "location", content: "Leitende Bio-Physikerin." },
    });
  });

  it("an empty description clears the body to null", async () => {
    api.PATCH.mockResolvedValue({ data: MAYA, response: ok() });
    mount(harnessEdit);
    openDialog();
    fireEvent.change(screen.getByLabelText(de["knowledge.crud.descriptionLabel"]), { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: de["knowledge.crud.save"] }));
    await waitFor(() => expect(api.PATCH).toHaveBeenCalled());
    expect(api.PATCH.mock.calls[0][1].body.content).toBeNull();
  });

  it("a refusal keeps the answers and names the loss-free error with a retry", async () => {
    api.PATCH.mockResolvedValue({ data: undefined, response: ok(500) });
    mount(harnessEdit);
    openDialog();
    fireEvent.change(screen.getByLabelText(de["knowledge.crud.nameLabel"]), { target: { value: "Maya" } });
    fireEvent.click(screen.getByRole("button", { name: de["knowledge.crud.save"] }));
    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText(de["knowledge.crud.error"])).toBeTruthy();
    // The answer is kept, the dialog stands.
    expect((screen.getByLabelText(de["knowledge.crud.nameLabel"]) as HTMLInputElement).value).toBe("Maya");
    expect(screen.getByRole("dialog")).toBeTruthy();
    // The retry re-runs the very ask.
    api.PATCH.mockResolvedValue({ data: MAYA, response: ok() });
    fireEvent.click(within(alert).getByRole("button", { name: de["knowledge.crud.retry"] }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(api.PATCH).toHaveBeenCalledTimes(2);
  });

  it("busy holds every close path; Escape and the scrim wait", async () => {
    let resolve: (value: { data: Entity; response: Response }) => void = () => {};
    api.PATCH.mockImplementation(() => new Promise((r) => { resolve = r; }));
    mount(harnessEdit);
    openDialog();
    fireEvent.change(screen.getByLabelText(de["knowledge.crud.nameLabel"]), { target: { value: "Maya" } });
    fireEvent.click(screen.getByRole("button", { name: de["knowledge.crud.save"] }));
    await waitFor(() => expect(screen.getByRole("button", { name: de["knowledge.crud.busy"] })).toBeTruthy());
    // Escape does not close while busy.
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.getByRole("dialog")).toBeTruthy();
    // The cross is unavailable while busy.
    expect((screen.getByRole("button", { name: de["knowledge.crud.close"] }) as HTMLButtonElement).disabled).toBe(true);
    resolve({ data: MAYA, response: ok() });
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  it("the dirty rule: Escape closes pristine, holds while edits stand; focus returns to the opener", () => {
    mount(harnessEdit);
    openDialog();
    // Pristine — Escape closes and hands focus back.
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).toBe(screen.getByText("opener"));
    // Reopen, type a change — Escape now holds.
    openDialog();
    fireEvent.change(screen.getByLabelText(de["knowledge.crud.nameLabel"]), { target: { value: "Maya" } });
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.getByRole("dialog")).toBeTruthy();
    // Cancel leaves with edits standing and returns focus.
    fireEvent.click(screen.getByRole("button", { name: de["knowledge.crud.cancel"] }));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).toBe(screen.getByText("opener"));
  });

  it("Tab wraps inside the panel at both ends", () => {
    mount(harnessEdit);
    openDialog();
    const panel = screen.getByRole("dialog");
    const focusables = Array.from(panel.querySelectorAll<HTMLElement>("button:not([disabled]), input, select, textarea"));
    const first = focusables[0];
    const last = focusables[focusables.length - 1];
    last.focus();
    fireEvent.keyDown(document, { key: "Tab" });
    expect(document.activeElement).toBe(first);
    fireEvent.keyDown(document, { key: "Tab", shiftKey: true });
    expect(document.activeElement).toBe(last);
  });
});

describe("DeleteEntityDialog — the destructive confirm family", () => {
  const harnessDelete = harness((close) => (
    <DeleteEntityDialog entity={MAYA} relationCount={2} openerId="opener" onClose={close} />
  ));

  it("names the loss with the real relation count; focus on the safe answer", () => {
    mount(harnessDelete);
    openDialog();
    const dialog = screen.getByRole("alertdialog");
    expect(within(dialog).getByText(de["knowledge.crud.deleteEntityTitle"])).toBeTruthy();
    expect(within(dialog).getByText(/Dr\. Maya Chen/)).toBeTruthy();
    expect(within(dialog).getByText(/2 Relationen/)).toBeTruthy();
    expect(document.activeElement).toBe(screen.getByRole("button", { name: de["knowledge.crud.cancel"] }));
  });

  it("confirm fires the real DELETE and closes; the scrim does not dismiss", async () => {
    api.DELETE.mockResolvedValue({ data: undefined, response: ok(204) });
    mount(harnessDelete);
    openDialog();
    // A press on the scrim is not an answer.
    fireEvent.mouseDown(screen.getByRole("alertdialog").parentElement as HTMLElement);
    expect(screen.getByRole("alertdialog")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: de["knowledge.crud.deleteConfirm"] }));
    await waitFor(() => expect(screen.queryByRole("alertdialog")).toBeNull());
    expect(api.DELETE).toHaveBeenCalledWith("/api/knowledge/entities/{entity_id}", {
      params: { path: { entity_id: "e1" } },
    });
  });

  it("Escape cancels and returns focus to the opener", () => {
    mount(harnessDelete);
    openDialog();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("alertdialog")).toBeNull();
    expect(document.activeElement).toBe(screen.getByText("opener"));
  });

  it("a refusal names the delete error and keeps the question", async () => {
    api.DELETE.mockResolvedValue({ data: undefined, response: ok(500) });
    mount(harnessDelete);
    openDialog();
    fireEvent.click(screen.getByRole("button", { name: de["knowledge.crud.deleteConfirm"] }));
    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText(de["knowledge.crud.deleteError"])).toBeTruthy();
    expect(screen.getByRole("alertdialog")).toBeTruthy();
  });

  it("the singular relation count reads the locale's own plural", () => {
    const Harness = harness((close) => (
      <DeleteEntityDialog entity={MAYA} relationCount={1} openerId="opener" onClose={close} />
    ));
    mount(Harness);
    openDialog();
    expect(screen.getByText(/1 Relation\b/)).toBeTruthy();
  });
});

describe("CreateRelationDialog", () => {
  const harnessAdd = harness((close) => (
    <CreateRelationDialog novelId={NOVEL_ID} entities={ENTITIES} from={MAYA} openerId="opener" onClose={close} />
  ));

  it("from is fixed and named; to is selectable from the novel's entities; focus on the to box", () => {
    mount(harnessAdd);
    openDialog();
    // From is fixed: no from select, the name shown as a read-only row.
    expect(screen.queryByLabelText(de["knowledge.crud.fromLabel"])).toBeNull();
    expect(screen.getAllByText("Dr. Maya Chen").length).toBeGreaterThan(0);
    const to = screen.getByLabelText(de["knowledge.crud.toLabel"]) as HTMLSelectElement;
    expect(document.activeElement).toBe(to);
    // Every entity of the novel is an option (self-relations allowed); the
    // empty placeholder is not an end.
    const ends = Array.from(to.querySelectorAll("option")).filter((option) => option.value !== "");
    expect(ends).toHaveLength(ENTITIES.length);
  });

  it("a missing end or type is refused before the wire", () => {
    mount(harnessAdd);
    openDialog();
    fireEvent.click(screen.getByRole("button", { name: de["knowledge.crud.save"] }));
    expect(screen.getByText(de["knowledge.crud.toRequired"])).toBeTruthy();
    expect(api.POST).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText(de["knowledge.crud.toLabel"]), { target: { value: "e2" } });
    fireEvent.click(screen.getByRole("button", { name: de["knowledge.crud.save"] }));
    expect(screen.getByText(de["knowledge.crud.relationTypeRequired"])).toBeTruthy();
    expect(api.POST).not.toHaveBeenCalled();
  });

  it("a picked suggestion resolves to its key; the note is optional; the real POST fires", async () => {
    api.POST.mockResolvedValue({ data: R1, response: ok(201) });
    mount(harnessAdd);
    openDialog();
    fireEvent.change(screen.getByLabelText(de["knowledge.crud.toLabel"]), { target: { value: "e2" } });
    fireEvent.change(screen.getByLabelText(de["knowledge.crud.relationTypeLabel"]), {
      target: { value: de["knowledge.relation.ally_of"] },
    });
    fireEvent.click(screen.getByRole("button", { name: de["knowledge.crud.save"] }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(api.POST).toHaveBeenCalledWith("/api/knowledge/entities/{entity_id}/relations", {
      params: { path: { entity_id: "e1" } },
      body: { to_entity_id: "e2", relation_type: "ally_of", note: undefined },
    });
  });

  it("free text rides as the type it is (D7); a carried note rides trimmed", async () => {
    api.POST.mockResolvedValue({ data: R1, response: ok(201) });
    mount(harnessAdd);
    openDialog();
    fireEvent.change(screen.getByLabelText(de["knowledge.crud.toLabel"]), { target: { value: "e3" } });
    fireEvent.change(screen.getByLabelText(de["knowledge.crud.relationTypeLabel"]), { target: { value: "Neuro-Link" } });
    fireEvent.change(screen.getByLabelText(de["knowledge.crud.noteLabel"]), { target: { value: "  Direkter Kanal  " } });
    fireEvent.click(screen.getByRole("button", { name: de["knowledge.crud.save"] }));
    await waitFor(() => expect(api.POST).toHaveBeenCalled());
    expect(api.POST.mock.calls[0][1].body).toEqual({
      to_entity_id: "e3",
      relation_type: "Neuro-Link",
      note: "Direkter Kanal",
    });
  });

  it("a 409 names the duplicate, not an outage", async () => {
    api.POST.mockResolvedValue({ data: undefined, response: ok(409) });
    mount(harnessAdd);
    openDialog();
    fireEvent.change(screen.getByLabelText(de["knowledge.crud.toLabel"]), { target: { value: "e2" } });
    fireEvent.change(screen.getByLabelText(de["knowledge.crud.relationTypeLabel"]), { target: { value: "ally_of" } });
    fireEvent.click(screen.getByRole("button", { name: de["knowledge.crud.save"] }));
    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText(de["knowledge.crud.relationExists"])).toBeTruthy();
  });

  it("with no fixed end the from box appears and is required", () => {
    const Harness = harness((close) => (
      <CreateRelationDialog novelId={NOVEL_ID} entities={ENTITIES} from={null} openerId="opener" onClose={close} />
    ));
    mount(Harness);
    openDialog();
    const from = screen.getByLabelText(de["knowledge.crud.fromLabel"]) as HTMLSelectElement;
    expect(document.activeElement).toBe(from);
    fireEvent.change(screen.getByLabelText(de["knowledge.crud.toLabel"]), { target: { value: "e2" } });
    fireEvent.change(screen.getByLabelText(de["knowledge.crud.relationTypeLabel"]), { target: { value: "ally_of" } });
    fireEvent.click(screen.getByRole("button", { name: de["knowledge.crud.save"] }));
    expect(screen.getByText(de["knowledge.crud.fromRequired"])).toBeTruthy();
    expect(api.POST).not.toHaveBeenCalled();
  });
});

describe("EditRelationDialog", () => {
  const harnessEdit = harness((close) => (
    <EditRelationDialog relation={R1} entities={ENTITIES} openerId="opener" onClose={close} />
  ));

  it("prefills the type's wording and the note; the ends are named and immutable", () => {
    mount(harnessEdit);
    openDialog();
    expect((screen.getByLabelText(de["knowledge.crud.relationTypeLabel"]) as HTMLInputElement).value).toBe(
      de["knowledge.relation.ally_of"],
    );
    expect((screen.getByLabelText(de["knowledge.crud.noteLabel"]) as HTMLTextAreaElement).value).toBe(
      "Symbiotische Co-Pilotin.",
    );
    expect(screen.getByText(/Dr\. Maya Chen → ARIA/)).toBeTruthy();
    expect(screen.getByText(de["knowledge.crud.editRelationHint"])).toBeTruthy();
    // No end selectors — the ends cannot move.
    expect(screen.queryByLabelText(de["knowledge.crud.toLabel"])).toBeNull();
  });

  it("save fires the real PATCH with type and note only", async () => {
    api.PATCH.mockResolvedValue({ data: R1, response: ok() });
    mount(harnessEdit);
    openDialog();
    fireEvent.change(screen.getByLabelText(de["knowledge.crud.relationTypeLabel"]), { target: { value: "enemy_of" } });
    fireEvent.change(screen.getByLabelText(de["knowledge.crud.noteLabel"]), { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: de["knowledge.crud.save"] }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(api.PATCH).toHaveBeenCalledWith("/api/knowledge/relations/{relation_id}", {
      params: { path: { relation_id: "r1" } },
      body: { relation_type: "enemy_of", note: null },
    });
  });

  it("a 409 names the duplicate", async () => {
    api.PATCH.mockResolvedValue({ data: undefined, response: ok(409) });
    mount(harnessEdit);
    openDialog();
    fireEvent.change(screen.getByLabelText(de["knowledge.crud.relationTypeLabel"]), { target: { value: "rival_of" } });
    fireEvent.click(screen.getByRole("button", { name: de["knowledge.crud.save"] }));
    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText(de["knowledge.crud.relationExists"])).toBeTruthy();
  });

  it("a label-colliding free-text type saves UNCHANGED on an untouched save (review fix)", async () => {
    // The stored type is free text that happens to spell the de label of ally_of.
    const colliding = de["knowledge.relation.ally_of"];
    const freeTextRelation = relationRow({ id: "r9", relation_type: colliding, note: null });
    api.PATCH.mockResolvedValue({ data: freeTextRelation, response: ok() });
    const Harness = harness((close) => (
      <EditRelationDialog relation={freeTextRelation} entities={ENTITIES} openerId="opener" onClose={close} />
    ));
    mount(Harness);
    openDialog();
    // The box opens on the free text itself; save without touching it.
    expect((screen.getByLabelText(de["knowledge.crud.relationTypeLabel"]) as HTMLInputElement).value).toBe(colliding);
    fireEvent.click(screen.getByRole("button", { name: de["knowledge.crud.save"] }));
    await waitFor(() => expect(api.PATCH).toHaveBeenCalled());
    expect(api.PATCH.mock.calls[0][1].body.relation_type).toBe(colliding);
    expect(api.PATCH.mock.calls[0][1].body.relation_type).not.toBe("ally_of");
  });
});

describe("DeleteRelationDialog — the destructive confirm family", () => {
  const harnessDelete = harness((close) => (
    <DeleteRelationDialog relation={R1} entities={ENTITIES} openerId="opener" onClose={close} />
  ));

  it("names the edge and that both entities stay; focus on the safe answer", () => {
    mount(harnessDelete);
    openDialog();
    const dialog = screen.getByRole("alertdialog");
    expect(within(dialog).getByText(/Dr\. Maya Chen → ARIA/)).toBeTruthy();
    expect(within(dialog).getByText(de["knowledge.crud.deleteRelationTitle"])).toBeTruthy();
    expect(document.activeElement).toBe(screen.getByRole("button", { name: de["knowledge.crud.cancel"] }));
  });

  it("confirm fires the real DELETE on the edge and closes", async () => {
    api.DELETE.mockResolvedValue({ data: undefined, response: ok(204) });
    mount(harnessDelete);
    openDialog();
    fireEvent.click(screen.getByRole("button", { name: de["knowledge.crud.deleteConfirm"] }));
    await waitFor(() => expect(screen.queryByRole("alertdialog")).toBeNull());
    expect(api.DELETE).toHaveBeenCalledWith("/api/knowledge/relations/{relation_id}", {
      params: { path: { relation_id: "r1" } },
    });
  });
});

describe("MergeDialog — source → target, the confirm family", () => {
  const harnessMerge = harness((close) => (
    <MergeDialog novelId={NOVEL_ID} entities={ENTITIES} source={MAYA} openerId="opener" onClose={close} />
  ));

  it("names the fixed source and offers the others as target; focus on the safe answer", () => {
    mount(harnessMerge);
    openDialog();
    expect(screen.getByText(de["knowledge.crud.mergeSourceLabel"])).toBeTruthy();
    const target = screen.getByLabelText(de["knowledge.crud.mergeTargetLabel"]) as HTMLSelectElement;
    // The source itself is not a target — an entity cannot merge into itself.
    const values = Array.from(target.querySelectorAll("option")).map((option) => option.value);
    expect(values).toContain("e2");
    expect(values).not.toContain("e1");
    expect(document.activeElement).toBe(screen.getByRole("button", { name: de["knowledge.crud.cancel"] }));
  });

  it("the body names source → target and the loss before it happens", () => {
    mount(harnessMerge);
    openDialog();
    fireEvent.change(screen.getByLabelText(de["knowledge.crud.mergeTargetLabel"]), { target: { value: "e2" } });
    const body = screen.getByRole("alertdialog");
    // The consequence paragraph (aria-describedby) names source → target.
    const para = document.getElementById(body.getAttribute("aria-describedby") ?? "");
    expect(para?.textContent).toContain("Dr. Maya Chen");
    expect(para?.textContent).toContain("ARIA");
    expect(within(body).getByText(de["knowledge.crud.mergeNote"])).toBeTruthy();
  });

  it("confirm is held until a target stands; then the real merge POST fires", async () => {
    api.POST.mockResolvedValue({ data: ARIA, response: ok() });
    mount(harnessMerge);
    openDialog();
    const confirm = screen.getByRole("button", { name: de["knowledge.crud.mergeConfirm"] }) as HTMLButtonElement;
    expect(confirm.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText(de["knowledge.crud.mergeTargetLabel"]), { target: { value: "e2" } });
    expect(confirm.disabled).toBe(false);
    fireEvent.click(confirm);
    await waitFor(() => expect(screen.queryByRole("alertdialog")).toBeNull());
    expect(api.POST).toHaveBeenCalledWith("/api/knowledge/entities/{entity_id}/merge", {
      params: { path: { entity_id: "e1" } },
      body: { target_id: "e2" },
    });
  });

  it("with no fixed source the source box appears and the target excludes it", () => {
    const Harness = harness((close) => (
      <MergeDialog novelId={NOVEL_ID} entities={ENTITIES} source={null} openerId="opener" onClose={close} />
    ));
    mount(Harness);
    openDialog();
    const source = screen.getByLabelText(de["knowledge.crud.mergeSourceLabel"]) as HTMLSelectElement;
    fireEvent.change(source, { target: { value: "e3" } });
    const target = screen.getByLabelText(de["knowledge.crud.mergeTargetLabel"]) as HTMLSelectElement;
    const values = Array.from(target.querySelectorAll("option")).map((option) => option.value);
    expect(values).not.toContain("e3");
    expect(values).toContain("e1");
  });

  it("the prompt names the missing SOURCE when a target stands but no source (review fix)", () => {
    const Harness = harness((close) => (
      <MergeDialog novelId={NOVEL_ID} entities={ENTITIES} source={null} openerId="opener" onClose={close} />
    ));
    mount(Harness);
    openDialog();
    // Pick a target while the source is still empty — the corner the old
    // prompt mislabeled as „choose the target".
    fireEvent.change(screen.getByLabelText(de["knowledge.crud.mergeTargetLabel"]), { target: { value: "e2" } });
    const body = screen.getByRole("alertdialog");
    const para = document.getElementById(body.getAttribute("aria-describedby") ?? "");
    expect(para?.textContent).toBe(de["knowledge.crud.mergeSourceRequired"]);
    expect(para?.textContent).not.toBe(de["knowledge.crud.mergeTargetRequired"]);
    // Once the source stands too, the body names the fold.
    fireEvent.change(screen.getByLabelText(de["knowledge.crud.mergeSourceLabel"]), { target: { value: "e1" } });
    expect(para?.textContent).toContain("Dr. Maya Chen");
  });

  it("a refusal names the merge error and keeps the question", async () => {
    api.POST.mockResolvedValue({ data: undefined, response: ok(500) });
    mount(harnessMerge);
    openDialog();
    fireEvent.change(screen.getByLabelText(de["knowledge.crud.mergeTargetLabel"]), { target: { value: "e2" } });
    fireEvent.click(screen.getByRole("button", { name: de["knowledge.crud.mergeConfirm"] }));
    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText(de["knowledge.crud.mergeError"])).toBeTruthy();
    expect(screen.getByRole("alertdialog")).toBeTruthy();
  });

  it("Escape cancels unless busy", async () => {
    let resolve: (value: { data: Entity; response: Response }) => void = () => {};
    api.POST.mockImplementation(() => new Promise((r) => { resolve = r; }));
    mount(harnessMerge);
    openDialog();
    fireEvent.change(screen.getByLabelText(de["knowledge.crud.mergeTargetLabel"]), { target: { value: "e2" } });
    fireEvent.click(screen.getByRole("button", { name: de["knowledge.crud.mergeConfirm"] }));
    await waitFor(() => expect(screen.getByRole("button", { name: de["knowledge.crud.mergeBusy"] })).toBeTruthy());
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.getByRole("alertdialog")).toBeTruthy();
    resolve({ data: ARIA, response: ok() });
    await waitFor(() => expect(screen.queryByRole("alertdialog")).toBeNull());
  });
});

describe("the focus survivor contract — a write that retires its opener (review fix)", () => {
  function survivorHarness(dialog: (close: () => void) => ReactNode, survivorId: string) {
    return function Harness() {
      const [open, setOpen] = useState(false);
      return (
        <>
          <button id="opener" type="button" onClick={() => setOpen(true)}>
            opener
          </button>
          <div id={survivorId} tabIndex={-1}>
            survivor
          </div>
          {open && dialog(() => setOpen(false))}
        </>
      );
    };
  }

  it("a relation delete lands focus on the surviving list, not the body", async () => {
    api.DELETE.mockResolvedValue({ data: undefined, response: ok(204) });
    const Harness = survivorHarness(
      (close) => (
        <DeleteRelationDialog relation={R1} entities={ENTITIES} openerId="opener" onClose={close} fallbackFocusId="survivor-list" />
      ),
      "survivor-list",
    );
    mount(Harness);
    openDialog();
    fireEvent.click(screen.getByRole("button", { name: de["knowledge.crud.deleteConfirm"] }));
    await waitFor(() => {
      expect(screen.queryByRole("alertdialog")).toBeNull();
      expect(document.activeElement).toBe(document.getElementById("survivor-list"));
    });
  });

  it("an entity delete lands focus on the surviving container, not the body", async () => {
    api.DELETE.mockResolvedValue({ data: undefined, response: ok(204) });
    const Harness = survivorHarness(
      (close) => (
        <DeleteEntityDialog entity={MAYA} relationCount={2} openerId="opener" onClose={close} fallbackFocusId="survivor-dossier" />
      ),
      "survivor-dossier",
    );
    mount(Harness);
    openDialog();
    fireEvent.click(screen.getByRole("button", { name: de["knowledge.crud.deleteConfirm"] }));
    await waitFor(() => {
      expect(screen.queryByRole("alertdialog")).toBeNull();
      expect(document.activeElement).toBe(document.getElementById("survivor-dossier"));
    });
  });

  it("a CANCEL still returns focus to the opener — the survivor is the write's path only", () => {
    const Harness = survivorHarness(
      (close) => (
        <DeleteRelationDialog relation={R1} entities={ENTITIES} openerId="opener" onClose={close} fallbackFocusId="survivor-list" />
      ),
      "survivor-list",
    );
    mount(Harness);
    openDialog();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("alertdialog")).toBeNull();
    expect(document.activeElement).toBe(screen.getByText("opener"));
  });
});

describe("the face speaks du-tone in every catalog — no German fallback", () => {
  it("the English edit dialog speaks the English catalog's own copy", () => {
    applyLocale("en");
    const en = catalogs.en;
    const Harness = harness((close) => <EditEntityDialog entity={MAYA} openerId="opener" onClose={close} />);
    mount(Harness);
    openDialog();
    expect(screen.getByText(en["knowledge.crud.editEntityTitle"])).toBeTruthy();
    expect(screen.getByRole("button", { name: en["knowledge.crud.save"] })).toBeTruthy();
    expect(screen.queryByText(de["knowledge.crud.editEntityTitle"])).toBeNull();
  });

  it("the French merge dialog speaks the French catalog's own copy", () => {
    applyLocale("fr");
    const fr = catalogs.fr;
    const Harness = harness((close) => (
      <MergeDialog novelId={NOVEL_ID} entities={ENTITIES} source={MAYA} openerId="opener" onClose={close} />
    ));
    mount(Harness);
    openDialog();
    expect(screen.getByText(fr["knowledge.crud.mergeTitle"])).toBeTruthy();
    expect(screen.queryByText(de["knowledge.crud.mergeTitle"])).toBeNull();
  });

  it("the three catalogs carry the crud keys in parity, each translated", () => {
    const keys = Object.keys(catalogs.de).filter((key) => key.startsWith("knowledge.crud."));
    expect(keys.length).toBeGreaterThan(0);
    for (const key of keys) {
      for (const locale of ["en", "fr"] as const) {
        expect(catalogs[locale][key as keyof typeof catalogs.en], `${locale}/${key}`).toBeTruthy();
      }
    }
    const translated = ["knowledge.crud.save", "knowledge.crud.cancel", "knowledge.crud.mergeTitle", "knowledge.crud.nameRequired"] as const;
    for (const key of translated) {
      expect(catalogs.en[key], key).not.toBe(catalogs.de[key]);
      expect(catalogs.fr[key], key).not.toBe(catalogs.de[key]);
    }
  });

  it("the German copy keeps the du register — no Sie form sneaks in", () => {
    for (const [key, value] of Object.entries(catalogs.de)) {
      if (!key.startsWith("knowledge.crud.")) continue;
      expect(value, key).not.toMatch(/\b(Sie|Ihnen|Ihr|Ihre)\b/);
    }
    expect(catalogs.de["knowledge.crud.error"]).toContain("Deine");
    expect(catalogs.de["knowledge.crud.fromRequired"]).toContain("Wähle");
  });
});

describe("the panels' viewport law (#926)", () => {
  it("the form panel keeps to a short viewport — the overflow scrolls inside the frame", () => {
    const harnessEdit = harness((close) => <EditEntityDialog entity={MAYA} openerId="opener" onClose={close} />);
    mount(harnessEdit);
    openDialog();
    const form = screen.getByRole("dialog");
    expect(form.className).toContain("max-h-[calc(100vh-2rem)]");
    expect(form.className).toContain("overflow-y-auto");
  });

  it("the confirm panel keeps to a short viewport too", () => {
    const harnessDelete = harness((close) => (
      <DeleteEntityDialog entity={MAYA} relationCount={2} openerId="opener" onClose={close} />
    ));
    mount(harnessDelete);
    openDialog();
    const confirm = screen.getByRole("alertdialog");
    expect(confirm.className).toContain("max-h-[calc(100vh-2rem)]");
    expect(confirm.className).toContain("overflow-y-auto");
  });
});
