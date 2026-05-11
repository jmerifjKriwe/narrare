import { NextRequest, NextResponse } from "next/server"

const PUBLIC_PATHS = ["/login", "/register", "/wizard"]

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl

  // Allow public paths without auth
  if (PUBLIC_PATHS.some((p) => pathname.startsWith(p))) {
    return NextResponse.next()
  }

  // Allow API routes (handled by backend)
  if (pathname.startsWith("/api/")) {
    return NextResponse.next()
  }

  // Auth check via cookie presence (access token is in-memory, but refresh
  // token cookie signals a valid session)
  const hasSession = request.cookies.has("narrare_session")
  if (!hasSession && pathname !== "/") {
    return NextResponse.redirect(new URL("/login", request.url))
  }

  return NextResponse.next()
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|public/).*)"],
}
