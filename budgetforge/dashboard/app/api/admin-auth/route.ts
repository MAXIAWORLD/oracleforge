import { NextRequest, NextResponse } from "next/server";

// H12: set/clear admin key as HttpOnly cookie (XSS cannot read it)
export async function POST(req: NextRequest) {
  const { key } = (await req.json()) as { key: string };
  const res = NextResponse.json({ ok: true });
  if (key) {
    res.cookies.set("bf_admin_key", key, {
      httpOnly: true,
      sameSite: "strict",
      secure: process.env.NODE_ENV === "production",
      maxAge: 30 * 24 * 3600,
      path: "/",
    });
  }
  return res;
}

export async function DELETE() {
  const res = NextResponse.json({ ok: true });
  res.cookies.delete("bf_admin_key");
  return res;
}
