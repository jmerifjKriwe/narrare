/**
 * Auth API — register, login, and user info.
 */

import type { TokenResponse, User } from "@/types";
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
};
