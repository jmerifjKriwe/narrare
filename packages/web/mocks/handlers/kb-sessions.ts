import { HttpResponse, http } from "msw";

// ---------------------------------------------------------------------------
// KB Sessions (Assisted Creation)
//
// Serves the REAL backend wire shapes (RULE-17 mirror of
// apps/api/narrare/kb/router_sessions.py):
// - suggest / interview / enhance are plain-JSON aggregates
//   `{ session, suggestion | question | enhancement }` — no SSE framing.
// - complete emulates the backend's name guard (F9-1): an absent body or
//   absent name is rejected with 400 when the session has no name.
// ---------------------------------------------------------------------------

function sessionFixture(overrides: Record<string, unknown> = {}) {
  return {
    id: "kb-session-1",
    novel_id: "novel-1",
    user_id: "test-user-id",
    entity_type: "character",
    status: "active",
    name: null,
    fields: [
      {
        field_key: "name",
        label: "Name",
        field_type: "text",
        required: true,
        options: null,
        user_value: "Test Character",
        ai_suggested_value: null,
        ai_reasoning: null,
        source: "user",
        final_value: "Test Character",
      },
      {
        field_key: "description",
        label: "Description",
        field_type: "text",
        required: false,
        options: null,
        user_value: null,
        ai_suggested_value: "A brave adventurer with a mysterious past.",
        ai_reasoning: "Based on common story patterns.",
        source: "ai",
        final_value: null,
      },
      {
        field_key: "background",
        label: "Background",
        field_type: "text",
        required: false,
        options: null,
        user_value: null,
        ai_suggested_value: null,
        ai_reasoning: null,
        source: "user",
        final_value: null,
      },
    ],
    context_entries: [],
    created_at: "2026-06-01T00:00:00Z",
    updated_at: "2026-06-01T00:10:00Z",
    ...overrides,
  };
}

