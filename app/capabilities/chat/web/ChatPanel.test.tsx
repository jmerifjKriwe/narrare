// @vitest-environment jsdom
/**
 * The chat panel's abort contract: closing the dock — or any other unmount —
 * while an answer is streaming stops the ask at the fetch. The stand-in
 * server holds the answer open mid-stream; an unmounted panel that keeps its
 * ask alive would leave the connection open, while a clean abort tears it
 * down. No module is mocked: the panel, the fetch and the socket are real,
 * only the answer's bytes are the server's own (the LLM boundary's stand-in).
 */
import "./chatApiServer";

import { cleanup, render, screen, waitFor } from "@testing-library/react";
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
});
