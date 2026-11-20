// @vitest-environment jsdom
/**
 * The timeline CRUD dialogs (W6 Task 3) — the planning capability's editing
 * layer on the modal discipline the house dialogs speak (`@shell/ui/
 * modalKeys`): the trap and the wrap shared, the Escape answer each
 * dialog's own (forms hold while dirty or busy, the destructive confirm
 * cancels unless busy), focus lands on the first answer and returns to
 * the opener on every close. The mutations fire the REAL client calls
 * (the client mocked at its module boundary, the house pattern); the
 * create POSTs the whole writer-facing row, the edit PUTs ONLY the
 * dirtied fields — the client's mirror of the server's `model_fields_set`
 * contract, a carried null clearing the chapter link or the position —
 * and the delete confirms the named loss before it happens. A refusal
 * keeps the answers and names the loss-free error with a retry. The face
 * speaks du-tone in all three catalogs.
 */
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, configure, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { useState, type ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@shell/lib/api/client", () => ({
  client: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn(), PUT: vi.fn(), DELETE: vi.fn() },
}));

import { client, type Chapter, type TimelineEvent } from "@shell/lib/api/client";
import { catalogs } from "@shell/lib/generated/catalogs";
import { applyLocale } from "@shell/lib/locale";
import { queryClient } from "@shell/lib/query";

import { CreateEventDialog, DeleteEventDialog, EditEventDialog } from "./timelineDialogs";

const de = catalogs.de;
const api = client as unknown as Record<"GET" | "POST" | "PUT" | "DELETE", ReturnType<typeof vi.fn>>;

configure({ asyncUtilTimeout: 5000 });

const NOVEL_ID = "11111111-1111-1111-1111-111111111111";
const CHAPTER_ID = "22222222-2222-2222-2222-222222222222";

function ok(status = 200): Response {
  return new Response(null, { status });
}

function chapterRow(overrides: Partial<Chapter> & { id: string }): Chapter {
  return {
    novel_id: NOVEL_ID,
    title: "Nevada-Rückblende",
    position: 2,
    word_count: 0,
    created_at: "2026-11-18T10:00:00Z",
    updated_at: "2026-11-18T10:00:00Z",
    scene_count: 0,
    target_words: null,
    ...overrides,
  };
}

const CHAPTERS = [
  chapterRow({ id: CHAPTER_ID, title: "Ankunft", position: 0 }),
  chapterRow({ id: "33333333-3333-3333-3333-333333333333", title: "Notfall-Code", position: 1 }),
];

function eventRow(overrides: Partial<TimelineEvent> & { id: string }): TimelineEvent {
  return {
    novel_id: NOVEL_ID,
    chapter_id: CHAPTER_ID,
    title: "Unglück auf Station 7",
    description: "Verdampfung des Hauptlabors.",
    position: 2,
    date_label: "14. Nov 2284",
    character_names: ["Maya Chen", "Lin Chen"],
    created_at: "2026-11-18T10:00:00Z",
    updated_at: "2026-11-18T10:00:00Z",
    ...overrides,
  };
}

const EVENT = eventRow({ id: "44444444-4444-4444-4444-444444444444" });

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

/** The labelled input the dialogs render, found by its label text. */
function field(label: string): HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement {
  const found = screen.getByLabelText(label);
  return found as HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement;
}

beforeEach(() => {
  applyLocale("de");
  api.POST.mockResolvedValue({ data: EVENT, response: ok(201) });
  api.PUT.mockResolvedValue({ data: EVENT, response: ok() });
  api.DELETE.mockResolvedValue({ data: undefined, response: ok(204) });
});

afterEach(() => {
  cleanup();
  queryClient.clear();
  vi.clearAllMocks();
  applyLocale(null);
});

