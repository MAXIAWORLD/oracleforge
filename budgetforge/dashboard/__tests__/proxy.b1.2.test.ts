/**
 * B1.2 — /clients dans PROTECTED_PATHS dashboard (audit C13).
 *
 * Bug confirmé live prod 2026-04-25 :
 *   GET https://llmbudget.maxiaworld.app/clients -> 200 (sans auth)
 *   GET /dashboard, /projects, /settings -> 307 redirect /login
 *
 * `/clients` doit être ajouté à PROTECTED_PATHS dans proxy.ts ET au matcher
 * `config.matcher` (sinon Next.js ne déclenche pas la fonction proxy pour
 * cette route).
 */
import { proxy } from "../proxy";
import { NextRequest } from "next/server";

const SECRET = "testsecret";
const PASSWORD = "testpassword";

function makeRequest(pathname: string, token?: string): NextRequest {
  const headers: HeadersInit = token ? { Cookie: `bf_session=${token}` } : {};
  return new NextRequest(`https://localhost${pathname}`, { headers });
}

describe("proxy — B1.2 /clients protected (C13)", () => {
  const origEnv = process.env;

  beforeEach(() => {
    process.env = {
      ...origEnv,
      SESSION_SECRET: SECRET,
      DASHBOARD_PASSWORD: PASSWORD,
    };
  });
  afterEach(() => {
    process.env = origEnv;
  });

  it("/clients without cookie → redirect to /login (was 200 unauth, audit C13)", () => {
    const req = makeRequest("/clients");
    const resp = proxy(req);
    expect(resp.headers.get("location")).toContain("/login");
  });

  it("/clients/sub-path without cookie → redirect to /login", () => {
    const req = makeRequest("/clients/some-sub");
    const resp = proxy(req);
    expect(resp.headers.get("location")).toContain("/login");
  });

  it("/clients in dev mode (no DASHBOARD_PASSWORD) → pass through (consistent with dashboard)", () => {
    delete process.env.DASHBOARD_PASSWORD;
    const req = makeRequest("/clients");
    const resp = proxy(req);
    expect(resp.headers.get("location")).toBeNull();
  });
});
