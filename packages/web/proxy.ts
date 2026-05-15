/**
 * ⚠️  DO NOT create a `middleware.ts` file in this directory!
 *
 * Next.js 16+ uses `proxy.ts` (this file) for route-level server logic.
 * If both middleware.ts and proxy.ts exist, the build FAILS with:
 *   "Both middleware file and proxy file are detected. Please use proxy.ts only."
 *
 * This has happened before. If you need to add route protection or
 * server-side logic, edit THIS file (proxy.ts), not middleware.ts.
 *
 * See: https://nextjs.org/docs/messages/middleware-to-proxy
 */

import { jwtVerify } from "jose";
import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

// Protected route prefixes — must match the middleware config matcher
const PROTECTED_PREFIXES = ["/dashboard", "/wizard", "/novel"];

export async function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Only protect matching paths (redundant with matcher, but explicit)
  const isProtected = PROTECTED_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  );
  if (!isProtected) return NextResponse.next();

  const token = request.cookies.get("narrare_auth")?.value;

  if (!token) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  try {
    const secret = new TextEncoder().encode(
      process.env.AUTH_JWT_SECRET ?? "change-me-run-just-generate-secret",
    );
    await jwtVerify(token, secret);
    return NextResponse.next();
  } catch {
    // Token invalid or expired — clear cookie and redirect
    const response = NextResponse.redirect(new URL("/login", request.url));
    response.cookies.set("narrare_auth", "", { path: "/", maxAge: 0 });
    return response;
  }
}

export const config = {
  matcher: ["/dashboard/:path*", "/wizard/:path*", "/novel/:path*"],
};
