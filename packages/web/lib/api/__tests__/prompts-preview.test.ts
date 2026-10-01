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
import { promptsApi, streamPromptLiveTest, templatesApi } from "@/lib/api/prompts";
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
    // msw 3 surfaces a failing mocked stream as a network abort (message
    // "aborted", cause ECONNRESET) instead of the handler's error text.
    expect(onError).toHaveBeenCalledWith(expect.objectContaining({ kind: "network" }));
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

describe("promptsApi REST methods", () => {
  beforeEach(() => {
    setAccessToken("test-access-token");
  });

  it("list returns prompts filtered by category", async () => {
    server.use(
      http.get("*/api/v1/prompts", ({ request }) => {
        const url = new URL(request.url);
        expect(url.searchParams.get("category")).toBe("writing");
        return HttpResponse.json([{ prompt_id: "writing/en/new_chapter", category: "writing" }]);
      }),
    );
    const result = await promptsApi.list("writing");
    expect(result).toHaveLength(1);
    expect(result[0].prompt_id).toBe("writing/en/new_chapter");
  });

  it("list returns all prompts when no category given", async () => {
    server.use(
      http.get("*/api/v1/prompts", ({ request }) => {
        const url = new URL(request.url);
        expect(url.search).toBe("");
        return HttpResponse.json([
          { prompt_id: "writing/en/new_chapter" },
          { prompt_id: "analysis/en/beta_reader" },
        ]);
      }),
    );
    const result = await promptsApi.list();
    expect(result).toHaveLength(2);
  });

  it("get returns prompt detail", async () => {
    server.use(
      http.get("*/api/v1/prompts/writing/en/new_chapter", () =>
        HttpResponse.json({ id: "writing/en/new_chapter", content: "You are an author." }),
      ),
    );
    const result = await promptsApi.get("writing/en/new_chapter");
    expect(result.content).toBe("You are an author.");
  });

  it("save PUTs content and returns void", async () => {
    server.use(
      http.put("*/api/v1/prompts/writing/en/new_chapter", async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        expect(body.content).toBe("New content");
        return HttpResponse.json(null, { status: 204 });
      }),
    );
    await expect(promptsApi.save("writing/en/new_chapter", "New content")).resolves.toBeUndefined();
  });

  it("reset deletes the override", async () => {
    server.use(
      http.delete("*/api/v1/prompts/writing/en/new_chapter/override", () =>
        HttpResponse.json(null, { status: 204 }),
      ),
    );
    await expect(promptsApi.reset("writing/en/new_chapter")).resolves.toBeUndefined();
  });

  it("cascade returns cascade paths", async () => {
    server.use(
      http.get("*/api/v1/prompts/writing/en/new_chapter/cascade", () =>
        HttpResponse.json([{ level: "user", path: "override", exists: true }]),
      ),
    );
    const result = await promptsApi.cascade("writing/en/new_chapter");
    expect(result).toHaveLength(1);
    expect(result[0].level).toBe("user");
  });

  it("updates returns available prompt updates", async () => {
    server.use(
      http.get("*/api/v1/prompts/updates", () =>
        HttpResponse.json([
          {
            prompt_id: "writing/en/new_chapter",
            override_version: "1",
            current_bundled_version: "2",
          },
        ]),
      ),
    );
    const result = await promptsApi.updates();
    expect(result).toHaveLength(1);
    expect(result[0].prompt_id).toBe("writing/en/new_chapter");
  });

  it("diff returns prompt diff", async () => {
    server.use(
      http.get("*/api/v1/prompts/writing/en/new_chapter/diff", () =>
        HttpResponse.json({
          prompt_id: "writing/en/new_chapter",
          override_content: "old",
          bundled_content: "new",
        }),
      ),
    );
    const result = await promptsApi.diff("writing/en/new_chapter");
    expect(result.override_content).toBe("old");
    expect(result.bundled_content).toBe("new");
  });
});

