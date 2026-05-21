/**
 * Unit tests for Summary API client.
 *
 * Verifies that summarizeChapter constructs the correct HTTP request
 * and that optional parameters are serialized properly.
 */

import { describe, expect, it, vi } from "vitest";
import { type SummarizeResponse, summaryApi } from "@/lib/api/summary";

// Mock the fetchApi client module
vi.mock("@/lib/api/client", () => ({
  fetchApi: vi.fn(),
}));

import { fetchApi } from "@/lib/api/client";

const mockFetchApi = fetchApi as ReturnType<typeof vi.fn>;

describe("summaryApi.summarizeChapter", () => {
  const chapterId = "chapter-123";
  const novelId = "novel-456";

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("makes a POST request to the correct endpoint", async () => {
    const expectedResponse: SummarizeResponse = {
      summary: "Test summary.",
      word_count: 3,
      key_points: ["Point one"],
    };
    mockFetchApi.mockResolvedValueOnce(expectedResponse);

    const result = await summaryApi.summarizeChapter(chapterId, novelId);

    expect(mockFetchApi).toHaveBeenCalledTimes(1);
    // Verify the URL path includes the summary endpoint
    const callUrl = mockFetchApi.mock.calls[0][0];
    expect(callUrl).toContain(`/summary/chapters/${chapterId}`);
    expect(callUrl).toContain(`novel_id=${novelId}`);
    // Verify method
    expect(mockFetchApi.mock.calls[0][1].method).toBe("POST");
    // No body when no options
    expect(mockFetchApi.mock.calls[0][1].body).toBeUndefined();

    expect(result).toEqual(expectedResponse);
  });

  it("serializes options in the request body", async () => {
    mockFetchApi.mockResolvedValueOnce({
      summary: "Short summary.",
      word_count: 2,
      key_points: [],
    });

    await summaryApi.summarizeChapter(chapterId, novelId, {
      max_sentences: 3,
      language: "de",
    });

    const callOptions = mockFetchApi.mock.calls[0][1];
    expect(callOptions.method).toBe("POST");
    const parsedBody = JSON.parse(callOptions.body);
    expect(parsedBody).toEqual({ max_sentences: 3, language: "de" });
  });

  it("appends query parameters for novel_id, max_sentences, and language", async () => {
    mockFetchApi.mockResolvedValueOnce({
      summary: "S.",
      word_count: 1,
      key_points: [],
    });

    await summaryApi.summarizeChapter(chapterId, novelId, {
      max_sentences: 5,
      language: "fr",
    });

    const callUrl = mockFetchApi.mock.calls[0][0];
    const url = new URL(callUrl, "http://test.local");
    expect(url.searchParams.get("novel_id")).toBe(novelId);
    expect(url.searchParams.get("max_sentences")).toBe("5");
    expect(url.searchParams.get("language")).toBe("fr");
  });

  it("omits novel_id query param when only default options are used", async () => {
    mockFetchApi.mockResolvedValueOnce({
      summary: "S.",
      word_count: 1,
      key_points: [],
    });

    await summaryApi.summarizeChapter(chapterId, novelId);

    const callUrl = mockFetchApi.mock.calls[0][0];
    const url = new URL(callUrl, "http://test.local");
    expect(url.searchParams.get("novel_id")).toBe(novelId);
    // max_sentences and language should not be in query when not provided
    expect(url.searchParams.has("max_sentences")).toBe(false);
    expect(url.searchParams.has("language")).toBe(false);
  });
});
