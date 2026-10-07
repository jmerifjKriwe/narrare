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

// --- Error type with machine-readable metadata (ADR-094) ---

/**
 * API error carrying the HTTP status and the backend's machine-readable
 * `code` field (e.g. 429 + "BUDGET_EXCEEDED", ADR-094). Extends Error so
 * existing `instanceof Error` / message handling keeps working; the parsed
 * body message stays the displayed text — the structured fields are for
 * programmatic mapping (never shown raw to the user, §16.5).
 */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string | null;

  constructor(message: string, status: number, code: string | null = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

/**
 * True when the error is the budget gate's 429 BUDGET_EXCEEDED (ADR-094):
 * the block-mode hard stop raised by `ModelRegistry.get_model()` and mapped
 * by the API error handler. The 429 only fires in block mode, so this
 * condition alone identifies "AI is stopped by the monthly budget".
 */
export function isBudgetExceededError(error: unknown): boolean {
  return error instanceof ApiError && error.status === 429 && error.code === "BUDGET_EXCEEDED";
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
    // Machine-readable code (e.g. "BUDGET_EXCEEDED") travels alongside the
    // human message; non-string code fields are treated as absent.
    const code = typeof err.code === "string" ? err.code : null;
    if (typeof err.detail === "string") {
      throw new ApiError(err.detail, response.status, code);
    }
    if (Array.isArray(err.detail)) {
      const messages = err.detail.map((e: { msg?: string }) => e.msg).filter(Boolean);
      throw new ApiError(messages.join("; ") || `HTTP ${response.status}`, response.status, code);
    }
    throw new ApiError(`HTTP ${response.status}`, response.status, code);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

/**
 * Raw API fetch wrapper for streaming endpoints.
 *
 * Mirrors ``fetchApi`` for auth headers, credentials, and one 401 refresh retry,
 * but returns the native ``Response`` so callers can consume ``response.body``.
 * Non-401 HTTP errors are intentionally returned instead of parsed/thrown because
 * streaming callers often need the status code to map provider-gate failures.
 */
export async function fetchApiRaw(endpoint: string, options: RequestInit = {}): Promise<Response> {
  const url = `/api/v1${endpoint}`;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((options.headers as Record<string, string>) ?? {}),
  };
  if (_accessToken) headers.Authorization = `Bearer ${_accessToken}`;

  const response = await fetch(url, { ...options, headers, credentials: "include" });
  if (response.status !== 401) return response;

  if (endpoint === "/auth/refresh") {
    clearAccessToken();
    if (typeof window !== "undefined" && window.location.pathname !== "/login") {
      saveBeforeRedirect();
      window.location.href = "/login";
    }
    throw new Error("Session expired");
  }

  try {
    await refreshAccessToken();
    headers.Authorization = `Bearer ${_accessToken}`;
    return await fetch(url, { ...options, headers, credentials: "include" });
  } catch {
    clearAccessToken();
    saveBeforeRedirect();
    window.location.href = "/login";
    throw new Error("Session expired");
  }
}

/**
 * Multipart upload wrapper (SETUP-003 import).
 *
 * Mirrors fetchApi's auth header + one 401-refresh retry, but intentionally
 * sets NO Content-Type — the browser must generate the multipart boundary.
 * FormData bodies are re-usable, so the retry re-sends the same object.
 */
export async function fetchApiUpload<T>(endpoint: string, options: { body: FormData }): Promise<T> {
  const url = `/api/v1${endpoint}`;
  const headers: Record<string, string> = {};
  if (_accessToken) headers.Authorization = `Bearer ${_accessToken}`;

  const response = await fetch(url, {
    method: "POST",
    headers,
    credentials: "include",
    body: options.body,
  });

  if (response.status === 401) {
    await refreshAccessToken();
    headers.Authorization = `Bearer ${_accessToken}`;
    const retry = await fetch(url, {
      method: "POST",
      headers,
      credentials: "include",
      body: options.body,
    });
    if (!retry.ok) throw new Error(`HTTP ${retry.status}`);
    return retry.json() as Promise<T>;
  }

  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: response.statusText }));
    if (typeof err.detail === "string") throw new Error(err.detail);
    throw new Error(`HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}
