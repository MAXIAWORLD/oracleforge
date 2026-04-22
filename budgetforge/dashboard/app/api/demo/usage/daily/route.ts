export async function GET() {
  const daily = Array.from({ length: 30 }, (_, i) => {
    const d = new Date("2026-03-23");
    d.setDate(d.getDate() + i);
    const dateStr = d.toISOString().split("T")[0];
    // More realistic spend pattern: low start, ramping up over time
    const baseSpend = i < 3 ? 0 : Math.min(25, i * 0.4);
    const variation = Math.sin(i * 0.5) * 3 + Math.random() * 2;
    const spend = Math.max(0, baseSpend + variation);

    return {
      date: dateStr,
      spend: parseFloat(spend.toFixed(4)),
    };
  });

  return Response.json(daily);
}
