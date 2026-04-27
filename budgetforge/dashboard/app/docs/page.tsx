import Link from "next/link";
import { NavBar } from "@/components/nav-bar";

const CODE_BG = { background: "#0d1117", border: "1px solid var(--border)" };

function Code({ children }: { children: string }) {
  return (
    <pre className="rounded-lg p-4 text-sm overflow-x-auto" style={CODE_BG}>
      <code style={{ color: "#c8d8e8" }}>{children}</code>
    </pre>
  );
}

function Section({
  id,
  title,
  children,
}: {
  id: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section id={id} className="mb-14">
      <h2
        className="text-xl font-bold mb-5 pb-2"
        style={{ borderBottom: "1px solid var(--border)" }}
      >
        {title}
      </h2>
      {children}
    </section>
  );
}

export default function DocsPage() {
  return (
    <div
      className="min-h-screen"
      style={{ background: "var(--background)", color: "var(--foreground)" }}
    >
      <NavBar />

      <div className="max-w-3xl mx-auto px-6 py-16">
        <div className="mb-12">
          <h1 className="text-3xl font-bold mb-3">Documentation</h1>
          <p style={{ color: "#c8d8e8" }}>
            BudgetForge is a drop-in proxy that enforces hard budget limits on
            your LLM API calls. No code changes needed — just swap the base URL.
          </p>
        </div>

        {/* Quick nav */}
        <nav className="mb-12 flex flex-wrap gap-3 text-sm">
          {["quickstart", "providers", "sdk", "webhooks", "api"].map((id) => (
            <a
              key={id}
              href={`#${id}`}
              className="px-3 py-1 rounded-full capitalize hover:opacity-80"
              style={{ border: "1px solid var(--border)", color: "#c8d8e8" }}
            >
              {id === "api"
                ? "API reference"
                : id.charAt(0).toUpperCase() + id.slice(1)}
            </a>
          ))}
        </nav>

        {/* ── Quick start ─────────────────────────────────────────────── */}
        <Section id="quickstart" title="Quick start">
          <p className="mb-4 text-sm" style={{ color: "#c8d8e8" }}>
            1. Get your BudgetForge key from the{" "}
            <Link
              href="/portal"
              className="underline"
              style={{ color: "var(--amber)" }}
            >
              portal
            </Link>
            . 2. Replace your provider base URL with the BudgetForge proxy URL.{" "}
            3. Pass your original provider key as{" "}
            <code className="text-xs px-1 rounded" style={CODE_BG}>
              X-Provider-Key
            </code>
            .
          </p>

          <p
            className="text-sm font-semibold mb-2"
            style={{ color: "#c8d8e8" }}
          >
            Python / OpenAI SDK
          </p>
          <Code>{`import openai

client = openai.OpenAI(
    api_key="YOUR-BUDGETFORGE-KEY",
    base_url="https://llmbudget.maxiaworld.app/proxy/openai/v1",
    default_headers={"X-Provider-Key": "YOUR-OPENAI-KEY"},
)

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Hello"}],
)`}</Code>

          <p
            className="text-sm font-semibold mb-2 mt-6"
            style={{ color: "#c8d8e8" }}
          >
            Anthropic SDK
          </p>
          <Code>{`import anthropic

client = anthropic.Anthropic(
    api_key="YOUR-BUDGETFORGE-KEY",
    base_url="https://llmbudget.maxiaworld.app/proxy/anthropic",
    default_headers={"X-Provider-Key": "YOUR-ANTHROPIC-KEY"},
)`}</Code>

          <p
            className="text-sm font-semibold mb-2 mt-6"
            style={{ color: "#c8d8e8" }}
          >
            Cursor / n8n / any OpenAI-compatible tool
          </p>
          <Code>{`API Key:  YOUR-BUDGETFORGE-KEY
Base URL: https://llmbudget.maxiaworld.app/proxy/openai`}</Code>
        </Section>

        {/* ── Providers ───────────────────────────────────────────────── */}
        <Section id="providers" title="Supported providers">
          <div className="overflow-x-auto">
            <table
              className="w-full text-sm"
              style={{ borderCollapse: "collapse" }}
            >
              <thead>
                <tr style={{ borderBottom: "1px solid var(--border)" }}>
                  {["Provider", "Proxy path", "Plan"].map((h) => (
                    <th
                      key={h}
                      className="text-left py-2 pr-6 font-semibold"
                      style={{ color: "#c8d8e8" }}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {[
                  ["OpenAI", "/proxy/openai/v1/…", "Free+"],
                  ["Anthropic", "/proxy/anthropic/…", "Free+"],
                  ["Google AI", "/proxy/google/…", "Pro+"],
                  ["DeepSeek", "/proxy/deepseek/…", "Pro+"],
                  ["Ollama (local)", "/proxy/ollama/…", "Free+"],
                ].map(([provider, path, plan]) => (
                  <tr
                    key={provider}
                    style={{ borderBottom: "1px solid var(--border)" }}
                  >
                    <td className="py-2 pr-6">{provider}</td>
                    <td
                      className="py-2 pr-6 font-mono text-xs"
                      style={{ color: "#c8d8e8" }}
                    >
                      {path}
                    </td>
                    <td className="py-2" style={{ color: "var(--amber)" }}>
                      {plan}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>

        {/* ── SDK ─────────────────────────────────────────────────────── */}
        <Section id="sdk" title="Python SDK">
          <p className="text-sm mb-4" style={{ color: "#c8d8e8" }}>
            Drop-in SDK — no extra setup required.
          </p>
          <Code>{`pip install budgetforge`}</Code>

          <p
            className="text-sm font-semibold mb-2 mt-6"
            style={{ color: "#c8d8e8" }}
          >
            LLM (simple prompt)
          </p>
          <Code>{`from budgetforge import BudgetForgeLLM

llm = BudgetForgeLLM(api_key="YOUR-BUDGETFORGE-KEY")
print(llm.invoke("Summarize this in one sentence: ..."))`}</Code>

          <p
            className="text-sm font-semibold mb-2 mt-6"
            style={{ color: "#c8d8e8" }}
          >
            Chat (messages list)
          </p>
          <Code>{`from budgetforge import BudgetForgeChat

chat = BudgetForgeChat(api_key="YOUR-BUDGETFORGE-KEY", provider="anthropic")
result = chat.invoke([
    {"role": "user", "content": "Hello!"}
])
print(result["content"])`}</Code>

          <p
            className="text-sm font-semibold mb-2 mt-6"
            style={{ color: "#c8d8e8" }}
          >
            LangChain integration
          </p>
          <Code>{`pip install langchain-budgetforge`}</Code>
          <Code>{`from langchain_budgetforge import BudgetForgeLLM

llm = BudgetForgeLLM(api_key="YOUR-BUDGETFORGE-KEY")
result = llm.invoke("Write a haiku about tokens.")
print(result)`}</Code>
        </Section>

        {/* ── Webhooks ─────────────────────────────────────────────────── */}
        <Section id="webhooks" title="Webhooks (Pro+)">
          <p className="text-sm mb-4" style={{ color: "#c8d8e8" }}>
            BudgetForge sends a POST to your webhook URL when a budget threshold
            is hit.
          </p>
          <Code>{`# Payload example
{
  "event": "budget.threshold",
  "project_id": "proj_xxx",
  "budget_used_pct": 90,
  "budget_usd": 10.00,
  "spent_usd": 9.02,
  "timestamp": "2026-04-24T14:00:00Z"
}`}</Code>
          <p className="text-sm mt-4" style={{ color: "#c8d8e8" }}>
            Configure webhooks in your{" "}
            <Link
              href="/portal"
              className="underline"
              style={{ color: "var(--amber)" }}
            >
              project settings
            </Link>
            .
          </p>
        </Section>

        {/* ── API reference ───────────────────────────────────────────── */}
        <Section id="api" title="API reference">
          <div className="space-y-6 text-sm" style={{ color: "#c8d8e8" }}>
            {[
              {
                method: "POST",
                path: "/proxy/{provider}/v1/chat/completions",
                desc: "Forward a chat completion request through BudgetForge. Identical body to the provider API.",
              },
              {
                method: "GET",
                path: "/api/usage",
                desc: "Returns calls used and budget consumed for the authenticated project.",
              },
              {
                method: "GET",
                path: "/health",
                desc: 'Health check. Returns {"status": "ok"} with HTTP 200.',
              },
            ].map(({ method, path, desc }) => (
              <div key={path} className="rounded-lg p-4" style={CODE_BG}>
                <div className="flex items-center gap-3 mb-2">
                  <span
                    className="text-xs font-bold px-2 py-0.5 rounded"
                    style={{
                      background: method === "GET" ? "#1a3a1a" : "#3a1a1a",
                      color: method === "GET" ? "#4ade80" : "#f87171",
                    }}
                  >
                    {method}
                  </span>
                  <code className="text-xs" style={{ color: "var(--amber)" }}>
                    {path}
                  </code>
                </div>
                <p className="text-xs">{desc}</p>
              </div>
            ))}
          </div>

          <p className="text-sm mt-6" style={{ color: "#c8d8e8" }}>
            All requests require{" "}
            <code className="text-xs px-1 rounded" style={CODE_BG}>
              Authorization: Bearer YOUR-BUDGETFORGE-KEY
            </code>
            .
          </p>
        </Section>

        {/* Footer */}
        <div
          className="border-t pt-8 text-sm flex flex-wrap gap-4 justify-between"
          style={{ borderColor: "var(--border)", color: "#6b7a8d" }}
        >
          <span>
            Questions? Email{" "}
            <a href="mailto:support@maxiaworld.app" className="underline">
              support@maxiaworld.app
            </a>
          </span>
          <Link
            href="/"
            style={{ color: "#c8d8e8" }}
            className="hover:opacity-80"
          >
            ← Back to home
          </Link>
        </div>
      </div>
    </div>
  );
}
