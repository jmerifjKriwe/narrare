/**
 * Core API client tests — auth, session, and fetch-wrapper edge paths.
 *
 * `client.test.ts` covers the happy paths (MSW-backed). These tests drive the
 * remaining branch gaps in `core.ts` with a mocked global `fetch`:
 *   401 on `/auth/refresh` (redirect / already-on-/login guards),
 *   `/auth/login` + `/auth/register` error-detail discrimination
 *   (string / array / fallback), the refresh-retry paths (non-OK retry and
 *   204-as-undefined), non-OK error mapping, `fetchApiRaw` 401 handling, the
 *   in-flight refresh cache, and SSR-safe token clearing.
 *
 * @module core.test
 */

import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/hooks/use-content-recovery", () => ({
  saveBeforeRedirect: vi.fn(),
}));

import {
  ApiError,
  clearAccessToken,
  fetchApi,
  fetchApiRaw,
  getAccessToken,
  restoreSession,
  setAccessToken,
} from "@/lib/api/core";
import { saveBeforeRedirect } from "@/lib/hooks/use-content-recovery";

// Mock window.location so redirects don't trigger real navigation.
const mockLocation: { href: string; pathname: string } = { href: "", pathname: "/" };
Object.defineProperty(window, "location", {
  value: mockLocation,
  writable: true,
});

