// @vitest-environment jsdom
/**
 * The chat panel's abort contract: closing the dock — or any other unmount —
 * while an answer is streaming stops the ask at the fetch, and a later ask
 * keeps that unmount abort even when an earlier ask's cleanup settles
 * beside it. The stand-in server holds the answer open mid-stream; an
 * unmounted panel that keeps its ask alive would leave the connection
 * open, while a clean abort tears it down. No module is mocked: the
 * panel, the fetch and the socket are real, only the answer's bytes are
 * the server's own (the LLM boundary's stand-in).
 */
import "./chatApiServer";

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterAll, beforeAll, afterEach, describe, expect, it } from "vitest";

import { t } from "@shell/lib/i18n";

import { chatServer, startChatServer, stopChatServer } from "./chatApiServer";
import { ChatPanel } from "./ChatPanel";

beforeAll(startChatServer);
afterAll(stopChatServer);

afterEach(() => {
  cleanup();
  for (const ask of chatServer.asks) ask.finish();
  chatServer.asks.length = 0;
  chatServer.hold = false;
  chatServer.answerWith = null;
  chatServer.failWith = null;
});

describe("ChatPanel's in-flight ask", () => {
  it("aborts when the panel unmounts mid-answer", { timeout: 10_000 }, async () => {
    chatServer.answerWith = `data: ${JSON.stringify({ delta: "Eine halbe Antwort" })}\n\n`;
    chatServer.hold = true; // the answer stays open: it is mid-stream, not done
    render(<ChatPanel />);
    const user = userEvent.setup();
    await user.type(
      await screen.findByLabelText(t("chat.questionLabel")),
      "Wo war der Leuchtturm?",
    );
    await user.click(screen.getByRole("button", { name: t("chat.ask") }));

    // The answer began streaming: the first delta is on screen, and the
    // server is holding the rest.
    const answer = screen.getByRole("region", { name: t("chat.answerLabel") });
    await waitFor(() => expect(answer.textContent).toContain("Eine halbe Antwort"));
    expect(chatServer.asks).toHaveLength(1);

    // The panel goes away — the dock closed, the route left. The ask must
    // not keep streaming into it: the fetch aborts, and the held response
    // sees its connection torn down. A panel that kept asking would leave
    // the connection open until the server gave up.
    cleanup();
    await Promise.race([
      chatServer.asks[0]!.closed,
      new Promise((_, reject) =>
        setTimeout(
          () => reject(new Error("the ask kept streaming after the panel unmounted")),
          5_000,
        ),
      ),
    ]);
  });

  it("names a mid-answer network failure instead of throwing it away", { timeout: 10_000 }, async () => {
    // A delta arrives, then the wire dies: the fetch's body read rejects
    // mid-stream. The rethrow this test pins away would leave the half
    // answer looking finished beside an unhandled rejection — the failure
    // belongs on the panel, exactly like a refusal does.
    chatServer.answerWith = `data: ${JSON.stringify({ delta: "Eine halbe Antwort" })}\n\n`;
    chatServer.hold = true; // the answer stays open: it is mid-answer, not done
    render(<ChatPanel />);
    const user = userEvent.setup();
    await user.type(
      await screen.findByLabelText(t("chat.questionLabel")),
      "Wo war der Leuchtturm?",
    );
    await user.click(screen.getByRole("button", { name: t("chat.ask") }));

    // The answer began streaming: the first delta is on screen, and the
    // server is holding the rest.
    const answer = screen.getByRole("region", { name: t("chat.answerLabel") });
    await waitFor(() => expect(answer.textContent).toContain("Eine halbe Antwort"));
    expect(chatServer.asks).toHaveLength(1);

    // The wire dies mid-answer. The panel must say failed — and settle.
    chatServer.asks[0]!.break();
    await waitFor(() =>
      expect(screen.getByRole("alert").textContent).toContain(t("chat.error")),
    );
    const askButton = screen.getByRole("button", { name: t("chat.ask") }) as HTMLButtonElement;
    await waitFor(() => expect(askButton.disabled).toBe(false)); // the finally ran
  });

  it("supersedes a mid-stream ask: the old socket tears down, the new one keeps its unmount abort", { timeout: 10_000 }, async () => {
    // The supersession contract. A second ask while the first streams is
    // UI-unreachable today — the button disables for the whole ask — so
    // the second ask is started the way a future affordance (a stop
    // button mid-answer, a re-ask) would start it: a real submit event
    // through the form's own onSubmit, the same entry point the button
    // uses. The ask's entry aborts the in-flight fetch: the old socket
    // tears down at once — no two answers stream into one panel — and the
    // unmount abort passes whole to the successor. No module is mocked;
    // both asks, both sockets and the unmount are real.
    chatServer.answerWith = `data: ${JSON.stringify({ delta: "Erste halbe Antwort" })}\n\n`;
    chatServer.hold = true;
    const { container } = render(<ChatPanel />);
    const user = userEvent.setup();
    await user.type(
      await screen.findByLabelText(t("chat.questionLabel")),
      "Wo war der Leuchtturm?",
    );
    await user.click(screen.getByRole("button", { name: t("chat.ask") }));
    const answer = screen.getByRole("region", { name: t("chat.answerLabel") });
    await waitFor(() => expect(answer.textContent).toContain("Erste halbe Antwort"));
    expect(chatServer.asks).toHaveLength(1);

    // The second ask begins while the first is still held mid-answer, and
    // the first connection dies here — superseded, not left streaming.
    chatServer.answerWith = `data: ${JSON.stringify({ delta: "Zweite halbe Antwort" })}\n\n`;
    fireEvent.submit(container.querySelector("form")!);
    await Promise.race([
      chatServer.asks[0]!.closed,
      new Promise((_, reject) =>
        setTimeout(
          () => reject(new Error("the superseded ask kept its connection open")),
          5_000,
        ),
      ),
    ]);
    // The superseded turn keeps its partial answer beside the new one: the
    // turn list replaces nothing, so both halves stay on screen — the new
    // answer below the old, in ask order.
    const turns = container.querySelectorAll("[data-turn]");
    expect(turns).toHaveLength(2);
    expect(turns[0]!.textContent).toContain("Erste halbe Antwort");
    await waitFor(() => expect(answer.textContent).toContain("Zweite halbe Antwort"));
    expect(chatServer.asks).toHaveLength(2);

    // The panel goes away with the second ask still streaming. Its
    // controller owns the ref now — the superseded ask's cleanup saw the
    // ref replaced and kept its hands off — so the unmount aborts the
    // survivor and its connection tears down.
    cleanup();
    await Promise.race([
      chatServer.asks[1]!.closed,
      new Promise((_, reject) =>
        setTimeout(
          () => reject(new Error("the second ask lost its abort in the supersession")),
          5_000,
        ),
      ),
    ]);
  });
});

