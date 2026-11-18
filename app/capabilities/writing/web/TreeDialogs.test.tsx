// @vitest-environment jsdom
/**
 * The tree's dialogs (W4 Task 13): the rename/metadata edit and the delete
 * confirm, on the modal discipline the workspace already speaks
 * (NewBookDialog's form weight, LeaveGuardDialog's destructive calm). The
 * edit dialog carries the chapter's title alone or the scene's three
 * fields — the labels present-and-nullable (an empty input clears to null,
 * the honest unset) — and the dirty-state rule: typed changes hold the
 * scrim/Escape/cross, only Abbrechen and Speichern answer. The delete
 * confirm names the loss before it happens: the chapter's cascade with its
 * scene count, the scene's words with the chapter remaining (D16). Focus
 * returns to the opener on every close.
 */
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClientProvider } from "@tanstack/react-query";
import { useCallback, useState, type ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@shell/lib/api/client", () => ({
  client: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn(), PUT: vi.fn(), DELETE: vi.fn() },
}));

import { client, type Chapter, type Scene } from "@shell/lib/api/client";
import { catalogs } from "@shell/lib/generated/catalogs";
import { applyLocale } from "@shell/lib/locale";
import { queryClient } from "@shell/lib/query";

import { DeleteTreeDialog, TreeEditDialog } from "./TreeDialogs";
import type { SceneEntry } from "./workspace";

const de = catalogs.de;
const api = client as unknown as Record<"PUT" | "DELETE", ReturnType<typeof vi.fn>>;

const CHAPTER: Chapter = {
  id: "c1",
  novel_id: "n1",
  title: "Ghost in the Machine",
  position: 0,
  scene_count: 2,
  target_words: null,
  word_count: 765,
  created_at: "2026-11-01T10:00:00Z",
  updated_at: "2026-11-12T10:00:00Z",
};

const SCENE: Scene = {
  id: "s1",
  chapter_id: "c1",
  title: "Das Signal im Permafrost",
  body: "Prosa.",
  setting: "Forschungsstation 7",
  story_time: "27. Oktober 2094, 03:14 UTC",
  position: 2,
  word_count: 1,
  created_at: "2026-11-01T10:00:00Z",
  updated_at: "2026-11-14T09:30:00Z",
};

const ENTRY: SceneEntry = { scene: SCENE, chapter: CHAPTER };

function ok(): Response {
  return new Response(null, { status: 200 });
}

/** The opener the dialogs return focus to — a real button in the harness.
 *  The harness owns the open state the page owns: a close unmounts the
 *  dialog, so the focus return rides the unmount as it does in the page. */
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
  return render(<Harness />);
}

beforeEach(() => {
  applyLocale("de");
  api.PUT.mockResolvedValue({ data: SCENE, response: ok() });
  api.DELETE.mockResolvedValue({ data: undefined, response: new Response(null, { status: 204 }) });
});

afterEach(() => {
  cleanup();
  queryClient.clear();
  vi.clearAllMocks();
});

