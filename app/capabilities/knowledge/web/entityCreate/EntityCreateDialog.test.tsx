// @vitest-environment jsdom
/**
 * The entity create dialog (W9 Task 11, moved from crudDialogs): the form the
 * graph and the dossiers mount — a name and a type gate the save, a duplicate
 * name is a notice, a relation row the save will drop is counted rather than
 * lost, and the wire's coded refusals keep their code beside the answers.
 * The face speaks du-tone in all three catalogs.
 */
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, configure, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { useState, type ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@shell/lib/api/client", () => ({
  client: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn(), PUT: vi.fn(), DELETE: vi.fn() },
}));

import { client, type Entity } from "@shell/lib/api/client";
import { catalogs } from "@shell/lib/generated/catalogs";
import { applyLocale } from "@shell/lib/locale";
import { queryClient } from "@shell/lib/query";

import { EntityCreateDialog } from "./EntityCreateDialog";

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

describe("EntityCreateDialog — create by hand", () => {
  const harnessCreate = harness((close) => (
    <EntityCreateDialog novelId={NOVEL_ID} entities={ENTITIES} openerId="opener" onClose={close} />
  ));

  function openCreate() {
    mount(harnessCreate);
    openDialog();
    return screen.getByTestId("entity-create-dialog");
  }

  it("save stays disabled until name and type are set", () => {
    openCreate();
    const save = screen.getByTestId("entity-create-save") as HTMLButtonElement;
    expect(save.disabled).toBe(true);
    fireEvent.change(screen.getByTestId("entity-create-name"), {
      target: { value: "Nevada-Trümmerfeld" },
    });
    expect(save.disabled).toBe(true);
    fireEvent.change(screen.getByTestId("entity-create-type"), { target: { value: "location" } });
    expect(save.disabled).toBe(false);
  });

  it("the duplicate-name notice shows and keeps save enabled", () => {
    openCreate();
    fireEvent.change(screen.getByTestId("entity-create-name"), {
      target: { value: "  dr. maya chen  " },
    });
    fireEvent.change(screen.getByTestId("entity-create-type"), { target: { value: "character" } });
    expect(screen.getByTestId("entity-create-duplicate-note").textContent).toContain(
      de["knowledge.create.duplicateNote"].slice(0, 20),
    );
    expect((screen.getByTestId("entity-create-save") as HTMLButtonElement).disabled).toBe(false);
  });

  it("an added relation row is sent", async () => {
    api.POST.mockResolvedValue({
      data: entityRow({ id: "e9", name: "Nevada-Trümmerfeld", type: "location" }),
      response: ok(201),
    });
    openCreate();
    fireEvent.change(screen.getByTestId("entity-create-name"), {
      target: { value: "Nevada-Trümmerfeld" },
    });
    fireEvent.change(screen.getByTestId("entity-create-type"), { target: { value: "location" } });
    fireEvent.click(screen.getByTestId("entity-create-add-relation"));
    fireEvent.change(screen.getByTestId("entity-create-relation-0-entity"), {
      target: { value: "Station 7" },
    });
    fireEvent.change(screen.getByTestId("entity-create-relation-0-label"), {
      target: { value: de["knowledge.relation.located_in"] },
    });
    fireEvent.change(screen.getByTestId("entity-create-relation-0-note"), {
      target: { value: "  nördlich  " },
    });
    fireEvent.click(screen.getByTestId("entity-create-save"));
    await waitFor(() => expect(screen.queryByTestId("entity-create-dialog")).toBeNull());
    expect(api.POST).toHaveBeenCalledWith("/api/knowledge/entities", {
      body: {
        novel_id: NOVEL_ID,
        name: "Nevada-Trümmerfeld",
        type: "location",
        aliases: [],
        tags: [],
        content: "",
        relations: [
          { to_entity_id: "e3", relation_type: "located_in", note: "nördlich" },
        ],
      },
    });
  });

  it("the add control stops at twelve rows and names the bound", () => {
    openCreate();
    const add = screen.getByTestId("entity-create-add-relation") as HTMLButtonElement;
    expect(screen.queryByTestId("entity-create-relation-limit-note")).toBeNull();
    for (let index = 0; index < 12; index += 1) fireEvent.click(add);
    expect(screen.getAllByTestId(/entity-create-relation-\d+-entity$/)).toHaveLength(12);
    expect(add.disabled).toBe(true);
    const limitNote = screen.getByTestId("entity-create-relation-limit-note");
    expect(limitNote.textContent).toBe(de["knowledge.create.relationLimit"]);
    // The note is readable on its own and describes the control it explains.
    expect(limitNote.id).not.toBe("");
    expect(add.getAttribute("aria-describedby")).toBe(limitNote.id);

    // Removing a row reopens the door.
    fireEvent.click(screen.getAllByLabelText(de["knowledge.create.removeRelation"])[0]);
    expect(add.disabled).toBe(false);
    expect(screen.queryByTestId("entity-create-relation-limit-note")).toBeNull();
    expect(add.getAttribute("aria-describedby")).toBeNull();
  });

  it("a resolved target without a label is counted into the notice and marked", () => {
    openCreate();
    fireEvent.change(screen.getByTestId("entity-create-name"), {
      target: { value: "Nevada-Trümmerfeld" },
    });
    fireEvent.change(screen.getByTestId("entity-create-type"), { target: { value: "location" } });
    fireEvent.click(screen.getByTestId("entity-create-add-relation"));
    fireEvent.change(screen.getByTestId("entity-create-relation-0-entity"), {
      target: { value: "Station 7" },
    });
    const note = screen.getByTestId("entity-create-unresolved-note");
    expect(note.textContent).toBe(de["knowledge.create.unresolvedNote"]);
    const label = screen.getByTestId("entity-create-relation-0-label");
    expect(label.getAttribute("aria-invalid")).toBe("true");
    // The marked field points at the note that says why.
    expect(note.id).not.toBe("");
    expect(label.getAttribute("aria-describedby")).toBe(note.id);

    // Filling the label lifts both signals: the row will land.
    fireEvent.change(label, { target: { value: de["knowledge.relation.located_in"] } });
    expect(screen.queryByTestId("entity-create-unresolved-note")).toBeNull();
    expect(label.getAttribute("aria-describedby")).toBeNull();
    expect(label.getAttribute("aria-invalid")).toBeNull();
  });

  it("the duplicate-name notice sits directly under the name field", () => {
    openCreate();
    fireEvent.change(screen.getByTestId("entity-create-name"), {
      target: { value: "Dr. Maya Chen" },
    });
    fireEvent.change(screen.getByTestId("entity-create-type"), { target: { value: "character" } });
    const nameField = screen.getByTestId("entity-create-name").closest("div") as HTMLElement;
    const note = screen.getByTestId("entity-create-duplicate-note");
    const typeField = screen.getByTestId("entity-create-type").closest("div") as HTMLElement;
    expect(nameField.compareDocumentPosition(note) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(note.compareDocumentPosition(typeField) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("the fields hold while the save is pending", async () => {
    let resolve: (value: { data: Entity; response: Response }) => void = () => {};
    api.POST.mockImplementation(() => new Promise((r) => { resolve = r; }));
    openCreate();
    const name = screen.getByTestId("entity-create-name") as HTMLInputElement;
    const type = screen.getByTestId("entity-create-type") as HTMLSelectElement;
    fireEvent.change(name, { target: { value: "Nevada-Trümmerfeld" } });
    fireEvent.change(type, { target: { value: "location" } });
    fireEvent.click(screen.getByTestId("entity-create-save"));
    await waitFor(() => expect(screen.getByTestId("entity-create-save").textContent).toContain(de["knowledge.crud.busy"]));
    // The fieldset disables its fields; :disabled sees the ancestor's state.
    expect(name.closest("fieldset")?.disabled).toBe(true);
    expect(name.matches(":disabled")).toBe(true);
    expect(type.matches(":disabled")).toBe(true);
    expect(screen.getByTestId("entity-create-tags").matches(":disabled")).toBe(true);
    resolve({ data: entityRow({ id: "e9", name: "Nevada-Trümmerfeld", type: "location" }), response: ok(201) });
    await waitFor(() => expect(screen.queryByTestId("entity-create-dialog")).toBeNull());
  });

  it("a chip draft is committed on blur", () => {
    openCreate();
    const aliases = screen.getByTestId("entity-create-aliases") as HTMLInputElement;
    fireEvent.change(aliases, { target: { value: "  Nevada  " } });
    fireEvent.blur(aliases);
    expect(screen.getByText("Nevada")).toBeTruthy();
    expect(aliases.value).toBe("");
  });

  it("a chip draft the writer never confirmed still rides the save and is capped at 200", async () => {
    api.POST.mockResolvedValue({
      data: entityRow({ id: "e9", name: "Nevada-Trümmerfeld", type: "location" }),
      response: ok(201),
    });
    openCreate();
    fireEvent.change(screen.getByTestId("entity-create-name"), {
      target: { value: "Nevada-Trümmerfeld" },
    });
    fireEvent.change(screen.getByTestId("entity-create-type"), { target: { value: "location" } });
    const tags = screen.getByTestId("entity-create-tags") as HTMLInputElement;
    expect(tags.maxLength).toBe(200);
    // No Enter, no blur: only the save flushes this draft.
    fireEvent.change(tags, { target: { value: "  Ruine  " } });
    fireEvent.click(screen.getByTestId("entity-create-save"));
    await waitFor(() => expect(screen.queryByTestId("entity-create-dialog")).toBeNull());
    expect(api.POST.mock.calls[0][1].body.tags).toEqual(["Ruine"]);
  });

  it("a blank target with a typed label is counted, not dropped silently", () => {
    openCreate();
    fireEvent.change(screen.getByTestId("entity-create-name"), {
      target: { value: "Nevada-Trümmerfeld" },
    });
    fireEvent.change(screen.getByTestId("entity-create-type"), { target: { value: "location" } });
    fireEvent.click(screen.getByTestId("entity-create-add-relation"));
    const target = screen.getByTestId("entity-create-relation-0-entity");
    fireEvent.change(screen.getByTestId("entity-create-relation-0-label"), {
      target: { value: de["knowledge.relation.located_in"] },
    });
    expect(screen.getByTestId("entity-create-unresolved-note").textContent).toBe(
      de["knowledge.create.unresolvedNote"],
    );
    expect(target.getAttribute("aria-invalid")).toBe("true");
    // A blank target's marked field names the same note.
    expect(target.getAttribute("aria-describedby")).toBe(
      screen.getByTestId("entity-create-unresolved-note").id,
    );

    // The target the writer meant lifts both signals.
    fireEvent.change(target, { target: { value: "Station 7" } });
    expect(screen.queryByTestId("entity-create-unresolved-note")).toBeNull();
    expect(target.getAttribute("aria-invalid")).toBeNull();
    expect(target.getAttribute("aria-describedby")).toBeNull();
  });

  it("an HTTP failure without a coded detail speaks the catalog, not the raw message", async () => {
    api.POST.mockResolvedValue({ data: undefined, response: ok(500) });
    openCreate();
    fireEvent.change(screen.getByTestId("entity-create-name"), {
      target: { value: "Nevada-Trümmerfeld" },
    });
    fireEvent.change(screen.getByTestId("entity-create-type"), { target: { value: "location" } });
    fireEvent.click(screen.getByTestId("entity-create-save"));
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain(de["knowledge.create.failedUnexpected"]);
    expect(alert.textContent).not.toContain("create refused");
    expect(within(alert).queryByTestId("entity-create-refusal-code")).toBeNull();
  });

  it("a transport failure speaks the catalog's sentence, never the browser's English", async () => {
    api.POST.mockRejectedValue(new TypeError("Failed to fetch"));
    openCreate();
    fireEvent.change(screen.getByTestId("entity-create-name"), {
      target: { value: "Nevada-Trümmerfeld" },
    });
    fireEvent.change(screen.getByTestId("entity-create-type"), { target: { value: "location" } });
    fireEvent.click(screen.getByTestId("entity-create-save"));
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain(de["knowledge.create.failedTransport"]);
    expect(alert.textContent).not.toContain("Failed to fetch");
    // «transport» is a front-end pseudo-code, not a wire code: no chip.
    expect(within(alert).queryByTestId("entity-create-refusal-code")).toBeNull();
    // The fields stand; the dialog is the writer's again.
    expect((screen.getByTestId("entity-create-name") as HTMLInputElement).value).toBe(
      "Nevada-Trümmerfeld",
    );
  });

  it("a coded refusal speaks the catalog and keeps the code chip", async () => {
    api.POST.mockResolvedValue({
      data: undefined,
      error: {
        detail: {
          code: "relation-target-invalid",
          detail: "relation row 0 names an entity outside the novel",
          row: 0,
        },
      },
      response: ok(422),
    });
    openCreate();
    fireEvent.change(screen.getByTestId("entity-create-name"), {
      target: { value: "Nevada-Trümmerfeld" },
    });
    fireEvent.change(screen.getByTestId("entity-create-type"), { target: { value: "location" } });
    fireEvent.click(screen.getByTestId("entity-create-add-relation"));
    fireEvent.change(screen.getByTestId("entity-create-relation-0-entity"), {
      target: { value: "Station 7" },
    });
    fireEvent.change(screen.getByTestId("entity-create-relation-0-label"), {
      target: { value: de["knowledge.relation.located_in"] },
    });
    fireEvent.click(screen.getByTestId("entity-create-save"));
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain(de["knowledge.create.refused.relation-target-invalid"]);
    expect(alert.textContent).not.toContain("relation row 0");
    expect(within(alert).getByTestId("entity-create-refusal-code").textContent).toBe(
      "relation-target-invalid",
    );
    // The refused row is the one on screen, and its field describes the alert.
    expect(
      screen.getByTestId("entity-create-relation-0-entity").getAttribute("aria-invalid"),
    ).toBe("true");
    expect(
      screen.getByTestId("entity-create-relation-0-entity").getAttribute("aria-describedby"),
    ).toBe(alert.id);
    expect(alert.id).not.toBe("");
    // The answer is kept, the dialog stands.
    expect((screen.getByTestId("entity-create-name") as HTMLInputElement).value).toBe(
      "Nevada-Trümmerfeld",
    );
    expect(screen.getByTestId("entity-create-dialog")).toBeTruthy();
  });

  it("a duplicate refusal's sent row maps to the visible row it names", async () => {
    api.POST.mockResolvedValue({
      data: undefined,
      error: {
        detail: {
          code: "relation-duplicate",
          detail: "relation row 1 duplicates an earlier relation",
          row: 1,
        },
      },
      response: ok(422),
    });
    openCreate();
    fireEvent.change(screen.getByTestId("entity-create-name"), {
      target: { value: "Nevada-Trümmerfeld" },
    });
    fireEvent.change(screen.getByTestId("entity-create-type"), { target: { value: "location" } });
    // Row 0 stays an untouched add-row: dropped before the wire, so the sent
    // list starts at visible row 1.
    fireEvent.click(screen.getByTestId("entity-create-add-relation"));
    for (const index of [1, 2]) {
      fireEvent.click(screen.getByTestId("entity-create-add-relation"));
      fireEvent.change(screen.getByTestId(`entity-create-relation-${index}-entity`), {
        target: { value: "Station 7" },
      });
      fireEvent.change(screen.getByTestId(`entity-create-relation-${index}-label`), {
        target: { value: de["knowledge.relation.located_in"] },
      });
    }
    fireEvent.click(screen.getByTestId("entity-create-save"));
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain(de["knowledge.create.refused.relation-duplicate"]);
    expect(alert.textContent).not.toContain("relation row 1");

    // Sent row 1 is visible row 2; the blank row 0 is not the refusal's row.
    expect(
      screen.getByTestId("entity-create-relation-2-entity").closest("[data-refused]"),
    ).not.toBeNull();
    expect(
      screen.getByTestId("entity-create-relation-0-entity").closest("[data-refused]"),
    ).toBeNull();
  });

  it("two rows with one target and a localized label beside its key are both flagged", () => {
    openCreate();
    fireEvent.change(screen.getByTestId("entity-create-name"), {
      target: { value: "Nevada-Trümmerfeld" },
    });
    fireEvent.change(screen.getByTestId("entity-create-type"), { target: { value: "location" } });
    fireEvent.click(screen.getByTestId("entity-create-add-relation"));
    fireEvent.change(screen.getByTestId("entity-create-relation-0-entity"), {
      target: { value: "Station 7" },
    });
    fireEvent.change(screen.getByTestId("entity-create-relation-0-label"), {
      target: { value: de["knowledge.relation.located_in"] },
    });
    fireEvent.click(screen.getByTestId("entity-create-add-relation"));
    fireEvent.change(screen.getByTestId("entity-create-relation-1-entity"), {
      target: { value: "Station 7" },
    });
    fireEvent.change(screen.getByTestId("entity-create-relation-1-label"), {
      target: { value: "located_in" },
    });

    expect(screen.getByTestId("entity-create-relation-duplicate-note").textContent).toBe(
      de["knowledge.create.relationDuplicate"],
    );
    const duplicateNoteId = screen.getByTestId("entity-create-relation-duplicate-note").id;
    expect(duplicateNoteId).not.toBe("");
    for (const index of [0, 1]) {
      expect(
        screen.getByTestId(`entity-create-relation-${index}-entity`).getAttribute("aria-invalid"),
      ).toBe("true");
      expect(
        screen.getByTestId(`entity-create-relation-${index}-entity`).getAttribute("aria-describedby"),
      ).toBe(duplicateNoteId);
      expect(
        screen.getByTestId(`entity-create-relation-${index}-label`).getAttribute("aria-invalid"),
      ).toBe("true");
      expect(
        screen.getByTestId(`entity-create-relation-${index}-label`).getAttribute("aria-describedby"),
      ).toBe(duplicateNoteId);
    }
    // The duplicate is a flag, not a block: the save stays possible.
    expect((screen.getByTestId("entity-create-save") as HTMLButtonElement).disabled).toBe(false);

    // A genuinely different label lifts both flags.
    fireEvent.change(screen.getByTestId("entity-create-relation-1-label"), {
      target: { value: de["knowledge.relation.enemy_of"] },
    });
    expect(screen.queryByTestId("entity-create-relation-duplicate-note")).toBeNull();
    for (const index of [0, 1]) {
      expect(
        screen.getByTestId(`entity-create-relation-${index}-entity`).getAttribute("aria-invalid"),
      ).toBeNull();
    }
  });
});
