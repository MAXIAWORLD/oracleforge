export async function GET() {
  const summary = {
    total_cost_usd: 614.47,
    total_calls: 4891,
    projects_count: 5,
    at_risk_count: 2,
    exceeded_count: 1,
  };

  return Response.json(summary);
}
