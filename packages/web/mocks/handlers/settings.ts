import { HttpResponse, http } from "msw";

// ---------------------------------------------------------------------------
// Settings — User & Project
// ---------------------------------------------------------------------------

export const handlers = [
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
