// @vitest-environment jsdom
/**
 * The prompts page renders the server's summary rows and never mints scope
 * facts of its own: the chips a card offers come from `novel_scopable`, the
 * inherits-label names the tier the API says is in force, and a save for the
 * novel scope carries `novel_id` — the body is what keeps the write off the
 * global row. A 422 renders the reason and detail the refusal names.
 *
 * The API client is mocked at its module boundary: the cases here are about
 * what the page says, and the requests are verified by the backend and E2E
 * suites against the real stack.
 */
import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { t } from "@shell/lib/i18n";

vi.mock("@shell/lib/api/client", () => ({
  client: {
    GET: vi.fn(),
    POST: vi.fn(),
    PATCH: vi.fn(),
    PUT: vi.fn(),
    DELETE: vi.fn(),
  },
}));

import { client } from "@shell/lib/api/client";

import { PromptsPage } from "./PromptsPage";

/** The client's methods as plain mocks; the real client's generics stay out. */
const api = client as unknown as Record<
  "GET" | "POST" | "PATCH" | "PUT" | "DELETE",
  ReturnType<typeof vi.fn>
>;

type Query = { novel_id?: string } | undefined;
type GetOptions = { params?: { path?: Record<string, string>; query?: Query } };

const NOVEL_ID = "44444444-4444-4444-4444-444444444444";

const NOVELS = [
  {
    id: NOVEL_ID,
    title: "Der steinerne Traum",
    author: null,
    blurb: null,
    genre: null,
    language: null,
    created_at: "2026-10-27T10:00:00Z",
    updated_at: "2026-10-27T10:00:00Z",
  },
];

const SUMMARIES = [
  {
    key: "writing.continuation",
    novel_scopable: true,
    override_global: true,
    override_novel: false,
    bundled_summary: "Continue the story from the chapter's end.",
  },
  {
    key: "chat.ask",
    novel_scopable: false,
    override_global: false,
    override_novel: false,
    bundled_summary: "Answer a question about the book.",
  },
  {
    key: "knowledge.extract-entities",
    novel_scopable: true,
    override_global: false,
    override_novel: false,
    bundled_summary: "Extract the entities of a chapter.",
  },
  {
    key: "knowledge.check-consistency",
    novel_scopable: true,
    override_global: false,
    override_novel: true,
    bundled_summary: "Check the novel for contradictions.",
  },
];

const BUNDLED = "Continue the story in the same voice.";
const OVERRIDE = "Continue the story in the voice of a sea captain.";
const NOVEL_OVERRIDE = "Continue the story in this novel's own voice.";
const CONSISTENCY_BUNDLED = "Check the findings against the chapters.";

/** The detail the editor loads, per key and per requested tier. The reads are
 *  scope-aware, so a test wired to the wrong tier reads the wrong words: the
 *  consistency check's global read shows the bundled template, its novel read
 *  shows the novel's own row. The continuation's novel tier is empty, so both
 *  of its reads inherit the global text — the tier a request targets is
 *  visible in the request itself, and the tests assert exactly that. */
function detailFor(key: string, novelId?: string): object {
  if (key === "writing.continuation") {
    return {
      bundled_content: BUNDLED,
      variables: [
        { name: "chapter_text", example: "The harbour was empty." },
        { name: "sources", example: "a passage of the book" },
      ],
      override: { scope: "global", content: OVERRIDE },
      effective_content: OVERRIDE,
    };
  }
  if (key === "knowledge.check-consistency") {
    const shared = {
      bundled_content: CONSISTENCY_BUNDLED,
      variables: [{ name: "findings", example: "Two chapters disagree." }],
    };
    if (novelId === undefined) {
      return { ...shared, override: null, effective_content: CONSISTENCY_BUNDLED };
    }
    return { ...shared, override: { scope: "novel", content: NOVEL_OVERRIDE }, effective_content: NOVEL_OVERRIDE };
  }
  return {
    bundled_content: BUNDLED,
    variables: [],
    override: null,
    effective_content: BUNDLED,
  };
}

