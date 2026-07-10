/**
 * useChat hook tests — free-form chat over SSE, wrapped via useAIOperation.
 *
 * Strategy: mock useAIOperation but CAPTURE the options object it receives
 * (execute / errorMapper / onSuccess / onError) so we can invoke the hook's
 * internal callbacks directly — covering the branches that a plain mock
 * leaves untested. chatApi.streamChat is also mocked so execute can be driven.
 *
 * Covers:
 *  - sendMessage: empty/while-loading early return, happy path
 *  - execute: no-message early return, streamChat onMeta/onToken accumulation, onError throw
 *  - errorMapper: AbortError (DOMException + Error) vs other error
 *  - onSuccess: with content vs null
 *  - onError: partial absent (no message) path
 *  - clearConversation / cancelStream
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type {
  AIErrorResponse,
  AIOperationState,
  UseAIOperationOptions,
  UseAIOperationReturn,
} from "@/lib/hooks/use-ai-operation";

const { createMockAiOp } = vi.hoisted(() => {
  function createMockAiOp<T>(
    overrides: Partial<UseAIOperationReturn<T>> = {},
  ): UseAIOperationReturn<T> {
    return {
      state: { status: "idle", result: null, error: null, attemptCount: 0 } as AIOperationState<T>,
      start: vi.fn(),
      cancel: vi.fn(),
      retry: vi.fn(),
      reset: vi.fn(),
      notifyData: vi.fn(),
      isIdle: true,
      isLoading: false,
      isStreaming: false,
      isComplete: false,
      isError: false,
      isConnectionLost: false,
      ...overrides,
    };
  }
  return { createMockAiOp };
});

vi.mock("@/lib/hooks/use-ai-operation", () => ({ useAIOperation: vi.fn() }));
vi.mock("@/lib/api/client", () => ({ chatApi: { streamChat: vi.fn() } }));
vi.mock("@/lib/api/ai-error-mapping", () => ({
  mapSSEError: (e: Error): AIErrorResponse => ({
    kind: "stream",
    i18nKey: "studio.aiActions.genericError",
    userMessage: e.message,
    retryable: false,
    cause: e,
  }),
}));

import { mapSSEError } from "@/lib/api/ai-error-mapping";
import { chatApi } from "@/lib/api/client";
import { useAIOperation } from "@/lib/hooks/use-ai-operation";
import { useChat } from "@/lib/hooks/useChat";

const mockedUseAIOperation = vi.mocked(useAIOperation);
const streamChat = vi.mocked(chatApi.streamChat);

// Options captured from the useAIOperation call inside useChat.
type ChatOptions = {
  execute: (signal: AbortSignal) => Promise<string | null>;
  errorMapper: (error: unknown) => unknown;
  onSuccess: (content: string | null) => void;
  onError: (errResponse: AIErrorResponse) => void;
};
let capturedOptions: ChatOptions;
let mockAiOp: UseAIOperationReturn<unknown>;

function setup(overrides: Partial<UseAIOperationReturn<unknown>> = {}) {
  mockAiOp = createMockAiOp(overrides);
  mockedUseAIOperation.mockImplementation((opts: UseAIOperationOptions<unknown>) => {
    capturedOptions = opts as unknown as ChatOptions;
    return mockAiOp;
  });
}

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  setup();
});
afterEach(() => cleanup());

describe("useChat — sendMessage", () => {
  it("ignores empty messages", () => {
    const { result } = renderHook(() => useChat("proj-1"), { wrapper: createWrapper() });

    result.current.sendMessage("   ");

    expect(result.current.messages).toHaveLength(0);
    expect(mockAiOp.start).not.toHaveBeenCalled();
  });

  it("ignores messages while a stream is loading/streaming", () => {
    setup({ isLoading: true });
    const { result } = renderHook(() => useChat("proj-1"), { wrapper: createWrapper() });

    result.current.sendMessage("hello");

    expect(result.current.messages).toHaveLength(0);
    expect(mockAiOp.start).not.toHaveBeenCalled();
  });

  it("adds a user message and starts the operation on valid input", () => {
    const { result } = renderHook(() => useChat("proj-1"), { wrapper: createWrapper() });

    act(() => {
      result.current.sendMessage("hello");
    });

    expect(result.current.messages).toHaveLength(1);
    expect(result.current.messages[0].role).toBe("user");
    expect(result.current.messages[0].content).toBe("hello");
    expect(mockAiOp.start).toHaveBeenCalledTimes(1);
  });
});

describe("useChat — execute (streamChat lifecycle)", () => {
  it("returns null when there is no staged message", async () => {
    renderHook(() => useChat("proj-1"), { wrapper: createWrapper() });

    const out = await capturedOptions.execute(new AbortController().signal);

    expect(out).toBeNull();
    expect(streamChat).not.toHaveBeenCalled();
  });

  it("accumulates tokens and returns the full content", async () => {
    const { result } = renderHook(() => useChat("proj-1"), { wrapper: createWrapper() });

    result.current.sendMessage("hi"); // stages messageRef
    streamChat.mockImplementationOnce((_body, cbs) => {
      cbs.onMeta({ conversation_id: "c1", request_id: "r1" });
      cbs.onToken("Hello ");
      cbs.onToken("world");
      cbs.onDone({
        type: "done",
        usage: { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 },
      });
      return Promise.resolve();
    });

    const out = await capturedOptions.execute(new AbortController().signal);

    expect(out).toBe("Hello world");
    expect(mockAiOp.notifyData).toHaveBeenCalled();
  });

  it("rejects when the stream reports an error", async () => {
    const { result } = renderHook(() => useChat("proj-1"), { wrapper: createWrapper() });

    result.current.sendMessage("hi");
    streamChat.mockImplementationOnce((_body, cbs) => {
      cbs.onError(new Error("stream broke"));
      return Promise.resolve();
    });

    await expect(capturedOptions.execute(new AbortController().signal)).rejects.toThrow(
      "stream broke",
    );
  });
});

describe("useChat — errorMapper", () => {
  it("returns null for a DOMException AbortError", () => {
    renderHook(() => useChat("proj-1"), { wrapper: createWrapper() });

    const mapped = capturedOptions.errorMapper(new DOMException("aborted", "AbortError"));

    expect(mapped).toBeNull();
  });

  it("returns null for an Error named AbortError", () => {
    renderHook(() => useChat("proj-1"), { wrapper: createWrapper() });

    const err = new Error("aborted");
    err.name = "AbortError";
    const mapped = capturedOptions.errorMapper(err);

    expect(mapped).toBeNull();
  });

  it("maps other errors via mapSSEError", () => {
    renderHook(() => useChat("proj-1"), { wrapper: createWrapper() });

    const mapped = capturedOptions.errorMapper(new Error("boom"));

    expect(mapped).toEqual(mapSSEError(new Error("boom")));
  });
});

describe("useChat — onSuccess", () => {
  it("adds an assistant message when content is present", () => {
    const { result } = renderHook(() => useChat("proj-1"), { wrapper: createWrapper() });

    act(() => {
      capturedOptions.onSuccess("hello there");
    });

    expect(result.current.messages).toHaveLength(1);
    expect(result.current.messages[0].role).toBe("assistant");
    expect(result.current.messages[0].content).toBe("hello there");
    expect(result.current.error).toBeNull();
  });

  it("adds no message when content is null", () => {
    const { result } = renderHook(() => useChat("proj-1"), { wrapper: createWrapper() });

    act(() => {
      capturedOptions.onSuccess(null);
    });

    expect(result.current.messages).toHaveLength(0);
    expect(result.current.error).toBeNull();
  });
});

describe("useChat — onError", () => {
  it("stores the error message and adds no message when no partial accumulated", () => {
    const { result } = renderHook(() => useChat("proj-1"), { wrapper: createWrapper() });

    act(() => {
      capturedOptions.onError({
        kind: "stream",
        i18nKey: "studio.aiActions.genericError",
        userMessage: "stream failed",
        retryable: false,
        cause: new Error("stream failed"),
      });
    });

    expect(result.current.messages).toHaveLength(0);
    expect(result.current.error).toBe("stream failed");
  });
});

describe("useChat — clearConversation & cancelStream", () => {
  it("clearConversation resets messages, conversation, error and cancels", () => {
    const { result } = renderHook(() => useChat("proj-1"), { wrapper: createWrapper() });

    act(() => {
      result.current.sendMessage("hi");
    });
    act(() => {
      capturedOptions.onSuccess("reply");
    });
    expect(result.current.messages).toHaveLength(2);

    act(() => {
      result.current.clearConversation();
    });

    expect(result.current.messages).toHaveLength(0);
    expect(result.current.conversationId).toBeNull();
    expect(result.current.error).toBeNull();
    expect(mockAiOp.cancel).toHaveBeenCalled();
  });

  it("cancelStream cancels the operation", () => {
    const { result } = renderHook(() => useChat("proj-1"), { wrapper: createWrapper() });

    result.current.cancelStream();

    expect(mockAiOp.cancel).toHaveBeenCalled();
  });
});
