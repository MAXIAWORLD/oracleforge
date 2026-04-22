import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { createHmac, timingSafeEqual } from "crypto";

const PROTECTED_PATHS = ["/dashboard", "/projects", "/activity", "/settings", "/clients"];

const TOKEN_MAX_AGE_MS = 86_400_000; // 24 h

function isProtected(pathname: string): boolean {
  return PROTECTED_PATHS.some(
    (p) => pathname === p || pathname.startsWith(p + "/")
  );
}

function verifyToken(cookie: string, secret: string): boolean {
  const dotIdx = cookie.lastIndexOf(".");
  if (dotIdx === -1) return false;

  const ts = cookie.slice(0, dotIdx);
  const sig = cookie.slice(dotIdx + 1);

  const timestamp = parseInt(ts, 10);
  if (isNaN(timestamp) || Date.now() - timestamp > TOKEN_MAX_AGE_MS) return false;

  const expected = createHmac("sha256", secret).update(ts).digest("hex");
  if (sig.length !== expected.length) return false;
  return timingSafeEqual(Buffer.from(sig, "utf8"), Buffer.from(expected, "utf8"));
}

export function proxy(request: NextRequest): NextResponse {
  const dashboardPassword = process.env.DASHBOARD_PASSWORD ?? "";

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
  matcher: ["/dashboard/:path*", "/projects/:path*", "/activity/:path*", "/settings/:path*", "/clients/:path*"],
};