describe("the chapter rename dialog", () => {
  function renderDialog(overrides: { onClose?: () => void } = {}) {
    const onClose = overrides.onClose ?? vi.fn();
    renderWithOpener((openerId, close) => (
      <TreeEditDialog
        novelId="n1"
        target={{ kind: "chapter", chapter: CHAPTER }}
        openerId={openerId}
        onClose={() => {
          onClose();
          close();
        }}
      />
    ));
    return onClose;
  }

  it("carries the stored title — not the placeholder — and focuses the field", () => {
    renderDialog();
    expect(screen.getByRole("dialog").getAttribute("aria-modal")).toBe("true");
    expect(
      screen.getByRole("heading", { name: de["writing.workspace.crud.editChapterTitle"] }),
    ).toBeTruthy();
    const input = screen.getByRole("textbox", { name: de["writing.workspace.crud.titleLabel"] });
    expect((input as HTMLInputElement).value).toBe("Ghost in the Machine");
    expect(document.activeElement).toBe(input);
    // A chapter carries the title alone — no scene labels invented.
    expect(screen.queryByRole("textbox", { name: de["writing.workspace.crud.settingLabel"] })).toBeNull();
  });

  it("saves the trimmed title and closes", async () => {
    const onClose = renderDialog();
    const input = screen.getByRole("textbox", { name: de["writing.workspace.crud.titleLabel"] });
    fireEvent.change(input, { target: { value: "  Neuer Name  " } });
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.crud.save"] }));
    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(api.PUT).toHaveBeenCalledWith("/api/writing/chapters/{chapter_id}", {
      params: { path: { chapter_id: "c1" } },
      body: { title: "Neuer Name" },
    });
  });

  it("an empty title is the honest unnamed — the placeholder a rendering", async () => {
    renderDialog();
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "   " } });
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.crud.save"] }));
    await waitFor(() => expect(api.PUT).toHaveBeenCalled());
    expect(api.PUT.mock.calls[0][1].body).toEqual({ title: "" });
  });

  it("a refusal keeps the dialog and the answer, names the loss-free error, retries", async () => {
    api.PUT.mockResolvedValue({ data: undefined, response: new Response(null, { status: 503 }) });
    const onClose = renderDialog();
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.crud.save"] }));
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(screen.getByText(de["writing.workspace.crud.error"])).toBeTruthy();
    expect(onClose).not.toHaveBeenCalled();
    // The retry re-runs the very ask.
    api.PUT.mockResolvedValue({ data: CHAPTER, response: ok() });
    fireEvent.click(screen.getByRole("button", { name: de["writing.shelf.error.retry"] }));
    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(api.PUT).toHaveBeenCalledTimes(2);
  });

  it("Escape, Abbrechen and the cross close and return focus to the opener", () => {
    const onClose = renderDialog();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(document.activeElement?.id).toBe("opener");
    cleanup();
    renderDialog();
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.crud.cancel"] }));
    expect(onClose).toHaveBeenCalledTimes(1);
    cleanup();
    renderDialog();
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.crud.close"] }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("a busy dialog holds against Escape and the cancel", async () => {
    let release: (() => void) | undefined;
    api.PUT.mockImplementation(
      () =>
        new Promise((resolve) => {
          release = () => resolve({ data: CHAPTER, response: ok() });
        }),
    );
    const onClose = renderDialog();
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.crud.save"] }));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: de["writing.workspace.crud.cancel"] }).hasAttribute("disabled")).toBe(true),
    );
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).not.toHaveBeenCalled();
    release?.();
    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });
});

describe("the scene edit dialog — title, setting, story_time", () => {
  function renderDialog(scene: Scene = SCENE) {
    const onClose = vi.fn();
    renderWithOpener((openerId, close) => (
      <TreeEditDialog
        novelId="n1"
        target={{ kind: "scene", entry: { scene, chapter: CHAPTER } }}
        openerId={openerId}
        onClose={() => {
          onClose();
          close();
        }}
      />
    ));
    return onClose;
  }

  it("carries all three fields with their stored values — unset labels read empty", () => {
    renderDialog({ ...SCENE, setting: null, story_time: null });
    expect(
      screen.getByRole("heading", { name: de["writing.workspace.crud.editSceneTitle"] }),
    ).toBeTruthy();
    expect((screen.getByRole("textbox", { name: de["writing.workspace.crud.titleLabel"] }) as HTMLInputElement).value).toBe(
      "Das Signal im Permafrost",
    );
    expect((screen.getByRole("textbox", { name: de["writing.workspace.crud.settingLabel"] }) as HTMLInputElement).value).toBe("");
    expect((screen.getByRole("textbox", { name: de["writing.workspace.crud.storyTimeLabel"] }) as HTMLInputElement).value).toBe("");
    expect(screen.getByText(de["writing.workspace.crud.labelsHint"])).toBeTruthy();
  });

  it("saves the three fields — an empty label clears to null (present-and-nullable)", async () => {
    const onClose = renderDialog();
    fireEvent.change(screen.getByRole("textbox", { name: de["writing.workspace.crud.titleLabel"] }), {
      target: { value: "Neuer Titel" },
    });
    fireEvent.change(screen.getByRole("textbox", { name: de["writing.workspace.crud.settingLabel"] }), {
      target: { value: "  " },
    });
    fireEvent.change(screen.getByRole("textbox", { name: de["writing.workspace.crud.storyTimeLabel"] }), {
      target: { value: " Dritte Stunde " },
    });
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.crud.save"] }));
    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(api.PUT).toHaveBeenCalledWith("/api/writing/scenes/{scene_id}", {
      params: { path: { scene_id: "s1" } },
      body: { title: "Neuer Titel", setting: null, story_time: "Dritte Stunde" },
    });
  });

  it("never carries the body — the autosave owns the prose", async () => {
    renderDialog();
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.crud.save"] }));
    await waitFor(() => expect(api.PUT).toHaveBeenCalled());
    expect(api.PUT.mock.calls[0][1].body).not.toHaveProperty("body");
  });
});

