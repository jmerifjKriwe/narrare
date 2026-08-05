/**
 * Series API client tests — band-summary methods (Spec 2, Task 8).
 *
 * Verifies that the four band-summary methods on `seriesApi` construct the
 * correct HTTP call (URL, method, body) and return the parsed response.
 * Mirrors the `summary.test.ts` pattern: `fetchApi` is mocked per-module so
 * each test asserts the wire shape without hitting the network.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/core", () => ({
  fetchApi: vi.fn(),
}));

import { fetchApi } from "@/lib/api/core";
import { seriesApi } from "@/lib/api/series";
import type { BandSummary } from "@/types";

const mockFetchApi = fetchApi as ReturnType<typeof vi.fn>;

const SERIES_ID = "series-1";
const NOVEL_ID = "novel-1";

const bandSummaryFixture: BandSummary = {
  novel_id: NOVEL_ID,
  full_summary: "The crew discovers the proto…",
  short_summary: "Discovery.",
  override: null,
  generated_at: "2026-08-02T12:00:00Z",
};

describe("seriesApi band-summary methods", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("getBandSummary → GET …/band-summary", async () => {
    mockFetchApi.mockResolvedValueOnce(bandSummaryFixture);

    const result = await seriesApi.getBandSummary(SERIES_ID, NOVEL_ID);

    expect(mockFetchApi).toHaveBeenCalledTimes(1);
    expect(mockFetchApi).toHaveBeenCalledWith(
      `/series/${SERIES_ID}/novels/${NOVEL_ID}/band-summary`,
    );
    expect(result).toEqual(bandSummaryFixture);
  });

  it("generateBandSummary → POST …/band-summary", async () => {
    const regenerated: BandSummary = {
      ...bandSummaryFixture,
      generated_at: "2026-08-03T00:00:00Z",
    };
    mockFetchApi.mockResolvedValueOnce(regenerated);

    const result = await seriesApi.generateBandSummary(SERIES_ID, NOVEL_ID);

    expect(mockFetchApi).toHaveBeenCalledTimes(1);
    const [url, options] = mockFetchApi.mock.calls[0];
    expect(url).toBe(`/series/${SERIES_ID}/novels/${NOVEL_ID}/band-summary`);
    expect(options.method).toBe("POST");
    expect(result).toEqual(regenerated);
  });

  it("updateBandSummaryOverride → PATCH …/band-summary with override body", async () => {
    const withOverride: BandSummary = { ...bandSummaryFixture, override: "Manual edit" };
    mockFetchApi.mockResolvedValueOnce(withOverride);

    const result = await seriesApi.updateBandSummaryOverride(SERIES_ID, NOVEL_ID, "Manual edit");

    expect(mockFetchApi).toHaveBeenCalledTimes(1);
    const [url, options] = mockFetchApi.mock.calls[0];
    expect(url).toBe(`/series/${SERIES_ID}/novels/${NOVEL_ID}/band-summary`);
    expect(options.method).toBe("PATCH");
    expect(JSON.parse(options.body)).toEqual({ override: "Manual edit" });
    expect(result).toEqual(withOverride);
  });

  it("clearBandSummaryOverride → DELETE …/band-summary/override", async () => {
    mockFetchApi.mockResolvedValueOnce(undefined);

    await seriesApi.clearBandSummaryOverride(SERIES_ID, NOVEL_ID);

    expect(mockFetchApi).toHaveBeenCalledTimes(1);
    const [url, options] = mockFetchApi.mock.calls[0];
    expect(url).toBe(`/series/${SERIES_ID}/novels/${NOVEL_ID}/band-summary/override`);
    expect(options.method).toBe("DELETE");
  });
});
