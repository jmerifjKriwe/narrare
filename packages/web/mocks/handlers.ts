import { HttpResponse, http } from "msw";

export const handlers = [
  // ---------------------------------------------------------------------------
  // Auth
  // ---------------------------------------------------------------------------

  http.post("*/api/v1/auth/register", async ({ request }) => {
    const _body = (await request.json()) as Record<string, string>;
    return HttpResponse.json({
      access_token: "test-access-token",
      refresh_token: "test-refresh-token",
      token_type: "bearer",
      expires_in: 3600,
    });
  }),

  http.post("*/api/v1/auth/login", async ({ request }) => {
    const _body = (await request.json()) as Record<string, string>;
    return HttpResponse.json({
      access_token: "test-access-token",
      refresh_token: "test-refresh-token",
      token_type: "bearer",
      expires_in: 3600,
    });
  }),

  http.post("*/api/v1/auth/refresh", async ({ request }) => {
    // Simulate production behavior: refresh requires credentials: "include"
    // so the httpOnly cookie is sent. In tests we verify the request was
    // made without a body (cookie-based, not JSON body-based).
    const contentType = request.headers.get("Content-Type");
    // Cookie-based refresh should NOT send Content-Type (no body)
    if (contentType) {
      return HttpResponse.json({ detail: "Unexpected body" }, { status: 400 });
    }
    return HttpResponse.json({
      access_token: "refreshed-access-token",
      refresh_token: "refreshed-refresh-token",
      token_type: "bearer",
      expires_in: 3600,
    });
  }),

  http.get("*/api/v1/auth/me", async ({ request }) => {
    const authHeader = request.headers.get("Authorization");
    if (!authHeader) {
      return HttpResponse.json({ detail: "Not authenticated" }, { status: 401 });
    }
    return HttpResponse.json({
      id: "test-user-id",
      email: "test@example.com",
      display_name: "Test User",
      is_active: true,
      is_verified: true,
      created_at: "2026-01-01T00:00:00Z",
    });
  }),

  // ---------------------------------------------------------------------------
  // Novels
  // ---------------------------------------------------------------------------

  http.get("*/api/v1/novels", async () => {
    return HttpResponse.json([
      {
        id: "novel-1",
        title: "Test Novel One",
        author: "Author One",
        genre: "fantasy",
        language: "en",
        is_demo: false,
        updated_at: "2026-01-15T10:30:00Z",
      },
      {
        id: "novel-2",
        title: "Test Novel Two",
        author: "Author Two",
        genre: "scifi",
        language: "en",
        is_demo: true,
        updated_at: "2026-02-20T14:00:00Z",
      },
    ]);
  }),

  http.post("*/api/v1/novels", async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json(
      {
        id: "new-novel-id",
        title: body.title ?? "New Novel",
        author: body.author ?? "",
        genre: body.genre ?? "",
        language: body.language ?? "en",
        tone: body.tone ?? "",
        story_structure: body.story_structure ?? "three_act",
        logline: body.logline ?? "",
        synopsis: body.synopsis ?? "",
        is_demo: false,
        created_at: "2026-03-01T00:00:00Z",
        updated_at: "2026-03-01T00:00:00Z",
      },
      { status: 201 },
    );
  }),

  http.get("*/api/v1/novels/:id", async ({ params }) => {
    const { id } = params;
    return HttpResponse.json({
      id,
      title: "Test Novel",
      author: "Test Author",
      genre: "fantasy",
      language: "en",
      tone: "dramatic",
      story_structure: "three_act",
      logline: "A test logline",
      synopsis: "A test synopsis",
      is_demo: false,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    });
  }),

  http.patch("*/api/v1/novels/:id", async ({ params, request }) => {
    const { id } = params;
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json({
      id,
      title: body.title ?? "Updated Novel",
      author: body.author ?? "Test Author",
      genre: body.genre ?? "fantasy",
      language: body.language ?? "en",
      tone: body.tone ?? "",
      story_structure: body.story_structure ?? "three_act",
      logline: body.logline ?? "",
      synopsis: body.synopsis ?? "",
      is_demo: false,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-06-01T00:00:00Z",
    });
  }),

  http.delete("*/api/v1/novels/:id", async () => {
    return new HttpResponse(null, { status: 204 });
  }),

  // ---------------------------------------------------------------------------
  // Chapters
  // ---------------------------------------------------------------------------

  http.get("*/api/v1/novels/:novelId/chapters", async () => {
    return HttpResponse.json([
      {
        id: "chapter-1",
        novel_id: "novel-1",
        volume_id: null,
        title: "Chapter One",
        position: 0,
        word_count: 1500,
        status: "draft",
        updated_at: "2026-01-15T10:30:00Z",
      },
      {
        id: "chapter-2",
        novel_id: "novel-1",
        volume_id: null,
        title: "Chapter Two",
        position: 1,
        word_count: 2300,
        status: "reviewed",
        updated_at: "2026-01-20T14:00:00Z",
      },
    ]);
  }),

  http.post("*/api/v1/novels/:novelId/chapters", async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json(
      {
        id: "new-chapter-id",
        novel_id: "novel-1",
        volume_id: null,
        title: body.title ?? "New Chapter",
        content: body.content ?? "",
        summary: "",
        position: 2,
        word_count: 0,
        status: "draft",
        pov_character_id: "",
        timeline_position: "",
        created_at: "2026-03-01T00:00:00Z",
        updated_at: "2026-03-01T00:00:00Z",
      },
      { status: 201 },
    );
  }),

  // ---------------------------------------------------------------------------
  // Setup Wizard
  // ---------------------------------------------------------------------------

  http.post("*/api/v1/setup/validate/step-1", async () => {
    return HttpResponse.json({ valid: true });
  }),

  http.post("*/api/v1/setup/validate/step-2", async () => {
    return HttpResponse.json({ valid: true });
  }),

  http.post("*/api/v1/setup/validate/step-3", async () => {
    return HttpResponse.json({ valid: true, starter: "blank", demo_info: null });
  }),

  http.post("*/api/v1/setup/validate/step-4", async () => {
    return HttpResponse.json({ valid: true });
  }),

  http.get("*/api/v1/setup/providers/:provider/models", async () => {
    return HttpResponse.json({
      provider: "openai",
      models: [
        { id: "gpt-4", name: "GPT-4" },
        { id: "gpt-4o", name: "GPT-4o" },
      ],
    });
  }),

  http.post("*/api/v1/setup/complete", async () => {
    return HttpResponse.json({
      novel_id: "new-novel-id",
      redirect_to: "/novel/new-novel-id",
      message: "Setup complete",
    });
  }),

  // ---------------------------------------------------------------------------
  // Prompts
  // ---------------------------------------------------------------------------

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
      culture: body.culture ?? "fantasy",
      is_duplicate: i === 0,
      confidence: 0.9 - i * 0.05,
    }));
    return HttpResponse.json({
      names,
      count: names.length,
      culture: body.culture ?? "fantasy",
      name_type: body.name_type ?? "character",
    });
  }),
];
