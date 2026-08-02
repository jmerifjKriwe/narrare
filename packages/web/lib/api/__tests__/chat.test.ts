/**
 * chatApi.streamChat tests — SSE event discrimination for ADR-024 free-form chat.
 *
 * The SSE transport (`./streaming`) is mocked; each test captures the
 * `connectSSE` options and drives `onChunk` with typed chat events to verify
 * the client translates the meta/token/done discriminated stream into the
 * correct callbacks, including the optional-field fallbacks (missing
 * conversation_id, missing usage) and the transport error path.
 *
 * @module chat.test
 */

import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/streaming", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/streaming")>();
  return {
    ...actual,
    connectSSE: vi.fn(),
  };
});

import { chatApi } from "@/lib/api/chat";
import { connectSSE, type SSEOptions, SSEStreamError } from "@/lib/api/streaming";

const mockedConnectSSE = vi.mocked(connectSSE);

/** Local mirror of chat.ts's internal ChatStreamEvent shape. */
interface ChatStreamEvent {
  type?: "meta" | "token" | "done";
  conversation_id?: string;
  request_id?: string;
  text?: string;
  usage?: { prompt_tokens: number; completion_tokens: number; total_tokens: number };
}

interface Captured {
  options: SSEOptions<ChatStreamEvent>;
  onChunk: (event: ChatStreamEvent) => void;
}

function capture(): Captured {
  expect(mockedConnectSSE).toHaveBeenCalled();
  const options = mockedConnectSSE.mock.calls.at(-1)?.[0] as
    | SSEOptions<ChatStreamEvent>
    | undefined;
  expect(options).toBeDefined();
  return { options: options!, onChunk: options!.onChunk };
}

const ZERO_USAGE = { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 };

describe("chatApi.streamChat", () => {
  beforeEach(() => {
    mockedConnectSSE.mockClear();
  });

  it("POSTs to /chat with the body and forwards the abort signal", async () => {
    const body = { project_id: "project-1", message: "Hello", conversation_id: "conv-1" };
    const controller = new AbortController();

    await chatApi.streamChat(
      body,
      { onMeta: vi.fn(), onToken: vi.fn(), onDone: vi.fn(), onError: vi.fn() },
      controller.signal,
    );

    const { options } = capture();
    expect(options.url).toBe("/chat");
    expect(options.method).toBe("POST");
    expect(options.body).toEqual(body);
    expect(options.signal).toBe(controller.signal);
  });

  it("fires onMeta for a meta event, defaulting missing ids to empty strings", async () => {
    const onMeta = vi.fn();
    await chatApi.streamChat(
      { project_id: "p", message: "m" },
      { onMeta, onToken: vi.fn(), onDone: vi.fn(), onError: vi.fn() },
    );

    capture().onChunk({ type: "meta" });

    expect(onMeta).toHaveBeenCalledTimes(1);
    expect(onMeta).toHaveBeenCalledWith({ conversation_id: "", request_id: "" });
  });

  it("fires onMeta when only conversation_id is present (no type discriminator)", async () => {
    const onMeta = vi.fn();
    await chatApi.streamChat(
      { project_id: "p", message: "m" },
      { onMeta, onToken: vi.fn(), onDone: vi.fn(), onError: vi.fn() },
    );

    capture().onChunk({ conversation_id: "conv-9", request_id: "req-9" });

    expect(onMeta).toHaveBeenCalledTimes(1);
    expect(onMeta).toHaveBeenCalledWith({ conversation_id: "conv-9", request_id: "req-9" });
  });

  it("fires onToken for a token event with text", async () => {
    const onToken = vi.fn();
    await chatApi.streamChat(
      { project_id: "p", message: "m" },
      { onMeta: vi.fn(), onToken, onDone: vi.fn(), onError: vi.fn() },
    );

    capture().onChunk({ type: "token", text: "Once upon" });

    expect(onToken).toHaveBeenCalledTimes(1);
    expect(onToken).toHaveBeenCalledWith("Once upon");
  });

  it("does not fire onToken for a token event without text", async () => {
    const onToken = vi.fn();
    await chatApi.streamChat(
      { project_id: "p", message: "m" },
      { onMeta: vi.fn(), onToken, onDone: vi.fn(), onError: vi.fn() },
    );

    capture().onChunk({ type: "token" });

    expect(onToken).not.toHaveBeenCalled();
  });

  it("fires onDone with the usage for a done event", async () => {
    const onDone = vi.fn();
    const usage = { prompt_tokens: 10, completion_tokens: 20, total_tokens: 30 };
    await chatApi.streamChat(
      { project_id: "p", message: "m" },
      { onMeta: vi.fn(), onToken: vi.fn(), onDone, onError: vi.fn() },
    );

    capture().onChunk({ type: "done", usage });

    expect(onDone).toHaveBeenCalledTimes(1);
    expect(onDone).toHaveBeenCalledWith({ type: "done", usage });
  });

  it("defaults usage to zeroes when a done event omits it", async () => {
    const onDone = vi.fn();
    await chatApi.streamChat(
      { project_id: "p", message: "m" },
      { onMeta: vi.fn(), onToken: vi.fn(), onDone, onError: vi.fn() },
    );

    capture().onChunk({ type: "done" });

    expect(onDone).toHaveBeenCalledTimes(1);
    expect(onDone).toHaveBeenCalledWith({ type: "done", usage: ZERO_USAGE });
  });

  it("ignores events that match no discriminator branch", async () => {
    const onMeta = vi.fn();
    const onToken = vi.fn();
    const onDone = vi.fn();
    await chatApi.streamChat(
      { project_id: "p", message: "m" },
      { onMeta, onToken, onDone, onError: vi.fn() },
    );

    capture().onChunk({ type: "stream" as ChatStreamEvent["type"] });

    expect(onMeta).not.toHaveBeenCalled();
    expect(onToken).not.toHaveBeenCalled();
    expect(onDone).not.toHaveBeenCalled();
  });

  it("forwards transport errors to onError", async () => {
    const onError = vi.fn();
    await chatApi.streamChat(
      { project_id: "p", message: "m" },
      { onMeta: vi.fn(), onToken: vi.fn(), onDone: vi.fn(), onError },
    );

    capture().options.onError?.(new SSEStreamError("HTTP 500", "http", 500));

    expect(onError).toHaveBeenCalledTimes(1);
    expect(onError.mock.calls[0]?.[0]).toBeInstanceOf(SSEStreamError);
  });
});
