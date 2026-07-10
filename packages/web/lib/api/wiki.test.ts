/**
 * Wiki API client tests — covers wikiApi, including the getSummaries/markStale
 * optional-parameter branches.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/core", () => ({ fetchApi: vi.fn() }));

import { fetchApi } from "@/lib/api/core";
import { wikiApi } from "@/lib/api/wiki";

const f = vi.mocked(fetchApi);

beforeEach(() => vi.clearAllMocks());

describe("wikiApi", () => {
  it("getSummaries omits params when no entity ids are given", async () => {
    f.mockResolvedValueOnce({} as never);
    await wikiApi.getSummaries("n1");
    expect(f).toHaveBeenCalledWith("/novels/n1/wiki/summaries");
  });

  it("getSummaries appends entity_ids when provided", async () => {
    f.mockResolvedValueOnce({} as never);
    await wikiApi.getSummaries("n1", ["e1", "e2"]);
    expect(f).toHaveBeenCalledWith("/novels/n1/wiki/summaries?entity_ids=e1,e2");
  });

  it("getSummary → GET single summary", async () => {
    f.mockResolvedValueOnce({} as never);
    await wikiApi.getSummary("n1", "e1");
    expect(f).toHaveBeenCalledWith("/novels/n1/wiki/summaries/e1");
  });

  it("getChapterSummary → GET chapter summary", async () => {
    f.mockResolvedValueOnce({} as never);
    await wikiApi.getChapterSummary("n1", "c1");
    expect(f).toHaveBeenCalledWith("/novels/n1/wiki/chapters/c1/summary");
  });

  it("refreshSummary → POST with force defaulting to false", async () => {
    f.mockResolvedValueOnce({} as never);
    await wikiApi.refreshSummary("n1", "e1");
    expect(f).toHaveBeenCalledWith("/novels/n1/wiki/summaries/e1/refresh", {
      method: "POST",
      body: JSON.stringify({ entity_id: "e1", force: false }),
    });
  });

  it("refreshSummary forwards force=true", async () => {
    f.mockResolvedValueOnce({} as never);
    await wikiApi.refreshSummary("n1", "e1", true);
    expect(f).toHaveBeenCalledWith("/novels/n1/wiki/summaries/e1/refresh", {
      method: "POST",
      body: JSON.stringify({ entity_id: "e1", force: true }),
    });
  });

  it("getWikiIndex → GET index", async () => {
    f.mockResolvedValueOnce({} as never);
    await wikiApi.getWikiIndex("n1");
    expect(f).toHaveBeenCalledWith("/novels/n1/wiki/index");
  });

  it("markStale sends an empty body when no prompt version is given", async () => {
    f.mockResolvedValueOnce({} as never);
    await wikiApi.markStale("n1");
    expect(f).toHaveBeenCalledWith("/novels/n1/wiki/mark-stale", {
      method: "POST",
      body: JSON.stringify({}),
    });
  });

  it("markStale sends the prompt version when provided", async () => {
    f.mockResolvedValueOnce({} as never);
    await wikiApi.markStale("n1", "v2");
    expect(f).toHaveBeenCalledWith("/novels/n1/wiki/mark-stale", {
      method: "POST",
      body: JSON.stringify({ prompt_version: "v2" }),
    });
  });
});
