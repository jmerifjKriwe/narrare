/**
 * Consistency API client tests — KB consistency check endpoints.
 *
 * Tests:
 * 1. consistencyApi.checkConsistency POSTs correct URL + body
 * 2. Returns ConsistencyCheckResponse with issues and summary
 * 3. Works with default (empty) request body
 * 4. Error handling
 */

import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { server } from "@/mocks/server";
import { setAccessToken } from "../client";
import { consistencyApi, consistencyFingerprint } from "../consistency";
import type { ConsistencyIssue } from "../worldbuilding";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const mockConsistencyResponse = {
  novel_id: "novel-1",
  entity_count: 25,
  issues: [
    {
      finding_index: 0,
      category: "geography" as const,
      entity_ids: ["entity-1", "entity-2"],
      entity_names: ["Castle", "Forest"],
      description: "Travel time inconsistency between Castle and Forest.",
      contradiction: "Chapter 1 says 2 days, Chapter 5 says 2 hours.",
      suggested_resolution: "Standardize travel time to 2 days on horseback.",
      severity: "critical" as const,
      confidence: 0.92,
    },
    {
      finding_index: 1,
      category: "character" as const,
      entity_ids: ["entity-3"],
      entity_names: ["Anna"],
      description: "Eye color mismatch.",
      contradiction: "Chapter 1 says blue, Chapter 3 says green.",
      suggested_resolution: null,
      severity: "minor" as const,
      confidence: 0.85,
    },
  ],
  summary: { critical: 1, major: 0, minor: 1 },
  suppressed_count: 2,
  checked_at: "2026-05-27T12:00:00Z",
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("consistencyApi", () => {
  beforeEach(() => {
    setAccessToken("test-access-token");
  });

  describe("checkConsistency", () => {
    it("should POST to /novels/:novelId/kb/consistency-check and return response", async () => {
      server.use(
        http.post("*/api/v1/novels/novel-1/kb/consistency-check", async () =>
          HttpResponse.json(mockConsistencyResponse),
        ),
      );

      const result = await consistencyApi.checkConsistency("novel-1");

      expect(result.novel_id).toBe("novel-1");
      expect(result.entity_count).toBe(25);
      expect(result.issues).toHaveLength(2);
      expect(result.suppressed_count).toBe(2);
      expect(result.checked_at).toBe("2026-05-27T12:00:00Z");
    });

    it("should send request body with options when provided", async () => {
      let capturedBody: Record<string, unknown> = {};

      server.use(
        http.post("*/api/v1/novels/novel-1/kb/consistency-check", async ({ request }) => {
          capturedBody = (await request.json()) as Record<string, unknown>;
          return HttpResponse.json(mockConsistencyResponse);
        }),
      );

      await consistencyApi.checkConsistency("novel-1", {
        entity_types: ["character", "location"],
        include_entry_internal: true,
        include_asymmetry: false,
        include_cross_entity: true,
        refresh: true,
      });

      expect(capturedBody.entity_types).toEqual(["character", "location"]);
      expect(capturedBody.include_entry_internal).toBe(true);
      expect(capturedBody.include_asymmetry).toBe(false);
      expect(capturedBody.include_cross_entity).toBe(true);
      expect(capturedBody.refresh).toBe(true);
    });

    it("should send empty object body when no request provided", async () => {
      let capturedBody: unknown = null;

      server.use(
        http.post("*/api/v1/novels/novel-1/kb/consistency-check", async ({ request }) => {
          capturedBody = await request.json();
          return HttpResponse.json(mockConsistencyResponse);
        }),
      );

      await consistencyApi.checkConsistency("novel-1");

      expect(capturedBody).toEqual({});
    });

    it("should return issues with correct structure", async () => {
      server.use(
        http.post("*/api/v1/novels/novel-1/kb/consistency-check", async () =>
          HttpResponse.json(mockConsistencyResponse),
        ),
      );

      const result = await consistencyApi.checkConsistency("novel-1");

      const issue = result.issues[0];
      expect(issue.category).toBe("geography");
      expect(issue.severity).toBe("critical");
      expect(issue.entity_ids).toHaveLength(2);
      expect(issue.confidence).toBe(0.92);
      expect(issue.suggested_resolution).toBeTruthy();
    });

    it("should return summary as Record<string, number>", async () => {
      server.use(
        http.post("*/api/v1/novels/novel-1/kb/consistency-check", async () =>
          HttpResponse.json(mockConsistencyResponse),
        ),
      );

      const result = await consistencyApi.checkConsistency("novel-1");

      expect(result.summary).toEqual({ critical: 1, major: 0, minor: 1 });
    });

    it("should construct correct URL for different novel IDs", async () => {
      let capturedUrl = "";

      server.use(
        http.post("*/api/v1/novels/:novelId/kb/consistency-check", ({ request }) => {
          capturedUrl = new URL(request.url).pathname;
          return HttpResponse.json({ ...mockConsistencyResponse, novel_id: "other-novel" });
        }),
      );

      await consistencyApi.checkConsistency("other-novel");
      expect(capturedUrl).toContain("/novels/other-novel/kb/consistency-check");
    });

    it("should handle 500 error", async () => {
      server.use(
        http.post("*/api/v1/novels/:novelId/kb/consistency-check", async () =>
          HttpResponse.json({ detail: "Internal error" }, { status: 500 }),
        ),
      );

      await expect(consistencyApi.checkConsistency("novel-1")).rejects.toThrow();
    });

    it("should handle empty issues list", async () => {
      server.use(
        http.post("*/api/v1/novels/novel-1/kb/consistency-check", async () =>
          HttpResponse.json({
            novel_id: "novel-1",
            entity_count: 10,
            issues: [],
            summary: {},
            suppressed_count: 0,
            checked_at: "2026-05-27T12:00:00Z",
          }),
        ),
      );

      const result = await consistencyApi.checkConsistency("novel-1");
      expect(result.issues).toHaveLength(0);
      expect(result.summary).toEqual({});
      expect(result.suppressed_count).toBe(0);
    });
  });

  describe("consistencyFingerprint", () => {
    function createIssue(overrides: Partial<ConsistencyIssue> = {}): ConsistencyIssue {
      return {
        finding_index: 0,
        category: "timeline",
        entity_ids: ["e1", "e2"],
        entity_names: ["Anna", "Johann"],
        description: "Timeline mismatch",
        contradiction: "Wrong order",
        suggested_resolution: null,
        severity: "major",
        confidence: 0.8,
        ...overrides,
      } as ConsistencyIssue;
    }

    it("produces description::sorted_entity_names fingerprint", () => {
      const fp = consistencyFingerprint(createIssue());

      // Sorted alphabetically: Anna, Johann
      expect(fp).toBe("Timeline mismatch::Anna,Johann");
    });

    it("sorts entity_names so order is irrelevant", () => {
      const a = consistencyFingerprint(createIssue({ entity_names: ["Johann", "Anna"] }));
      const b = consistencyFingerprint(createIssue({ entity_names: ["Anna", "Johann"] }));

      expect(a).toBe(b);
    });

    it("is stable across re-runs for identical content", () => {
      const issue = createIssue();
      expect(consistencyFingerprint(issue)).toBe(consistencyFingerprint({ ...issue }));
    });

    it("does not mutate the original entity_names array", () => {
      const issue = createIssue({ entity_names: ["Johann", "Anna"] });
      const original = [...issue.entity_names];

      consistencyFingerprint(issue);

      expect(issue.entity_names).toEqual(original);
    });

    it("handles a single entity", () => {
      const fp = consistencyFingerprint(createIssue({ entity_names: ["Solo"] }));

      expect(fp).toBe("Timeline mismatch::Solo");
    });
  });

  describe("dismissFinding", () => {
    it("POSTs fingerprint to dismiss endpoint", async () => {
      let capturedBody: Record<string, unknown> = {};
      let capturedUrl = "";

      server.use(
        http.post("*/api/v1/novels/novel-1/kb/consistency/dismiss", async ({ request }) => {
          capturedUrl = new URL(request.url).pathname;
          capturedBody = (await request.json()) as Record<string, unknown>;
          return HttpResponse.json({ success: true });
        }),
      );

      const result = await consistencyApi.dismissFinding("novel-1", {
        fingerprint: "desc::Anna,Johann",
        reason: "intentional",
      });

      expect(capturedUrl).toBe("/api/v1/novels/novel-1/kb/consistency/dismiss");
      expect(capturedBody.fingerprint).toBe("desc::Anna,Johann");
      expect(capturedBody.reason).toBe("intentional");
      expect(result.success).toBe(true);
    });

    it("omits reason when not provided", async () => {
      let capturedBody: Record<string, unknown> = {};

      server.use(
        http.post("*/api/v1/novels/novel-1/kb/consistency/dismiss", async ({ request }) => {
          capturedBody = (await request.json()) as Record<string, unknown>;
          return HttpResponse.json({ success: true });
        }),
      );

      await consistencyApi.dismissFinding("novel-1", { fingerprint: "fp" });

      expect(capturedBody.fingerprint).toBe("fp");
      expect(capturedBody).not.toHaveProperty("reason");
    });
  });

  describe("listDismissed", () => {
    it("GETs dismissed fingerprints list", async () => {
      server.use(
        http.get("*/api/v1/novels/novel-1/kb/consistency/dismissed", async () =>
          HttpResponse.json({ fingerprints: ["fp1::a,b", "fp2::c"] }),
        ),
      );

      const result = await consistencyApi.listDismissed("novel-1");

      expect(result.fingerprints).toEqual(["fp1::a,b", "fp2::c"]);
    });

    it("returns empty list when none dismissed", async () => {
      server.use(
        http.get("*/api/v1/novels/novel-1/kb/consistency/dismissed", async () =>
          HttpResponse.json({ fingerprints: [] }),
        ),
      );

      const result = await consistencyApi.listDismissed("novel-1");

      expect(result.fingerprints).toEqual([]);
    });
  });

  describe("undismissFinding", () => {
    it("DELETEs the URL-encoded fingerprint", async () => {
      let capturedUrl = "";
      let capturedMethod = "";

      server.use(
        http.delete(
          "*/api/v1/novels/novel-1/kb/consistency/dismissed/:fingerprint",
          ({ request, params }) => {
            capturedUrl = new URL(request.url).pathname;
            capturedMethod = request.method;
            return HttpResponse.json({ success: true });
          },
        ),
      );

      const fingerprint = "desc::Anna,Johann";

      const result = await consistencyApi.undismissFinding("novel-1", fingerprint);

      expect(capturedMethod).toBe("DELETE");
      // Fingerprint must be URL-encoded in the path
      expect(capturedUrl).toContain(encodeURIComponent(fingerprint));
      expect(result.success).toBe(true);
    });
  });
});
