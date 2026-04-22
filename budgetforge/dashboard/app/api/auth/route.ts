import { createHmac, timingSafeEqual } from "crypto";

function generateSessionToken(secret: string): string {
  const ts = Date.now().toString();
  const hmac = createHmac("sha256", secret).update(ts).digest("hex");
  return `${ts}.${hmac}`;
}

export async function POST(req: Request): Promise<Response> {
  const dashboardPassword = process.env.DASHBOARD_PASSWORD ?? "";
  const sessionSecret = process.env.SESSION_SECRET ?? "default-secret";

  if (dashboardPassword && !process.env.SESSION_SECRET) {
    return new Response(
      JSON.stringify({ error: "SESSION_SECRET must be set in .env.local" }),
      { status: 500, headers: { "Content-Type": "application/json" } }
    );
  }

  if (!dashboardPassword) {
    const token = generateSessionToken(sessionSecret);
    return new Response(JSON.stringify({ ok: true }), {
      status: 200,
      headers: {
        "Content-Type": "application/json",
        "Set-Cookie": `bf_session=${token}; Path=/; HttpOnly; SameSite=Lax; Max-Age=86400`,
      },
    });
  }

  let body: { password?: string };
  try {
    body = await req.json();
  } catch {
    return new Response(JSON.stringify({ error: "Invalid JSON" }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });
  }

  const { password } = body;
  const a = Buffer.from(password ?? "", "utf8");
  const b = Buffer.from(dashboardPassword, "utf8");
  if (a.length !== b.length || !timingSafeEqual(a, b)) {
    return new Response(JSON.stringify({ error: "Invalid password" }), {
      status: 401,
      headers: { "Content-Type": "application/json" },
    });
  }

  const token = generateSessionToken(sessionSecret);
  return new Response(JSON.stringify({ ok: true }), {
    status: 200,
    headers: {
      "Content-Type": "application/json",
      "Set-Cookie": `bf_session=${token}; Path=/; HttpOnly; SameSite=Lax; Max-Age=86400`,
    },
  });
}

export async function DELETE(_req: Request): Promise<Response> {
  return new Response(JSON.stringify({ ok: true }), {
    status: 200,
    headers: {
      "Content-Type": "application/json",
      "Set-Cookie": `bf_session=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0`,
    },
  });
}
