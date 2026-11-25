// @vitest-environment jsdom
/**
 * The interview panel (W9 Task 10) — the conversation and its faces, driven
 * through the real API seam (the client mocked at its module boundary, the
 * house pattern) and the real catalogs. The panel opens on the graph's
 * search parameter; this suite pins the controller and the faces it draws:
 * the chooser starts a typed session, every chip sends the act the wire
 * names, a failed turn keeps the writer's text and offers it again, hiding
 * the panel never closes the session, and ending it removes the composer
 * while the proposal stays readable.
 */
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, configure, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
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

function readback(overrides: Record<string, unknown> = {}) {
  return {
    reply: "Notiert.",
    proposal: detail.proposal,
    suggestion: null,
    seq: 9,
    ...overrides,
  };
}

function renderPanel(sessionId: string | null = SESSION_ID) {
  const onSelectSession = vi.fn();
  const onClose = vi.fn();
  const onManual = vi.fn();
  const onSave = vi.fn();
  render(
    <QueryClientProvider client={queryClient}>
      <EntityInterview
        novelId={NOVEL_ID}
        sessionId={sessionId}
        onSelectSession={onSelectSession}
        onClose={onClose}
        onManual={onManual}
        onSave={onSave}
      />
    </QueryClientProvider>,
  );
  return { onSelectSession, onClose, onManual, onSave };
}

function composer(): HTMLTextAreaElement {
  return screen.getByPlaceholderText(de["knowledge.interview.placeholder"]) as HTMLTextAreaElement;
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

describe("hiding is not ending", () => {
  it("the close button hides the panel and never closes the session", async () => {
    const { onClose } = renderPanel();
    await readySession();
    fireEvent.click(screen.getByTestId("entity-interview-close"));
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(api.POST).not.toHaveBeenCalled();
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
});