describe("ChatPanel's conversation", () => {
  it("renders turns in order: each question first, then its answer", { timeout: 10_000 }, async () => {
    const { container } = render(<ChatPanel />);
    const user = userEvent.setup();
    const field = await screen.findByLabelText(t("chat.questionLabel"));

    chatServer.answerWith = `data: ${JSON.stringify({ delta: "Der Leuchtturm stand hinter der Düne." })}\n\n`;
    await user.type(field, "Wo war der Leuchtturm?");
    await user.click(screen.getByRole("button", { name: t("chat.ask") }));
    await waitFor(() => expect(container.querySelectorAll("[data-turn]")).toHaveLength(1));

    chatServer.answerWith = `data: ${JSON.stringify({ delta: "Der Hafen schlief." })}\n\n`;
    await user.clear(field);
    await user.type(field, "Wo lag der Hafen?");
    await user.click(screen.getByRole("button", { name: t("chat.ask") }));
    await waitFor(() => expect(container.querySelectorAll("[data-turn]")).toHaveLength(2));

    // The turns stand in ask order, and each turn reads question-first:
    // the question precedes the answer it was asked for.
    const turns = container.querySelectorAll("[data-turn]");
    const first = turns[0]!.textContent ?? "";
    const second = turns[1]!.textContent ?? "";
    expect(first).toContain("Wo war der Leuchtturm?");
    expect(first.indexOf("Wo war der Leuchtturm?")).toBeLessThan(
      first.indexOf("Der Leuchtturm stand hinter der Düne."),
    );
    expect(second).toContain("Wo lag der Hafen?");
    expect(second.indexOf("Wo lag der Hafen?")).toBeLessThan(second.indexOf("Der Hafen schlief."));
  });

  it("renders sources as chips carrying the document title", { timeout: 10_000 }, async () => {
    render(<ChatPanel />);
    const user = userEvent.setup();
    chatServer.answerWith =
      `data: ${JSON.stringify({ delta: "Der Leuchtturm stand hinter der Düne." })}\n\n` +
      `data: ${JSON.stringify({ sources: [{ chunk_id: "c1", document_title: "Notizen", text: "Der Leuchtturm war seit Jahren dunkel." }] })}\n\n`;
    await user.type(await screen.findByLabelText(t("chat.questionLabel")), "Wo war der Leuchtturm?");
    await user.click(screen.getByRole("button", { name: t("chat.ask") }));

    // The citation is a chip wearing the document's title — not a bare
    // string — and the quoted passage stays behind the toggle until asked.
    const chip = await screen.findByRole("button", { name: "Notizen" });
    expect(chip.getAttribute("aria-expanded")).toBe("false");
    expect(screen.queryByText("Der Leuchtturm war seit Jahren dunkel.")).toBeNull();
    await user.click(chip);
    expect(chip.getAttribute("aria-expanded")).toBe("true");
    // The passage renders only once its chip opens: presence is the pin —
    // the suite wears no jest-dom visibility matchers.
    const passage = screen.getByText("Der Leuchtturm war seit Jahren dunkel.");
    expect(passage.textContent).toContain("dunkel.");
  });

  it("shows the ask's progress while it streams", { timeout: 10_000 }, async () => {
    const { container } = render(<ChatPanel />);
    const user = userEvent.setup();
    chatServer.answerWith = `data: ${JSON.stringify({ delta: "Der Leuchtturm stand hinter der Düne." })}\n\n`;
    chatServer.hold = true; // the answer stays open: it is mid-stream, not done
    await user.type(await screen.findByLabelText(t("chat.questionLabel")), "Wo war der Leuchtturm?");
    await user.click(screen.getByRole("button", { name: t("chat.ask") }));

    // The in-flight ask is a running job: the "Läuft…" line, no bar — the
    // stream reports no share, only movement. The status carries no
    // accessible name (live-region roles prohibit naming), so the text is
    // read off the element, the suite's own alert pattern.
    const progress = await screen.findByRole("status");
    expect(progress.textContent).toContain(t("jobs.running"));
    expect(progress.getAttribute("data-job-status")).toBe("running");

    chatServer.asks[0]!.finish();
    await waitFor(() => expect(screen.queryByRole("status")).toBeNull());
    const answer = screen.getByRole("region", { name: t("chat.answerLabel") });
    expect(answer.textContent).toContain("Der Leuchtturm stand hinter der Düne.");
    expect(container.querySelectorAll("[data-turn]")).toHaveLength(1);
  });

  it("a refused ask renders a Notice with a retry that re-asks", { timeout: 10_000 }, async () => {
    render(<ChatPanel />);
    const user = userEvent.setup();
    chatServer.failWith = 500; // the ask is refused, like a dead provider
    await user.type(await screen.findByLabelText(t("chat.questionLabel")), "Wo war der Leuchtturm?");
    await user.click(screen.getByRole("button", { name: t("chat.ask") }));

    // The refusal is a Notice with a way back — not a dead end.
    await screen.findByRole("alert");
    const retry = await screen.findByRole("button", { name: t("settings.retry") });
    chatServer.answerWith = `data: ${JSON.stringify({ delta: "Der Leuchtturm stand hinter der Düne." })}\n\n`;
    await user.click(retry);

    const answer = screen.getByRole("region", { name: t("chat.answerLabel") });
    await waitFor(() =>
      expect(answer.textContent).toContain("Der Leuchtturm stand hinter der Düne."),
    );
    await waitFor(() => expect(screen.queryByRole("alert")).toBeNull());
    expect(chatServer.asks).toHaveLength(2);
  });
});
