import { HttpResponse, http } from "msw";

// ---------------------------------------------------------------------------
// Prompts
// ---------------------------------------------------------------------------

export const handlers = [
  http.get("*/api/v1/prompts", async ({ request }) => {
    const url = new URL(request.url);
    const category = url.searchParams.get("category");

    const allPrompts = [
      {
        prompt_id: "write-extend-en",
        name: "Write / Extend",
        category: "writing",
        language: "en",
        source: "bundled",
        has_override: false,
        prompt_version: "1.0.0",
        is_overridden: false,
      },
      {
        prompt_id: "write-extend-de",
        name: "Write / Extend (DE)",
        category: "writing",
        language: "de",
        source: "bundled",
        has_override: false,
        prompt_version: "1.0.0",
        is_overridden: false,
      },
      {
        prompt_id: "analyse-sentiment-en",
        name: "Analyse / Sentiment",
        category: "analysis",
        language: "en",
        source: "override",
        has_override: true,
        prompt_version: "1.1.0",
        is_overridden: true,
      },
      {
        prompt_id: "kb-create-en",
        name: "KB / Create",
        category: "kb",
        language: "en",
        source: "bundled",
        has_override: false,
        prompt_version: "1.0.0",
        is_overridden: false,
      },
      {
        prompt_id: "generation-names-en",
        name: "Generation / Names",
        category: "generation",
        language: "en",
        source: "bundled",
        has_override: false,
        prompt_version: "1.0.0",
        is_overridden: false,
      },
    ];

    const filtered = category ? allPrompts.filter((p) => p.category === category) : allPrompts;
    return HttpResponse.json(filtered);
  }),

  http.get("*/api/v1/prompts/updates", async () => {
    return HttpResponse.json([
      {
        prompt_id: "analyse-sentiment-en",
        override_version: "1.0.0",
        current_bundled_version: "1.1.0",
      },
    ]);
  }),

  http.get("*/api/v1/prompts/:id", async ({ params }) => {
    const { id } = params;
    const isOverridden = (id as string).includes("sentiment");
    return HttpResponse.json({
      prompt_id: id,
      content: isOverridden
        ? "You are a sentiment analysis expert. Override content here."
        : "You are a helpful writing assistant. Base content here.",
      base_content: "You are a helpful writing assistant. Base content here.",
      source: isOverridden ? "override" : "bundled",
      is_overridden: isOverridden,
      variables: ["text", "language", "context"],
      metadata: { version: "1.0.0" },
    });
  }),

  http.put("*/api/v1/prompts/:id", async () => {
    return new HttpResponse(null, { status: 204 });
  }),

  http.delete("*/api/v1/prompts/:id/override", async () => {
    return new HttpResponse(null, { status: 204 });
  }),

  http.get("*/api/v1/prompts/:id/diff", async () => {
    return HttpResponse.json({
      prompt_id: "analyse-sentiment-en",
      override_content: "You are a sentiment analysis expert. Override content here.",
      bundled_content:
        "You are a sentiment analysis expert. New bundled version with improvements.",
    });
  }),

  // ---------------------------------------------------------------------------
  // Generation — Names
  // ---------------------------------------------------------------------------

  http.post("*/api/v1/generation/names", async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    const count = (body.count as number) || 5;
    const names = Array.from({ length: count }, (_, i) => ({
      name: `TestName${i + 1}`,
      pronunciation: i % 2 === 0 ? "TEST-nam" : null,
      meaning: i % 3 === 0 ? "Test meaning" : null,
      type: body.name_type ?? "character",
      name_style: (body as Record<string, unknown>).name_style ?? "fantasy",
      is_duplicate: i === 0,
      confidence: 0.9 - i * 0.05,
    }));
    return HttpResponse.json({
      names,
      count: names.length,
      name_style: (body as Record<string, unknown>).name_style ?? "fantasy",
      name_type: body.name_type ?? "character",
    });
  }),

  // ---------------------------------------------------------------------------
  // Writing — Generation
  // ---------------------------------------------------------------------------

  http.post("*/api/v1/writing/chapters/:chapterId/generate", async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json({
      request_id: "gen-test-id",
      status: "pending",
      mode: body.mode ?? "full_draft",
    });
  }),

  http.delete("*/api/v1/writing/generation/:requestId", async () => {
    return HttpResponse.json({
      request_id: "gen-test-id",
      status: "stopped",
      word_count: 800,
    });
  }),

  http.post("*/api/v1/writing/generation/:requestId/accept", async () => {
    return HttpResponse.json({
      request_id: "gen-test-id",
      chapter_id: "chapter-1",
      word_count: 1200,
    });
  }),

  http.post("*/api/v1/writing/generation/:requestId/reject", async () => {
    return HttpResponse.json({
      request_id: "gen-test-id",
      status: "rejected",
    });
  }),

  http.post("*/api/v1/writing/generation/:requestId/scene/next", async () => {
    return HttpResponse.json({
      request_id: "gen-test-id",
      scene_number: 2,
      status: "streaming",
    });
  }),

  http.post("*/api/v1/writing/generation/:requestId/scene/:sceneNum/accept", async () => {
    return HttpResponse.json({
      request_id: "gen-test-id",
      chapter_id: "chapter-1",
      word_count: 400,
    });
  }),

  http.get("*/api/v1/writing/novels/:novelId/stats", async () => {
    return HttpResponse.json({
      total_generations: 42,
      success_rate: 0.95,
      avg_tokens: 1500,
      avg_word_count: 800,
      most_used_model: "gpt-4",
    });
  }),
];
