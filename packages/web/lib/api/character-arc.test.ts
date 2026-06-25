/**
 * Tests for the character-arc API client.
 *
 * Verifies endpoint path, request body shape, abort-signal forwarding,
 * and error handling. Uses MSW (project standard for API client tests).
 */
import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { server } from "@/mocks/server";
import { type CharacterArcResponse, generateCharacterArc } from "./character-arc";
import { setAccessToken } from "./client";

describe("generateCharacterArc", () => {
  const NOVEL_ID = "novel-123";

  beforeEach(() => {
    setAccessToken("");
  });

  // --- 1. Happy path: correct endpoint, method, and body ---

  it("posts to /planning/character-arc/{novelId} with the request body", async () => {
    let capturedMethod: string | null = null;
    let capturedBody: Record<string, unknown> | null = null;
    let capturedNovelId: string | null = null;

    server.use(
      http.post("*/api/v1/planning/character-arc/:novelId", async ({ request, params }) => {
        capturedMethod = request.method;
        capturedBody = (await request.json()) as Record<string, unknown>;
        capturedNovelId = params.novelId as string;

        return HttpResponse.json<CharacterArcResponse>({
          character_name: "Alice",
          starting_state: "afraid",
          ending_state: "confident",
          arc_type: "growth",
          phases: [],
          key_relationships: [],
          internal_conflict: "",
          resolution: "",
        });
      }),
    );

    const result = await generateCharacterArc(NOVEL_ID, {
      character_name: "Alice",
      character_current_state: "afraid of public speaking",
      character_goal_state: "confident speaker",
    });

    expect(capturedMethod).toBe("POST");
    expect(capturedNovelId).toBe(NOVEL_ID);
    expect(capturedBody).toEqual({
      character_name: "Alice",
      character_current_state: "afraid of public speaking",
      character_goal_state: "confident speaker",
    });
    expect(result.character_name).toBe("Alice");
    expect(result.arc_type).toBe("growth");
  });

  // --- 2. Optional fields default to empty strings ---

  it("sends empty strings for optional fields when omitted", async () => {
    let capturedBody: Record<string, unknown> | null = null;

    server.use(
      http.post("*/api/v1/planning/character-arc/:novelId", async ({ request }) => {
        capturedBody = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json<CharacterArcResponse>({
          character_name: "Bob",
          starting_state: "",
          ending_state: "",
          arc_type: "flat",
          phases: [],
          key_relationships: [],
          internal_conflict: "",
          resolution: "",
        });
      }),
    );

    await generateCharacterArc(NOVEL_ID, {
      character_name: "Bob",
      character_current_state: "",
      character_goal_state: "",
    });

    expect(capturedBody).toEqual({
      character_name: "Bob",
      character_current_state: "",
      character_goal_state: "",
    });
  });

  // --- 3. Abort signal is forwarded ---

  it("rejects with AbortError when the signal is aborted", async () => {
    server.use(
      http.post("*/api/v1/planning/character-arc/:novelId", async () => {
        // Simulate a slow response
        await new Promise((resolve) => setTimeout(resolve, 500));
        return HttpResponse.json<CharacterArcResponse>({
          character_name: "Late",
          starting_state: "",
          ending_state: "",
          arc_type: "growth",
          phases: [],
          key_relationships: [],
          internal_conflict: "",
          resolution: "",
        });
      }),
    );

    const controller = new AbortController();
    controller.abort();

    await expect(
      generateCharacterArc(
        NOVEL_ID,
        { character_name: "X", character_current_state: "", character_goal_state: "" },
        controller.signal,
      ),
    ).rejects.toThrow();
  });

  // --- 4. HTTP error is surfaced ---

  it("rejects on HTTP error", async () => {
    server.use(
      http.post("*/api/v1/planning/character-arc/:novelId", async () => {
        return HttpResponse.json({ detail: "Boom" }, { status: 500 });
      }),
    );

    await expect(
      generateCharacterArc(NOVEL_ID, {
        character_name: "X",
        character_current_state: "",
        character_goal_state: "",
      }),
    ).rejects.toThrow("Boom");
  });
});
