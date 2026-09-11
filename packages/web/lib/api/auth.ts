/**
 * Auth API — register, login, user info, and WS handshake tickets.
 */

import type { TokenResponse, User, WsTicket } from "@/types";
import { fetchApi } from "./core";

export const authApi = {
  register: (email: string, password: string, displayName = "") =>
    fetchApi<TokenResponse>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password, display_name: displayName }),
    }),

  login: (email: string, password: string) =>
    fetchApi<TokenResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  me: () => fetchApi<User>("/auth/me"),

  /**
   * Mint a single-use, short-lived (60 s) WebSocket handshake ticket
   * (ADR-084). Bearer auth is attached by `fetchApi`; the raw token is
   * delivered exactly once and consumed by the writing WS handshake.
   */
  wsTicket: () => fetchApi<WsTicket>("/auth/ws-ticket", { method: "POST" }),
};
