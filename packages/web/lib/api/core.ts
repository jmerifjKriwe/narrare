/**
 * Narrare API client — core infrastructure.
 *
 * Typed fetch wrapper with auth + auto-refresh on 401.
 * Components never call fetch directly — always use these functions.
 *
 * Access token is stored in memory (not localStorage).
 * Refresh token is in an httpOnly cookie (set by server).
 */

import { saveBeforeRedirect } from "@/lib/hooks/use-content-recovery";
import type { TokenResponse } from "@/types";

// --- In-memory token storage (never localStorage — security) ---

let _accessToken: string | null = null;

export function setAccessToken(token: string): void {
  _accessToken = token;
  // Sync cookie for Next.js middleware (server-side route protection)
  if (typeof document !== "undefined") {
    // biome-ignore lint/suspicious/noDocumentCookie: cookie needed for Next.js middleware server-side route protection
    document.cookie = `narrare_auth=${token}; path=/; max-age=3600; samesite=lax`;
  }
}

export function clearAccessToken(): void {
  _accessToken = null;
  // Clear auth cookie
  if (typeof document !== "undefined") {
    // biome-ignore lint/suspicious/noDocumentCookie: clearing auth cookie for Next.js middleware
    document.cookie = "narrare_auth=; path=/; max-age=0";
  }
}

export function getAccessToken(): string | null {
  return _accessToken;
}

// --- Core fetch wrapper with auth + auto-refresh on 401 ---

let _isRefreshing = false;
let _refreshPromise: Promise<void> | null = null;

async function refreshAccessToken(): Promise<void> {
  if (_isRefreshing && _refreshPromise) return _refreshPromise;
  _isRefreshing = true;
  _refreshPromise = (async () => {
    try {
      // IMPORTANT: Must include Content-Type + empty body. The Next.js dev
      // proxy can hang on POST requests without Content-Type during page load
      // when the response takes more than a few seconds (e.g. cold DB start).
      // The httpOnly refresh cookie is sent via credentials: "include".
      const res = await fetch("/api/v1/auth/refresh", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: "{}",
      });
      if (!res.ok) throw new Error("Refresh failed");
      const data: TokenResponse = await res.json();
      setAccessToken(data.access_token);
    } finally {
      _isRefreshing = false;
      _refreshPromise = null;
    }
  })();
  return _refreshPromise;
}

/**
 * Log out on the server: POST to /api/v1/auth/logout to clear the httpOnly
 * refresh cookie. This uses raw fetch (not fetchApi) because there may be no
 * access token at the time of logout.
 */
export async function logoutApi(): Promise<void> {
  try {
    await fetch("/api/v1/auth/logout", {
      method: "POST",
      credentials: "include",
    });
  } catch {
    // Network error — ignore, we still clear local state
  }
}

export async function restoreSession(): Promise<boolean> {
  if (_accessToken) return true; // already have a valid token
  try {
    await refreshAccessToken();
    return true;
  } catch {
    return false;
  }
}

export async function fetchApi<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `/api/v1${endpoint}`;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((options.headers as Record<string, string>) ?? {}),
  };
  if (_accessToken) headers.Authorization = `Bearer ${_accessToken}`;

  const response = await fetch(url, { ...options, headers, credentials: "include" });

  if (response.status === 401) {
    if (endpoint === "/auth/refresh") {
      clearAccessToken();
      if (typeof window !== "undefined" && window.location.pathname !== "/login") {
        saveBeforeRedirect();
        window.location.href = "/login";
      }
      throw new Error("Session expired");
    }
    // Auth endpoints: 401 means "wrong credentials", not "session expired"
    if (endpoint === "/auth/login" || endpoint === "/auth/register") {
      const err = await response.json().catch(() => ({ detail: response.statusText }));
      if (typeof err.detail === "string") {
        throw new Error(err.detail);
      }
      if (Array.isArray(err.detail)) {
        const messages = err.detail.map((e: { msg?: string }) => e.msg).filter(Boolean);
        throw new Error(messages.join("; ") || `HTTP ${response.status}`);
      }
      throw new Error(`HTTP ${response.status}`);
    }
    try {
      await refreshAccessToken();
      headers.Authorization = `Bearer ${_accessToken}`;
      const retry = await fetch(url, { ...options, headers, credentials: "include" });
      if (!retry.ok) throw new Error(`HTTP ${retry.status}`);
      if (retry.status === 204) return undefined as T;
      return retry.json() as Promise<T>;
    } catch {
      clearAccessToken();
      saveBeforeRedirect();
      window.location.href = "/login";
      throw new Error("Session expired");
    }
  }

  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: response.statusText }));
    if (typeof err.detail === "string") {
      throw new Error(err.detail);
    }
    if (Array.isArray(err.detail)) {
      const messages = err.detail.map((e: { msg?: string }) => e.msg).filter(Boolean);
      throw new Error(messages.join("; ") || `HTTP ${response.status}`);
    }
    throw new Error(`HTTP ${response.status}`);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}
