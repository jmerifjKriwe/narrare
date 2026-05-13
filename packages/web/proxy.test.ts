import { beforeEach, describe, expect, it, vi } from "vitest";

// --- Shared mock functions (hoisted so vi.mock factories can reference them) ---
const { mockCookiesSet, mockJwtVerify } = vi.hoisted(() => ({
  mockCookiesSet: vi.fn(),
  mockJwtVerify: vi.fn(),
}));

// --- Mock dependencies ---
vi.mock("jose", () => ({
  jwtVerify: mockJwtVerify,
}));

vi.mock("next/server", () => ({
  NextResponse: {
    next: vi.fn(),
    redirect: vi.fn(() => ({
      cookies: { set: mockCookiesSet },
    })),
  },
}));

// --- Imports (resolved after hoisted mocks) ---
import { NextResponse } from "next/server";
import { proxy } from "./proxy";

// --- Helpers ---

/** Create a minimal mock that satisfies the proxy's NextRequest usage. */
function createMockRequest(pathname: string, cookieValue?: string) {
  return {
    nextUrl: { pathname },
    url: `http://localhost:3000${pathname}`,
    cookies: {
      get: (name: string) => {
        if (name === "narrare_auth" && cookieValue !== undefined) {
          return { value: cookieValue };
        }
        return undefined;
      },
    },
  } as Parameters<typeof proxy>[0];
}

// --- Tests ---

describe("proxy", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("protected routes — no cookie", () => {
    it("should redirect to /login when no auth cookie is present on /dashboard", async () => {
      const request = createMockRequest("/dashboard");

      await proxy(request);

      expect(NextResponse.redirect).toHaveBeenCalledOnce();
      expect(NextResponse.redirect).toHaveBeenCalledWith(
        new URL("/login", "http://localhost:3000/dashboard"),
      );
      expect(NextResponse.next).not.toHaveBeenCalled();
      // No cookie to clear when there was no cookie to begin with
      expect(mockCookiesSet).not.toHaveBeenCalled();
    });

    it("should redirect to /login when no auth cookie is present on /wizard", async () => {
      const request = createMockRequest("/wizard");

      await proxy(request);

      expect(NextResponse.redirect).toHaveBeenCalledOnce();
      expect(NextResponse.next).not.toHaveBeenCalled();
    });

    it("should redirect to /login when no auth cookie is present on /novel", async () => {
      const request = createMockRequest("/novel");

      await proxy(request);

      expect(NextResponse.redirect).toHaveBeenCalledOnce();
      expect(NextResponse.next).not.toHaveBeenCalled();
    });

    it("should redirect for nested protected routes like /dashboard/settings", async () => {
      const request = createMockRequest("/dashboard/settings");

      await proxy(request);

      expect(NextResponse.redirect).toHaveBeenCalledOnce();
    });
  });

  describe("invalid JWT", () => {
    it("should redirect to /login AND clear cookie when JWT is invalid", async () => {
      mockJwtVerify.mockRejectedValue(new Error("invalid signature"));
      const request = createMockRequest("/dashboard", "some-jwt-token");

      await proxy(request);

      expect(mockJwtVerify).toHaveBeenCalledWith("some-jwt-token", expect.anything());
      expect(NextResponse.redirect).toHaveBeenCalledOnce();
      expect(mockCookiesSet).toHaveBeenCalledWith("narrare_auth", "", {
        path: "/",
        maxAge: 0,
      });
    });
  });

  describe("valid JWT", () => {
    it("should call NextResponse.next() when JWT is valid on a protected route", async () => {
      mockJwtVerify.mockResolvedValue({ payload: { sub: "user-123" } });
      const request = createMockRequest("/dashboard", "valid-jwt-token");

      await proxy(request);

      expect(mockJwtVerify).toHaveBeenCalledWith("valid-jwt-token", expect.anything());
      expect(NextResponse.next).toHaveBeenCalledOnce();
      expect(NextResponse.redirect).not.toHaveBeenCalled();
    });
  });

  describe("expired JWT", () => {
    it("should redirect to /login and clear cookie when JWT is expired", async () => {
      mockJwtVerify.mockRejectedValue(new Error("JWT expired"));
      const request = createMockRequest("/dashboard", "expired-jwt-token");

      await proxy(request);

      expect(NextResponse.redirect).toHaveBeenCalledOnce();
      expect(mockCookiesSet).toHaveBeenCalledWith("narrare_auth", "", {
        path: "/",
        maxAge: 0,
      });
    });
  });

  describe("unprotected paths", () => {
    it("should call NextResponse.next() for /login without checking cookies", async () => {
      const request = createMockRequest("/login");

      await proxy(request);

      expect(NextResponse.next).toHaveBeenCalledOnce();
      expect(NextResponse.redirect).not.toHaveBeenCalled();
      expect(mockJwtVerify).not.toHaveBeenCalled();
    });

    it("should call NextResponse.next() for /register", async () => {
      const request = createMockRequest("/register");

      await proxy(request);

      expect(NextResponse.next).toHaveBeenCalledOnce();
      expect(NextResponse.redirect).not.toHaveBeenCalled();
    });

    it("should call NextResponse.next() for the root path", async () => {
      const request = createMockRequest("/");

      await proxy(request);

      expect(NextResponse.next).toHaveBeenCalledOnce();
      expect(NextResponse.redirect).not.toHaveBeenCalled();
    });
  });
});
