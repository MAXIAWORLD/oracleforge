import { NavBar } from "@/components/nav-bar";
import { PricingSection } from "@/components/pricing-section";
import { FreeSignupForm } from "@/components/free-signup-form";
import { QuickSetupLanding } from "@/components/quick-setup-landing";

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
          Budget control for AI APIs
        </div>
        <h1 className="text-4xl sm:text-5xl font-bold leading-tight mb-6">
          Stop unexpected
          <br />
          <span style={{ color: "var(--amber)" }}>AI API bills</span>
        </h1>
        <p className="text-lg mb-10 max-w-xl mx-auto" style={{ color: "#c8d8e8" }}>
          Set a spending limit on your AI APIs. BudgetForge automatically blocks requests
          the moment your budget is reached — no surprises, no runaway costs.
        </p>
        <FreeSignupForm />
      </section>

      {/* Code preview */}
      <section className="max-w-2xl mx-auto px-6 pb-16">
        <div
          className="rounded-xl p-6"
          style={{ border: "1px solid var(--border)", background: "var(--card)", fontFamily: "var(--font-mono, monospace)" }}
        >
          <p className="text-xs mb-4 font-sans" style={{ color: "#c8d8e8" }}>
            Works with any OpenAI-compatible SDK — 3 settings to change
          </p>
          <pre className="text-sm leading-relaxed overflow-x-auto" style={{ color: "#6b7280" }}>{`# Before
client = OpenAI(api_key="sk-your-openai-key")`}</pre>
          <pre className="text-sm leading-relaxed overflow-x-auto mt-4" style={{ color: "#4ade80" }}>{`# After — budget protected
client = OpenAI(
    api_key="bf-your-budgetforge-key",
    base_url="https://llmbudget.maxiaworld.app/proxy/openai/v1",
    default_headers={"X-Provider-Key": "sk-your-openai-key"}
)`}</pre>
        </div>
      </section>

      {/* How it works */}
      <section id="how" className="max-w-3xl mx-auto px-6 pb-20">
        <h2 className="text-center text-2xl font-bold mb-3">How it works</h2>
        <p className="text-center text-sm mb-10" style={{ color: "#c8d8e8" }}>
          Up and running in under 2 minutes. Your API keys stay yours — we never store them.
        </p>
        <div className="grid sm:grid-cols-3 gap-6">
          {[
            {
              step: "1",
              title: "Get your free key",
              desc: "Enter your email above. Your BudgetForge key arrives instantly — no credit card.",
            },
            {
              step: "2",
              title: "Point your tool to us",
              desc: "Change 3 settings: your BF key, our proxy URL, and your original key as a header.",
            },
            {
              step: "3",
              title: "Set your limit & relax",
              desc: "Pick a dollar limit in the portal. We block AI requests the moment it's hit — zero surprise bills.",
            },
          ].map((item) => (
            <div key={item.step} className="flex flex-col items-center text-center">
              <div
                className="w-10 h-10 rounded-full flex items-center justify-center font-bold text-lg mb-4"
                style={{ background: "var(--amber)", color: "#000" }}
              >
                {item.step}
              </div>
              <h3 className="font-semibold mb-2">{item.title}</h3>
              <p className="text-sm leading-relaxed" style={{ color: "#c8d8e8" }}>{item.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Step-by-step setup */}
      <QuickSetupLanding />

      {/* Features */}
      <section id="features" className="max-w-4xl mx-auto px-6 pb-20">
        <h2 className="text-center text-2xl font-bold mb-10">Everything you need</h2>
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {[
            { icon: "🛑", title: "Hard limits", desc: "AI requests are blocked the moment your budget is hit. No overages, ever." },
            { icon: "🔑", title: "Zero key storage", desc: "Your OpenAI / Anthropic key never touches our database. You pass it per-request." },
            { icon: "⬇️", title: "Auto-downgrade", desc: "Automatically switch to a cheaper AI model when you reach a threshold you choose." },
            { icon: "🔔", title: "Alerts", desc: "Get an email or Slack message before you hit your limit — not after." },
            { icon: "📥", title: "Usage export", desc: "Download your usage as CSV or JSON for billing, accounting, or reporting." },
            { icon: "👥", title: "Team access", desc: "Invite teammates as admin or viewer. No shared passwords." },
          ].map((f) => (
            <div
              key={f.title}
              className="rounded-xl p-5"
              style={{ border: "1px solid var(--border)", background: "var(--card)" }}
            >
              <div className="text-2xl mb-3">{f.icon}</div>
              <h3 className="font-semibold mb-1">{f.title}</h3>
              <p className="text-sm leading-relaxed" style={{ color: "#c8d8e8" }}>{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Pricing */}
      <PricingSection />

      {/* CTA */}
      <section
        className="py-16 text-center px-6"
        style={{ borderTop: "1px solid var(--border)" }}
      >
        <h2 className="text-2xl font-bold mb-3">Ready to stop overpaying?</h2>
        <p className="text-sm mb-8" style={{ color: "#c8d8e8" }}>Free to start. No credit card required.</p>
        <a
          href="#hero"
          className="inline-block px-8 py-3 rounded-lg font-semibold transition-opacity hover:opacity-90"
          style={{ background: "var(--amber)", color: "#000" }}
        >
          Get started free →
        </a>
      </section>
    </div>
  );
}
