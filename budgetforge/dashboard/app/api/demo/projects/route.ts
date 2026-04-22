export async function GET() {
  const projects = [
    {
      name: "AI Chat Assistant",
      budget_usd: 150,
      used_usd: 108.45,
      pct_used: 72.3,
      action: "downgrade",
      allowed_providers: ["openai", "anthropic"],
    },
    {
      name: "Content Generator",
      budget_usd: 300,
      used_usd: 287.92,
      pct_used: 95.97,
      action: "block",
      allowed_providers: ["openai", "anthropic", "google"],
    },
    {
      name: "Web Scraper Agent",
      budget_usd: 75,
      used_usd: 22.10,
      pct_used: 29.5,
      action: null,
      allowed_providers: ["openai"],
    },
    {
      name: "Image Analysis",
      budget_usd: 200,
      used_usd: 156.33,
      pct_used: 78.2,
      action: null,
      allowed_providers: ["google", "anthropic"],
    },
    {
      name: "Code Review Bot",
      budget_usd: 100,
      used_usd: 38.67,
      pct_used: 38.7,
      action: null,
      allowed_providers: ["openai", "anthropic"],
    },
  ];

  return Response.json(projects);
}
