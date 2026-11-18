// @vitest-environment jsdom
/**
 * The inline goal setters (W4 Task 19, D20): the daily ring's and the
 * chapter-target pill's drafted affordances answer with one small dialog
 * on the tree dialogs' established weight — one numeric field, the empty
 * input the honest unset, the dirty rule, focus on the field and back to
 * the opener. The daily goal rides the settings PATCH (the locale always
 * carried), the chapter goal the chapter PUT.
 */
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClientProvider } from "@tanstack/react-query";
import { useCallback, useState, type ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@shell/lib/api/client", () => ({
  client: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn(), PUT: vi.fn(), DELETE: vi.fn() },
}));

import { client } from "@shell/lib/api/client";
import { catalogs } from "@shell/lib/generated/catalogs";
import { applyLocale } from "@shell/lib/locale";
import { queryClient } from "@shell/lib/query";

import { GoalSetterDialog } from "./GoalSetter";

const de = catalogs.de;
const api = client as unknown as Record<"GET" | "PATCH" | "PUT", ReturnType<typeof vi.fn>>;

function ok(): Response {
  return new Response(null, { status: 200 });
}

function valueOf(el: HTMLElement): string {
  return (el as HTMLInputElement).value;
}

function renderWithOpener(makeUi: (openerId: string, onClose: () => void) => ReactNode) {
  function Harness() {
    const [open, setOpen] = useState(true);
    const close = useCallback(() => setOpen(false), []);
    return (
      <QueryClientProvider client={queryClient}>
        <div>
          <button type="button" id="opener">
            opener
          </button>
          {open && makeUi("opener", close)}
        </div>
      </QueryClientProvider>
    );
  }
  render(<Harness />);
}

beforeEach(() => {
  applyLocale("de");
  api.GET.mockImplementation(async (path: string) => {
    if (path === "/api/settings") {
      return { data: { locale: "de", theme: null, author_name: null, daily_goal_words: 500, email: null }, response: ok() };
    }
    throw new Error(`unexpected GET: ${path}`);
  });
  api.PATCH.mockResolvedValue({ data: {}, response: ok() });
  api.PUT.mockImplementation(async (_path: string, init?: { body?: Record<string, unknown> }) => ({
    data: { id: "c1", target_words: init?.body?.target_words ?? null },
    response: ok(),
  }));
});

afterEach(() => {
  cleanup();
  queryClient.clear();
  vi.clearAllMocks();
});

