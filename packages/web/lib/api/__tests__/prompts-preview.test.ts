/**
 * Tests for PROMPT-003 prompts preview / reset / live-test API surface.
 *
 * The REST endpoints (preview, resetWithMetadata) are exercised via MSW
 * using the project's standard pattern. The SSE live-test uses the
 * existing connectSSE transport — these tests assert that
 * streamPromptLiveTest emits onMeta → onChunk → onComplete in order.
 */

import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { setAccessToken } from "@/lib/api/client";
import { promptsApi, streamPromptLiveTest } from "@/lib/api/prompts";
import { server } from "@/mocks/server";

function sseStream(lines: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const line of lines) controller.enqueue(encoder.encode(`${line}\n`));
      controller.close();
    },
  });
}

describe("promptsApi.preview", () => {
  beforeEach(() => {
    setAccessToken("test-access-token");
  });

  it("POST /prompts/{id}/preview returns PromptPreview", async () => {
    server.use(
      http.post("*/api/v1/prompts/writing/en/new_chapter/preview", async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        expect(body.language).toBe("en");
        return HttpResponse.json({
          system_prompt: "resolved system",
          user_prompt: "resolved user",
          first_message: null,
          cascade_source: "bundled",
          variables: [
            {
              name: "language",
              description: "ISO language code",
              variable_type: "text",
              required: true,
              provenance: "system_generated",
              security: "system_only",
            },
          ],
          diagnostics: [],
        });
      }),
    );

    const result = await promptsApi.preview("writing/en/new_chapter", {
      variables: { language: "en" },
      language: "en",
    });

    expect(result.system_prompt).toBe("resolved system");
    expect(result.user_prompt).toBe("resolved user");
    expect(result.cascade_source).toBe("bundled");
    expect(result.variables[0].provenance).toBe("system_generated");
    expect(result.variables[0].security).toBe("system_only");
  });

  it("surfaces preview diagnostics from the backend", async () => {
    server.use(
      http.post("*/api/v1/prompts/writing/en/new_chapter/preview", async () =>
        HttpResponse.json({
          system_prompt: "",
          user_prompt: "",
          first_message: null,
          cascade_source: "",
          variables: [],
          diagnostics: [
            {
              kind: "missing_variable",
              variable_name: "project_title",
              message: "missing_required_variable:project_title",
            },
          ],
        }),
      ),
    );

    const result = await promptsApi.preview("writing/en/new_chapter", {
      variables: {},
      language: "en",
    });

    expect(result.diagnostics).toHaveLength(1);
    expect(result.diagnostics[0].kind).toBe("missing_variable");
    expect(result.diagnostics[0].variable_name).toBe("project_title");
  });
});

describe("promptsApi.resetWithMetadata", () => {
  beforeEach(() => {
    setAccessToken("test-access-token");
  });

  it("POST /prompts/{id}/reset returns PromptResetResult metadata", async () => {
    server.use(
      http.post("*/api/v1/prompts/writing/en/new_chapter/reset", async () =>
        HttpResponse.json({
          reset: true,
          effective_source: "bundled",
          effective_content: "default prompt body",
        }),
      ),
    );

    const result = await promptsApi.resetWithMetadata("writing/en/new_chapter");

    expect(result.reset).toBe(true);
    expect(result.effective_source).toBe("bundled");
    expect(result.effective_content).toBe("default prompt body");
  });
});

