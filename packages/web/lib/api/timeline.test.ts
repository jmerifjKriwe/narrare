/**
 * Timeline API client tests — covers timelineApi + confirmExtractedEvent.
 *
 * Focuses on URL/method correctness and the buildFilterParams branches.
 * (SSE streaming helpers are exercised elsewhere; these tests cover the
 * REST helpers.)
 */

import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/core", () => ({ fetchApi: vi.fn() }));

import { fetchApi } from "@/lib/api/core";
import { confirmExtractedEvent, timelineApi } from "@/lib/api/timeline";
import type { ExtractedEvent } from "@/types/timeline";

const f = vi.mocked(fetchApi);

beforeEach(() => vi.clearAllMocks());

describe("timelineApi.listEvents — buildFilterParams branches", () => {
  it("omits the query string when no filters are given", async () => {
    f.mockResolvedValueOnce([] as never);
    await timelineApi.listEvents("n1");
    expect(f).toHaveBeenCalledWith("/planning/timeline/n1/events");
  });

  it("appends event_type only", async () => {
    f.mockResolvedValueOnce([] as never);
    await timelineApi.listEvents("n1", { event_type: "battle" });
    expect(f).toHaveBeenCalledWith("/planning/timeline/n1/events?event_type=battle");
  });

  it("appends chapter_id only", async () => {
    f.mockResolvedValueOnce([] as never);
    await timelineApi.listEvents("n1", { chapter_id: "ch-1" });
    expect(f).toHaveBeenCalledWith("/planning/timeline/n1/events?chapter_id=ch-1");
  });

  it("appends source only", async () => {
    f.mockResolvedValueOnce([] as never);
    await timelineApi.listEvents("n1", { source: "manual" });
    expect(f).toHaveBeenCalledWith("/planning/timeline/n1/events?source=manual");
  });

  it("appends is_confirmed as a string for both true and false", async () => {
    f.mockResolvedValue([] as never);
    await timelineApi.listEvents("n1", { is_confirmed: true });
    expect(f).toHaveBeenLastCalledWith("/planning/timeline/n1/events?is_confirmed=true");

    await timelineApi.listEvents("n1", { is_confirmed: false });
    expect(f).toHaveBeenLastCalledWith("/planning/timeline/n1/events?is_confirmed=false");
  });

  it("combines multiple filters", async () => {
    f.mockResolvedValueOnce([] as never);
    await timelineApi.listEvents("n1", {
      event_type: "battle",
      chapter_id: "ch-1",
      source: "manual",
      is_confirmed: true,
    });
    expect(f).toHaveBeenCalledWith(
      "/planning/timeline/n1/events?event_type=battle&chapter_id=ch-1&source=manual&is_confirmed=true",
    );
  });
});

describe("timelineApi — CRUD & analysis endpoints", () => {
  it("createEvent → POST", async () => {
    f.mockResolvedValueOnce({} as never);
    const data = { event_name: "E" };
    await timelineApi.createEvent("n1", data);
    expect(f).toHaveBeenCalledWith("/planning/timeline/n1/events", {
      method: "POST",
      body: JSON.stringify(data),
    });
  });

  it("getEvent → GET by id", async () => {
    f.mockResolvedValueOnce({} as never);
    await timelineApi.getEvent("n1", "e1");
    expect(f).toHaveBeenCalledWith("/planning/timeline/n1/events/e1");
  });

  it("updateEvent → PUT", async () => {
    f.mockResolvedValueOnce({} as never);
    await timelineApi.updateEvent("n1", "e1", { event_name: "X" });
    expect(f).toHaveBeenCalledWith(
      "/planning/timeline/n1/events/e1",
      expect.objectContaining({ method: "PUT" }),
    );
  });

  it("deleteEvent → DELETE", async () => {
    f.mockResolvedValueOnce(undefined as never);
    await timelineApi.deleteEvent("n1", "e1");
    expect(f).toHaveBeenCalledWith(
      "/planning/timeline/n1/events/e1",
      expect.objectContaining({ method: "DELETE" }),
    );
  });

  it("getAnalysis → GET", async () => {
    f.mockResolvedValueOnce({} as never);
    await timelineApi.getAnalysis("n1");
    expect(f).toHaveBeenCalledWith("/planning/timeline/n1");
  });

  it("checkConsistency → GET", async () => {
    f.mockResolvedValueOnce({} as never);
    await timelineApi.checkConsistency("n1");
    expect(f).toHaveBeenCalledWith("/planning/timeline/n1/consistency");
  });

  it("getCharacterAges → GET", async () => {
    f.mockResolvedValueOnce({} as never);
    await timelineApi.getCharacterAges("n1");
    expect(f).toHaveBeenCalledWith("/planning/timeline/n1/character-ages");
  });
});

describe("confirmExtractedEvent", () => {
  it("POSTs the extracted fields to the confirm endpoint", async () => {
    f.mockResolvedValueOnce({} as never);
    const extracted: ExtractedEvent = {
      id: "x1",
      expression: "in 1999",
      event_name: "Turn",
      timestamp_raw: "1999",
      chapter_reference: "Chapter 1",
      character_names: ["Anna"],
      location_name: "Hall",
      confidence: 0.9,
      context: "ctx",
    };
    await confirmExtractedEvent("n1", extracted);

    expect(f).toHaveBeenCalledWith(
      "/planning/timeline/n1/extract/confirm",
      expect.objectContaining({ method: "POST" }),
    );
    const call = f.mock.calls[0][1] as RequestInit;
    const body = JSON.parse(call.body as string);
    expect(body.expression).toBe("in 1999");
    expect(body.confidence).toBe(0.9);
  });
});
