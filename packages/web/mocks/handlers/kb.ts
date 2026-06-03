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

// ---------------------------------------------------------------------------
// KB Entries
// ---------------------------------------------------------------------------

export const handlers = [
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
];
