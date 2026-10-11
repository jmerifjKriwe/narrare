import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { server } from "@/mocks/server";
import type { ChapterPlanContext } from "@/types/planning";
import { setAccessToken } from "../client";
import { chaptersApi } from "../novels";

/**
 * Unit tests for the summary-only chapter plan-context wrapper
 * (PLAN-001 Wave-3 W-D FE half).
 *
 * Follows the planning.test.ts house pattern: MSW intercepts the request,
 * URL/method are captured via a per-test handler override, and the parsed
 * payload is asserted field-exactly (RULE-17 — incl. nullable neighbors).
 */

let capturedMethod = "";
let capturedUrl = "";

const planContextHandlers = [
  http.get("*/api/v1/novels/:novelId/chapters/:chapterId/plan-context", ({ request }) => {
    capturedMethod = request.method;
    capturedUrl = new URL(request.url).pathname;
    return HttpResponse.json<ChapterPlanContext>({
      chapter: { title: "The Gate", summary: "John reaches the gate." },
      previous: { title: "Storm", summary: "The fleet sails." },
      next: { title: "Ash", summary: "The city burns." },
    });
  }),
];

describe("chaptersApi.getPlanContext", () => {
  beforeEach(() => {
    capturedMethod = "";
    capturedUrl = "";
    setAccessToken("test-access-token");
    server.use(...planContextHandlers);
  });

  it("should GET /novels/:novelId/chapters/:chapterId/plan-context and return the payload", async () => {
    const result = await chaptersApi.getPlanContext("novel-42", "chapter-99");

    expect(capturedMethod).toBe("GET");
    expect(capturedUrl).toContain("/api/v1/novels/novel-42/chapters/chapter-99/plan-context");
    expect(result.chapter).toEqual({ title: "The Gate", summary: "John reaches the gate." });
    expect(result.previous).toEqual({ title: "Storm", summary: "The fleet sails." });
    expect(result.next).toEqual({ title: "Ash", summary: "The city burns." });
  });

  it("should carry no content field (summary-only payload)", async () => {
    const result = await chaptersApi.getPlanContext("novel-1", "ch-1");

    expect(Object.keys(result.chapter)).toEqual(["title", "summary"]);
    expect(JSON.stringify(result)).not.toContain("content");
  });

  it("should round-trip null neighbors at the chapter edges", async () => {
    server.use(
      http.get("*/api/v1/novels/:novelId/chapters/:chapterId/plan-context", () =>
        HttpResponse.json<ChapterPlanContext>({
          chapter: { title: "The Gate", summary: "John reaches the gate." },
          previous: null,
          next: null,
        }),
      ),
    );

    const result = await chaptersApi.getPlanContext("novel-1", "ch-1");

    expect(result.chapter.title).toBe("The Gate");
    expect(result.previous).toBeNull();
    expect(result.next).toBeNull();
  });
});
