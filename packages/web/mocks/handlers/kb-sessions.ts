import { HttpResponse, http } from "msw";

// ---------------------------------------------------------------------------
// KB Sessions (Assisted Creation)
// ---------------------------------------------------------------------------

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

  http.post("*/api/v1/novels/:novelId/kb/sessions/:sessionId/suggest/:fieldKey", async () => {
    // Note: SSE endpoints are harder to mock with MSW.
    // In tests, we mock connectSSE directly.
    return HttpResponse.json({
      field_key: "description",
      suggestion: "A brave adventurer seeking their destiny.",
      reasoning: "Common heroic archetype for fantasy stories.",
    });
  }),

  http.post("*/api/v1/novels/:novelId/kb/sessions/:sessionId/interview", async () => {
    return HttpResponse.json({
      question: "Tell me about this character's greatest fear.",
      target_field: "background",
      context: "",
    });
  }),

  http.post("*/api/v1/novels/:novelId/kb/sessions/:sessionId/enhance", async () => {
    return HttpResponse.json([
      {
        field_key: "description",
        original: "A brave hero",
        suggested: "A brave and compassionate hero who always puts others before themselves.",
        reasoning: "Enhanced to show more depth and character traits.",
      },
    ]);
  }),

  http.post("*/api/v1/novels/:novelId/kb/sessions/:sessionId/complete", async () => {
    return HttpResponse.json({
      session: {
        id: "kb-session-1",
        novel_id: "novel-1",
        user_id: "test-user-id",
        entity_type: "character",
        status: "complete",
        fields: [],
        context_entries: [],
        created_at: "2026-06-01T00:00:00Z",
        updated_at: "2026-06-01T00:15:00Z",
      },
      entry_id: "kb-entry-new-123",
    });
  }),

  http.delete("*/api/v1/novels/:novelId/kb/sessions/:sessionId", async () => {
    return new HttpResponse(null, { status: 204 });
  }),
];
