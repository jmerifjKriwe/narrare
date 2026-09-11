// Authentication & API response types

export interface User {
  id: string;
  email: string;
  display_name: string;
  is_active: boolean;
  is_verified: boolean;
  has_providers: boolean;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

/**
 * Single-use WebSocket handshake ticket (ADR-084, `POST /auth/ws-ticket`).
 *
 * Mirrors the backend `WsTicketResponse` schema (RULE-17 snake_case): the
 * opaque `token` is presented as the `token` query param on the writing
 * WS handshake and is consumed exactly once; `expires_in` is the ticket
 * lifetime in seconds (60).
 */
export interface WsTicket {
  token: string;
  expires_in: number;
}

// API error shape
export interface ApiError {
  detail: string;
  code?: string;
}