describe("templatesApi", () => {
  beforeEach(() => {
    setAccessToken("test-access-token");
  });

  it("list returns KB templates for a novel", async () => {
    server.use(
      http.get("*/api/v1/novels/novel-1/kb/templates", () =>
        HttpResponse.json([{ entity_type: "character", version: 1 }]),
      ),
    );
    const result = await templatesApi.list("novel-1");
    expect(result).toHaveLength(1);
  });

  it("get returns template detail", async () => {
    server.use(
      http.get("*/api/v1/novels/novel-1/kb/templates/character", () =>
        HttpResponse.json({ entity_type: "character", content: "Template for characters" }),
      ),
    );
    const result = await templatesApi.get("novel-1", "character");
    expect(result.content).toBe("Template for characters");
  });

  it("save POSTs template content", async () => {
    server.use(
      http.post("*/api/v1/novels/novel-1/kb/templates/character", async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        expect(body.content).toBe("Updated template");
        return new HttpResponse(null, { status: 204 });
      }),
    );
    await expect(
      templatesApi.save("novel-1", "character", "Updated template"),
    ).resolves.toBeUndefined();
  });

  it("save POSTs with based_on_version", async () => {
    server.use(
      http.post("*/api/v1/novels/novel-1/kb/templates/character", async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        expect(body.based_on_version).toBe("v2");
        return new HttpResponse(null, { status: 204 });
      }),
    );
    await expect(
      templatesApi.save("novel-1", "character", "Template", "v2"),
    ).resolves.toBeUndefined();
  });

  it("reset DELETES the template", async () => {
    server.use(
      http.delete("*/api/v1/novels/novel-1/kb/templates/character", () =>
        HttpResponse.json(null, { status: 204 }),
      ),
    );
    await expect(templatesApi.reset("novel-1", "character")).resolves.toBeUndefined();
  });

  it("updates returns template updates", async () => {
    server.use(
      http.get("*/api/v1/novels/novel-1/kb/templates/updates", () =>
        HttpResponse.json([{ entity_type: "character", has_update: true }]),
      ),
    );
    const result = await templatesApi.updates("novel-1");
    expect(result).toHaveLength(1);
  });

  it("diff returns template diff", async () => {
    server.use(
      http.get("*/api/v1/novels/novel-1/kb/templates/character/diff", () =>
        HttpResponse.json({
          entity_type: "character",
          override_content: "old",
          bundled_content: "new",
        }),
      ),
    );
    const result = await templatesApi.diff("novel-1", "character");
    expect(result.override_content).toBe("old");
    expect(result.bundled_content).toBe("new");
  });
});

describe("streamPromptLiveTest edge cases", () => {
  beforeEach(() => {
    setAccessToken("test-access-token");
  });

  it("does not double-fire onComplete when transport calls complete twice", async () => {
    const onComplete = vi.fn();
    const onChunk = vi.fn();

    server.use(
      http.post(
        "*/api/v1/prompts/writing/en/new_chapter/live-test",
        () =>
          new HttpResponse(sseStream(['data: {"text":"hello","is_final":true}', "data: [DONE]"]), {
            headers: { "Content-Type": "text/event-stream" },
          }),
      ),
    );

    await streamPromptLiveTest(
      "writing/en/new_chapter",
      { variables: {}, language: "en", user_prompt: "", acknowledge_token_cost: true },
      { onMeta: vi.fn(), onChunk, onComplete, onError: vi.fn() },
    );

    expect(onComplete).toHaveBeenCalledOnce();
  });

  it("calls onChunk for text events without meta fields", async () => {
    const chunks: string[] = [];

    server.use(
      http.post(
        "*/api/v1/prompts/writing/en/new_chapter/live-test",
        () =>
          new HttpResponse(
            sseStream(['data: {"text":"chunk1"}', 'data: {"text":"chunk2"}', "data: [DONE]"]),
            { headers: { "Content-Type": "text/event-stream" } },
          ),
      ),
    );

    await streamPromptLiveTest(
      "writing/en/new_chapter",
      { variables: {}, language: "en", user_prompt: "", acknowledge_token_cost: true },
      {
        onMeta: vi.fn(),
        onChunk: (text) => chunks.push(text),
        onComplete: vi.fn(),
        onError: vi.fn(),
      },
    );

    expect(chunks).toEqual(["chunk1", "chunk2"]);
  });
});
