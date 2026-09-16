import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Static assets, api routes, and public auth paths bypass middleware
  if (
    pathname.startsWith("/_next") ||
    pathname.startsWith("/api") ||
    pathname.startsWith("/static") ||
    pathname.includes(".") ||
    pathname === "/login" ||
    pathname === "/register" ||
    pathname === "/callback"
  ) {
    return NextResponse.next();
  }

  // Token presence check in cookie (session synchronization)
  const token = request.cookies.get("titan_token")?.value;

  // If visiting sub-views like /documents, /connectors, /analytics, /admin without token
  const protectedRoutes = ["/documents", "/connectors", "/analytics", "/admin"];
  const isProtected = protectedRoutes.some((route) => pathname.startsWith(route));

  if (isProtected && !token) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("redirect", pathname);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
};
