// @vitest-environment jsdom
/**
 * The inline goal setters (W4 Task 19, D20): the daily ring's and the
 * chapter-target pill's drafted affordances answer with one small dialog
 * on the tree dialogs' established weight — one numeric field, the empty
 * input the honest unset, the dirty rule, focus on the field and back to
 * the opener. The daily goal rides the settings PATCH (the locale always
 * carried), the chapter goal the chapter PUT.
 */
import { cleanup, configure, fireEvent, render, screen, waitFor } from "@testing-library/react";

// Full-suite load: see WorkspacePage.test.tsx.
configure({ asyncUtilTimeout: 5000 });
import { QueryClientProvider } from "@tanstack/react-query";
import { useCallback, useState, type ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@shell/lib/api/client", () => ({
  client: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn(), PUT: vi.fn(), DELETE: vi.fn() },
}));

import { client } from "@shell/lib/api/client";
import { catalogs } from "@shell/lib/generated/catalogs";
import { useLanguageChoice } from "@shell/lib/language";
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

describe("the locale the daily save carries — #933", () => {
  function saveButton(): HTMLButtonElement {
    return screen.getByRole("button", { name: de["writing.workspace.crud.save"] }) as HTMLButtonElement;
  }

  it("over an outage the save honestly waits — a dressed-up null never rides", async () => {
    // The chrome's tolerant read answers an outage with dressed-up nulls;
    // the save's read is the strict one, so an outage is no answer and the
    // gate waits — no PATCH may carry {locale: null} over the stored choice.
    api.GET.mockImplementation(async (path: string) => {
      if (path === "/api/settings") throw new TypeError("settings unreachable");
      throw new Error(`unexpected GET: ${path}`);
    });
    renderWithOpener((openerId, onClose) => (
      <GoalSetterDialog kind="daily" initial={500} openerId={openerId} onClose={onClose} />
    ));
    await screen.findByLabelText(de["writing.workspace.goal.dailyLabel"]);
    await waitFor(() => expect(api.GET.mock.calls.length).toBeGreaterThan(0));
    await waitFor(() => expect(saveButton().disabled).toBe(true));
    fireEvent.change(screen.getByLabelText(de["writing.workspace.goal.dailyLabel"]), {
      target: { value: "750" },
    });
    fireEvent.click(saveButton());
    expect(api.PATCH).not.toHaveBeenCalled();
  });

  it("a stored follow-browser null still rides — the row's own answer, not an outage's", async () => {
    api.GET.mockImplementation(async (path: string) => {
      if (path === "/api/settings") {
        return { data: { locale: null, theme: null, author_name: null, daily_goal_words: 500, email: null }, response: ok() };
      }
      throw new Error(`unexpected GET: ${path}`);
    });
    renderWithOpener((openerId, onClose) => (
      <GoalSetterDialog kind="daily" initial={500} openerId={openerId} onClose={onClose} />
    ));
    const field = await screen.findByLabelText(de["writing.workspace.goal.dailyLabel"]);
    await waitFor(() => expect(saveButton().disabled).toBe(false));
    fireEvent.change(field, { target: { value: "750" } });
    fireEvent.click(saveButton());
    await waitFor(() => expect(api.PATCH).toHaveBeenCalledTimes(1));
    expect(api.PATCH.mock.calls[0][1].body).toEqual({ locale: null, daily_goal_words: 750 });
  });

  it("the save carries the freshest cached locale, not the rendered answer", async () => {
    renderWithOpener((openerId, onClose) => (
      <GoalSetterDialog kind="daily" initial={500} openerId={openerId} onClose={onClose} />
    ));
    const field = await screen.findByLabelText(de["writing.workspace.goal.dailyLabel"]);
    await waitFor(() => expect(saveButton().disabled).toBe(false));
    // A language choice landed between the render and this click: the row's
    // cache answer moved on, the dialog still wears the older one. The save
    // reads the cache at click time and carries the freshest known truth —
    // so the choice set up here must survive this very save.
    const cached = queryClient.getQueryData<{ locale: string | null }>(["settings", "read"]);
    expect(cached?.locale).toBe("de");
    fireEvent.change(field, { target: { value: "750" } });
    queryClient.setQueryData<{ locale: string | null }>(["settings", "read"], {
      ...cached,
      locale: "en",
    });
    fireEvent.click(saveButton());
    await waitFor(() => expect(api.PATCH).toHaveBeenCalledTimes(1));
    expect(api.PATCH.mock.calls[0][1].body).toEqual({ locale: "en", daily_goal_words: 750 });
  });

  it("a language choice made before the save rides it — the seam's optimistic patch", async () => {
    // #939's writing half, through the real seam: the choice moves the
    // row's strict cache at choice time, so the dialog's click-time read
    // carries the pending choice even while the choice's own invalidation
    // refetch is still in flight (held below — it never lands).
    let held = false;
    let storedLocale: string | null = "de";
    api.GET.mockImplementation(async (path: string) => {
      if (path === "/api/settings") {
        if (held) return new Promise(() => {});
        return {
          data: { locale: storedLocale, theme: null, author_name: null, daily_goal_words: 500, email: null },
          response: ok(),
        };
      }
      throw new Error(`unexpected GET: ${path}`);
    });
    api.PATCH.mockImplementation(async (path: string, init?: { body?: Record<string, unknown> }) => {
      if (path !== "/api/settings") throw new Error(`unexpected PATCH: ${path}`);
      if (init?.body && "daily_goal_words" in init.body) return { data: {}, response: ok() };
      storedLocale = (init?.body?.locale as string | null) ?? null;
      return { data: {}, response: ok() };
    });
    function ChoiceProbe() {
      const { choose } = useLanguageChoice();
      return (
        <button type="button" onClick={() => void choose("en")}>
          choose-en
        </button>
      );
    }
    function Harness() {
      const [open, setOpen] = useState(true);
      const close = useCallback(() => setOpen(false), []);
      return (
        <QueryClientProvider client={queryClient}>
          <div>
            <button type="button" id="opener">
              opener
            </button>
            <ChoiceProbe />
            {open && <GoalSetterDialog kind="daily" initial={500} openerId="opener" onClose={close} />}
          </div>
        </QueryClientProvider>
      );
    }
    render(<Harness />);
    const field = await screen.findByLabelText(de["writing.workspace.goal.dailyLabel"]);
    await waitFor(() => expect(saveButton().disabled).toBe(false));

    fireEvent.click(screen.getByRole("button", { name: "choose-en" }));
    held = true; // the choice's refetch never lands — the window stays open
    fireEvent.change(field, { target: { value: "750" } });
    fireEvent.click(screen.getByRole("button", { name: catalogs.en["writing.workspace.crud.save"] }));

    await waitFor(() => expect(api.PATCH).toHaveBeenCalledTimes(2));
    const savePatch = api.PATCH.mock.calls.find(([, init]) => "daily_goal_words" in (init?.body ?? {}));
    expect(savePatch?.[1].body).toEqual({ locale: "en", daily_goal_words: 750 });
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
