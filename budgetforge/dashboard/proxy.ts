import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { createHmac, timingSafeEqual } from "crypto";

const PROTECTED_PATHS = [
  "/dashboard",
  "/projects",
  "/clients",
  "/activity",
  "/settings",
];

const TOKEN_TTL_S = 86400;

function verifyToken(cookie: string, secret: string): boolean {
  const dot = cookie.indexOf(".");
  if (dot === -1) return false;
  const iatStr = cookie.slice(0, dot);
  const sig = cookie.slice(dot + 1);
  const iat = parseInt(iatStr, 10);
  if (isNaN(iat)) return false;
  if (Math.floor(Date.now() / 1000) - iat > TOKEN_TTL_S) return false;
  const expected = createHmac("sha256", secret).update(iatStr).digest("hex");
  const a = Buffer.from(sig, "utf8");
  const b = Buffer.from(expected, "utf8");
  return a.length === b.length && timingSafeEqual(a, b);
}

function isProtected(pathname: string): boolean {
  return PROTECTED_PATHS.some(
    (p) => pathname === p || pathname.startsWith(p + "/"),
  );
}

export function proxy(request: NextRequest): NextResponse {
  const dashboardPassword = process.env.DASHBOARD_PASSWORD ?? "";

  // Dev mode: no password set → pass through
  if (!dashboardPassword) {
    return NextResponse.next();
  }

  const pathname = request.nextUrl.pathname;

  if (!isProtected(pathname)) {
    return NextResponse.next();
  }

  const sessionSecret = process.env.SESSION_SECRET ?? "default-secret";
  const sessionCookie = request.cookies.get("bf_session")?.value ?? "";

  if (verifyToken(sessionCookie, sessionSecret)) return NextResponse.next();

  const loginUrl = new URL("/login", request.url);
  loginUrl.searchParams.set("from", pathname);
  return NextResponse.redirect(loginUrl);
}

export const config = {
  matcher: [
    "/dashboard/:path*",
    "/projects/:path*",
    "/clients/:path*",
    "/activity/:path*",
    "/settings/:path*",
  ],
};