function jsonResponse(status: number, body: unknown): Response {
  return new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const refreshedToken = {
  access_token: "fresh-token",
  token_type: "bearer",
  expires_in: 3600,
};

describe("core API client", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
    clearAccessToken();
    mockLocation.href = "";
    mockLocation.pathname = "/";
  });

  describe("token clearing in SSR", () => {
    it("does not throw when document is undefined", () => {
      vi.stubGlobal("document", undefined);
      expect(() => clearAccessToken()).not.toThrow();
      vi.unstubAllGlobals();
    });
  });

  describe("refreshAccessToken cache", () => {
    it("shares a single in-flight refresh promise across concurrent callers", async () => {
      let resolveRefresh!: (response: Response) => void;
      fetchMock.mockImplementationOnce(
        () =>
          new Promise<Response>((resolve) => {
            resolveRefresh = resolve;
          }),
      );

      const first = restoreSession();
      const second = restoreSession();

      resolveRefresh!(jsonResponse(200, refreshedToken));
      await expect(Promise.all([first, second])).resolves.toEqual([true, true]);
      expect(fetchMock).toHaveBeenCalledTimes(1);
      expect(getAccessToken()).toBe("fresh-token");
    });
  });

  describe("fetchApi 401 on /auth/refresh", () => {
    it("clears the session, saves redirect state, and redirects to /login", async () => {
      fetchMock.mockResolvedValue(jsonResponse(401, { detail: "expired" }));

      await expect(fetchApi("/auth/refresh")).rejects.toThrow("Session expired");
      expect(getAccessToken()).toBeNull();
      expect(saveBeforeRedirect).toHaveBeenCalledTimes(1);
      expect(mockLocation.href).toBe("/login");
    });

    it("skips the redirect when already on /login", async () => {
      mockLocation.pathname = "/login";
      fetchMock.mockResolvedValue(jsonResponse(401, { detail: "expired" }));

      await expect(fetchApi("/auth/refresh")).rejects.toThrow("Session expired");
      expect(saveBeforeRedirect).not.toHaveBeenCalled();
      expect(mockLocation.href).toBe("");
    });
  });

  describe("fetchApi 401 on auth endpoints", () => {
    it("surfaces a string error detail for /auth/login", async () => {
      fetchMock.mockResolvedValue(jsonResponse(401, { detail: "Invalid credentials" }));

      await expect(fetchApi("/auth/login", { method: "POST", body: "{}" })).rejects.toThrow(
        "Invalid credentials",
      );
    });

    it("joins array error details for /auth/register", async () => {
      fetchMock.mockResolvedValue(
        jsonResponse(401, { detail: [{ msg: "email invalid" }, { msg: "password too short" }] }),
      );

      await expect(fetchApi("/auth/register")).rejects.toThrow("email invalid; password too short");
    });

    it("filters array items without a message", async () => {
      fetchMock.mockResolvedValue(jsonResponse(401, { detail: [{ msg: "first" }, {}] }));

      await expect(fetchApi("/auth/login")).rejects.toThrow("first");
    });

    it("falls back to HTTP status when detail is an empty array", async () => {
      fetchMock.mockResolvedValue(jsonResponse(401, { detail: [{}, {}] }));

      await expect(fetchApi("/auth/login")).rejects.toThrow("HTTP 401");
    });
  });

  describe("fetchApi 401 refresh-retry", () => {
    it("returns undefined when the retried request succeeds with 204", async () => {
      fetchMock
        .mockResolvedValueOnce(jsonResponse(401, { detail: "expired" }))
        .mockResolvedValueOnce(jsonResponse(200, refreshedToken))
        .mockResolvedValueOnce(new Response(null, { status: 204 }));

      await expect(fetchApi("/test")).resolves.toBeUndefined();
      expect(getAccessToken()).toBe("fresh-token");
    });

    it("rethrows a failed retried request as ApiError instead of the /login redirect", async () => {
      fetchMock
        .mockResolvedValueOnce(jsonResponse(401, { detail: "expired" }))
        .mockResolvedValueOnce(jsonResponse(200, refreshedToken))
        .mockResolvedValueOnce(jsonResponse(500, { detail: "boom" }));

      // A6 review fix round 1 #3: a non-ok retry is the API's real answer —
      // it propagates as ApiError (status + code parsed like the primary
      // path) and must NOT be misrouted to the session-expiry redirect
      // (e.g. a 429-after-refresh is a budget stop, not a dead session).
      const error = await fetchApi("/test").then(
        () => null,
        (e: unknown) => e,
      );
      expect(error).toBeInstanceOf(ApiError);
      expect((error as ApiError).status).toBe(500);
      expect((error as ApiError).message).toBe("boom");
      expect(getAccessToken()).not.toBeNull(); // session is still alive
      expect(saveBeforeRedirect).not.toHaveBeenCalled();
      expect(mockLocation.href).toBe("");
    });

    it("still redirects when the retried request is again 401", async () => {
      fetchMock
        .mockResolvedValueOnce(jsonResponse(401, { detail: "expired" }))
        .mockResolvedValueOnce(jsonResponse(200, refreshedToken))
        .mockResolvedValueOnce(jsonResponse(401, { detail: "still expired" }));

      await expect(fetchApi("/test")).rejects.toThrow("Session expired");
      expect(getAccessToken()).toBeNull();
      expect(saveBeforeRedirect).toHaveBeenCalledTimes(1);
      expect(mockLocation.href).toBe("/login");
    });

    it("clears the session and redirects when refresh fails", async () => {
      fetchMock
        .mockResolvedValueOnce(jsonResponse(401, { detail: "expired" }))
        .mockResolvedValueOnce(jsonResponse(401, { detail: "no refresh cookie" }));

      await expect(fetchApi("/test")).rejects.toThrow("Session expired");
      expect(getAccessToken()).toBeNull();
      expect(saveBeforeRedirect).toHaveBeenCalledTimes(1);
      expect(mockLocation.href).toBe("/login");
    });
  });

  describe("fetchApi non-2xx error mapping", () => {
    it("joins array error details", async () => {
      fetchMock.mockResolvedValue(jsonResponse(422, { detail: [{ msg: "a" }, { msg: "b" }] }));

      await expect(fetchApi("/test")).rejects.toThrow("a; b");
    });

    it("falls back to HTTP status when detail is not a string or array", async () => {
      fetchMock.mockResolvedValue(jsonResponse(500, { detail: 42 }));

      await expect(fetchApi("/test")).rejects.toThrow("HTTP 500");
    });

    it("falls back to the status text when the body is not JSON", async () => {
      fetchMock.mockResolvedValue(
        new Response("not json", { status: 500, statusText: "Internal Server Error" }),
      );

      await expect(fetchApi("/test")).rejects.toThrow("Internal Server Error");
    });
  });

  describe("fetchApiRaw", () => {
    it("returns the native response for non-401 statuses", async () => {
      const response = jsonResponse(200, { ok: true });
      fetchMock.mockResolvedValue(response);

      await expect(fetchApiRaw("/test")).resolves.toBe(response);
    });

    it("clears the session and redirects on 401 for /auth/refresh", async () => {
      fetchMock.mockResolvedValue(jsonResponse(401, { detail: "expired" }));

      await expect(fetchApiRaw("/auth/refresh")).rejects.toThrow("Session expired");
      expect(mockLocation.href).toBe("/login");
      expect(saveBeforeRedirect).toHaveBeenCalledTimes(1);
    });

    it("retries the request after a successful refresh", async () => {
      const okResponse = jsonResponse(200, { data: 1 });
      fetchMock
        .mockResolvedValueOnce(jsonResponse(401, { detail: "expired" }))
        .mockResolvedValueOnce(jsonResponse(200, refreshedToken))
        .mockResolvedValueOnce(okResponse);

      await expect(fetchApiRaw("/test")).resolves.toBe(okResponse);
      expect(getAccessToken()).toBe("fresh-token");
    });

    it("redirects to /login when the refresh fails", async () => {
      fetchMock
        .mockResolvedValueOnce(jsonResponse(401, { detail: "expired" }))
        .mockResolvedValueOnce(jsonResponse(401, { detail: "no refresh cookie" }));

      await expect(fetchApiRaw("/test")).rejects.toThrow("Session expired");
      expect(mockLocation.href).toBe("/login");
      expect(saveBeforeRedirect).toHaveBeenCalledTimes(1);
    });

    it("skips the redirect when already on /login", async () => {
      mockLocation.pathname = "/login";
      fetchMock.mockResolvedValue(jsonResponse(401, { detail: "expired" }));

      await expect(fetchApiRaw("/auth/refresh")).rejects.toThrow("Session expired");
      expect(mockLocation.href).toBe("");
      expect(saveBeforeRedirect).not.toHaveBeenCalled();
    });
  });

  describe("token management helpers", () => {
    it("restores immediately when an access token already exists", async () => {
      setAccessToken("existing-token");

      await expect(restoreSession()).resolves.toBe(true);
      expect(fetchMock).not.toHaveBeenCalled();
    });
  });
});
