import { HttpResponse, http } from "msw";

// ---------------------------------------------------------------------------
// Novels
// ---------------------------------------------------------------------------

export const handlers = [
  http.get("*/api/v1/novels", async () => {
    return HttpResponse.json([
      {
        id: "novel-1",
        title: "Test Novel One",
        author: "Author One",
        genre: "fantasy",
        writing_language: "en",
        is_demo: false,
        updated_at: "2026-01-15T10:30:00Z",
      },
      {
        id: "novel-2",
        title: "Test Novel Two",
        author: "Author Two",
        genre: "scifi",
        writing_language: "en",
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
        writing_language: (body as Record<string, unknown>).writing_language ?? "en",
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
      writing_language: "en",
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
      writing_language: (body as Record<string, unknown>).writing_language ?? "en",
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
  // Volumes
  // ---------------------------------------------------------------------------

  http.get("*/api/v1/novels/:novelId/volumes", async () => {
    return HttpResponse.json([
      {
        id: "volume-1",
        novel_id: "novel-1",
        title: "Volume One",
        subtitle: "The Beginning",
        description: "The first volume",
        word_count_target: 50000,
        is_default: true,
        position: 0,
        created_at: "2026-01-01T00:00:00Z",
      },
      {
        id: "volume-2",
        novel_id: "novel-1",
        title: "Volume Two",
        subtitle: null,
        description: null,
        word_count_target: 60000,
        is_default: false,
        position: 1,
        created_at: "2026-02-01T00:00:00Z",
      },
    ]);
  }),

  http.post("*/api/v1/novels/:novelId/volumes", async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json(
      {
        id: "new-volume-id",
        novel_id: "novel-1",
        title: body.title ?? "New Volume",
        subtitle: body.subtitle ?? null,
        description: body.description ?? null,
        word_count_target: body.word_count_target ?? null,
        is_default: false,
        position: 2,
        created_at: "2026-03-01T00:00:00Z",
      },
      { status: 201 },
    );
  }),

  http.patch("*/api/v1/novels/:novelId/volumes/:volumeId", async ({ params, request }) => {
    const { volumeId } = params;
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json({
      id: volumeId,
      novel_id: "novel-1",
      title: body.title ?? "Updated Volume",
      subtitle: body.subtitle ?? null,
      description: body.description ?? null,
      word_count_target: body.word_count_target ?? null,
      is_default: false,
      position: 0,
      created_at: "2026-01-01T00:00:00Z",
    });
  }),

  http.delete("*/api/v1/novels/:novelId/volumes/:volumeId", async () => {
    return new HttpResponse(null, { status: 204 });
  }),

  http.get("*/api/v1/novels/:novelId/volumes/:volumeId/stats", async () => {
    return HttpResponse.json({
      word_count: 45000,
      chapter_count: 12,
      word_count_target: 50000,
      completion_percentage: 90,
    });
  }),

  http.patch("*/api/v1/novels/:novelId/volumes/reorder", async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    const volumeIds = body.volume_ids as string[];
    const volumes = volumeIds.map((id, index) => ({
      id,
      novel_id: "novel-1",
      title: `Volume ${index + 1}`,
      subtitle: null,
      description: null,
      word_count_target: null,
      is_default: index === 0,
      position: index,
      created_at: "2026-01-01T00:00:00Z",
    }));
    return HttpResponse.json(volumes);
  }),

  // ---------------------------------------------------------------------------
  // Chapter Details
  // ---------------------------------------------------------------------------

  http.get("*/api/v1/novels/:novelId/chapters/:chapterId", async ({ params }) => {
    const { chapterId } = params;
    return HttpResponse.json({
      id: chapterId,
      novel_id: "novel-1",
      volume_id: null,
      title: "Test Chapter",
      content: "<p>Chapter content here.</p>",
      summary: "A test chapter summary",
      position: 0,
      word_count: 1500,
      status: "draft",
      pov_character_id: "",
      timeline_position: "",
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-15T10:30:00Z",
    });
  }),

  http.put("*/api/v1/novels/:novelId/chapters/:chapterId/content", async ({ params, request }) => {
    const { chapterId } = params;
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json({
      id: chapterId,
      novel_id: "novel-1",
      volume_id: null,
      title: "Test Chapter",
      content: body.content ?? "<p>Updated content.</p>",
      summary: "A test chapter summary",
      position: 0,
      word_count: (body.content as string)?.split(/\s+/).length ?? 1500,
      status: "draft",
      pov_character_id: "",
      timeline_position: "",
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-06-01T00:00:00Z",
    });
  }),

  http.patch("*/api/v1/novels/:novelId/chapters/:chapterId", async ({ params, request }) => {
    const { chapterId } = params;
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json({
      id: chapterId,
      novel_id: "novel-1",
      volume_id: body.volume_id ?? null,
      title: body.title ?? "Updated Chapter",
      content: "<p>Chapter content here.</p>",
      summary: body.summary ?? "A test chapter summary",
      position: body.position ?? 0,
      word_count: 1500,
      status: body.status ?? "draft",
      pov_character_id: body.pov_character_id ?? "",
      timeline_position: body.timeline_position ?? "",
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-06-01T00:00:00Z",
    });
  }),

  http.delete("*/api/v1/novels/:novelId/chapters/:chapterId", async () => {
    return new HttpResponse(null, { status: 204 });
  }),

  http.post("*/api/v1/novels/:novelId/chapters/reorder", async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    const chapterIds = body.chapter_ids as string[];
    const chapters = chapterIds.map((id, index) => ({
      id,
      novel_id: "novel-1",
      volume_id: null,
      title: `Chapter ${index + 1}`,
      position: index,
      word_count: 1500,
      status: "draft",
      updated_at: "2026-01-15T10:30:00Z",
    }));
    return HttpResponse.json(chapters);
  }),
];
