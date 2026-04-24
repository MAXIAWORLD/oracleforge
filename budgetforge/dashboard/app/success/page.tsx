"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import Image from "next/image";

type Status = "reconciling" | "confirmed" | "pending" | "error";

export default function SuccessPage() {
  return (
    <Suspense fallback={<SuccessFallback />}>
      <SuccessContent />
    </Suspense>
  );
}

function SuccessFallback() {
  return (
    <div
      className="min-h-screen flex items-center justify-center px-6"
      style={{ background: "var(--background)", color: "var(--foreground)" }}
    >
      <p className="text-sm" style={{ color: "var(--muted)" }}>
        Loading…
      </p>
    </div>
  );
}

function SuccessContent() {
  const params = useSearchParams();
  const sessionId = params.get("session_id");
  const [status, setStatus] = useState<Status>(
    sessionId ? "reconciling" : "confirmed",
  );
  const [errorMsg, setErrorMsg] = useState("");

  useEffect(() => {
    if (!sessionId) return;
    let cancelled = false;
    (async () => {
      try {
        const resp = await fetch(
          `/api/billing/reconcile/${encodeURIComponent(sessionId)}`,
        );
        if (cancelled) return;
        if (resp.ok) {
          setStatus("confirmed");
        } else if (resp.status === 402) {
          setStatus("pending");
        } else {
          const body = await resp.json().catch(() => ({}));
          setErrorMsg(body?.detail || `HTTP ${resp.status}`);
          setStatus("error");
        }
      } catch (e) {
        if (cancelled) return;
        setErrorMsg(e instanceof Error ? e.message : "Network error");
        setStatus("error");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  return (
    <div
      className="min-h-screen flex flex-col items-center justify-center px-6 text-center"
      style={{ background: "var(--background)", color: "var(--foreground)" }}
    >
      <Image
        src="/logo.png"
        alt="BudgetForge"
        width={48}
        height={48}
        className="rounded-xl mb-6"
      />

      {status === "reconciling" && (
        <>
          <div
            className="w-12 h-12 rounded-full flex items-center justify-center mb-6 animate-pulse"
            style={{
              background: "rgba(245,158,11,0.13)",
              border: "1px solid var(--amber)",
            }}
          >
            <span className="text-[--amber]">…</span>
          </div>
          <h1 className="text-2xl font-bold mb-3">Confirming your payment…</h1>
          <p className="text-sm max-w-sm" style={{ color: "var(--muted)" }}>
            Stripe is a few seconds behind sometimes. We&apos;re syncing your
            subscription now.
          </p>
        </>
      )}

      {status === "confirmed" && (
        <>
          <div
            className="w-12 h-12 rounded-full flex items-center justify-center text-2xl mb-6"
            style={{ background: "#4ade8022", border: "1px solid #4ade80" }}
          >
            ✓
          </div>
          <h1 className="text-2xl font-bold mb-3">Payment confirmed!</h1>
          <p
            className="text-sm mb-2 max-w-sm"
            style={{ color: "var(--muted)" }}
          >
            Check your email — your BudgetForge API key and setup instructions
            are on their way.
          </p>
          <p className="text-xs mb-8" style={{ color: "var(--muted)" }}>
            Didn&apos;t receive anything? Check your spam folder or contact{" "}
            <a
              href="mailto:support@maxiaworld.app"
              style={{ color: "var(--amber)" }}
            >
              support@maxiaworld.app
            </a>
          </p>
          <Link
            href="/"
            className="px-6 py-2.5 rounded-lg font-semibold text-sm transition-opacity hover:opacity-90"
            style={{ background: "var(--amber)", color: "#000" }}
          >
            Back to home
          </Link>
        </>
      )}

      {status === "pending" && (
        <>
          <div
            className="w-12 h-12 rounded-full flex items-center justify-center text-2xl mb-6"
            style={{
              background: "rgba(245,158,11,0.13)",
              border: "1px solid var(--amber)",
            }}
          >
            ⏳
          </div>
          <h1 className="text-2xl font-bold mb-3">Payment still processing</h1>
          <p
            className="text-sm mb-6 max-w-sm"
            style={{ color: "var(--muted)" }}
          >
            Stripe hasn&apos;t finalized the charge yet. Refresh this page in a
            minute or contact{" "}
            <a
              href="mailto:support@maxiaworld.app"
              style={{ color: "var(--amber)" }}
            >
              support@maxiaworld.app
            </a>
            .
          </p>
          <Link
            href="/"
            className="px-6 py-2.5 rounded-lg font-semibold text-sm transition-opacity hover:opacity-90"
            style={{ background: "var(--amber)", color: "#000" }}
          >
            Back to home
          </Link>
        </>
      )}

      {status === "error" && (
        <>
          <div
            className="w-12 h-12 rounded-full flex items-center justify-center text-2xl mb-6"
            style={{
              background: "rgba(239,68,68,0.13)",
              border: "1px solid #ef4444",
            }}
          >
            !
          </div>
          <h1 className="text-2xl font-bold mb-3">
            Couldn&apos;t sync your payment
          </h1>
          <p
            className="text-sm mb-2 max-w-sm"
            style={{ color: "var(--muted)" }}
          >
            Your payment was accepted by Stripe, but we couldn&apos;t sync it
            automatically.
          </p>
          <p
            className="text-xs mb-6 max-w-sm font-mono"
            style={{ color: "#ef4444" }}
          >
            {errorMsg}
          </p>
          <p
            className="text-xs mb-6 max-w-sm"
            style={{ color: "var(--muted)" }}
          >
            Contact{" "}
            <a
              href="mailto:support@maxiaworld.app"
              style={{ color: "var(--amber)" }}
            >
              support@maxiaworld.app
            </a>{" "}
            with your Stripe receipt — we&apos;ll activate your account
            manually.
          </p>
          <Link
            href="/"
            className="px-6 py-2.5 rounded-lg font-semibold text-sm transition-opacity hover:opacity-90"
            style={{ background: "var(--amber)", color: "#000" }}
          >
            Back to home
          </Link>
        </>
      )}
    </div>
  );
}
