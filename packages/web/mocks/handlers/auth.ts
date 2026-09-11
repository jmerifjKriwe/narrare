import { HttpResponse, http } from "msw";

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

export const handlers = [
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

  http.post("*/api/v1/auth/refresh", async () => {
    // Simulate successful cookie-based refresh.
    // The client sends Content-Type: application/json with an empty body
    // to avoid Next.js dev proxy hangs — the handler accepts this.
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

  // ADR-084: single-use WS handshake ticket. Static token by default — tests
  // that need per-mint freshness install a counting handler via server.use().
  http.post("*/api/v1/auth/ws-ticket", async () => {
    return HttpResponse.json({ token: "test-ws-ticket", expires_in: 60 });
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
];
