// @vitest-environment jsdom
/**
 * The interview panel (W9 Task 10) — the conversation and its faces, driven
 * through the real API seam (the client mocked at its module boundary, the
 * house pattern) and the real catalogs. The panel opens on the graph's
 * search parameter; this suite pins the controller and the faces it draws:
 * the chooser starts a typed session, every chip sends the act the wire
 * names, a failed typed answer keeps its text and a failed button keeps its
 * body for the retry, hiding the panel never closes the session, and ending
 * it removes the composer while the proposal stays readable.
 */
import { QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, configure, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@shell/lib/api/client", () => ({
  client: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn(), PUT: vi.fn(), DELETE: vi.fn() },
}));

import {
  client,
  type AssistantSession,
  type AssistantSessionSummary,
  type AssistantTurnRead,
  type Proposal,
} from "@shell/lib/api/client";
import { catalogs } from "@shell/lib/generated/catalogs";
import { applyLocale } from "@shell/lib/locale";
import { queryClient } from "@shell/lib/query";

import { EntityInterview } from "./EntityInterview";

const de = catalogs.de;
const api = client as unknown as Record<"GET" | "POST", ReturnType<typeof vi.fn>>;

configure({ asyncUtilTimeout: 5000 });

const NOVEL_ID = "11111111-1111-1111-1111-111111111111";
const SESSION_ID = "s1";
const SECOND_ID = "s2";

function ok(): Response {
  return new Response(null, { status: 200 });
}

function proposal(overrides: Partial<Proposal> = {}): Proposal {
  return {
    name: null,
    name_suggested: false,
    aliases: [],
    tags: [],
    content: "",
    relations: [],
    ...overrides,
  };
}

function turn(overrides: Partial<AssistantTurnRead> & { seq: number }): AssistantTurnRead {
  return {
    role: "assistant",
    text: "",
    act: null,
    suggestion: null,
    suggestion_state: null,
    created_at: "2026-11-24T14:02:00Z",
    ...overrides,
  };
}

let detail: AssistantSession;
let sessions: AssistantSessionSummary[];

function sessionDetail(overrides: Partial<AssistantSession> = {}): AssistantSession {
  return {
    id: SESSION_ID,
    novel_id: NOVEL_ID,
    mode: "knowledge.entity",
    entity_type: "object",
    target_id: null,
    proposal: null,
    turns: [],
    closed_at: null,
    created_at: "2026-11-24T14:00:00Z",
    updated_at: "2026-11-24T14:00:00Z",
    ...overrides,
  };
}

function summary(overrides: Partial<AssistantSessionSummary> = {}): AssistantSessionSummary {
  return {
    id: SESSION_ID,
    novel_id: NOVEL_ID,
    mode: "knowledge.entity",
    entity_type: "object",
    target_id: null,
    name: null,
    closed_at: null,
    created_at: "2026-11-24T14:00:00Z",
    updated_at: "2026-11-24T14:00:00Z",
    ...overrides,
  };
}

function detailGet(path: string): Promise<{ data: unknown; response: Response }> {
  if (path === "/api/chat/sessions") {
    return Promise.resolve({ data: { items: sessions }, response: ok() });
  }
  if (path === "/api/chat/sessions/{session_id}") {
    return Promise.resolve({ data: detail, response: ok() });
  }
  throw new Error(`unexpected GET: ${path}`);
}

/** Two interviews at once: the read answers each id with its own row, so a
 *  switch can never pass A's transcript off as B's. */
function readsById(second: AssistantSession) {
  return (path: string, init?: { params?: { path?: { session_id?: string } } }) => {
    if (path === "/api/chat/sessions") {
      return Promise.resolve({ data: { items: sessions }, response: ok() });
    }
    if (path === "/api/chat/sessions/{session_id}") {
      const id = init?.params?.path?.session_id ?? "";
      return Promise.resolve({ data: id === second.id ? second : detail, response: ok() });
    }
    throw new Error(`unexpected GET: ${path}`);
  };
}

/** How often the panel asked for one session: the counter the settle's
 *  invalidation and the show's own ask are read by. */
function sessionReads(): number {
  return api.GET.mock.calls.filter(([path]) => path === "/api/chat/sessions/{session_id}").length;
}

function readback(overrides: Record<string, unknown> = {}) {
  return {
    reply: "Notiert.",
    proposal: detail.proposal,
    suggestion: null,
    seq: 9,
    ...overrides,
  };
}

/** A response the test settles exactly once, so a turn's flight is decided
 *  by the test and never by timing. */
function deferred(): { promise: Promise<unknown>; settle: (value: unknown) => void } {
  let settle: (value: unknown) => void = () => {};
  const promise = new Promise<unknown>((resolve) => {
    settle = resolve;
  });
  return { promise, settle };
}

function renderPanel(
  sessionId: string | null | undefined = SESSION_ID,
  options: { handedOver?: boolean; onEnded?: (sessionId: string) => void } = {},
) {
  const onSelectSession = vi.fn();
  const onClose = vi.fn();
  const onManual = vi.fn();
  const onSave = vi.fn();
  const onEnded = options.onEnded ?? vi.fn();
  let shown: string | null | undefined = sessionId;
  let handed = options.handedOver ?? false;
  const handlers = { onSelectSession, onClose, onManual, onSave, onEnded };
  const view = render(
    <QueryClientProvider client={queryClient}>
      <EntityInterview novelId={NOVEL_ID} sessionId={shown} handedOver={handed} {...handlers} />
    </QueryClientProvider>,
  );
  /** Hide (undefined), reopen a session (its id) or show the chooser (null);
   *  the handover flag travels with the page's own state, so a reopen keeps it
   *  unless the test ends the interview. */
  const show = (next: string | null | undefined, handedOver = handed) => {
    shown = next;
    handed = handedOver;
    view.rerender(
      <QueryClientProvider client={queryClient}>
        <EntityInterview novelId={NOVEL_ID} sessionId={shown} handedOver={handed} {...handlers} />
      </QueryClientProvider>,
    );
  };
  return { ...handlers, show };
}

function composer(): HTMLTextAreaElement {
  return screen.getByPlaceholderText(de["knowledge.interview.placeholder"]) as HTMLTextAreaElement;
}

/** The textarea even while a turn runs and its placeholder names the wait. */
function composerField(): HTMLTextAreaElement {
  const field = within(screen.getByTestId("entity-interview-composer")).getByRole("textbox");
  return field as HTMLTextAreaElement;
}

async function readySession(): Promise<void> {
  await screen.findByTestId("entity-interview-proposal");
  await waitFor(() => expect(screen.getByTestId("entity-interview-no-idea")).toBeTruthy());
}

beforeEach(() => {
  applyLocale("de");
  vi.stubGlobal("navigator", { language: "de-DE", languages: ["de-DE"] });
  detail = sessionDetail();
  sessions = [summary()];
  api.GET.mockImplementation(detailGet);
  api.POST.mockResolvedValue({ data: readback(), response: ok() });
});

