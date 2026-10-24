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

  it("keeps the unmount abort when an earlier ask settles beside a later one", { timeout: 10_000 }, async () => {
    // The identity guard's witness. A second ask while the first streams
    // is UI-unreachable today — the button disables for the whole ask —
    // so the second ask is started the way a future affordance (a stop
    // button mid-answer) would start it: a real submit event through the
    // form's own onSubmit, the same entry point the button uses. No
    // module is mocked; both asks, both sockets and the unmount are real.
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

    // The second ask begins while the first is still held mid-answer.
    chatServer.answerWith = `data: ${JSON.stringify({ delta: "Zweite halbe Antwort" })}\n\n`;
    fireEvent.submit(container.querySelector("form")!);
    await waitFor(() => expect(answer.textContent).toContain("Zweite halbe Antwort"));
    expect(chatServer.asks).toHaveLength(2);

    // The first ask settles now: its finally runs — the button coming
    // back is the same finally's setAsking(false), so by then its cleanup
    // has already done whatever it did to the shared ref.
    chatServer.asks[0]!.finish();
    const askButton = screen.getByRole("button", { name: t("chat.ask") }) as HTMLButtonElement;
    await waitFor(() => expect(askButton.disabled).toBe(false));

    // The panel goes away with the second ask still streaming. Its
    // controller must have survived the first ask's cleanup: an
    // unconditional null would leave the unmount nothing to abort, and
    // the second connection would outlive its panel.
    cleanup();
    await Promise.race([
      chatServer.asks[1]!.closed,
      new Promise((_, reject) =>
        setTimeout(
          () => reject(new Error("the second ask lost its abort to the first ask's cleanup")),
          5_000,
        ),
      ),
    ]);
  });
});