function ok(): Response {
  return new Response(null, { status: 200 });
}

function refused(): { error: object; response: Response } {
  return {
    error: { detail: { reason: "contract", detail: "the frame did not survive" } },
    response: new Response(null, { status: 422 }),
  };
}

function mockApi(): void {
  api.GET.mockImplementation(async (path: string, options?: GetOptions) => {
    switch (path) {
      case "/api/writing/novels":
        return { data: NOVELS, response: ok() };
      case "/api/prompts":
        return { data: SUMMARIES, response: ok() };
      case "/api/prompts/{key}":
        return {
          data: detailFor(options?.params?.path?.key ?? "", options?.params?.query?.novel_id),
          response: ok(),
        };
      case "/api/prompts/{key}/diff":
        return {
          data: { bundled_content: BUNDLED, override_content: OVERRIDE },
          response: ok(),
        };
      default:
        throw new Error(`unexpected GET ${path}`);
    }
  });
}

async function renderPage(): Promise<void> {
  render(<PromptsPage />);
  // The mount's fetch fills the list; the cards only exist after it lands.
  await screen.findByText(t("settings.task.writing.continuation"));
}

/** The novel filter moved to the one mocked novel; the cards re-render. */
async function selectNovel(): Promise<void> {
  await userEvent.selectOptions(screen.getByLabelText(t("prompts.filter")), NOVEL_ID);
  await screen.findAllByText(t("prompts.scope.novel"));
}

/** The card of one key: the list item that carries the key's label. */
function cardOf(label: string): HTMLElement {
  const card = screen.getByText(label).closest("li");
  if (card === null) throw new Error(`no card for ${label}`);
  return card;
}