describe("the dirty-state rule — typed changes hold the silent paths", () => {
  /** The chapter shape (one field) on the stateful harness: a close
   *  unmounts the dialog, as the page's own state does. */
  function renderChapter() {
    const onClose = vi.fn();
    renderWithOpener((openerId, close) => (
      <TreeEditDialog
        novelId="n1"
        target={{ kind: "chapter", chapter: CHAPTER }}
        openerId={openerId}
        onClose={() => {
          onClose();
          close();
        }}
      />
    ));
    return onClose;
  }

  function typeTitle(value: string) {
    fireEvent.change(screen.getByRole("textbox", { name: de["writing.workspace.crud.titleLabel"] }), {
      target: { value },
    });
  }

  function pressScrim() {
    fireEvent.mouseDown(screen.getByRole("dialog").parentElement as Element);
  }

  it("pristine: the scrim closes — no typed change stands to lose", () => {
    const onClose = renderChapter();
    pressScrim();
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("pristine: Escape closes", () => {
    const onClose = renderChapter();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("dirty: the scrim holds — a press outside is not an answer", () => {
    const onClose = renderChapter();
    typeTitle("Ein neuer Name");
    pressScrim();
    expect(onClose).not.toHaveBeenCalled();
    expect(screen.getByRole("dialog")).toBeTruthy();
    expect(
      (screen.getByRole("textbox", { name: de["writing.workspace.crud.titleLabel"] }) as HTMLInputElement).value,
    ).toBe("Ein neuer Name");
  });

  it("dirty: Escape holds — only the named answers leave", () => {
    const onClose = renderChapter();
    typeTitle("Ein neuer Name");
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).not.toHaveBeenCalled();
    expect(screen.getByRole("dialog")).toBeTruthy();
  });

  it("dirty: the cross is honestly unavailable — Abbrechen and Speichern alone answer", () => {
    const onClose = renderChapter();
    typeTitle("Ein neuer Name");
    const cross = screen.getByRole("button", { name: de["writing.workspace.crud.close"] });
    expect(cross.hasAttribute("disabled")).toBe(true);
    fireEvent.click(cross);
    expect(onClose).not.toHaveBeenCalled();
    // Abbrechen is the deliberate discard — it answers with edits standing.
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.crud.cancel"] }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("a field returned to its stored value is pristine again — the rule compares, not latches", () => {
    const onClose = renderChapter();
    typeTitle("Ein neuer Name");
    typeTitle("Ghost in the Machine");
    pressScrim();
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("the scene shape: any field counts — a label alone holds Escape", () => {
    const onClose = vi.fn();
    renderWithOpener((openerId, close) => (
      <TreeEditDialog
        novelId="n1"
        target={{ kind: "scene", entry: ENTRY }}
        openerId={openerId}
        onClose={() => {
          onClose();
          close();
        }}
      />
    ));
    fireEvent.change(screen.getByRole("textbox", { name: de["writing.workspace.crud.settingLabel"] }), {
      target: { value: "Hafen bei Nacht" },
    });
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).not.toHaveBeenCalled();
    pressScrim();
    expect(onClose).not.toHaveBeenCalled();
    expect(screen.getByRole("dialog")).toBeTruthy();
  });
});

describe("the delete confirm — the loss named before it happens", () => {
  function renderChapterDialog(chapter: Chapter = CHAPTER, onDeleted = vi.fn()) {
    const onClose = vi.fn();
    renderWithOpener((openerId, close) => (
      <DeleteTreeDialog
        novelId="n1"
        target={{ kind: "chapter", chapter }}
        openerId={openerId}
        onClose={() => {
          onClose();
          close();
        }}
        onDeleted={onDeleted}
      />
    ));
    return { onClose, onDeleted };
  }

  it("names the chapter and its cascade — the plural scene count, the zero honest", () => {
    renderChapterDialog();
    const dialog = screen.getByRole("alertdialog");
    expect(dialog.getAttribute("aria-modal")).toBe("true");
    expect(
      screen.getByRole("heading", { name: de["writing.workspace.crud.deleteChapterTitle"] }),
    ).toBeTruthy();
    expect(screen.getByText("«Ghost in the Machine» wird mit 2 Szenen endgültig gelöscht.")).toBeTruthy();
    cleanup();
    renderChapterDialog({ ...CHAPTER, scene_count: 1 });
    expect(screen.getByText("«Ghost in the Machine» wird mit 1 Szene endgültig gelöscht.")).toBeTruthy();
    cleanup();
    renderChapterDialog({ ...CHAPTER, scene_count: 0 });
    expect(screen.getByText("«Ghost in the Machine» wird endgültig gelöscht.")).toBeTruthy();
  });

  it("focus lands on the safe answer; Escape cancels without a write", () => {
    const { onClose } = renderChapterDialog();
    const cancel = screen.getByRole("button", { name: de["writing.workspace.crud.cancel"] });
    expect(document.activeElement).toBe(cancel);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(api.DELETE).not.toHaveBeenCalled();
    expect(document.activeElement?.id).toBe("opener");
  });

  it("the consequence rides the delete control — the drafted second step", () => {
    renderChapterDialog();
    const confirm = screen.getByRole("button", { name: de["writing.workspace.crud.deleteConfirm"] });
    expect(confirm.getAttribute("title")).toBe(de["writing.workspace.crud.deleteChapterNote"]);
  });

  it("confirming deletes, tells the page and closes", async () => {
    const { onClose, onDeleted } = renderChapterDialog();
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.crud.deleteConfirm"] }));
    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(api.DELETE).toHaveBeenCalledWith("/api/writing/chapters/{chapter_id}", {
      params: { path: { chapter_id: "c1" } },
    });
    expect(onDeleted).toHaveBeenCalledTimes(1);
  });

  it("a refusal keeps the confirm open with the loss-free error and a retry", async () => {
    api.DELETE.mockResolvedValue({ data: undefined, response: new Response(null, { status: 503 }) });
    const { onClose, onDeleted } = renderChapterDialog();
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.crud.deleteConfirm"] }));
    expect(await screen.findByText(de["writing.workspace.crud.deleteError"])).toBeTruthy();
    expect(onClose).not.toHaveBeenCalled();
    expect(onDeleted).not.toHaveBeenCalled();
    api.DELETE.mockResolvedValue({ data: undefined, response: new Response(null, { status: 204 }) });
    fireEvent.click(screen.getByRole("button", { name: de["writing.shelf.error.retry"] }));
    await waitFor(() => expect(onDeleted).toHaveBeenCalled());
  });

  it("the scrim does not discard the question — only the named answers leave", () => {
    const { onClose } = renderChapterDialog();
    fireEvent.mouseDown(screen.getByRole("alertdialog").parentElement as Element);
    expect(onClose).not.toHaveBeenCalled();
    expect(screen.getByRole("alertdialog")).toBeTruthy();
  });

  it("the scene confirm names the words and the chapter remaining (D16)", async () => {
    const onClose = vi.fn();
    const onDeleted = vi.fn();
    renderWithOpener((openerId, close) => (
      <DeleteTreeDialog
        novelId="n1"
        target={{ kind: "scene", entry: ENTRY }}
        openerId={openerId}
        onClose={() => {
          onClose();
          close();
        }}
        onDeleted={onDeleted}
      />
    ));
    expect(
      screen.getByRole("heading", { name: de["writing.workspace.crud.deleteSceneTitle"] }),
    ).toBeTruthy();
    expect(
      screen.getByText("«Das Signal im Permafrost» wird endgültig gelöscht. Das Kapitel bleibt bestehen."),
    ).toBeTruthy();
    const confirm = screen.getByRole("button", { name: de["writing.workspace.crud.deleteConfirm"] });
    expect(confirm.getAttribute("title")).toBe(de["writing.workspace.crud.deleteSceneNote"]);
    fireEvent.click(confirm);
    await waitFor(() => expect(onDeleted).toHaveBeenCalled());
    expect(api.DELETE).toHaveBeenCalledWith("/api/writing/scenes/{scene_id}", {
      params: { path: { scene_id: "s1" } },
    });
  });
});
