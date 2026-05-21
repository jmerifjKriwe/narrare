import { HttpResponse, http } from "msw";

// ---------------------------------------------------------------------------
// KB Mock Data (shared across KB handlers)
// ---------------------------------------------------------------------------

const kbEntries = [
  {
    id: "kb-entry-1",
    novel_id: "novel-1",
    entity_type: "character",
    name: "Anna Schmidt",
    slug: "anna-schmidt",
    status: "canon",
    tags: ["protagonist", "historian"],
    metadata: { role: "Protagonist" },
    body: "A young historian who works at the university library.",
    template_version: null,
    created_at: "2026-01-10T10:00:00Z",
    updated_at: "2026-05-15T14:30:00Z",
  },
  {
    id: "kb-entry-2",
    novel_id: "novel-1",
    entity_type: "character",
    name: "Dr. Viktor Stein",
    slug: "dr-viktor-stein",
    status: "draft",
    tags: ["antagonist"],
    metadata: { role: "Antagonist" },
    body: "A charismatic professor of medieval history.",
    template_version: null,
    created_at: "2026-01-12T08:00:00Z",
    updated_at: "2026-05-14T09:00:00Z",
  },
  {
    id: "kb-entry-3",
    novel_id: "novel-1",
    entity_type: "location",
    name: "The Old Archive",
    slug: "the-old-archive",
    status: "reviewed",
    tags: ["underground", "secret"],
    metadata: { type: "Underground" },
    body: "An underground archive beneath the old university library.",
    template_version: null,
    created_at: "2026-02-01T12:00:00Z",
    updated_at: "2026-05-10T16:00:00Z",
  },
  {
    id: "kb-entry-4",
    novel_id: "novel-1",
    entity_type: "object",
    name: "The Encrypted Diary",
    slug: "the-encrypted-diary",
    status: "draft",
    tags: ["artifact", "cipher"],
    metadata: { category: "Document" },
    body: "A leather diary from the 18th century with an unbroken cipher.",
    template_version: null,
    created_at: "2026-03-01T10:00:00Z",
    updated_at: "2026-05-01T11:00:00Z",
  },
  {
    id: "kb-entry-5",
    novel_id: "novel-1",
    entity_type: "faction",
    name: "The Order of the Key",
    slug: "the-order-of-the-key",
    status: "canon",
    tags: ["secret-society"],
    metadata: {},
    body: "A centuries-old secret society dedicated to protecting ancient knowledge.",
    template_version: null,
    created_at: "2026-02-15T09:00:00Z",
    updated_at: "2026-05-12T13:00:00Z",
  },
];

