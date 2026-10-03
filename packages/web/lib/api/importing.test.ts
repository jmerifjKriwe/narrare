/**
 * Tests for the importing API client (multipart encoding, RULE-17 shapes).
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { importApi } from "./importing";

const fetchMock = vi.fn();

beforeEach(() => {
  vi.unstubAllGlobals();
  vi.stubGlobal("fetch", fetchMock);
  fetchMock.mockReset();
});

describe("importApi", () => {
  it("preview posts multipart with files under the 'files' key", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({ items: [], file_count: 1, chapter_count: 1, total_word_count: 0 }),
        { status: 200 },
      ),
    );
    const file = new File(["# T\nbody"], "a.md", { type: "text/markdown" });
    await importApi.preview([file]);
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const body = init.body as FormData;
    expect(body.getAll("files")).toHaveLength(1);
    expect(init.method).toBe("POST");
    // MUST NOT set a JSON Content-Type — the browser sets the multipart boundary
    expect((init.headers as Record<string, string>)["Content-Type"]).toBeUndefined();
  });

  it("commit posts files + novel_id + adjustments JSON", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          novel_id: "n",
          created_count: 1,
          first_position: 0,
          last_position: 0,
          chapters: [],
        }),
        { status: 200 },
      ),
    );
    const file = new File(["Chapter 1\nx"], "a.txt", { type: "text/plain" });
    await importApi.commit([file], "novel-uuid", {
      splits: [],
      merges: [],
      excluded_indices: [],
      title_overrides: {},
    });
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const body = init.body as FormData;
    expect(body.getAll("files")).toHaveLength(1);
    expect(body.get("novel_id")).toBe("novel-uuid");
    expect(JSON.parse(body.get("adjustments") as string)).toEqual({
      splits: [],
      merges: [],
      excluded_indices: [],
      title_overrides: {},
    });
  });

  it("preview surfaces the backend detail message on 422", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          detail: "File 'a.docx': unsupported type (allowed: .md, .txt).",
          code: "...",
        }),
        { status: 422 },
      ),
    );
    const file = new File(["x"], "a.docx");
    await expect(importApi.preview([file])).rejects.toThrow("unsupported type");
  });
});