afterEach(() => {
  cleanup();
  queryClient.clear();
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

describe("the door's type chooser", () => {
  it("starts a session on the chosen type and hands its id back", async () => {
    const onSelect = vi.fn();
    api.POST.mockResolvedValue({ data: sessionDetail(), response: new Response(null, { status: 201 }) });
    render(
      <QueryClientProvider client={queryClient}>
        <EntityInterview
          novelId={NOVEL_ID}
          sessionId={null}
          onSelectSession={onSelect}
          onClose={vi.fn()}
          onManual={vi.fn()}
          onSave={vi.fn()}
          onEnded={vi.fn()}
        />
      </QueryClientProvider>,
    );

    // Deliberately unselected on arrival — no type is «the» default, so the
    // start stays disabled until the writer picks one. The illustrated tile
    // draws «Objekt» selected; that divergence is in the wave's gap ledger and
    // is not a bug to "fix" back toward the tile.
    const start = screen.getByTestId("entity-interview-start") as HTMLButtonElement;
    expect(start.disabled).toBe(true);
    expect(screen.getByTestId("entity-interview-type-object").getAttribute("aria-pressed")).toBe("false");
    fireEvent.click(screen.getByTestId("entity-interview-type-object"));
    expect((screen.getByTestId("entity-interview-start") as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(screen.getByTestId("entity-interview-start"));

    await waitFor(() =>
      expect(api.POST).toHaveBeenCalledWith("/api/chat/sessions", {
        body: { novel_id: NOVEL_ID, mode: "knowledge.entity", entity_type: "object" },
      }),
    );
    await waitFor(() => expect(onSelect).toHaveBeenCalledWith(SESSION_ID));
  });

  it("offers the quiet manual path beside the interview", async () => {
    const { onManual } = renderPanel(null);
    fireEvent.click(screen.getByTestId("entity-interview-manual"));
    expect(onManual).toHaveBeenCalledTimes(1);
    expect(api.POST).not.toHaveBeenCalled();
  });

  it("a start the wire refuses names its failure under the type grid", async () => {
    api.POST.mockResolvedValueOnce({
      data: undefined,
      error: { detail: { code: "provider-unavailable", detail: "no serving tier for chat.ask" } },
      response: new Response(null, { status: 502 }),
    });
    renderPanel(null);
    fireEvent.click(screen.getByTestId("entity-interview-type-object"));
    fireEvent.click(screen.getByTestId("entity-interview-start"));

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toBe(de["knowledge.interview.startFailed"]);
    // The chosen type still stands and the start can be tried again.
    expect(screen.getByTestId("entity-interview-type-object").getAttribute("aria-pressed")).toBe("true");
    expect((screen.getByTestId("entity-interview-start") as HTMLButtonElement).disabled).toBe(false);
  });
});

describe("the list closes on the row it opens", () => {
  it("«Neues Interview» on the chooser closes the list at once", async () => {
    const { onSelectSession } = renderPanel(null);
    fireEvent.click(screen.getByTestId("entity-interview-sessions"));
    const list = await screen.findByTestId("entity-interview-list");
    fireEvent.click(within(list).getByRole("button", { name: de["knowledge.interview.newInterview"] }));

    expect(onSelectSession).toHaveBeenCalledWith("new");
    expect(screen.queryByTestId("entity-interview-list")).toBeNull();
  });

  it("«Fortsetzen» on the session already shown closes the list at once", async () => {
    const { onSelectSession } = renderPanel();
    await readySession();
    fireEvent.click(screen.getByTestId("entity-interview-sessions"));
    const list = await screen.findByTestId("entity-interview-list");
    fireEvent.click(within(list).getByRole("button", { name: de["knowledge.interview.resume"] }));

    expect(onSelectSession).toHaveBeenCalledWith(SESSION_ID);
    expect(screen.queryByTestId("entity-interview-list")).toBeNull();
  });
});

describe("the list counts its interviews", () => {
  it("says «2 Interviews» for two open rows, never «Sitzungen»", async () => {
    sessions = [summary(), summary({ id: SECOND_ID, entity_type: "location" })];
    renderPanel();
    await readySession();
    fireEvent.click(screen.getByTestId("entity-interview-sessions"));
    const list = await screen.findByTestId("entity-interview-list");

    expect(list.textContent).toContain("2 Interviews");
    expect(list.textContent).not.toContain("Sitzung");
  });

  it("says «1 Interview» for one open row", async () => {
    renderPanel();
    await readySession();
    fireEvent.click(screen.getByTestId("entity-interview-sessions"));
    const list = await screen.findByTestId("entity-interview-list");

    expect(list.textContent).toContain("1 Interview");
  });

  it("shows the loading line, not a zero, while the list is still unread", async () => {
    let release: (value: unknown) => void = () => {};
    const held = new Promise((resolve) => {
      release = resolve;
    });
    api.GET.mockImplementation((path: string, init?: { params?: unknown }) =>
      path === "/api/chat/sessions" ? held : detailGet(path),
    );
    renderPanel();
    await readySession();
    fireEvent.click(screen.getByTestId("entity-interview-sessions"));
    const list = await screen.findByTestId("entity-interview-list");

    // The wire has said nothing yet: no count and no row may stand, and the
    // list says that it is loading instead — its own sentence, since it reads
    // a list of interviews and not one interview.
    expect(list.textContent).toContain(de["knowledge.interview.listLoading"]);
    expect(list.textContent).not.toContain(de["knowledge.interview.loading"]);
    expect(list.textContent).not.toContain(de["knowledge.interview.openTitle"]);
    expect(list.textContent).not.toContain(de["knowledge.interview.noName"]);
    expect(within(list).queryAllByRole("button")).toHaveLength(2);

    release({ data: { items: sessions }, response: ok() });
    await waitFor(() => expect(list.textContent).toContain("1 Interview"));
    expect(list.textContent).toContain(de["knowledge.interview.noName"]);
    expect(list.textContent).not.toContain(de["knowledge.interview.listLoading"]);
  });

  it("a failed list read names its failure with a retry, never a zero", async () => {
    let fail = true;
    api.GET.mockImplementation((path: string) =>
      path === "/api/chat/sessions"
        ? fail
          ? Promise.reject(new Error("list read failed"))
          : Promise.resolve({ data: { items: sessions }, response: ok() })
        : detailGet(path),
    );
    renderPanel();
    await readySession();
    fireEvent.click(screen.getByTestId("entity-interview-sessions"));
    const list = await screen.findByTestId("entity-interview-list");

    // The wire refused the read: its own sentence and the retry stand, and
    // neither a count nor a row may claim what the read never answered.
    const alert = await within(list).findByRole("alert");
    expect(alert.textContent).toBe(de["knowledge.interview.listFailed"]);
    expect(list.textContent).not.toContain(de["knowledge.interview.openTitle"]);
    expect(list.textContent).not.toContain(de["knowledge.interview.noName"]);
    expect(list.textContent).not.toContain("1 Interview");
    expect(within(list).queryByRole("button", { name: de["knowledge.interview.resume"] })).toBeNull();

    // The retry asks the list again, and its answer restores counts and rows.
    fail = false;
    fireEvent.click(within(list).getByRole("button", { name: de["knowledge.interview.retry"] }));
    await waitFor(() => expect(list.textContent).toContain("1 Interview"));
    expect(list.textContent).toContain(de["knowledge.interview.noName"]);
    expect(list.textContent).not.toContain(de["knowledge.interview.listFailed"]);
  });

  it("a failed background refresh keeps the cached rows and their counts", async () => {
    let fail = false;
    api.GET.mockImplementation((path: string) =>
      path === "/api/chat/sessions"
        ? fail
          ? Promise.reject(new Error("refresh failed"))
          : Promise.resolve({ data: { items: sessions }, response: ok() })
        : detailGet(path),
    );
    renderPanel();
    await readySession();
    fireEvent.click(screen.getByTestId("entity-interview-sessions"));
    const list = await screen.findByTestId("entity-interview-list");
    await within(list).findByText(de["knowledge.interview.noName"]);
    expect(list.textContent).toContain("1 Interview");

    // A turn or a close invalidates the list; when that background refresh
    // fails, the rows the writer already sees must stay — a stale list beats
    // an empty one — and the failure face may not claim there is nothing.
    fail = true;
    await act(async () => {
      await queryClient.refetchQueries({ queryKey: ["chat", "sessions", NOVEL_ID] });
    });
    // The observer's notification is scheduled, not rendered inside the
    // refetch's own promise: give that turn its flush before reading the list.
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
    expect(list.textContent).toContain("1 Interview");
    expect(list.textContent).toContain(de["knowledge.interview.noName"]);
    expect(within(list).queryByTestId("entity-interview-list-failed")).toBeNull();
    expect(within(list).queryByRole("alert")).toBeNull();
    expect(
      within(list).getByRole("button", { name: de["knowledge.interview.resume"] }),
    ).toBeTruthy();
  });
});

describe("each chip sends its act", () => {
  it("no-idea and fill-all send their labels with their acts", async () => {
    renderPanel();
    await readySession();

    const noIdea = screen.getByTestId("entity-interview-no-idea") as HTMLButtonElement;
    fireEvent.click(noIdea);
    await waitFor(() =>
      expect(api.POST).toHaveBeenCalledWith("/api/chat/sessions/{session_id}/turns", {
        params: { path: { session_id: SESSION_ID } },
        body: { text: de["knowledge.interview.noIdea"], act: "no-idea" },
      }),
    );
    await waitFor(() => expect(noIdea.disabled).toBe(false));

    fireEvent.click(screen.getByTestId("entity-interview-fill-all"));
    await waitFor(() =>
      expect(api.POST).toHaveBeenCalledWith("/api/chat/sessions/{session_id}/turns", {
        params: { path: { session_id: SESSION_ID } },
        body: { text: de["knowledge.interview.fillAll"], act: "fill-all" },
      }),
    );
  });

  it("accept sends an empty text; the server stores the suggestion", async () => {
    detail = sessionDetail({
      turns: [
        turn({ seq: 1, role: "user", text: de["knowledge.interview.noIdea"], act: "no-idea" }),
        turn({ seq: 2, suggestion: "Ein Vorschlag.", suggestion_state: "pending" }),
      ],
    });
    renderPanel();
    await screen.findByTestId("entity-interview-suggestion");
    fireEvent.click(screen.getByTestId("entity-interview-suggestion-accept"));

    await waitFor(() =>
      expect(api.POST).toHaveBeenCalledWith("/api/chat/sessions/{session_id}/turns", {
        params: { path: { session_id: SESSION_ID } },
        body: { text: "", act: "accept-suggestion" },
      }),
    );
  });

  it("edit fills the composer and sends nothing", async () => {
    detail = sessionDetail({
      turns: [turn({ seq: 1, suggestion: "Ein Vorschlag.", suggestion_state: "pending" })],
    });
    renderPanel();
    await screen.findByTestId("entity-interview-suggestion");
    fireEvent.click(screen.getByTestId("entity-interview-suggestion-edit"));

    expect(composer().value).toBe("Ein Vorschlag.");
    expect(api.POST).not.toHaveBeenCalled();
  });

  it("reject and drop send their labels with their acts", async () => {
    detail = sessionDetail({
      proposal: proposal({
        name: "Resonanz-Transponder LC-89",
        tags: ["Technologie"],
        suggested: { aliases: [], tags: ["Technologie"], content: false },
      }),
      turns: [turn({ seq: 1, suggestion: "Ein Vorschlag.", suggestion_state: "pending" })],
    });
    renderPanel();
    await screen.findByTestId("entity-interview-suggestion");

    fireEvent.click(screen.getByTestId("entity-interview-suggestion-reject"));
    await waitFor(() =>
      expect(api.POST).toHaveBeenCalledWith("/api/chat/sessions/{session_id}/turns", {
        params: { path: { session_id: SESSION_ID } },
        body: { text: de["knowledge.interview.reject"], act: "reject-suggestion" },
      }),
    );

    fireEvent.click(screen.getByTestId("entity-interview-drop-suggestions"));
    await waitFor(() =>
      expect(api.POST).toHaveBeenCalledWith("/api/chat/sessions/{session_id}/turns", {
        params: { path: { session_id: SESSION_ID } },
        body: { text: de["knowledge.interview.dropSuggestions"], act: "drop-suggestions" },
      }),
    );
  });
});

describe("only the newest standing suggestion is actionable", () => {
  it("draws the three actions on the newest card and leaves the older as a plain turn", async () => {
    detail = sessionDetail({
      turns: [
        turn({ seq: 1, role: "user", text: de["knowledge.interview.noIdea"], act: "no-idea" }),
        turn({
          seq: 2,
          text: "Hier ist ein Vorschlag.",
          suggestion: "Der ältere Vorschlag.",
          suggestion_state: "pending",
        }),
        turn({ seq: 3, role: "user", text: de["knowledge.interview.noIdea"], act: "no-idea" }),
        turn({
          seq: 4,
          text: "Hier ist noch ein Vorschlag.",
          suggestion: "Der neuere Vorschlag.",
          suggestion_state: "pending",
        }),
      ],
    });
    renderPanel();

    // The server settles the newest pending suggestion, so the actions stand
    // on that card alone: an older pending suggestion is the assistant's
    // plain turn, its text standing and no action of its own.
    await readySession();
    const cards = screen.getAllByTestId("entity-interview-suggestion");
    expect(cards).toHaveLength(1);
    const card = cards[0];
    expect(card.textContent).toContain("Der neuere Vorschlag.");
    for (const action of ["accept", "edit", "reject"]) {
      expect(within(card).getByTestId(`entity-interview-suggestion-${action}`)).toBeTruthy();
    }
    const transcript = screen.getByTestId("entity-interview-transcript");
    expect(transcript.textContent).toContain("Hier ist ein Vorschlag.");
    expect(transcript.textContent).not.toContain("Der ältere Vorschlag.");
    expect(screen.getAllByTestId("entity-interview-suggestion-accept")).toHaveLength(1);
  });

  it("moves the actions to the older suggestion once the newer one is settled", async () => {
    detail = sessionDetail({
      turns: [
        turn({
          seq: 1,
          text: "Hier ist ein Vorschlag.",
          suggestion: "Der ältere Vorschlag.",
          suggestion_state: "pending",
        }),
        turn({
          seq: 2,
          text: "Hier ist noch ein Vorschlag.",
          suggestion: "Der neuere Vorschlag.",
          suggestion_state: "accepted",
        }),
      ],
    });
    renderPanel();

    const card = await screen.findByTestId("entity-interview-suggestion");
    expect(card.textContent).toContain("Der ältere Vorschlag.");
    expect(card.textContent).toContain(de["knowledge.interview.accept"]);
    expect(screen.getByTestId("entity-interview-transcript").textContent).toContain(
      de["knowledge.interview.accepted"],
    );
  });
});

describe("a failed turn keeps the writer's text", () => {
  it("names the failure, keeps the text and sends it again on retry", async () => {
    api.POST.mockResolvedValueOnce({
      data: undefined,
      error: { detail: { code: "extraction-failed", detail: "Die Antwort war nicht auswertbar." } },
      response: new Response(null, { status: 502 }),
    });
    renderPanel();
    await readySession();

    fireEvent.change(composer(), { target: { value: "Es stammt aus dem Labor von Lin." } });
    fireEvent.click(screen.getByTestId("entity-interview-send"));

    await screen.findByText(de["knowledge.interview.failedExtraction"]);
    expect(composer().value).toBe("Es stammt aus dem Labor von Lin.");
    expect(screen.getByPlaceholderText(de["knowledge.interview.placeholder"])).toBeTruthy();

    api.POST.mockResolvedValueOnce({ data: readback(), response: ok() });
    fireEvent.click(screen.getByTestId("entity-interview-retry"));
    await waitFor(() =>
      expect(api.POST).toHaveBeenLastCalledWith("/api/chat/sessions/{session_id}/turns", {
        params: { path: { session_id: SESSION_ID } },
        body: { text: "Es stammt aus dem Labor von Lin." },
      }),
    );
    await waitFor(() => expect(screen.queryByTestId("entity-interview-retry")).toBeNull());
  });
});

describe("a chip's failed turn promises no text", () => {
  it("names the failure without the composer clause and retries the chip's label", async () => {
    api.POST.mockResolvedValueOnce({
      data: undefined,
      error: { detail: { code: "provider-error", detail: "offline" } },
      response: new Response(null, { status: 502 }),
    });
    renderPanel();
    await readySession();

    // The plain path: the field was never typed in — the chip sends its own
    // label, so the typed answer's «Dein Text ist noch im Eingabefeld» would
    // name a text that never existed.
    fireEvent.click(screen.getByTestId("entity-interview-no-idea"));

    const failure = await screen.findByTestId("entity-interview-failure");
    expect(failure.textContent).not.toContain("Dein Text ist noch im Eingabefeld.");
    expect(within(failure).getByText(de["knowledge.interview.failedProviderChip"])).toBeTruthy();
    expect(composer().value).toBe("");
    expect(screen.getByTestId("entity-interview-retry")).toBeTruthy();

    // «Erneut versuchen» re-sends the failed body exactly: the chip's label
    // and its act, never the composer's (empty) draft.
    api.POST.mockResolvedValueOnce({ data: readback(), response: ok() });
    fireEvent.click(screen.getByTestId("entity-interview-retry"));
    await waitFor(() =>
      expect(api.POST).toHaveBeenLastCalledWith("/api/chat/sessions/{session_id}/turns", {
        params: { path: { session_id: SESSION_ID } },
        body: { text: de["knowledge.interview.noIdea"], act: "no-idea" },
      }),
    );
  });

  it("an unparseable chip answer wears its own sentence, without the composer clause", async () => {
    api.POST.mockResolvedValueOnce({
      data: undefined,
      error: { detail: { code: "extraction-failed", detail: "unparseable" } },
      response: new Response(null, { status: 502 }),
    });
    renderPanel();
    await readySession();

    fireEvent.click(screen.getByTestId("entity-interview-fill-all"));

    const failure = await screen.findByTestId("entity-interview-failure");
    expect(failure.textContent).not.toContain("Dein Text ist noch im Eingabefeld.");
    expect(within(failure).getByText(de["knowledge.interview.failedExtractionChip"])).toBeTruthy();
  });
});

describe("hiding is not ending", () => {
  it("the close button hides the panel and never closes the session", async () => {
    const { onClose } = renderPanel();
    await readySession();
    fireEvent.click(screen.getByTestId("entity-interview-close"));
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(api.POST).not.toHaveBeenCalled();
  });
});

describe("the conversation outlives the panel's hide", () => {
  it("a reply landing while hidden is there on reopen, and a reopened turn still thinks", async () => {
    detail = sessionDetail({ proposal: proposal({ name: "Resonanz-Transponder LC-89" }) });
    const first = deferred();
    api.POST.mockImplementationOnce(() => first.promise);
    const { show } = renderPanel();
    await readySession();

    // Half one: the turn is released while the panel is hidden. Reopening
    // shows the answer and a free composer — not a turn that looks running.
    fireEvent.change(composer(), { target: { value: "Es stammt aus dem Labor von Lin." } });
    fireEvent.click(screen.getByTestId("entity-interview-send"));
    await screen.findByText(de["knowledge.interview.thinking"]);
    show(undefined);
    expect(screen.queryByTestId("entity-interview")).toBeNull();

    detail = sessionDetail({
      proposal: proposal({ name: "Resonanz-Transponder LC-89" }),
      turns: [
        turn({ seq: 1, role: "user", text: "Es stammt aus dem Labor von Lin." }),
        turn({ seq: 2, text: "Notiert." }),
      ],
    });
    const reads = sessionReads();
    first.settle({ data: readback(), response: ok() });
    // The settle's own refetch is the marker that the reply landed — and the
    // panel is still hidden while it does.
    await waitFor(() => expect(sessionReads()).toBeGreaterThan(reads));
    expect(screen.queryByTestId("entity-interview")).toBeNull();

    show(SESSION_ID);
    await waitFor(() => expect(composerField().disabled).toBe(false));
    expect(screen.queryByText(de["knowledge.interview.thinking"])).toBeNull();
    await waitFor(() =>
      expect(screen.getByTestId("entity-interview-transcript").textContent).toContain("Notiert."),
    );

    // Half two: reopened before its release, the turn still runs and the
    // panel must not look idle. The save waits for the same answer.
    const second = deferred();
    api.POST.mockImplementationOnce(() => second.promise);
    fireEvent.change(composer(), { target: { value: "Noch ein Detail." } });
    fireEvent.click(screen.getByTestId("entity-interview-send"));
    await screen.findByText(de["knowledge.interview.thinking"]);

    show(undefined);
    expect(screen.queryByTestId("entity-interview")).toBeNull();

    show(SESSION_ID);
    expect(screen.getByText(de["knowledge.interview.thinking"])).toBeTruthy();
    expect(composerField().disabled).toBe(true);
    expect((screen.getByTestId("entity-interview-save") as HTMLButtonElement).disabled).toBe(true);

    // The settle's refetch is the transcript's own truth: the reply stands
    // there, not merely as the mutation's answer.
    detail = sessionDetail({
      proposal: proposal({ name: "Resonanz-Transponder LC-89" }),
      turns: [
        turn({ seq: 1, role: "user", text: "Es stammt aus dem Labor von Lin." }),
        turn({ seq: 2, text: "Notiert." }),
        turn({ seq: 3, role: "user", text: "Noch ein Detail." }),
        turn({ seq: 4, text: "Notiert, noch ein Detail." }),
      ],
    });
    second.settle({ data: readback({ seq: 4 }), response: ok() });
    await waitFor(() => expect(composerField().disabled).toBe(false));
    expect(screen.queryByText(de["knowledge.interview.thinking"])).toBeNull();
    await waitFor(() =>
      expect(screen.getByTestId("entity-interview-transcript").textContent).toContain(
        "Notiert, noch ein Detail.",
      ),
    );
  });

  it("a turn that fails while hidden keeps its face and the sent text", async () => {
    detail = sessionDetail({ proposal: proposal({ name: "Resonanz-Transponder LC-89" }) });
    let fail: (value: unknown) => void = () => {};
    const held = new Promise((resolve) => {
      fail = resolve;
    });
    api.POST.mockImplementation(() => held);
    const { show } = renderPanel();
    await readySession();

    fireEvent.change(composer(), { target: { value: "Es stammt aus dem Labor von Lin." } });
    fireEvent.click(screen.getByTestId("entity-interview-send"));
    await screen.findByText(de["knowledge.interview.thinking"]);

    show(undefined);
    fail({
      data: undefined,
      error: { detail: { code: "provider-error", detail: "offline" } },
      response: new Response(null, { status: 502 }),
    });

    show(SESSION_ID);
    const failure = await screen.findByTestId("entity-interview-failure");
    expect(failure.textContent).toContain(de["knowledge.interview.failedProvider"]);
    expect(composer().value).toBe("Es stammt aus dem Labor von Lin.");

    // «Erneut versuchen» re-sends the body the hidden turn failed with.
    api.POST.mockResolvedValueOnce({ data: readback(), response: ok() });
    fireEvent.click(screen.getByTestId("entity-interview-retry"));
    await waitFor(() =>
      expect(api.POST).toHaveBeenLastCalledWith("/api/chat/sessions/{session_id}/turns", {
        params: { path: { session_id: SESSION_ID } },
        body: { text: "Es stammt aus dem Labor von Lin." },
      }),
    );
  });

  it("an unsent draft survives hiding", async () => {
    const { show } = renderPanel();
    await readySession();

    fireEvent.change(composer(), { target: { value: "Ein Name für später." } });
    show(undefined);
    show(SESSION_ID);

    await waitFor(() => expect(composer().value).toBe("Ein Name für später."));
  });

  it("each interview keeps its own draft and failure across a switch", async () => {
    detail = sessionDetail({ proposal: proposal({ name: "Resonanz-Transponder LC-89" }) });
    api.GET.mockImplementation(
      readsById(sessionDetail({ id: SECOND_ID, entity_type: "location" })),
    );
    api.POST.mockResolvedValueOnce({
      data: undefined,
      error: { detail: { code: "provider-error", detail: "offline" } },
      response: new Response(null, { status: 502 }),
    });
    const { show } = renderPanel();
    await readySession();

    fireEvent.change(composer(), { target: { value: "Bleibt hier." } });
    fireEvent.click(screen.getByTestId("entity-interview-send"));
    await screen.findByTestId("entity-interview-failure");
    expect(composer().value).toBe("Bleibt hier.");

    // The other interview starts clean: nothing of A's failure or text.
    show(SECOND_ID);
    await readySession();
    expect(screen.queryByTestId("entity-interview-failure")).toBeNull();
    expect(composer().value).toBe("");

    // The first one still holds its own failure and the text it was sent with.
    show(SESSION_ID);
    await readySession();
    await screen.findByTestId("entity-interview-failure");
    expect(composer().value).toBe("Bleibt hier.");
  });

  it("an unsent draft is each interview's own across a switch", async () => {
    detail = sessionDetail({ proposal: proposal({ name: "Resonanz-Transponder LC-89" }) });
    api.GET.mockImplementation(
      readsById(sessionDetail({ id: SECOND_ID, entity_type: "location" })),
    );
    const { show } = renderPanel();
    await readySession();
    fireEvent.change(composer(), { target: { value: "Ein Name für später." } });

    show(SECOND_ID);
    await readySession();
    expect(composer().value).toBe("");
    fireEvent.change(composer(), { target: { value: "Für B." } });

    show(SESSION_ID);
    await readySession();
    expect(composer().value).toBe("Ein Name für später.");

    show(SECOND_ID);
    await readySession();
    expect(composer().value).toBe("Für B.");
  });

  it("a hidden session's 404 waits for the panel to be shown again", async () => {
    const { show, onSelectSession } = renderPanel();
    await readySession();
    const sessionReads = () =>
      api.GET.mock.calls.filter(([path]) => path === "/api/chat/sessions/{session_id}").length;
    const before = sessionReads();

    api.GET.mockImplementation((path: string) => {
      if (path === "/api/chat/sessions") {
        return Promise.resolve({ data: { items: sessions }, response: ok() });
      }
      return Promise.resolve({
        data: undefined,
        error: { detail: { code: "not-found", detail: "no such session" } },
        response: new Response(null, { status: 404 }),
      });
    });

    show(undefined);
    void queryClient.invalidateQueries({ queryKey: ["chat", "session", SESSION_ID] });
    await waitFor(() => expect(sessionReads()).toBeGreaterThan(before));
    await waitFor(() =>
      expect(queryClient.getQueryState(["chat", "session", SESSION_ID])?.status).toBe("error"),
    );
    // The hidden read must not take the writer to the chooser behind their back.
    expect(onSelectSession).not.toHaveBeenCalled();

    show(SESSION_ID);
    await waitFor(() => expect(onSelectSession).toHaveBeenCalledWith("new"));
  });

  it("a turn's 404 that lands while hidden does not open the chooser", async () => {
    let fail: (value: unknown) => void = () => {};
    const held = new Promise((resolve) => {
      fail = resolve;
    });
    api.POST.mockImplementation(() => held);
    const { show, onSelectSession } = renderPanel();
    await readySession();

    fireEvent.change(composer(), { target: { value: "Noch eine Antwort." } });
    fireEvent.click(screen.getByTestId("entity-interview-send"));
    await screen.findByText(de["knowledge.interview.thinking"]);
    show(undefined);

    // The session vanished mid-turn: the settle refetch answers the same 404
    // the read would, and neither may open the panel behind the writer.
    api.GET.mockImplementation((path: string) => {
      if (path === "/api/chat/sessions") {
        return Promise.resolve({ data: { items: sessions }, response: ok() });
      }
      return Promise.resolve({
        data: undefined,
        error: { detail: { code: "not-found", detail: "no such session" } },
        response: new Response(null, { status: 404 }),
      });
    });
    fail({
      data: undefined,
      error: { detail: { code: "not-found", detail: "no such session" } },
      response: new Response(null, { status: 404 }),
    });
    await waitFor(() =>
      expect(queryClient.getQueryState(["chat", "session", SESSION_ID])?.status).toBe("error"),
    );
    expect(onSelectSession).not.toHaveBeenCalled();

    show(SESSION_ID);
    await waitFor(() => expect(onSelectSession).toHaveBeenCalledWith("new"));
  });
});

describe("a turn belongs to the session it was sent for", () => {
  /** The interview the writer moves on to: nothing of A's may appear in it. */
  function secondSession(): AssistantSession {
    return sessionDetail({
      id: SECOND_ID,
      entity_type: "location",
      proposal: proposal({ name: "Forschungsstation" }),
    });
  }

  it("a reply for the interview the writer left leaves this one quiet", async () => {
    detail = sessionDetail({ proposal: proposal({ name: "Resonanz-Transponder LC-89" }) });
    api.GET.mockImplementation(readsById(secondSession()));
    let release: (value: unknown) => void = () => {};
    const held = new Promise((resolve) => {
      release = resolve;
    });
    api.POST.mockImplementation(() => held);

    const { show } = renderPanel();
    await readySession();
    fireEvent.change(composer(), { target: { value: "Es stammt aus dem Labor von Lin." } });
    fireEvent.click(screen.getByTestId("entity-interview-send"));
    await screen.findByText(de["knowledge.interview.thinking"]);

    // The writer moves on while A's answer is still on its way: A's turn is
    // no reason for B to look busy or to keep B's composer closed.
    show(SECOND_ID);
    await readySession();
    expect(screen.queryByText(de["knowledge.interview.thinking"])).toBeNull();
    expect(composerField().disabled).toBe(false);

    fireEvent.change(composer(), { target: { value: "Gehört zu B." } });
    const reads = sessionReads();
    detail = sessionDetail({
      proposal: proposal({ name: "Resonanz-Transponder LC-89" }),
      turns: [
        turn({ seq: 1, role: "user", text: "Es stammt aus dem Labor von Lin." }),
        turn({ seq: 2, text: "Notiert." }),
      ],
    });
    release({ data: readback(), response: ok() });
    // The settle invalidates the family; B's own read is the anchor.
    await waitFor(() => expect(sessionReads()).toBeGreaterThan(reads));

    // A's answer is A's: it neither reaches B's transcript nor its composer.
    expect(composer().value).toBe("Gehört zu B.");
    expect(screen.getByTestId("entity-interview-transcript").textContent).not.toContain("Notiert.");

    // The interview the writer left kept its own answer: its transcript holds
    // the reply, its composer is empty and no failure stands.
    show(SESSION_ID);
    await readySession();
    expect(composer().value).toBe("");
    expect(screen.queryByTestId("entity-interview-failure")).toBeNull();
    await waitFor(() =>
      expect(screen.getByTestId("entity-interview-transcript").textContent).toContain("Notiert."),
    );
  });

  it("a failure of the interview the writer left shows no face here", async () => {
    detail = sessionDetail({ proposal: proposal({ name: "Resonanz-Transponder LC-89" }) });
    api.GET.mockImplementation(readsById(secondSession()));
    let fail: (value: unknown) => void = () => {};
    const held = new Promise((resolve) => {
      fail = resolve;
    });
    api.POST.mockImplementation(() => held);

    const { show } = renderPanel();
    await readySession();
    fireEvent.change(composer(), { target: { value: "Es stammt aus dem Labor von Lin." } });
    fireEvent.click(screen.getByTestId("entity-interview-send"));
    await screen.findByText(de["knowledge.interview.thinking"]);

    show(SECOND_ID);
    await readySession();
    const reads = sessionReads();
    fail({
      data: undefined,
      error: { detail: { code: "provider-error", detail: "offline" } },
      response: new Response(null, { status: 502 }),
    });
    await waitFor(() => expect(sessionReads()).toBeGreaterThan(reads));

    // A's failure (and A's failed body) never land in B: no face, and no
    // retry that would send A's text through B's session.
    expect(screen.queryByTestId("entity-interview-failure")).toBeNull();
    expect(screen.queryByTestId("entity-interview-retry")).toBeNull();
  });

  it("a 404 of the interview the writer left does not open the chooser here", async () => {
    detail = sessionDetail({ proposal: proposal({ name: "Resonanz-Transponder LC-89" }) });
    api.GET.mockImplementation(readsById(secondSession()));
    let fail: (value: unknown) => void = () => {};
    const held = new Promise((resolve) => {
      fail = resolve;
    });
    api.POST.mockImplementation(() => held);

    const { show, onSelectSession } = renderPanel();
    await readySession();
    fireEvent.change(composer(), { target: { value: "Noch eine Antwort." } });
    fireEvent.click(screen.getByTestId("entity-interview-send"));
    await screen.findByText(de["knowledge.interview.thinking"]);

    show(SECOND_ID);
    await readySession();
    const reads = sessionReads();
    fail({
      data: undefined,
      error: { detail: { code: "not-found", detail: "no such session" } },
      response: new Response(null, { status: 404 }),
    });
    await waitFor(() => expect(sessionReads()).toBeGreaterThan(reads));

    // A vanished; B did not. The chooser is not B's answer.
    expect(onSelectSession).not.toHaveBeenCalled();
    expect(screen.getByTestId("entity-interview-proposal").textContent).toContain("Forschungsstation");
  });

  it("an answer still out marks its own interview when the writer returns to it", async () => {
    detail = sessionDetail({ proposal: proposal({ name: "Resonanz-Transponder LC-89" }) });
    const second = secondSession();
    api.GET.mockImplementation(readsById(second));
    let releaseA: (value: unknown) => void = () => {};
    let releaseB: (value: unknown) => void = () => {};
    const heldA = new Promise((resolve) => {
      releaseA = resolve;
    });
    const heldB = new Promise((resolve) => {
      releaseB = resolve;
    });
    api.POST.mockImplementationOnce(() => heldA).mockImplementationOnce(() => heldB);

    const { show } = renderPanel();
    await readySession();
    fireEvent.change(composer(), { target: { value: "Es stammt aus dem Labor von Lin." } });
    fireEvent.click(screen.getByTestId("entity-interview-send"));
    await screen.findByText(de["knowledge.interview.thinking"]);

    // A's answer is still out; the writer answers B meanwhile.
    show(SECOND_ID);
    await readySession();
    expect(screen.queryByText(de["knowledge.interview.thinking"])).toBeNull();
    fireEvent.change(composer(), { target: { value: "Gehört zu B." } });
    fireEvent.click(screen.getByTestId("entity-interview-send"));
    await screen.findByText(de["knowledge.interview.thinking"]);

    // Back in A before its answer lands: A's own turn still runs, whoever
    // was sent after it. Its composer, save door and end button wait.
    show(SESSION_ID);
    await readySession();
    expect(screen.getByText(de["knowledge.interview.thinking"])).toBeTruthy();
    expect(composerField().disabled).toBe(true);
    expect((screen.getByTestId("entity-interview-save") as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByTestId("entity-interview-end") as HTMLButtonElement).disabled).toBe(true);

    detail = sessionDetail({
      proposal: proposal({ name: "Resonanz-Transponder LC-89" }),
      turns: [
        turn({ seq: 1, role: "user", text: "Es stammt aus dem Labor von Lin." }),
        turn({ seq: 2, text: "Notiert." }),
      ],
    });
    releaseA({ data: readback(), response: ok() });
    await waitFor(() => expect(composerField().disabled).toBe(false));
    expect(screen.queryByText(de["knowledge.interview.thinking"])).toBeNull();
    await waitFor(() =>
      expect(screen.getByTestId("entity-interview-transcript").textContent).toContain("Notiert."),
    );

    // A's settle leaves B alone: B's own turn is still out.
    show(SECOND_ID);
    await readySession();
    expect(screen.getByText(de["knowledge.interview.thinking"])).toBeTruthy();
    expect(composerField().disabled).toBe(true);

    second.turns = [
      turn({ seq: 1, role: "user", text: "Gehört zu B." }),
      turn({ seq: 2, text: "Notiert." }),
    ];
    releaseB({ data: readback(), response: ok() });
    await waitFor(() => expect(composerField().disabled).toBe(false));
    expect(screen.queryByText(de["knowledge.interview.thinking"])).toBeNull();
    // B's own answer landed in B's transcript, exactly as A's did in A's:
    // the release is the refetch's truth, not just the mutation's promise.
    await waitFor(() =>
      expect(screen.getByTestId("entity-interview-transcript").textContent).toContain("Notiert."),
    );

    // The count cannot leak: after both answers landed, both are idle.
    show(SESSION_ID);
    await readySession();
    expect(screen.queryByText(de["knowledge.interview.thinking"])).toBeNull();
    expect(composerField().disabled).toBe(false);
  });

  it("a failure of the interview the writer left is there when they return", async () => {
    detail = sessionDetail({ proposal: proposal({ name: "Resonanz-Transponder LC-89" }) });
    const second = secondSession();
    api.GET.mockImplementation(readsById(second));
    let releaseA: (value: unknown) => void = () => {};
    const heldA = new Promise((resolve) => {
      releaseA = resolve;
    });
    api.POST.mockImplementationOnce(() => heldA).mockImplementation(() => new Promise<never>(() => {}));
    const sent = "Es stammt aus dem Labor von Lin.";

    const { show } = renderPanel();
    await readySession();
    fireEvent.change(composer(), { target: { value: sent } });
    fireEvent.click(screen.getByTestId("entity-interview-send"));
    await screen.findByText(de["knowledge.interview.thinking"]);

    // The writer moves on; B holds a draft of its own.
    show(SECOND_ID);
    await readySession();
    fireEvent.change(composer(), { target: { value: "Gehört zu B." } });

    // A fails while B is shown: nothing of it lands in B.
    releaseA({
      data: undefined,
      error: { detail: { code: "provider-error", detail: "offline" } },
      response: new Response(null, { status: 502 }),
    });
    await waitFor(() => expect(composer().value).toBe("Gehört zu B."));
    expect(screen.queryByTestId("entity-interview-failure")).toBeNull();
    expect(screen.queryByTestId("entity-interview-retry")).toBeNull();

    // Back in A: its own failure, its own text — the switch did not erase the
    // turn that failed while the writer was away.
    show(SESSION_ID);
    await readySession();
    const failure = await screen.findByTestId("entity-interview-failure");
    expect(failure.textContent).toContain(de["knowledge.interview.failedProvider"]);
    expect(composer().value).toBe(sent);

    // «Erneut versuchen» sends A's body to A, not to the interview shown
    // when the turn failed.
    api.POST.mockResolvedValueOnce({ data: readback(), response: ok() });
    fireEvent.click(screen.getByTestId("entity-interview-retry"));
    await waitFor(() =>
      expect(api.POST).toHaveBeenLastCalledWith("/api/chat/sessions/{session_id}/turns", {
        params: { path: { session_id: SESSION_ID } },
        body: { text: sent },
      }),
    );
  });

  it("a 404 of the interview the writer returned to sends it to the chooser", async () => {
    detail = sessionDetail({ proposal: proposal({ name: "Resonanz-Transponder LC-89" }) });
    const second = secondSession();
    api.GET.mockImplementation(readsById(second));
    let releaseA: (value: unknown) => void = () => {};
    const heldA = new Promise((resolve) => {
      releaseA = resolve;
    });
    api.POST.mockImplementationOnce(() => heldA).mockImplementation(() => new Promise<never>(() => {}));

    const { show, onSelectSession } = renderPanel();
    await readySession();
    fireEvent.change(composer(), { target: { value: "Noch eine Antwort." } });
    fireEvent.click(screen.getByTestId("entity-interview-send"));
    await screen.findByText(de["knowledge.interview.thinking"]);

    show(SECOND_ID);
    await readySession();
    fireEvent.change(composer(), { target: { value: "Gehört zu B." } });
    fireEvent.click(screen.getByTestId("entity-interview-send"));
    await screen.findByText(de["knowledge.interview.thinking"]);

    // A vanished while the writer was in B; back in A, its own failure is
    // the one that hands this panel back to the chooser.
    show(SESSION_ID);
    await readySession();
    releaseA({
      data: undefined,
      error: { detail: { code: "not-found", detail: "no such session" } },
      response: new Response(null, { status: 404 }),
    });
    await waitFor(() => expect(onSelectSession).toHaveBeenCalledWith("new"));
  });

  it("a close of the other interview reports nothing here, while this one still does", async () => {
    detail = sessionDetail({ proposal: proposal({ name: "Resonanz-Transponder LC-89" }) });
    api.GET.mockImplementation(readsById(secondSession()));
    api.POST.mockImplementation((path: string) =>
      path === "/api/chat/sessions/{session_id}/close"
        ? Promise.resolve({
            data: undefined,
            error: { detail: { code: "provider-error", detail: "offline" } },
            response: new Response(null, { status: 500 }),
          })
        : Promise.resolve({ data: readback(), response: ok() }),
    );
    const { show } = renderPanel();
    await readySession();
    fireEvent.click(screen.getByTestId("entity-interview-end"));
    await screen.findByText(de["knowledge.interview.endFailed"]);

    // A's failed close is A's; B's footer owes no explanation for it.
    show(SECOND_ID);
    await readySession();
    expect(screen.queryByText(de["knowledge.interview.endFailed"])).toBeNull();

    // B's own failed close still names itself.
    fireEvent.click(screen.getByTestId("entity-interview-end"));
    await screen.findByText(de["knowledge.interview.endFailed"]);
  });
});

describe("showing the panel asks its session read again", () => {
  it("a session hidden for a while is read again when the panel is shown", async () => {
    const { show } = renderPanel();
    await readySession();
    const before = sessionReads();

    show(undefined);
    show(SESSION_ID);

    await waitFor(() => expect(sessionReads()).toBe(before + 1));
  });

  it("the chooser has no session to ask for", async () => {
    const { show } = renderPanel();
    await readySession();
    const before = sessionReads();

    show(undefined);
    show(null);
    await screen.findByTestId("entity-interview-type-object");

    expect(sessionReads()).toBe(before);
  });
});

describe("the wire's refusals find their own face", () => {
  it("a session closed elsewhere answers 409 and becomes the ended face", async () => {
    api.POST.mockImplementation(() => {
      detail = { ...detail, closed_at: "2026-11-24T14:30:00Z" };
      return Promise.resolve({
        data: undefined,
        error: { detail: { code: "session-closed", detail: "the interview ended" } },
        response: new Response(null, { status: 409 }),
      });
    });
    renderPanel();
    await readySession();
    fireEvent.change(composer(), { target: { value: "Noch eine Antwort." } });
    fireEvent.click(screen.getByTestId("entity-interview-send"));

    await screen.findByText(de["knowledge.interview.endedBanner"]);
    expect(screen.queryByPlaceholderText(de["knowledge.interview.placeholder"])).toBeNull();
  });

  it("a stale suggestion wears its own face, offers no retry and refetches the session", async () => {
    detail = sessionDetail({
      turns: [turn({ seq: 1, suggestion: "Ein Vorschlag.", suggestion_state: "pending" })],
    });
    api.POST.mockResolvedValueOnce({
      data: undefined,
      error: {
        detail: { code: "suggestion-mismatch", detail: "there is no pending suggestion to accept" },
      },
      response: new Response(null, { status: 422 }),
    });
    renderPanel();
    await screen.findByTestId("entity-interview-suggestion");
    const reads = () =>
      api.GET.mock.calls.filter(([path]) => path === "/api/chat/sessions/{session_id}").length;
    const before = reads();

    // The other tab settled it first: the next read carries the settled state,
    // so the panel must show that rather than re-send the stale acceptance.
    detail = sessionDetail({
      turns: [turn({ seq: 1, suggestion: "Ein Vorschlag.", suggestion_state: "accepted" })],
    });
    fireEvent.click(screen.getByTestId("entity-interview-suggestion-accept"));

    await screen.findByText(de["knowledge.interview.failure.suggestion-mismatch"]);
    expect(screen.queryByTestId("entity-interview-retry")).toBeNull();
    await waitFor(() => expect(reads()).toBeGreaterThan(before));
    await waitFor(() => expect(screen.queryByTestId("entity-interview-suggestion")).toBeNull());
  });

  it("a missing model names the settings door beside the retry", async () => {
    api.POST.mockResolvedValueOnce({
      data: undefined,
      error: {
        detail: { code: "provider-unavailable", detail: "no serving tier for chat.ask" },
      },
      response: new Response(null, { status: 502 }),
    });
    renderPanel();
    await readySession();
    fireEvent.change(composer(), { target: { value: "Noch eine Antwort." } });
    fireEvent.click(screen.getByTestId("entity-interview-send"));

    const failure = await screen.findByTestId("entity-interview-failure");
    expect(within(failure).getByText(de["knowledge.interview.failedUnavailable"])).toBeTruthy();
    const door = screen.getByTestId("entity-interview-settings-door");
    expect(door.getAttribute("href")).toBe("/settings/ai-regeln");
    expect(door.textContent).toBe(de["knowledge.interview.settingsDoor"]);
    // The model may be there by the time the writer returns: the retry stands.
    expect(screen.getByTestId("entity-interview-retry")).toBeTruthy();
    expect(screen.queryByTestId("entity-interview-prompt-door")).toBeNull();
  });

  it("a refused prompt opens the prompt editor and offers no retry", async () => {
    api.POST.mockResolvedValueOnce({
      data: undefined,
      error: {
        detail: { code: "prompt-refused", detail: "the override renders no text" },
      },
      response: new Response(null, { status: 502 }),
    });
    renderPanel();
    await readySession();
    fireEvent.change(composer(), { target: { value: "Noch eine Antwort." } });
    fireEvent.click(screen.getByTestId("entity-interview-send"));

    const failure = await screen.findByTestId("entity-interview-failure");
    expect(within(failure).getByText(de["knowledge.interview.failedPrompt"])).toBeTruthy();
    const door = screen.getByTestId("entity-interview-prompt-door");
    expect(door.getAttribute("href")).toBe("/settings/prompts");
    expect(door.textContent).toBe(de["knowledge.interview.promptDoor"]);
    // Sending the same body again cannot repair the prompt.
    expect(screen.queryByTestId("entity-interview-retry")).toBeNull();
    expect(screen.queryByTestId("entity-interview-settings-door")).toBeNull();
  });

  it("an unknown refusal keeps its wire code beside the generic copy", async () => {
    api.POST.mockResolvedValueOnce({
      data: undefined,
      error: { detail: { code: "rate-limited", detail: "the provider asked us to wait" } },
      response: new Response(null, { status: 502 }),
    });
    renderPanel();
    await readySession();

    fireEvent.change(composer(), { target: { value: "Noch eine Antwort." } });
    fireEvent.click(screen.getByTestId("entity-interview-send"));

    const failure = await screen.findByTestId("entity-interview-failure");
    // The closed set names its own copy; an unknown code falls back to the
    // generic sentence and shows the raw code beside it, never the wire's
    // English detail.
    expect(within(failure).getByText(de["knowledge.interview.failedProvider"])).toBeTruthy();
    expect(within(failure).getByText("rate-limited")).toBeTruthy();
    expect(failure.textContent).not.toContain("the provider asked us to wait");
    expect(screen.getByTestId("entity-interview-retry")).toBeTruthy();
    expect(composer().value).toBe("Noch eine Antwort.");
  });

  it("a missing session hands the panel back to the chooser", async () => {
    api.GET.mockImplementation((path: string) => {
      if (path === "/api/chat/sessions") {
        return Promise.resolve({ data: { items: sessions }, response: ok() });
      }
      if (path === "/api/chat/sessions/{session_id}") {
        return Promise.resolve({
          data: undefined,
          error: { detail: { code: "not-found", detail: "no such session" } },
          response: new Response(null, { status: 404 }),
        });
      }
      throw new Error(`unexpected GET: ${path}`);
    });
    const { onSelectSession } = renderPanel();
    await waitFor(() => expect(onSelectSession).toHaveBeenCalledWith("new"));
  });
});

describe("ending makes it read-only", () => {
  it("removes the composer, keeps the proposal and closes the session", async () => {
    detail = sessionDetail({ proposal: proposal({ name: "Resonanz-Transponder LC-89" }) });
    api.POST.mockImplementation((path: string) => {
      if (path === "/api/chat/sessions/{session_id}/close") {
        detail = { ...detail, closed_at: "2026-11-24T14:30:00Z" };
        return Promise.resolve({ data: detail, response: ok() });
      }
      return Promise.resolve({ data: readback(), response: ok() });
    });
    renderPanel();
    await readySession();

    fireEvent.click(screen.getByTestId("entity-interview-end"));

    await screen.findByText(de["knowledge.interview.endedBanner"]);
    expect(screen.queryByPlaceholderText(de["knowledge.interview.placeholder"])).toBeNull();
    expect(screen.getByTestId("entity-interview-proposal").textContent).toContain("Resonanz-Transponder LC-89");
    expect(api.POST).toHaveBeenCalledWith("/api/chat/sessions/{session_id}/close", {
      params: { path: { session_id: SESSION_ID } },
    });
  });

  it("a failed close reports beside the footer and leaves the action standing", async () => {
    detail = sessionDetail({ proposal: proposal({ name: "Resonanz-Transponder LC-89" }) });
    api.POST.mockResolvedValueOnce({
      data: undefined,
      error: { detail: { code: "provider-error", detail: "offline" } },
      response: new Response(null, { status: 500 }),
    });
    renderPanel();
    await readySession();
    const end = screen.getByTestId("entity-interview-end") as HTMLButtonElement;
    fireEvent.click(end);

    await screen.findByText(de["knowledge.interview.endFailed"]);
    expect(end.disabled).toBe(false);

    api.POST.mockImplementation(() => {
      detail = { ...detail, closed_at: "2026-11-24T14:30:00Z" };
      return Promise.resolve({ data: detail, response: ok() });
    });
    fireEvent.click(end);
    await screen.findByText(de["knowledge.interview.endedBanner"]);
    expect(screen.queryByText(de["knowledge.interview.endFailed"])).toBeNull();
  });
});

describe("the proposal becomes an entity", () => {
  it("the save door is enabled only by a ready proposal and hands the prefill over", async () => {
    detail = sessionDetail({ proposal: proposal({ name: null }) });
    const { onSave } = renderPanel();
    await readySession();

    const save = screen.getByTestId("entity-interview-save") as HTMLButtonElement;
    expect(save.disabled).toBe(true);
    expect(save.textContent).toBe(de["knowledge.interview.saveAsEntity"]);

    // The proposal gains its name: the door opens and maps the whole draft.
    detail = sessionDetail({
      proposal: proposal({
        name: "Resonanz-Transponder LC-89",
        aliases: ["LC-89"],
        tags: ["Technologie"],
        content: "Ein Relais.",
        suggested: { aliases: ["LC-89"], tags: ["Technologie"], content: true },
        relations: [{ target: "Forschungsstation", type: "related_to", note: "", suggested: true }],
      }),
    });
    await queryClient.invalidateQueries({ queryKey: ["chat", "session", SESSION_ID] });
    await waitFor(() => expect((screen.getByTestId("entity-interview-save") as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(screen.getByTestId("entity-interview-save"));

    expect(onSave).toHaveBeenCalledWith({
      name: "Resonanz-Transponder LC-89",
      type: "object",
      aliases: ["LC-89"],
      tags: ["Technologie"],
      content: "Ein Relais.",
      suggested: { aliases: ["LC-89"], tags: ["Technologie"], content: true },
      relations: [
        { target: "Forschungsstation", relation_type: "related_to", note: undefined, suggested: true },
      ],
    });
  });

  it("the save waits for the running turn", async () => {
    detail = sessionDetail({ proposal: proposal({ name: "Resonanz-Transponder LC-89" }) });
    let release: (value: { data: unknown; response: Response }) => void = () => {};
    api.POST.mockImplementation(() => new Promise((resolve) => { release = resolve; }));
    renderPanel();
    await readySession();

    const save = screen.getByTestId("entity-interview-save") as HTMLButtonElement;
    expect(save.disabled).toBe(false);

    // A turn is in flight: the proposal can still change under the save, so
    // the door waits until the landing answer has settled.
    fireEvent.change(composer(), { target: { value: "Es stammt aus dem Labor von Lin." } });
    fireEvent.click(screen.getByTestId("entity-interview-send"));
    await waitFor(() => expect(save.disabled).toBe(true));

    release({ data: readback(), response: ok() });
    await waitFor(() => expect(save.disabled).toBe(false));
  });

  it("an ended interview keeps the proposal savable", async () => {
    detail = sessionDetail({
      closed_at: "2026-11-24T14:30:00Z",
      proposal: proposal({ name: "Resonanz-Transponder LC-89" }),
    });
    renderPanel();
    await screen.findByText(de["knowledge.interview.endedBanner"]);

    const save = screen.getByTestId("entity-interview-save") as HTMLButtonElement;
    expect(save.disabled).toBe(false);
    expect(screen.getByTestId("entity-interview-new")).toBeTruthy();
    expect(screen.queryByTestId("entity-interview-end")).toBeNull();
  });

  it("an ended interview offers no write beside the save", async () => {
    detail = sessionDetail({
      closed_at: "2026-11-24T14:30:00Z",
      proposal: proposal({
        name: "Resonanz-Transponder LC-89",
        tags: ["Technologie"],
        suggested: { aliases: [], tags: ["Technologie"], content: false },
      }),
      turns: [turn({ seq: 1, suggestion: "Ein Vorschlag.", suggestion_state: "pending" })],
    });
    renderPanel();
    await screen.findByText(de["knowledge.interview.endedBanner"]);

    // The transcript is read-only: every action that would write or edit is
    // disabled, while the save door and «Neues Interview» stay open.
    for (const action of ["accept", "edit", "reject"]) {
      const button = screen.getByTestId(
        `entity-interview-suggestion-${action}`,
      ) as HTMLButtonElement;
      expect(button.disabled).toBe(true);
    }
    const drop = screen.getByTestId("entity-interview-drop-suggestions") as HTMLButtonElement;
    expect(drop.disabled).toBe(true);
    const save = screen.getByTestId("entity-interview-save") as HTMLButtonElement;
    expect(save.disabled).toBe(false);
    expect(screen.getByTestId("entity-interview-new")).toBeTruthy();
  });
});

describe("the door is shut for the interview the handover saved", () => {
  it("stays shut until the interview is ended, then the ended face re-livens it", async () => {
    detail = sessionDetail({ proposal: proposal({ name: "Resonanz-Transponder LC-89" }) });
    api.POST.mockImplementation((path: string) => {
      if (path === "/api/chat/sessions/{session_id}/close") {
        detail = { ...detail, closed_at: "2026-11-24T14:30:00Z" };
        return Promise.resolve({ data: detail, response: ok() });
      }
      return Promise.resolve({ data: readback(), response: ok() });
    });
    const onEnded = vi.fn();
    renderPanel(SESSION_ID, { handedOver: true, onEnded });
    await readySession();

    // The proposal became a row: the door the writer would press again is shut
    // while the interview still stands, and the page hears nothing yet.
    const save = screen.getByTestId("entity-interview-save") as HTMLButtonElement;
    expect(save.disabled).toBe(true);
    expect(onEnded).not.toHaveBeenCalled();

    fireEvent.click(screen.getByTestId("entity-interview-end"));
    await screen.findByText(de["knowledge.interview.endedBanner"]);
    // The design's residue: an ended interview's proposal stays savable, and
    // the ended face tells the page the handover's mark is spent.
    expect(save.disabled).toBe(false);
    expect(onEnded).toHaveBeenCalledWith(SESSION_ID);
  });

  it("stays shut when the same interview is hidden and reopened", async () => {
    detail = sessionDetail({ proposal: proposal({ name: "Resonanz-Transponder LC-89" }) });
    const { show } = renderPanel(SESSION_ID, { handedOver: true });
    await readySession();
    expect((screen.getByTestId("entity-interview-save") as HTMLButtonElement).disabled).toBe(true);

    // Hiding never closes the session; the page keeps its mark, so reopening
    // the same interview finds the door still shut.
    show(undefined);
    show(SESSION_ID);
    await readySession();
    expect((screen.getByTestId("entity-interview-save") as HTMLButtonElement).disabled).toBe(true);
  });

  it("a door shut while it holds focus hands focus to «Interview beenden»", async () => {
    detail = sessionDetail({ proposal: proposal({ name: "Resonanz-Transponder LC-89" }) });
    const { show } = renderPanel(SESSION_ID, { handedOver: false });
    await readySession();
    const save = screen.getByTestId("entity-interview-save") as HTMLButtonElement;
    save.focus();
    expect(document.activeElement).toBe(save);

    show(SESSION_ID, true);

    // The door is a dead control now: the one live action beside the banner
    // takes the focus instead of letting it fall to the body.
    const end = screen.getByTestId("entity-interview-end");
    await waitFor(() => expect(document.activeElement).toBe(end));
    expect((save as HTMLButtonElement).disabled).toBe(true);
  });
});