describe("the daily goal setter", () => {
  it("opens on the stored goal and saves through the settings PATCH", async () => {
    renderWithOpener((openerId, onClose) => (
      <GoalSetterDialog kind="daily" initial={500} openerId={openerId} onClose={onClose} />
    ));
    const field = await screen.findByLabelText(de["writing.workspace.goal.dailyLabel"]);
    await waitFor(() => expect((screen.getByRole("button", { name: de["writing.workspace.crud.save"] }) as HTMLButtonElement).disabled).toBe(false));
    expect(valueOf(field)).toBe("500");
    expect(document.activeElement).toBe(field);
    expect(screen.getByRole("heading", { name: de["writing.workspace.goal.dailyTitle"] })).toBeTruthy();

    fireEvent.change(field, { target: { value: "750" } });
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.crud.save"] }));
    await waitFor(() => expect(api.PATCH).toHaveBeenCalledTimes(1));
    expect(api.PATCH.mock.calls[0][0]).toBe("/api/settings");
    expect(api.PATCH.mock.calls[0][1].body).toEqual({ locale: "de", daily_goal_words: 750 });
    await waitFor(() => expect(document.activeElement).toBe(screen.getByRole("button", { name: "opener" })));
  });

  it("the empty input clears the goal — a carried null, never a zero", async () => {
    renderWithOpener((openerId, onClose) => (
      <GoalSetterDialog kind="daily" initial={500} openerId={openerId} onClose={onClose} />
    ));
    const field = await screen.findByLabelText(de["writing.workspace.goal.dailyLabel"]);
    await waitFor(() => expect((screen.getByRole("button", { name: de["writing.workspace.crud.save"] }) as HTMLButtonElement).disabled).toBe(false));
    fireEvent.change(field, { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.crud.save"] }));
    await waitFor(() => expect(api.PATCH).toHaveBeenCalledTimes(1));
    expect(api.PATCH.mock.calls[0][1].body).toEqual({ locale: "de", daily_goal_words: null });
  });

  it("an unset goal opens empty and stays unset on a pristine save", async () => {
    renderWithOpener((openerId, onClose) => (
      <GoalSetterDialog kind="daily" initial={null} openerId={openerId} onClose={onClose} />
    ));
    const field = await screen.findByLabelText(de["writing.workspace.goal.dailyLabel"]);
    await waitFor(() => expect((screen.getByRole("button", { name: de["writing.workspace.crud.save"] }) as HTMLButtonElement).disabled).toBe(false));
    expect(valueOf(field)).toBe("");
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.crud.save"] }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(api.PATCH).not.toHaveBeenCalled();
  });
});

describe("the chapter goal setter", () => {
  it("saves through the chapter PUT — the goal alone, the title untouched", async () => {
    renderWithOpener((openerId, onClose) => (
      <GoalSetterDialog
        kind="chapter"
        initial={null}
        novelId="n1"
        chapterId="c1"
        chapterName="Kapitel 1 — Der erste Schnee"
        openerId={openerId}
        onClose={onClose}
      />
    ));
    const field = await screen.findByLabelText(de["writing.workspace.goal.chapterLabel"]);
    expect(screen.getByText("Kapitel 1 — Der erste Schnee")).toBeTruthy();
    fireEvent.change(field, { target: { value: "1000" } });
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.crud.save"] }));
    await waitFor(() => expect(api.PUT).toHaveBeenCalledTimes(1));
    expect(api.PUT.mock.calls[0][0]).toBe("/api/writing/chapters/{chapter_id}");
    expect(api.PUT.mock.calls[0][1].body).toEqual({ target_words: 1000 });
  });
});

describe("the shared discipline", () => {
  it("a goal outside the bounds is refused before the wire", async () => {
    renderWithOpener((openerId, onClose) => (
      <GoalSetterDialog kind="daily" initial={500} openerId={openerId} onClose={onClose} />
    ));
    const field = await screen.findByLabelText(de["writing.workspace.goal.dailyLabel"]);
    await waitFor(() => expect((screen.getByRole("button", { name: de["writing.workspace.crud.save"] }) as HTMLButtonElement).disabled).toBe(false));
    fireEvent.change(field, { target: { value: "0" } });
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.crud.save"] }));
    expect(await screen.findByText(de["writing.workspace.goal.invalid"])).toBeTruthy();
    expect(api.PATCH).not.toHaveBeenCalled();
  });

  it("dirty holds Escape and the scrim; pristine Escape closes", async () => {
    renderWithOpener((openerId, onClose) => (
      <GoalSetterDialog kind="daily" initial={500} openerId={openerId} onClose={onClose} />
    ));
    const field = await screen.findByLabelText(de["writing.workspace.goal.dailyLabel"]);
    await waitFor(() => expect((screen.getByRole("button", { name: de["writing.workspace.crud.save"] }) as HTMLButtonElement).disabled).toBe(false));
    fireEvent.change(field, { target: { value: "600" } });
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog")).not.toBeNull();
    fireEvent.change(field, { target: { value: "500" } });
    fireEvent.keyDown(document, { key: "Escape" });
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  it("a refused save keeps the answer and offers the retry", async () => {
    api.PATCH.mockResolvedValueOnce({ data: undefined, response: new Response(null, { status: 500 }) });
    renderWithOpener((openerId, onClose) => (
      <GoalSetterDialog kind="daily" initial={500} openerId={openerId} onClose={onClose} />
    ));
    const field = await screen.findByLabelText(de["writing.workspace.goal.dailyLabel"]);
    await waitFor(() => expect((screen.getByRole("button", { name: de["writing.workspace.crud.save"] }) as HTMLButtonElement).disabled).toBe(false));
    fireEvent.change(field, { target: { value: "600" } });
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.crud.save"] }));
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(valueOf(field)).toBe("600");
    fireEvent.click(screen.getByRole("button", { name: de["writing.shelf.error.retry"] }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(api.PATCH).toHaveBeenCalledTimes(2);
  });
});