const kbRelationships = [
  {
    id: "rel-1",
    source_id: "kb-entry-1",
    target_id: "kb-entry-3",
    rel_type: "frequents",
    label: "Studies at",
    direction: "directed",
    metadata: {},
    source_name: "Anna Schmidt",
    target_name: "The Old Archive",
    source_type: "character",
    target_type: "location",
    created_at: "2026-03-01T00:00:00Z",
    updated_at: "2026-03-01T00:00:00Z",
  },
];

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

  http.post("*/api/v1/auth/logout", async () => {
    return new HttpResponse(null, { status: 204 });
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
  // KB Entries
  // ---------------------------------------------------------------------------

  http.get("*/api/v1/novels/:novelId/kb/entries", async ({ request, params }) => {
    const url = new URL(request.url);
    const entityType = url.searchParams.get("entity_type");
    const page = Number(url.searchParams.get("page")) || 1;
    const pageSize = Number(url.searchParams.get("page_size")) || 20;

    let filtered = kbEntries.filter((e) => e.novel_id === params.novelId);
    if (entityType) {
      filtered = filtered.filter((e) => e.entity_type === entityType);
    }

    const start = (page - 1) * pageSize;
    const items = filtered.slice(start, start + pageSize);

    return HttpResponse.json({
      items,
      total: filtered.length,
      page,
      page_size: pageSize,
    });
  }),

  http.get("*/api/v1/novels/:novelId/kb/entries/search", async ({ request }) => {
    const url = new URL(request.url);
    const q = url.searchParams.get("q") ?? "";
    const entityType = url.searchParams.get("entity_type");

    let filtered = kbEntries;
    if (entityType) filtered = filtered.filter((e) => e.entity_type === entityType);
    if (q) {
      const lower = q.toLowerCase();
      filtered = filtered.filter(
        (e) =>
          e.name.toLowerCase().includes(lower) ||
          e.body.toLowerCase().includes(lower) ||
          e.tags.some((t: string) => t.toLowerCase().includes(lower)),
      );
    }

    return HttpResponse.json({
      items: filtered,
      total: filtered.length,
      page: 1,
      page_size: 20,
    });
  }),

  http.get("*/api/v1/novels/:novelId/kb/entries/:entryId", async ({ params }) => {
    const entry = kbEntries.find((e) => e.id === params.entryId);
    if (!entry) return HttpResponse.json({ detail: "Not found" }, { status: 404 });
    return HttpResponse.json(entry);
  }),

  http.post("*/api/v1/novels/:novelId/kb/entries", async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    const newEntry = {
      id: "kb-entry-new",
      novel_id: "novel-1",
      entity_type: body.entity_type ?? "character",
      name: body.name ?? "New Entry",
      slug: ((body.name as string) ?? "new-entry").toLowerCase().replace(/\s+/g, "-"),
      status: body.status ?? "draft",
      tags: body.tags ?? [],
      metadata: body.metadata ?? {},
      body: body.body ?? "",
      template_version: null,
      created_at: "2026-06-01T00:00:00Z",
      updated_at: "2026-06-01T00:00:00Z",
    };
    return HttpResponse.json(newEntry, { status: 201 });
  }),

  http.patch("*/api/v1/novels/:novelId/kb/entries/:entryId", async ({ params, request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    const existing = kbEntries.find((e) => e.id === params.entryId);
    return HttpResponse.json({
      ...(existing ?? {}),
      ...body,
      id: params.entryId,
      updated_at: "2026-06-01T00:00:00Z",
    });
  }),

  http.delete("*/api/v1/novels/:novelId/kb/entries/:entryId", async () => {
    return new HttpResponse(null, { status: 204 });
  }),

  // ---------------------------------------------------------------------------
  // KB Relationships
  // ---------------------------------------------------------------------------

  http.get("*/api/v1/novels/:novelId/kb/entries/:entryId/relationships", async ({ params }) => {
    const rels = kbRelationships.filter(
      (r) => r.source_id === params.entryId || r.target_id === params.entryId,
    );
    return HttpResponse.json(rels);
  }),

  http.post("*/api/v1/novels/:novelId/kb/relationships", async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json(
      {
        id: "rel-new",
        source_id: body.source_id,
        target_id: body.target_id,
        rel_type: body.rel_type,
        label: body.label ?? null,
        direction: body.direction ?? "directed",
        metadata: body.metadata ?? {},
        created_at: "2026-06-01T00:00:00Z",
        updated_at: "2026-06-01T00:00:00Z",
      },
      { status: 201 },
    );
  }),

  http.delete("*/api/v1/novels/:novelId/kb/relationships/:relId", async () => {
    return new HttpResponse(null, { status: 204 });
  }),

  http.get("*/api/v1/novels/:novelId/kb/relationships/inverse-suggestion", async ({ request }) => {
    const url = new URL(request.url);
    const relType = url.searchParams.get("rel_type") ?? "";
    return HttpResponse.json({
      rel_type: relType,
      inverse_rel_type: relType.split("_").reverse().join("_"),
      description: `Inverse of ${relType}`,
    });
  }),

  // ---------------------------------------------------------------------------
  // KB Templates
  // ---------------------------------------------------------------------------

  http.get("*/api/v1/novels/:novelId/kb/templates", async () => {
    return HttpResponse.json([
      {
        entity_type: "character",
        scope: "default",
        schema_version: "2.0.0",
        has_override: false,
        has_update: false,
      },
    ]);
  }),

  http.get("*/api/v1/novels/:novelId/kb/templates/character", async () => {
    return HttpResponse.json({
      meta: {
        template_type: "character",
        template_version: "2.0.0",
        schema_version: "2.0.0",
      },
      fields: [
        { name: "age", field_type: "str", required: false, description: "Character's age" },
        { name: "role", field_type: "str", required: false, description: "Role in the story" },
      ],
      field_groups: [
        {
          name: "basic_info",
          label_key: "kb.groups.basicInfo",
          description_key: "",
          order: 1,
          fields: [
            { name: "age", field_type: "str", required: false, description: "Character's age" },
            { name: "role", field_type: "str", required: false, description: "Role in the story" },
            { name: "gender", field_type: "str", required: false, description: "Gender" },
            { name: "pronouns", field_type: "str", required: false, description: "Pronouns" },
            {
              name: "nationality",
              field_type: "str",
              required: false,
              description: "Nationality or origin",
            },
            {
              name: "pov_character",
              field_type: "bool",
              required: false,
              description: "Is this a POV character?",
            },
            {
              name: "affiliation",
              field_type: "str",
              required: false,
              description: "Group or organization",
            },
            {
              name: "aliases",
              field_type: "list",
              required: false,
              description: "Other names or titles",
            },
          ],
        },
        {
          name: "appearance",
          label_key: "kb.groups.appearance",
          description_key: "",
          order: 2,
          fields: [
            { name: "height", field_type: "str", required: false, description: "Height" },
            { name: "build", field_type: "str", required: false, description: "Body type" },
            { name: "hair_color", field_type: "str", required: false, description: "Hair color" },
            { name: "eye_color", field_type: "str", required: false, description: "Eye color" },
            { name: "skin_tone", field_type: "str", required: false, description: "Skin tone" },
            {
              name: "distinctive_marks",
              field_type: "str",
              required: false,
              description: "Scars, tattoos, etc.",
            },
            {
              name: "clothing_style",
              field_type: "str",
              required: false,
              description: "Typical attire",
            },
          ],
        },
        {
          name: "personality",
          label_key: "kb.groups.personality",
          description_key: "",
          order: 3,
          fields: [
            {
              name: "traits",
              field_type: "list",
              required: false,
              description: "Core personality traits",
            },
            {
              name: "strengths",
              field_type: "list",
              required: false,
              description: "Character strengths",
            },
            {
              name: "weaknesses",
              field_type: "list",
              required: false,
              description: "Character weaknesses",
            },
            {
              name: "fears",
              field_type: "list",
              required: false,
              description: "Fears and anxieties",
            },
            {
              name: "desires",
              field_type: "list",
              required: false,
              description: "Desires and goals",
            },
            {
              name: "motivations",
              field_type: "str",
              required: false,
              description: "Core motivations",
            },
            {
              name: "quirks",
              field_type: "list",
              required: false,
              description: "Quirks and habits",
            },
          ],
        },
      ],
      sections: [
        {
          name: "background",
          label_key: "kb.sections.background",
          description_key: "kb.sections.backgroundHint",
          order: 1,
        },
        {
          name: "development",
          label_key: "kb.sections.development",
          description_key: "kb.sections.developmentHint",
          order: 2,
        },
      ],
      body: "",
    });
  }),

  http.get("*/api/v1/novels/:novelId/kb/templates/:entityType", async ({ params }) => {
    const { entityType } = params;
    // Return 404 for non-character types to test fallback
    return HttpResponse.json(
      { detail: `No template found for entity type '${entityType}'` },
      { status: 404 },
    );
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

  // ---------------------------------------------------------------------------
  // Settings — User & Project
  // ---------------------------------------------------------------------------

  http.get("*/api/v1/settings/user", async () => {
    return HttpResponse.json({
      user_id: "test-user-id",
      display_name: "Test User",
      ui_language: "en",
      theme: "system",
      updated_at: "2026-01-01T00:00:00Z",
    });
  }),

  http.patch("*/api/v1/settings/user", async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json({
      user_id: "test-user-id",
      display_name: body.display_name ?? "Test User",
      ui_language: body.ui_language ?? "en",
      theme: body.theme ?? "system",
      updated_at: "2026-06-01T00:00:00Z",
    });
  }),

  http.get("*/api/v1/settings/novels/:novelId", async ({ params }) => {
    const { novelId } = params;
    return HttpResponse.json({
      novel_id: novelId,
      autosave_interval: 30,
      default_language: "en",
      ai_provider: "openai",
      ai_model: "gpt-4",
      model_overrides: "{}",
      updated_at: "2026-01-01T00:00:00Z",
    });
  }),

  http.patch("*/api/v1/settings/novels/:novelId", async ({ params, request }) => {
    const { novelId } = params;
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json({
      novel_id: novelId,
      autosave_interval: body.autosave_interval ?? 30,
      default_language: body.default_language ?? "en",
      ai_provider: body.ai_provider ?? "openai",
      ai_model: body.ai_model ?? "gpt-4",
      model_overrides: body.model_overrides ?? "{}",
      updated_at: "2026-06-01T00:00:00Z",
    });
  }),

  // ---------------------------------------------------------------------------
  // AI Settings — Providers
  // ---------------------------------------------------------------------------

  http.get("*/api/v1/settings/ai/providers", async () => {
    return HttpResponse.json([
      {
        id: "provider-1",
        provider_name: "openai",
        has_api_key: true,
        api_key_last4: "1234",
        base_url: null,
        is_active: true,
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
      },
      {
        id: "provider-2",
        provider_name: "anthropic",
        has_api_key: true,
        api_key_last4: "5678",
        base_url: null,
        is_active: false,
        created_at: "2026-02-01T00:00:00Z",
        updated_at: "2026-02-01T00:00:00Z",
      },
    ]);
  }),

  http.post("*/api/v1/settings/ai/providers", async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json(
      {
        id: "new-provider-id",
        provider_name: body.provider_name ?? "openai",
        has_api_key: true,
        api_key_last4: "abcd",
        base_url: body.base_url ?? null,
        is_active: true,
        created_at: "2026-03-01T00:00:00Z",
        updated_at: "2026-03-01T00:00:00Z",
      },
      { status: 201 },
    );
  }),

  http.patch("*/api/v1/settings/ai/providers/:id", async ({ params, request }) => {
    const { id } = params;
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json({
      id,
      provider_name: "openai",
      has_api_key: true,
      api_key_last4: body.api_key ? "wxyz" : "1234",
      base_url: body.base_url ?? null,
      is_active: body.is_active ?? true,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-06-01T00:00:00Z",
    });
  }),

  http.delete("*/api/v1/settings/ai/providers/:id", async () => {
    return new HttpResponse(null, { status: 204 });
  }),

  http.get("*/api/v1/settings/ai/providers/:providerId/models", async () => {
    return HttpResponse.json({
      provider: "openai",
      models: [
        { id: "gpt-4", name: "GPT-4", context_window: 8192 },
        { id: "gpt-4o", name: "GPT-4o", context_window: 128000 },
        { id: "gpt-4o-mini", name: "GPT-4o Mini", context_window: 128000 },
      ],
    });
  }),

  // ---------------------------------------------------------------------------
  // AI Settings — User & Project
  // ---------------------------------------------------------------------------

  http.get("*/api/v1/settings/ai", async () => {
    return HttpResponse.json({
      user_id: "test-user-id",
      default_provider_id: "provider-1",
      default_model: "gpt-4",
      category_overrides: {},
      intent_overrides: {},
      token_limit_profile: "balanced",
      token_limit_overrides: {},
      updated_at: "2026-01-01T00:00:00Z",
    });
  }),

  http.patch("*/api/v1/settings/ai", async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json({
      user_id: "test-user-id",
      default_provider_id: body.default_provider_id ?? "provider-1",
      default_model: body.default_model ?? "gpt-4",
      category_overrides: body.category_overrides ?? {},
      intent_overrides: body.intent_overrides ?? {},
      token_limit_profile: body.token_limit_profile ?? "balanced",
      token_limit_overrides: body.token_limit_overrides ?? {},
      updated_at: "2026-06-01T00:00:00Z",
    });
  }),

  http.get("*/api/v1/settings/ai/novels/:novelId", async ({ params }) => {
    const { novelId } = params;
    return HttpResponse.json({
      novel_id: novelId,
      category_overrides: {},
      intent_overrides: {},
      token_limit_overrides: {},
      updated_at: "2026-01-01T00:00:00Z",
    });
  }),

  http.patch("*/api/v1/settings/ai/novels/:novelId", async ({ params, request }) => {
    const { novelId } = params;
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json({
      novel_id: novelId,
      category_overrides: body.category_overrides ?? {},
      intent_overrides: body.intent_overrides ?? {},
      token_limit_overrides: body.token_limit_overrides ?? {},
      updated_at: "2026-06-01T00:00:00Z",
    });
  }),
];
