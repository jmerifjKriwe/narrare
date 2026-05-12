import { decodeJwt } from "jose";
import { type NextRequest, NextResponse } from "next/server";

const PUBLIC_PATHS = ["/login", "/register", "/wizard"];
const SESSION_COOKIE = "narrare_session";

/** Decode JWT payload and check expiration (no signature verification). */
function isSessionValid(token: string): boolean {
  try {
    const { exp } = decodeJwt(token);
    if (!exp) return false;
    return exp * 1000 > Date.now();
  } catch {
    return false;
  }
}

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Allow public paths without auth
  if (PUBLIC_PATHS.some((p) => pathname.startsWith(p))) {
    return NextResponse.next();
  }

  // Allow API routes (handled by backend)
  if (pathname.startsWith("/api/")) {
    return NextResponse.next();
  }

  const sessionToken = request.cookies.get(SESSION_COOKIE)?.value;

  // No cookie — allow root (landing page), redirect everything else
  if (!sessionToken) {
    if (pathname !== "/") {
      return NextResponse.redirect(new URL("/login", request.url));
    }
    return NextResponse.next();
  }

  // Cookie present but invalid/expired — clear and redirect to login
  if (!isSessionValid(sessionToken)) {
    const response = NextResponse.redirect(new URL("/login", request.url));
    response.cookies.delete(SESSION_COOKIE);
    return response;
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|public/).*)"],
};