beforeEach(() => {
  mockApi();
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("the summary list", () => {
  it("names the four keys and gives each a Global chip", async () => {
    await renderPage();

    for (const label of [
      t("settings.task.writing.continuation"),
      t("settings.task.chat.ask"),
      t("settings.task.knowledge.extract-entities"),
      t("settings.task.knowledge.check-consistency"),
    ]) {
      expect(screen.getByText(label)).toBeTruthy();
    }
    expect(screen.getAllByText(t("prompts.scope.global"))).toHaveLength(4);
  });

  it("offers the novel chip only where the API says the key takes it", async () => {
    await renderPage();
    await selectNovel();

    expect(screen.getAllByText(t("prompts.scope.novel"))).toHaveLength(3);
    const chat = cardOf(t("settings.task.chat.ask"));
    expect(within(chat).queryByText(t("prompts.scope.novel"))).toBeNull();
  });

  it("says what an empty novel scope inherits and creates prefilled", async () => {
    await renderPage();
    await selectNovel();

    // The continuation's novel tier is empty; the global tier is in force,
    // so the inherits-label names it — never a bare "empty".
    const card = cardOf(t("settings.task.writing.continuation"));
    expect(
      within(card).getByText(t("prompts.inherits", { state: t("prompts.inheritsFrom.global") })),
    ).toBeTruthy();

    await userEvent.click(within(card).getByRole("button", { name: t("prompts.create") }));

    // The editor asks for the novel tier, and the heading names the novel:
    // a create wired to the global tier is the silent fork the contract
    // forbids, and this is where it cannot hide.
    expect(api.GET).toHaveBeenCalledWith("/api/prompts/{key}", {
      params: { path: { key: "writing.continuation" }, query: { novel_id: NOVEL_ID } },
    });
    expect(
      await screen.findByText(`${t("settings.task.writing.continuation")} · ${NOVELS[0].title}`),
    ).toBeTruthy();

    const box = await screen.findByRole("textbox", {
      name: t("prompts.editor.contentLabel"),
    });
    // The editor opens prefilled with the effective text — the fork is an
    // explicit act on visible words, never a silent blank.
    expect((box as HTMLTextAreaElement).value).toBe(OVERRIDE);
  });

  it("keeps the page when the list cannot be loaded", async () => {
    api.GET.mockImplementation(async (path: string) => {
      if (path === "/api/writing/novels") return { data: NOVELS, response: ok() };
      throw new TypeError("Failed to fetch");
    });

    render(<PromptsPage />);
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain(t("prompts.errorLoad"));
  });
});

describe("a save", () => {
  it("carries the novel in the PUT body so the global row is untouched", async () => {
    await renderPage();
    await selectNovel();

    const card = cardOf(t("settings.task.knowledge.check-consistency"));
    await userEvent.click(within(card).getByRole("button", { name: t("prompts.editNovel") }));
    await screen.findByRole("textbox", { name: t("prompts.editor.contentLabel") });
    api.PUT.mockResolvedValue({
      data: detailFor("knowledge.check-consistency", NOVEL_ID),
      response: ok(),
    });

    await userEvent.click(screen.getByRole("button", { name: t("prompts.editor.save") }));

    expect(api.PUT).toHaveBeenCalledWith("/api/prompts/{key}", {
      params: { path: { key: "knowledge.check-consistency" } },
      body: { content: NOVEL_OVERRIDE, novel_id: NOVEL_ID },
    });
  });

  it("sends no novel for the global scope", async () => {
    await renderPage();

    const card = cardOf(t("settings.task.writing.continuation"));
    await userEvent.click(within(card).getByRole("button", { name: t("prompts.edit") }));
    await screen.findByRole("textbox", { name: t("prompts.editor.contentLabel") });
    api.PUT.mockResolvedValue({ data: detailFor("writing.continuation"), response: ok() });

    await userEvent.click(screen.getByRole("button", { name: t("prompts.editor.save") }));

    expect(api.PUT).toHaveBeenCalledWith("/api/prompts/{key}", {
      params: { path: { key: "writing.continuation" } },
      body: { content: OVERRIDE },
    });
  });

  it("keeps an open editor's words and target when the novel filter moves", async () => {
    await renderPage();
    await selectNovel();

    const card = cardOf(t("settings.task.knowledge.check-consistency"));
    await userEvent.click(within(card).getByRole("button", { name: t("prompts.editNovel") }));
    const box = await screen.findByRole("textbox", { name: t("prompts.editor.contentLabel") });
    await userEvent.clear(box);
    await userEvent.type(box, "A fresh voice for this one novel.");

    // The filter moves on; the editor's target was captured at open time,
    // so nothing it holds may drift or wipe.
    await userEvent.selectOptions(screen.getByLabelText(t("prompts.filter")), "");
    const kept = screen.getByRole("textbox", {
      name: t("prompts.editor.contentLabel"),
    }) as HTMLTextAreaElement;
    expect(kept.value).toBe("A fresh voice for this one novel.");
    // The heading still names the novel the editor was opened for.
    expect(
      screen.getByText(`${t("settings.task.knowledge.check-consistency")} · ${NOVELS[0].title}`),
    ).toBeTruthy();

    api.PUT.mockResolvedValue({
      data: detailFor("knowledge.check-consistency", NOVEL_ID),
      response: ok(),
    });
    await userEvent.click(screen.getByRole("button", { name: t("prompts.editor.save") }));

    // The save writes the novel it was opened for — never an empty
    // novel_id, never the global row.
    expect(api.PUT).toHaveBeenCalledWith("/api/prompts/{key}", {
      params: { path: { key: "knowledge.check-consistency" } },
      body: { content: "A fresh voice for this one novel.", novel_id: NOVEL_ID },
    });
  });

  it("renders the reason and detail a refusal names", async () => {
    await renderPage();

    const card = cardOf(t("settings.task.writing.continuation"));
    await userEvent.click(within(card).getByRole("button", { name: t("prompts.edit") }));
    await screen.findByRole("textbox", { name: t("prompts.editor.contentLabel") });
    api.PUT.mockResolvedValue(refused());

    await userEvent.click(screen.getByRole("button", { name: t("prompts.editor.save") }));

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toBe(
      t("prompts.saveRefused", {
        reason: t("prompts.reason.contract"),
        detail: "the frame did not survive",
      }),
    );
  });
});

describe("a reset", () => {
  it("deletes the novel scope the chip names", async () => {
    await renderPage();
    await selectNovel();

    const card = cardOf(t("settings.task.knowledge.check-consistency"));
    await userEvent.click(within(card).getByRole("button", { name: t("prompts.editNovel") }));
    await screen.findByRole("textbox", { name: t("prompts.editor.contentLabel") });
    api.DELETE.mockResolvedValue({ response: new Response(null, { status: 204 }) });

    await userEvent.click(screen.getByRole("button", { name: t("prompts.editor.reset") }));

    expect(api.DELETE).toHaveBeenCalledWith("/api/prompts/{key}", {
      params: { path: { key: "knowledge.check-consistency" }, query: { novel_id: NOVEL_ID } },
    });
  });

  it("deletes the global scope the chip names", async () => {
    await renderPage();

    const card = cardOf(t("settings.task.writing.continuation"));
    await userEvent.click(within(card).getByRole("button", { name: t("prompts.edit") }));
    await screen.findByRole("textbox", { name: t("prompts.editor.contentLabel") });
    api.DELETE.mockResolvedValue({ response: new Response(null, { status: 204 }) });

    await userEvent.click(screen.getByRole("button", { name: t("prompts.editor.reset") }));

    expect(api.DELETE).toHaveBeenCalledWith("/api/prompts/{key}", {
      params: { path: { key: "writing.continuation" } },
    });
  });
});

describe("a failed editor load", () => {
  it("offers retry and a way out when the detail cannot load", async () => {
    let detailCalls = 0;
    api.GET.mockImplementation(async (path: string, options?: GetOptions) => {
      if (path === "/api/prompts/{key}") {
        detailCalls += 1;
        if (detailCalls === 1) throw new TypeError("Failed to fetch");
        return { data: detailFor(options?.params?.path?.key ?? ""), response: ok() };
      }
      switch (path) {
        case "/api/writing/novels":
          return { data: NOVELS, response: ok() };
        case "/api/prompts":
          return { data: SUMMARIES, response: ok() };
        default:
          throw new Error(`unexpected GET ${path}`);
      }
    });

    await renderPage();
    const card = cardOf(t("settings.task.writing.continuation"));
    await userEvent.click(within(card).getByRole("button", { name: t("prompts.edit") }));

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain(t("prompts.editor.detailFailed"));

    // Retry recovers; cancel leaves the page — no dead editor, no reload.
    await userEvent.click(screen.getByRole("button", { name: t("prompts.editor.retry") }));
    expect(
      await screen.findByRole("textbox", { name: t("prompts.editor.contentLabel") }),
    ).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: t("prompts.editor.cancel") }));
    expect(
      screen.queryByRole("textbox", { name: t("prompts.editor.contentLabel") }),
    ).toBeNull();
    expect(detailCalls).toBe(2);
  });
});

describe("the diff view", () => {
  it("shows the bundled template and the override side by side", async () => {
    await renderPage();

    const card = cardOf(t("settings.task.writing.continuation"));
    await userEvent.click(within(card).getByRole("button", { name: t("prompts.edit") }));
    await screen.findByRole("textbox", { name: t("prompts.editor.contentLabel") });

    await userEvent.click(screen.getByRole("button", { name: t("prompts.editor.diff") }));

    const left = await screen.findByText(BUNDLED);
    // The override text also fills the editor's textarea, so the lookup is
    // scoped to the diff block the left cell already found.
    const grid = left.parentElement;
    if (grid === null) throw new Error("the diff block is missing");
    const right = within(grid).getByText(OVERRIDE);
    // Side by side: the two texts share one diff block, under the two
    // column headers that name them.
    expect(right.parentElement).toBe(left.parentElement);
    expect(screen.getByText(t("prompts.diff.bundled"))).toBeTruthy();
    expect(screen.getByText(t("prompts.diff.override"))).toBeTruthy();
  });
});

describe("the page's words", () => {
  it("renders no raw catalog key", async () => {
    await renderPage();
    await selectNovel();

    expect(screen.queryByText(/prompts\.[a-z-]/)).toBeNull();
  });
});
