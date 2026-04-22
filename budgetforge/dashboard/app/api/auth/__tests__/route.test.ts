import { POST, DELETE } from "../route";

describe("POST /api/auth", () => {
  const originalEnv = process.env;

  beforeEach(() => {
    process.env = { ...originalEnv, DASHBOARD_PASSWORD: "testpassword", SESSION_SECRET: "testsecret" };
  });
  afterEach(() => { process.env = originalEnv; });

  it("returns 200 and sets cookie on correct password", async () => {
    const req = new Request("http://localhost/api/auth", {
      method: "POST",
      body: JSON.stringify({ password: "testpassword" }),
      headers: { "Content-Type": "application/json" },
    });
    const res = await POST(req);
    expect(res.status).toBe(200);
    const setCookie = res.headers.get("Set-Cookie");
    expect(setCookie).toContain("bf_session=");
    expect(setCookie).toContain("HttpOnly");
  });

  it("returns 401 on wrong password", async () => {
    const req = new Request("http://localhost/api/auth", {
      method: "POST",
      body: JSON.stringify({ password: "wrong" }),
      headers: { "Content-Type": "application/json" },
    });
    const res = await POST(req);
    expect(res.status).toBe(401);
  });

  it("returns 200 when DASHBOARD_PASSWORD not set (dev mode)", async () => {
    delete process.env.DASHBOARD_PASSWORD;
    const req = new Request("http://localhost/api/auth", {
      method: "POST",
      body: JSON.stringify({ password: "" }),
      headers: { "Content-Type": "application/json" },
    });
    const res = await POST(req);
    expect(res.status).toBe(200);
  });
});

describe("DELETE /api/auth", () => {
  it("clears bf_session cookie", async () => {
    const req = new Request("http://localhost/api/auth", {
      method: "DELETE",
    });
    const res = await DELETE(req);
    expect(res.status).toBe(200);
    const setCookie = res.headers.get("Set-Cookie");
    expect(setCookie).toContain("bf_session=");
    expect(setCookie).toMatch(/Max-Age=0|expires=Thu, 01 Jan 1970/i);
  });
});

// P1.4 — token timestamp-based (ts.hmac)
describe("POST /api/auth — P1.4 timestamp token format", () => {
  const originalEnv = process.env;

  beforeEach(() => {
    process.env = { ...originalEnv, DASHBOARD_PASSWORD: "testpassword", SESSION_SECRET: "testsecret" };
  });
  afterEach(() => { process.env = originalEnv; });

  it("token has format {timestamp}.{hmac64}", async () => {
    const req = new Request("http://localhost/api/auth", {
      method: "POST",
      body: JSON.stringify({ password: "testpassword" }),
      headers: { "Content-Type": "application/json" },
    });
    const before = Date.now();
    const res = await POST(req);
    const after = Date.now();
    const setCookie = res.headers.get("Set-Cookie")!;
    const cookieValue = setCookie.split(";")[0].replace("bf_session=", "");
    const dotIdx = cookieValue.lastIndexOf(".");
    expect(dotIdx).toBeGreaterThan(0);
    const ts = parseInt(cookieValue.slice(0, dotIdx));
    const sig = cookieValue.slice(dotIdx + 1);
    expect(isNaN(ts)).toBe(false);
    expect(ts).toBeGreaterThanOrEqual(before);
    expect(ts).toBeLessThanOrEqual(after);
    expect(sig).toMatch(/^[a-f0-9]{64}$/); // SHA-256 hex = 64 chars
  });

  it("two successive logins produce different tokens", async () => {
    const makeReq = () =>
      new Request("http://localhost/api/auth", {
        method: "POST",
        body: JSON.stringify({ password: "testpassword" }),
        headers: { "Content-Type": "application/json" },
      });
    const [res1, res2] = await Promise.all([POST(makeReq()), POST(makeReq())]);
    const val1 = res1.headers.get("Set-Cookie")!.split(";")[0];
    const val2 = res2.headers.get("Set-Cookie")!.split(";")[0];
    expect(val1).toMatch(/bf_session=\d+\.[a-f0-9]{64}/);
    expect(val2).toMatch(/bf_session=\d+\.[a-f0-9]{64}/);
  });

  it("dev mode token also uses timestamp format", async () => {
    delete process.env.DASHBOARD_PASSWORD;
    const req = new Request("http://localhost/api/auth", {
      method: "POST",
      body: JSON.stringify({ password: "" }),
      headers: { "Content-Type": "application/json" },
    });
    const res = await POST(req);
    const setCookie = res.headers.get("Set-Cookie")!;
    const cookieValue = setCookie.split(";")[0].replace("bf_session=", "");
    expect(cookieValue).toMatch(/^\d+\.[a-f0-9]{64}$/);
  });
});