describe("CreateEventDialog", () => {
  it("focuses the title and returns to the opener on close", () => {
    mount(harness((onClose) => (
      <CreateEventDialog novelId={NOVEL_ID} chapters={CHAPTERS} openerId="opener" onClose={onClose} />
    )));
    openDialog();
    const title = field(de["planning.crud.titleLabel"]);
    expect(document.activeElement).toBe(title);
    fireEvent.click(screen.getByRole("button", { name: de["planning.crud.cancel"] }));
    const opener = document.getElementById("opener");
    expect(opener).not.toBeNull();
    expect(document.activeElement).toBe(opener);
  });

  it("refuses a blank title with its own words — the server never sees it", async () => {
    mount(harness((onClose) => (
      <CreateEventDialog novelId={NOVEL_ID} chapters={CHAPTERS} openerId="opener" onClose={onClose} />
    )));
    openDialog();
    fireEvent.click(screen.getByRole("button", { name: de["planning.crud.save"] }));
    const guard = await screen.findByRole("alert");
    expect(within(guard).getByText(de["planning.crud.titleRequired"])).toBeTruthy();
    expect(api.POST).not.toHaveBeenCalled();
  });

  it("POSTs the whole writer-facing row — chips as names, empty position as null", async () => {
    mount(harness((onClose) => (
      <CreateEventDialog novelId={NOVEL_ID} chapters={CHAPTERS} openerId="opener" onClose={onClose} />
    )));
    openDialog();
    fireEvent.change(field(de["planning.crud.titleLabel"]), { target: { value: "  Empfang des Notfall-Signals " } });
    fireEvent.change(field(de["planning.crud.dateLabel"]), { target: { value: "Tag 03 (04:12 Uhr)" } });
    fireEvent.change(field(de["planning.crud.descriptionLabel"]), {
      target: { value: "Das Signal moduliert auf 14.2 Hz." },
    });
    // The names box commits a chip on Enter, the draft's comma-separated way.
    const names = field(de["planning.crud.namesLabel"]) as HTMLInputElement;
    fireEvent.change(names, { target: { value: "Maya Chen" } });
    fireEvent.keyDown(names, { key: "Enter" });
    fireEvent.change(names, { target: { value: "ARIA" } });
    fireEvent.keyDown(names, { key: "," });
    fireEvent.change(field(de["planning.crud.positionLabel"]), { target: { value: "7" } });
    fireEvent.change(field(de["planning.crud.chapterLabel"]), { target: { value: CHAPTER_ID } });

    fireEvent.click(screen.getByRole("button", { name: de["planning.crud.save"] }));
    await waitFor(() => expect(api.POST).toHaveBeenCalled());
    expect(api.POST).toHaveBeenCalledWith("/api/planning/novels/{novel_id}/timeline-events", {
      params: { path: { novel_id: NOVEL_ID } },
      body: {
        title: "Empfang des Notfall-Signals",
        description: "Das Signal moduliert auf 14.2 Hz.",
        date_label: "Tag 03 (04:12 Uhr)",
        character_names: ["Maya Chen", "ARIA"],
        chapter_id: CHAPTER_ID,
        position: 7,
      },
    });
  });

  it("a fractional position is refused with its own words — the wire never sees it", async () => {
    mount(harness((onClose) => (
      <CreateEventDialog novelId={NOVEL_ID} chapters={CHAPTERS} openerId="opener" onClose={onClose} />
    )));
    openDialog();
    fireEvent.change(field(de["planning.crud.titleLabel"]), { target: { value: "Verlegung Transmitter L2" } });
    fireEvent.change(field(de["planning.crud.positionLabel"]), { target: { value: "2.5" } });
    fireEvent.click(screen.getByRole("button", { name: de["planning.crud.save"] }));
    const guard = await screen.findByRole("alert");
    expect(within(guard).getByText(de["planning.crud.positionInteger"])).toBeTruthy();
    expect(api.POST).not.toHaveBeenCalled();

    // A whole number passes the guard and crosses the wire.
    fireEvent.change(field(de["planning.crud.positionLabel"]), { target: { value: "3" } });
    fireEvent.click(screen.getByRole("button", { name: de["planning.crud.save"] }));
    await waitFor(() => expect(api.POST).toHaveBeenCalled());
    expect(api.POST.mock.calls[0][1].body).toMatchObject({ position: 3 });
  });

  it("an empty position and chapter POST as the honest nulls", async () => {
    mount(harness((onClose) => (
      <CreateEventDialog novelId={NOVEL_ID} chapters={CHAPTERS} openerId="opener" onClose={onClose} />
    )));
    openDialog();
    fireEvent.change(field(de["planning.crud.titleLabel"]), { target: { value: "Öffnung von Sektor D-4" } });
    fireEvent.click(screen.getByRole("button", { name: de["planning.crud.save"] }));
    await waitFor(() => expect(api.POST).toHaveBeenCalled());
    expect(api.POST.mock.calls[0][1].body).toMatchObject({
      chapter_id: null,
      position: null,
      character_names: [],
    });
  });

  it("holds every close path while busy, then closes on the landing", async () => {
    let resolvePost!: (answer: { data: TimelineEvent; response: Response }) => void;
    api.POST.mockImplementation(
      () =>
        new Promise<{ data: TimelineEvent; response: Response }>((resolve) => {
          resolvePost = resolve;
        }),
    );
    mount(harness((onClose) => (
      <CreateEventDialog novelId={NOVEL_ID} chapters={CHAPTERS} openerId="opener" onClose={onClose} />
    )));
    openDialog();
    fireEvent.change(field(de["planning.crud.titleLabel"]), { target: { value: "Neues Ereignis" } });
    fireEvent.click(screen.getByRole("button", { name: de["planning.crud.save"] }));
    const busy = await screen.findByRole("button", { name: de["planning.crud.busy"] });
    expect((busy as HTMLButtonElement).disabled).toBe(true);
    expect(
      (screen.getByRole("button", { name: de["planning.crud.cancel"] }) as HTMLButtonElement).disabled,
    ).toBe(true);
    // Escape holds too — the write is engaged.
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.getByRole("dialog")).toBeTruthy();

    resolvePost({ data: EVENT, response: ok(201) });
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  it("a refusal keeps the answers, names the error, and the retry re-fires the ask", async () => {
    api.POST.mockResolvedValueOnce({
      data: undefined,
      error: { detail: "unknown chapter id: x" },
      response: ok(422),
    });
    mount(harness((onClose) => (
      <CreateEventDialog novelId={NOVEL_ID} chapters={CHAPTERS} openerId="opener" onClose={onClose} />
    )));
    openDialog();
    fireEvent.change(field(de["planning.crud.titleLabel"]), { target: { value: "Neues Ereignis" } });
    fireEvent.click(screen.getByRole("button", { name: de["planning.crud.save"] }));
    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText(de["planning.crud.error"])).toBeTruthy();
    // The answers stay on the fields.
    expect((field(de["planning.crud.titleLabel"]) as HTMLInputElement).value).toBe("Neues Ereignis");

    fireEvent.click(screen.getByRole("button", { name: de["planning.crud.retry"] }));
    await waitFor(() => expect(api.POST).toHaveBeenCalledTimes(2));
  });

  it("pristine closes on Escape; a typed change holds the silent paths", () => {
    mount(harness((onClose) => (
      <CreateEventDialog novelId={NOVEL_ID} chapters={CHAPTERS} openerId="opener" onClose={onClose} />
    )));
    openDialog();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();

    // The first harness leaves before the second stands — one opener at a
    // time, or the text queries cannot tell them apart.
    cleanup();
    mount(harness((onClose) => (
      <CreateEventDialog novelId={NOVEL_ID} chapters={CHAPTERS} openerId="opener-2" onClose={onClose} />
    )));
    fireEvent.click(screen.getByText("opener"));
    fireEvent.change(field(de["planning.crud.titleLabel"]), { target: { value: "x" } });
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.getByRole("dialog")).toBeTruthy();
  });
});