export const handlers = [
  http.post("*/api/v1/novels/:novelId/kb/sessions", async ({ request, params }) => {
    const body = (await request.json()) as Record<string, unknown>;
    const entityType = (body.entity_type as string) || "character";

    // Default fields based on entity type
    const defaultFields = [
      {
        field_key: "name",
        label: "Name",
        field_type: "text",
        required: true,
        options: null,
        user_value: null,
        ai_suggested_value: null,
        ai_reasoning: null,
        source: "user",
        final_value: null,
      },
      {
        field_key: "description",
        label: "Description",
        field_type: "text",
        required: false,
        options: null,
        user_value: null,
        ai_suggested_value: null,
        ai_reasoning: null,
        source: "user",
        final_value: null,
      },
      {
        field_key: "background",
        label: "Background",
        field_type: "text",
        required: false,
        options: null,
        user_value: null,
        ai_suggested_value: null,
        ai_reasoning: null,
        source: "user",
        final_value: null,
      },
    ];

    return HttpResponse.json(
      {
        id: "kb-session-1",
        novel_id: params.novelId,
        user_id: "test-user-id",
        entity_type: entityType,
        status: "active",
        fields: defaultFields,
        context_entries: [],
        created_at: "2026-06-01T00:00:00Z",
        updated_at: "2026-06-01T00:00:00Z",
      },
      { status: 201 },
    );
  }),

  http.get("*/api/v1/novels/:novelId/kb/sessions/:sessionId", async ({ params }) => {
    return HttpResponse.json({
      id: params.sessionId,
      novel_id: params.novelId,
      user_id: "test-user-id",
      entity_type: "character",
      status: "active",
      fields: [
        {
          field_key: "name",
          label: "Name",
          field_type: "text",
          required: true,
          options: null,
          user_value: "Test Character",
          ai_suggested_value: null,
          ai_reasoning: null,
          source: "user",
          final_value: "Test Character",
        },
        {
          field_key: "description",
          label: "Description",
          field_type: "text",
          required: false,
          options: null,
          user_value: null,
          ai_suggested_value: "A brave adventurer with a mysterious past.",
          ai_reasoning: "Based on common story patterns.",
          source: "ai",
          final_value: null,
        },
        {
          field_key: "background",
          label: "Background",
          field_type: "text",
          required: false,
          options: null,
          user_value: null,
          ai_suggested_value: null,
          ai_reasoning: null,
          source: "user",
          final_value: null,
        },
      ],
      context_entries: [],
      created_at: "2026-06-01T00:00:00Z",
      updated_at: "2026-06-01T00:10:00Z",
    });
  }),

  http.patch(
    "*/api/v1/novels/:novelId/kb/sessions/:sessionId/fields/:fieldKey",
    async ({ params, request }) => {
      const body = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json({
        id: params.sessionId,
        novel_id: params.novelId,
        user_id: "test-user-id",
        entity_type: "character",
        status: "active",
        fields: [
          {
            field_key: params.fieldKey,
            label: params.fieldKey,
            field_type: "text",
            required: false,
            options: null,
            user_value: body.value,
            ai_suggested_value: null,
            ai_reasoning: null,
            source: "user",
            final_value: body.value,
          },
        ],
        context_entries: [],
        created_at: "2026-06-01T00:00:00Z",
        updated_at: "2026-06-01T00:10:00Z",
      });
    },
  ),

  // Aggregate JSON — mirrors request_suggestion in router_sessions.py.
  http.post("*/api/v1/novels/:novelId/kb/sessions/:sessionId/suggest/:fieldKey", async () => {
    return HttpResponse.json({
      session: sessionFixture({
        fields: [
          {
            field_key: "description",
            label: "Description",
            field_type: "text",
            required: false,
            options: null,
            user_value: null,
            ai_suggested_value: "A brave adventurer seeking their destiny.",
            ai_reasoning: "Common heroic archetype for fantasy stories.",
            source: "ai",
            final_value: null,
          },
        ],
      }),
      suggestion: {
        field_key: "description",
        suggestion: "A brave adventurer seeking their destiny.",
        reasoning: "Common heroic archetype for fantasy stories.",
        context_used: ["novel://novel-1/existing-characters"],
      },
    });
  }),

  // Aggregate JSON — mirrors request_interview_question in router_sessions.py.
  http.post("*/api/v1/novels/:novelId/kb/sessions/:sessionId/interview", async () => {
    return HttpResponse.json({
      session: sessionFixture(),
      question: {
        field_key: "background",
        question: "Tell me about this character's greatest fear.",
        reasoning: "Background is still empty; fears reveal backstory.",
      },
    });
  }),

  // Aggregate JSON — mirrors request_enhancement in router_sessions.py.
  http.post("*/api/v1/novels/:novelId/kb/sessions/:sessionId/enhance", async () => {
    return HttpResponse.json({
      session: sessionFixture({
        fields: [
          {
            field_key: "description",
            label: "Description",
            field_type: "text",
            required: false,
            options: null,
            user_value: "A brave hero",
            ai_suggested_value:
              "A brave and compassionate hero who always puts others before themselves.",
            ai_reasoning: "Enhanced to show more depth and character traits.",
            source: "ai",
            final_value: null,
          },
        ],
      }),
      enhancement: {
        draft_entry: {
          description: "A brave and compassionate hero who always puts others before themselves.",
        },
        progress: 0.5,
        reasoning: "Enhanced to show more depth and character traits.",
        context_used: [],
      },
    });
  }),

  // Mirrors complete_session in router_sessions_complete.py: the body is
  // optional; an absent name keeps the existing name-required guard (400).
  http.post("*/api/v1/novels/:novelId/kb/sessions/:sessionId/complete", async ({ request }) => {
    let body: Record<string, unknown> | null = null;
    try {
      body = (await request.json()) as Record<string, unknown>;
    } catch {
      body = null;
    }
    const name = typeof body?.name === "string" ? body.name : null;

    if (!name) {
      return HttpResponse.json(
        { detail: "Session must have a name before completion" },
        { status: 400 },
      );
    }

    return HttpResponse.json({
      session: sessionFixture({ status: "complete", name }),
      entry_id: "kb-entry-new-123",
    });
  }),

  http.delete("*/api/v1/novels/:novelId/kb/sessions/:sessionId", async () => {
    return new HttpResponse(null, { status: 204 });
  }),
];
