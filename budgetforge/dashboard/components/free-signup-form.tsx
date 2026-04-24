"use client";
import { useEffect, useRef, useState, FormEvent } from "react";
import Link from "next/link";

declare global {
  interface Window {
    turnstile?: {
      render: (el: HTMLElement, opts: Record<string, unknown>) => string;
      reset: (widgetId?: string) => void;
      remove: (widgetId?: string) => void;
    };
  }
}

const TURNSTILE_SITE_KEY = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY || "";

export function FreeSignupForm() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [turnstileToken, setTurnstileToken] = useState<string>("");
  const widgetContainerRef = useRef<HTMLDivElement | null>(null);
  const widgetIdRef = useRef<string | null>(null);

  // Mount Turnstile widget once the script loads (script injected via <Script> tag below)
  useEffect(() => {
    if (!TURNSTILE_SITE_KEY) return;
    let cancelled = false;

    const tryRender = () => {
      if (cancelled) return;
      if (!window.turnstile || !widgetContainerRef.current) {
        setTimeout(tryRender, 200);
        return;
      }
      if (widgetIdRef.current) return;
      widgetIdRef.current = window.turnstile.render(
        widgetContainerRef.current,
        {
          sitekey: TURNSTILE_SITE_KEY,
          callback: (token: string) => setTurnstileToken(token),
          "error-callback": () => setTurnstileToken(""),
          "expired-callback": () => setTurnstileToken(""),
          theme: "dark",
        },
      );
    };

    tryRender();
    return () => {
      cancelled = true;
      if (widgetIdRef.current && window.turnstile) {
        window.turnstile.remove(widgetIdRef.current);
        widgetIdRef.current = null;
      }
    };
  }, []);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const resp = await fetch("/api/signup/free", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email,
          turnstile_token: turnstileToken || null,
        }),
      });
      if (resp.status === 400) {
        const body = await resp.json().catch(() => ({}));
        setError(body?.detail || "Captcha verification failed. Please retry.");
        if (window.turnstile && widgetIdRef.current) {
          window.turnstile.reset(widgetIdRef.current);
          setTurnstileToken("");
        }
        return;
      }
      if (resp.status === 429) {
        setError("Too many attempts from this connection. Try again tomorrow.");
        return;
      }
      if (!resp.ok) throw new Error();
      setDone(true);
    } catch {
      setError("Something went wrong — please try again.");
    } finally {
      setLoading(false);
    }
  }

  if (done) {
    return (
      <div className="text-center">
        <p className="text-xl font-semibold mb-2">Check your inbox!</p>
        <p className="text-sm mb-4" style={{ color: "#c8d8e8" }}>
          Your BudgetForge key was sent to <strong>{email}</strong>.
        </p>
        <Link
          href="/portal"
          className="text-sm hover:opacity-80"
          style={{ color: "var(--amber)" }}
        >
          Already have it? Access your keys →
        </Link>
      </div>
    );
  }

  const captchaRequired = !!TURNSTILE_SITE_KEY;
  const submitDisabled = loading || (captchaRequired && !turnstileToken);

  return (
    <div className="flex flex-col gap-3 items-center w-full">
      {captchaRequired && (
        <script
          async
          defer
          src="https://challenges.cloudflare.com/turnstile/v0/api.js"
        />
      )}
      <form
        onSubmit={handleSubmit}
        className="flex flex-col sm:flex-row gap-3 justify-center w-full max-w-md"
      >
        <input
          type="email"
          required
          placeholder="your@email.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="flex-1 px-4 py-3 rounded-lg text-sm outline-none"
          style={{
            background: "var(--card)",
            border: "1px solid var(--border)",
            color: "var(--foreground)",
          }}
        />
        <button
          type="submit"
          disabled={submitDisabled}
          className="px-6 py-3 rounded-lg font-semibold text-sm transition-opacity hover:opacity-90 disabled:opacity-50 whitespace-nowrap"
          style={{ background: "var(--amber)", color: "#000" }}
        >
          {loading ? "Sending…" : "Get my free key →"}
        </button>
      </form>
      {captchaRequired && <div ref={widgetContainerRef} className="mt-1" />}
      {error && (
        <p className="text-xs" style={{ color: "#ef4444" }}>
          {error}
        </p>
      )}
      <p className="text-xs" style={{ color: "#c8d8e8" }}>
        Already have a key?{" "}
        <Link
          href="/portal"
          style={{ color: "var(--amber)" }}
          className="hover:opacity-80"
        >
          Access your portal →
        </Link>
      </p>
    </div>
  );
}