describe("EditEventDialog", () => {
  it("prefills every field from the row and PUTs nothing until dirtied", async () => {
    mount(harness((onClose) => (
      <EditEventDialog
        event={EVENT}
        chapters={CHAPTERS}
        openerId="opener"
        onClose={onClose}
        onRemove={() => {}}
      />
    )));
    openDialog();
    expect((field(de["planning.crud.titleLabel"]) as HTMLInputElement).value).toBe("Unglück auf Station 7");
    expect((field(de["planning.crud.dateLabel"]) as HTMLInputElement).value).toBe("14. Nov 2284");
    expect((field(de["planning.crud.chapterLabel"]) as HTMLSelectElement).value).toBe(CHAPTER_ID);
    // The chips render as the row's names, each removable.
    expect(screen.getByText("Maya Chen")).toBeTruthy();
    expect(screen.getByText("Lin Chen")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: de["planning.crud.saveChanges"] }));
    await waitFor(() => expect(api.PUT).toHaveBeenCalled());
    // Pristine in every field: the PUT carries an empty change set — the
    // server's exclude_unset leaves the row exactly as it stands.
    expect(api.PUT.mock.calls[0][1].body).toEqual({});
  });

  it("carries ONLY the dirtied fields — a cleared chapter and position ride as null", async () => {
    mount(harness((onClose) => (
      <EditEventDialog
        event={EVENT}
        chapters={CHAPTERS}
        openerId="opener"
        onClose={onClose}
        onRemove={() => {}}
      />
    )));
    openDialog();
    fireEvent.change(field(de["planning.crud.titleLabel"]), { target: { value: "Unglück auf Station 7 (überarbeitet)" } });
    // Clearing the chapter: the placeholder option is the empty value.
    fireEvent.change(field(de["planning.crud.chapterLabel"]), { target: { value: "" } });
    // Clearing the position: the empty input is the carried null.
    fireEvent.change(field(de["planning.crud.positionLabel"]), { target: { value: "" } });

    fireEvent.click(screen.getByRole("button", { name: de["planning.crud.saveChanges"] }));
    await waitFor(() => expect(api.PUT).toHaveBeenCalled());
    expect(api.PUT).toHaveBeenCalledWith(
      "/api/planning/novels/{novel_id}/timeline-events/{event_id}",
      {
        params: { path: { novel_id: NOVEL_ID, event_id: EVENT.id } },
        body: {
          title: "Unglück auf Station 7 (überarbeitet)",
          chapter_id: null,
          position: null,
        },
      },
    );
  });

  it("removing a name chip dirties the names alone", async () => {
    mount(harness((onClose) => (
      <EditEventDialog
        event={EVENT}
        chapters={CHAPTERS}
        openerId="opener"
        onClose={onClose}
        onRemove={() => {}}
      />
    )));
    openDialog();
    fireEvent.click(screen.getByRole("button", { name: de["planning.crud.removeName"].replace("{name}", "Lin Chen") }));
    fireEvent.click(screen.getByRole("button", { name: de["planning.crud.saveChanges"] }));
    await waitFor(() => expect(api.PUT).toHaveBeenCalled());
    expect(api.PUT.mock.calls[0][1].body).toEqual({ character_names: ["Maya Chen"] });
  });

  it("the destructive remove hands off to the page, disabled while busy", async () => {
    let resolvePut!: (answer: { data: TimelineEvent; response: Response }) => void;
    api.PUT.mockImplementation(
      () =>
        new Promise<{ data: TimelineEvent; response: Response }>((resolve) => {
          resolvePut = resolve;
        }),
    );
    const onRemove = vi.fn();
    mount(harness((onClose) => (
      <EditEventDialog event={EVENT} chapters={CHAPTERS} openerId="opener" onClose={onClose} onRemove={onRemove} />
    )));
    openDialog();
    const remove = screen.getByRole("button", { name: de["planning.crud.remove"] });
    expect(remove).toBeTruthy();
    fireEvent.change(field(de["planning.crud.titleLabel"]), { target: { value: "Geändert" } });
    fireEvent.click(screen.getByRole("button", { name: de["planning.crud.saveChanges"] }));
    await waitFor(() => expect(screen.getByRole("button", { name: de["planning.crud.busy"] })).toBeTruthy());
    expect((remove as HTMLButtonElement).disabled).toBe(true);

    resolvePut({ data: EVENT, response: ok() });
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    // Idle again on a later mount: the remove hands off.
    cleanup();
    mount(harness((onClose) => (
      <EditEventDialog event={EVENT} chapters={CHAPTERS} openerId="opener" onClose={onClose} onRemove={onRemove} />
    )));
    fireEvent.click(screen.getByText("opener"));
    fireEvent.click(screen.getByRole("button", { name: de["planning.crud.remove"] }));
    expect(onRemove).toHaveBeenCalledWith(EVENT);
  });
});

