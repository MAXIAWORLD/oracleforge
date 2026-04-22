import Link from "next/link";
import { NavBar } from "@/components/nav-bar";
import { FreeSignupForm } from "@/components/free-signup-form";
import { QuickSetupLanding } from "@/components/quick-setup-landing";
import { PricingSection } from "@/components/pricing-section";

export default function LandingPage() {
  return (
    <div
      className="min-h-screen"
      style={{ background: "var(--background)", color: "var(--foreground)" }}
    >
      <NavBar />

      {/* Hero */}
      <section id="hero" className="max-w-3xl mx-auto px-6 pt-20 pb-16 text-center">
        <div
          className="inline-block text-xs font-semibold px-3 py-1 rounded-full mb-6"
          style={{ border: "1px solid var(--amber)", color: "var(--amber)" }}
        >
          Hard budget limits for LLM APIs
        </div>
        <h1 className="text-4xl sm:text-5xl font-bold leading-tight mb-6">
          Stop unexpected
          <br />
          <span style={{ color: "var(--amber)" }}>LLM API bills</span>
        </h1>
        <p className="text-lg mb-10 max-w-xl mx-auto" style={{ color: "#c8d8e8" }}>
          BudgetForge sits between your code and the LLM APIs. Set hard limits per project,
          get alerts before you blow your budget, and auto-downgrade to cheaper models when
          limits are reached.
        </p>

        {/* Free signup — primary CTA */}
        <FreeSignupForm />

        {/* Secondary actions */}
        <div className="flex flex-col sm:flex-row gap-3 justify-center mt-8 text-sm">
          <Link
            href="/demo"
            className="px-5 py-2 rounded-lg transition-colors"
            style={{ border: "1px solid var(--border)", color: "var(--foreground)" }}
          >
            Try the live demo
          </Link>
          <a
            href="https://github.com/majorelalexis-stack/budgetforge"
            className="px-5 py-2 rounded-lg transition-colors"
            style={{ border: "1px solid var(--border)", color: "var(--foreground)" }}
          >
            View on GitHub
          </a>
        </div>
      </section>

      {/* How it works — quick setup tabs */}
      <div id="how">
        <QuickSetupLanding />
      </div>

      {/* Features */}
      <section className="max-w-4xl mx-auto px-6 pb-20">
        <h2 className="text-center text-2xl font-bold mb-10">Everything you need</h2>
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {[
            { icon: "🛑", title: "Hard Limits", desc: "Block or downgrade when budget is reached. No surprises." },
            { icon: "📊", title: "Per-Project Budgets", desc: "Separate budget, alerts and model policy per project." },
            { icon: "⬇️", title: "Auto-Downgrade", desc: "Automatically switch to cheaper models at threshold." },
            { icon: "🔔", title: "Alerts", desc: "Email and Slack/webhook alerts before you hit the ceiling." },
            { icon: "📥", title: "Usage Export", desc: "CSV and JSON export for billing, audits, and reporting." },
            { icon: "👥", title: "Team Members", desc: "Invite teammates as admin or viewer. No shared passwords." },
          ].map((f) => (
            <div
              key={f.title}
              className="rounded-xl p-5"
              style={{ border: "1px solid var(--border)", background: "var(--card)" }}
            >
              <div className="text-2xl mb-3">{f.icon}</div>
              <h3 className="font-semibold mb-1">{f.title}</h3>
              <p className="text-sm" style={{ color: "#c8d8e8" }}>{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Pricing */}
      <PricingSection />

      {/* Final CTA */}
      <section
        className="py-16 text-center px-6"
        style={{ borderTop: "1px solid var(--border)" }}
      >
        <h2 className="text-2xl font-bold mb-4">Ready to stop overspending?</h2>
        <p className="text-sm mb-8 max-w-md mx-auto" style={{ color: "#c8d8e8" }}>
          Get your first BudgetForge key in under a minute. Free forever for 1,000 calls/month.
        </p>
        <div className="flex flex-col sm:flex-row gap-3 justify-center">
          <a
            href="#hero"
            className="inline-block px-8 py-3 rounded-lg font-semibold transition-opacity hover:opacity-90"
            style={{ background: "var(--amber)", color: "#000" }}
          >
            Get my free key →
          </a>
          <Link
            href="/demo"
            className="inline-block px-8 py-3 rounded-lg transition-colors"
            style={{ border: "1px solid var(--border)", color: "var(--foreground)" }}
          >
            See the dashboard
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer
        className="py-8 px-6 text-center text-xs"
        style={{ color: "#c8d8e8", borderTop: "1px solid var(--border)" }}
      >
        <p>
          BudgetForge —{" "}
          <a
            href="https://github.com/majorelalexis-stack/budgetforge"
            className="hover:opacity-80"
            style={{ color: "var(--amber)" }}
          >
            open source
          </a>
          {" · "}
          <Link href="/portal" className="hover:opacity-80" style={{ color: "var(--amber)" }}>
            My keys
          </Link>
          {" · "}
          <a href="mailto:hello@maxiaworld.app" className="hover:opacity-80" style={{ color: "var(--amber)" }}>
            Contact
          </a>
        </p>
      </footer>
    </div>
  );
}