describe("streamPromptLiveTest", () => {
  beforeEach(() => {
    setAccessToken("test-access-token");
  });

  it("emits onMeta → onChunk → onComplete in order", async () => {
    const onMeta = vi.fn();
    const chunks: string[] = [];
    const onComplete = vi.fn();
    const onError = vi.fn();

    server.use(
      http.post("*/api/v1/prompts/writing/en/new_chapter/live-test", async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        expect(body.acknowledge_token_cost).toBe(true);
        return new HttpResponse(
          sseStream([
            'event: meta\ndata: {"prompt_id":"writing/en/new_chapter","intent":"writing","model_id":"gpt-test","rate_limit_remaining":4}',
            'data: {"text":"Hello "}',
            'data: {"text":"world"}',
            'event: done\ndata: {"is_final":true}',
            "data: [DONE]",
          ]),
          { headers: { "Content-Type": "text/event-stream" } },
        );
      }),
    );

    await streamPromptLiveTest(
      "writing/en/new_chapter",
      {
        variables: { language: "en" },
        language: "en",
        user_prompt: "",
        acknowledge_token_cost: true,
      },
      { onMeta, onChunk: (text) => chunks.push(text), onComplete, onError },
    );

    expect(onMeta).toHaveBeenCalledOnce();
    const meta = onMeta.mock.calls[0][0];
    expect(meta.prompt_id).toBe("writing/en/new_chapter");
    expect(meta.model_id).toBe("gpt-test");
    expect(meta.rate_limit_remaining).toBe(4);
    expect(chunks).toEqual(["Hello ", "world"]);
    expect(onComplete).toHaveBeenCalledOnce();
    expect(onError).not.toHaveBeenCalled();
  });

  it("reports stream errors via onError without dropping prior chunks", async () => {
    const chunks: string[] = [];
    const onError = vi.fn();
    const onComplete = vi.fn();

    server.use(
      http.post(
        "*/api/v1/prompts/writing/en/new_chapter/live-test",
        async () =>
          new HttpResponse(
            new ReadableStream({
              start(controller) {
                controller.enqueue(new TextEncoder().encode('data: {"text":"partial"}\n'));
                setTimeout(() => controller.error(new Error("connection lost")), 0);
              },
            }),
            { headers: { "Content-Type": "text/event-stream" } },
          ),
      ),
    );

    await streamPromptLiveTest(
      "writing/en/new_chapter",
      {
        variables: {},
        language: "en",
        user_prompt: "",
        acknowledge_token_cost: true,
      },
      { onMeta: vi.fn(), onChunk: (text) => chunks.push(text), onComplete, onError },
    );

    expect(chunks).toEqual(["partial"]);
    expect(onComplete).not.toHaveBeenCalled();
    expect(onError).toHaveBeenCalledWith(expect.objectContaining({ message: "connection lost" }));
  });

  it("reports backend error payloads via onError", async () => {
    const onError = vi.fn();
    const onComplete = vi.fn();

    server.use(
      http.post(
        "*/api/v1/prompts/writing/en/new_chapter/live-test",
        async () =>
          new HttpResponse(sseStream(['data: {"error":"provider_unavailable"}', "data: [DONE]"]), {
            headers: { "Content-Type": "text/event-stream" },
          }),
      ),
    );

    await streamPromptLiveTest(
      "writing/en/new_chapter",
      {
        variables: {},
        language: "en",
        user_prompt: "",
        acknowledge_token_cost: true,
      },
      { onMeta: vi.fn(), onChunk: vi.fn(), onComplete, onError },
    );

    expect(onError).toHaveBeenCalledWith(
      expect.objectContaining({ message: "provider_unavailable" }),
    );
    expect(onComplete).not.toHaveBeenCalled();
  });

  it("propagates caller aborts to the underlying fetch request", async () => {
    const controller = new AbortController();
    const observedAbort = vi.fn();
    const onError = vi.fn();
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementationOnce(
      (_input, init) =>
        new Promise<Response>((_resolve, reject) => {
          const fetchSignal = init?.signal;
          expect(fetchSignal).toBeInstanceOf(AbortSignal);
          if (fetchSignal instanceof AbortSignal) {
            fetchSignal.addEventListener(
              "abort",
              () => {
                observedAbort();
                reject(new DOMException("Aborted", "AbortError"));
              },
              { once: true },
            );
          }
          queueMicrotask(() => controller.abort());
        }),
    );

    try {
      await streamPromptLiveTest(
        "writing/en/new_chapter",
        {
          variables: {},
          language: "en",
          user_prompt: "",
          acknowledge_token_cost: true,
        },
        { onMeta: vi.fn(), onChunk: vi.fn(), onComplete: vi.fn(), onError },
        controller.signal,
      );
    } finally {
      fetchSpy.mockRestore();
    }

    expect(observedAbort).toHaveBeenCalledOnce();
    expect(onError).not.toHaveBeenCalled();
  });
});

describe("promptsApi.startLiveTest", () => {
  beforeEach(() => {
    setAccessToken("test-access-token");
  });

  it("returns the raw SSE Response for the stream reader", async () => {
    server.use(
      http.post("*/api/v1/prompts/writing/en/new_chapter/live-test", async ({ request }) => {
        expect(await request.json()).toMatchObject({ acknowledge_token_cost: true });
        return new HttpResponse("data: [DONE]\n\n", {
          headers: { "content-type": "text/event-stream" },
        });
      }),
    );

    const response = await promptsApi.startLiveTest("writing/en/new_chapter", {
      variables: {},
      language: "en",
      user_prompt: "",
      acknowledge_token_cost: true,
    });

    expect(response).toBeInstanceOf(Response);
    expect(response.headers.get("content-type")).toContain("text/event-stream");
  });
});