describe("DeleteEventDialog", () => {
  it("confirms the named loss; focus lands on the safe answer, the scrim does not dismiss", async () => {
    mount(harness((onClose) => (
      <DeleteEventDialog
        event={EVENT}
        novelId={NOVEL_ID}
        openerId="opener"
        onCancel={onClose}
        onDeleted={onClose}
      />
    )));
    openDialog();
    const dialog = screen.getByRole("alertdialog");
    expect(within(dialog).getByText(de["planning.crud.deleteTitle"])).toBeTruthy();
    expect(within(dialog).getByText(de["planning.crud.deleteBody"].replace("{title}", EVENT.title))).toBeTruthy();
    expect(document.activeElement).toBe(screen.getByRole("button", { name: de["planning.crud.cancel"] }));

    fireEvent.mouseDown(screen.getByRole("alertdialog").parentElement as HTMLElement);
    expect(screen.getByRole("alertdialog")).toBeTruthy();

    fireEvent.click(within(dialog).getByRole("button", { name: de["planning.crud.deleteConfirm"] }));
    await waitFor(() => expect(api.DELETE).toHaveBeenCalledWith(
      "/api/planning/novels/{novel_id}/timeline-events/{event_id}",
      { params: { path: { novel_id: NOVEL_ID, event_id: EVENT.id } } },
    ));
    await waitFor(() => expect(screen.queryByRole("alertdialog")).toBeNull());
  });

  it("a refusal keeps the confirm standing and names the error with a retry", async () => {
    api.DELETE.mockResolvedValueOnce({ data: undefined, response: ok(409) });
    mount(harness((onClose) => (
      <DeleteEventDialog
        event={EVENT}
        novelId={NOVEL_ID}
        openerId="opener"
        onCancel={onClose}
        onDeleted={onClose}
      />
    )));
    openDialog();
    fireEvent.click(screen.getByRole("button", { name: de["planning.crud.deleteConfirm"] }));
    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText(de["planning.crud.deleteError"])).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: de["planning.crud.retry"] }));
    await waitFor(() => expect(api.DELETE).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(screen.queryByRole("alertdialog")).toBeNull());
  });
});
