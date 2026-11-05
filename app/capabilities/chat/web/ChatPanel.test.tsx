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
