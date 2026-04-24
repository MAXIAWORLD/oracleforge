#!/usr/bin/env python3
"""
AWS Bedrock Monitoring Tool for BudgetForge

This tool helps monitor AWS Bedrock usage, costs, and performance through BudgetForge.
"""

import os
import requests
import time
from datetime import datetime, timedelta
import sqlite3
from typing import Dict, Any
import matplotlib.pyplot as plt
import pandas as pd

# Configuration
BUDGETFORGE_BASE_URL = "http://localhost:8011"
DATABASE_PATH = "budgetforge.db"


def get_usage_stats(days: int = 7) -> Dict[str, Any]:
    """Get usage statistics from BudgetForge database."""

    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        # Calculate date range
        cutoff_date = datetime.now() - timedelta(days=days)

        # Query AWS Bedrock usage
        query = """
        SELECT 
            provider,
            model,
            SUM(tokens_in) as total_input_tokens,
            SUM(tokens_out) as total_output_tokens,
            SUM(cost_usd) as total_cost,
            COUNT(*) as request_count
        FROM usages 
        WHERE provider = 'aws_bedrock' 
          AND created_at >= ?
        GROUP BY provider, model
        ORDER BY total_cost DESC
        """

        cursor.execute(query, (cutoff_date,))
        results = cursor.fetchall()

        stats = {
            "period_days": days,
            "models": [],
            "total_requests": 0,
            "total_cost": 0.0,
            "total_tokens": 0,
        }

        for row in results:
            model_stats = {
                "model": row[1],
                "input_tokens": row[2],
                "output_tokens": row[3],
                "cost": row[4],
                "requests": row[5],
            }
            stats["models"].append(model_stats)
            stats["total_requests"] += row[5]
            stats["total_cost"] += row[4]
            stats["total_tokens"] += row[2] + row[3]

        conn.close()
        return stats

    except Exception as e:
        print(f"❌ Error reading database: {e}")
        return {}


def get_current_pricing() -> Dict[str, Any]:
    """Get current AWS Bedrock pricing information."""

    # These are the standard AWS Bedrock prices (per 1M tokens)
    pricing = {
        "anthropic.claude-3-opus": {"input": 15.00, "output": 75.00},
        "anthropic.claude-3-sonnet": {"input": 3.00, "output": 15.00},
        "anthropic.claude-3-haiku": {"input": 0.80, "output": 4.00},
        "anthropic.claude-v2": {"input": 8.00, "output": 24.00},
        "anthropic.claude-v2:1": {"input": 8.00, "output": 24.00},
        "meta.llama2-13b-chat": {"input": 0.75, "output": 0.75},
        "meta.llama2-70b-chat": {"input": 2.05, "output": 2.05},
        "meta.llama3-8b-instruct": {"input": 0.60, "output": 0.60},
        "meta.llama3-70b-instruct": {"input": 2.65, "output": 2.65},
    }

    return pricing


def calculate_cost_efficiency(stats: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate cost efficiency metrics."""

    pricing = get_current_pricing()
    efficiency = {}

    for model_stats in stats.get("models", []):
        model = model_stats["model"]

        if model in pricing:
            expected_cost = (
                model_stats["input_tokens"] * pricing[model]["input"] / 1_000_000
                + model_stats["output_tokens"] * pricing[model]["output"] / 1_000_000
            )

            actual_cost = model_stats["cost"]
            cost_ratio = actual_cost / expected_cost if expected_cost > 0 else 1.0

            efficiency[model] = {
                "expected_cost": expected_cost,
                "actual_cost": actual_cost,
                "cost_ratio": cost_ratio,
                "efficiency": "Good" if cost_ratio <= 1.1 else "Review",
                "tokens_per_dollar": (
                    model_stats["input_tokens"] + model_stats["output_tokens"]
                )
                / actual_cost
                if actual_cost > 0
                else 0,
            }

    return efficiency


def generate_usage_report(stats: Dict[str, Any]) -> str:
    """Generate a formatted usage report."""

    efficiency = calculate_cost_efficiency(stats)

    report = f"""
AWS Bedrock Usage Report
{"=" * 50}
Period: Last {stats.get("period_days", 0)} days
Total Requests: {stats.get("total_requests", 0):,}
Total Tokens: {stats.get("total_tokens", 0):,}
Total Cost: ${stats.get("total_cost", 0):.4f}

Model Breakdown:
{"=" * 50}
"""

    for model_stats in stats.get("models", []):
        model = model_stats["model"]
        eff = efficiency.get(model, {})

        report += f"""
Model: {model}
  Requests: {model_stats["requests"]:,}
  Input Tokens: {model_stats["input_tokens"]:,}
  Output Tokens: {model_stats["output_tokens"]:,}
  Cost: ${model_stats["cost"]:.4f}
  Efficiency: {eff.get("efficiency", "N/A")} (Ratio: {eff.get("cost_ratio", 0):.2f})
  Tokens per Dollar: {eff.get("tokens_per_dollar", 0):,.0f}
"""

    return report


def plot_usage_trends(days: int = 30):
    """Generate plots showing usage trends."""

    try:
        conn = sqlite3.connect(DATABASE_PATH)

        # Get daily usage data
        query = """
        SELECT 
            DATE(created_at) as usage_date,
            model,
            SUM(tokens_in + tokens_out) as daily_tokens,
            SUM(cost_usd) as daily_cost
        FROM usages 
        WHERE provider = 'aws_bedrock' 
          AND created_at >= DATE('now', ?)
        GROUP BY usage_date, model
        ORDER BY usage_date
        """

        df = pd.read_sql_query(query, conn, params=[f"-{days} days"])
        conn.close()

        if df.empty:
            print("❌ No usage data found for the specified period")
            return

        # Create plots
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 10))

        # Plot 1: Daily token usage by model
        pivot_tokens = df.pivot(
            index="usage_date", columns="model", values="daily_tokens"
        ).fillna(0)
        pivot_tokens.plot(
            kind="area", stacked=True, ax=ax1, title="Daily Token Usage by Model"
        )
        ax1.set_ylabel("Tokens")
        ax1.legend(bbox_to_anchor=(1.05, 1), loc="upper left")

        # Plot 2: Daily cost by model
        pivot_cost = df.pivot(
            index="usage_date", columns="model", values="daily_cost"
        ).fillna(0)
        pivot_cost.plot(kind="area", stacked=True, ax=ax2, title="Daily Cost by Model")
        ax2.set_ylabel("Cost (USD)")
        ax2.legend(bbox_to_anchor=(1.05, 1), loc="upper left")

        # Plot 3: Model distribution (pie chart)
        model_totals = df.groupby("model")["daily_tokens"].sum()
        ax3.pie(model_totals, labels=model_totals.index, autopct="%1.1f%%")
        ax3.set_title("Token Distribution by Model")

        # Plot 4: Cost efficiency
        model_costs = df.groupby("model")["daily_cost"].sum()
        model_tokens = df.groupby("model")["daily_tokens"].sum()
        cost_per_token = model_costs / model_tokens * 1000  # Cost per 1K tokens

        cost_per_token.plot(kind="bar", ax=ax4, title="Cost per 1K Tokens by Model")
        ax4.set_ylabel("Cost per 1K Tokens (USD)")
        ax4.tick_params(axis="x", rotation=45)

        plt.tight_layout()
        plt.savefig("aws_bedrock_usage_report.png", dpi=300, bbox_inches="tight")
        print("✅ Usage report saved as 'aws_bedrock_usage_report.png'")

    except Exception as e:
        print(f"❌ Error generating plots: {e}")


def performance_benchmark():
    """Run a simple performance benchmark."""

    print("\n🔧 Running Performance Benchmark...")

    test_payload = {
        "model": "anthropic.claude-3-haiku",
        "messages": [{"role": "user", "content": "Respond with 'Hello, World!'"}],
        "max_tokens": 10,
    }

    latencies = []

    for i in range(5):  # Run 5 test requests
        start_time = time.time()

        try:
            response = requests.post(
                f"{BUDGETFORGE_BASE_URL}/proxy/aws-bedrock/v1/chat/completions",
                headers={
                    "Authorization": "Bearer bf-test-key",  # Use a test key
                    "Content-Type": "application/json",
                },
                json=test_payload,
                timeout=30,
            )

            latency = (time.time() - start_time) * 1000  # Convert to milliseconds
            latencies.append(latency)

            if response.status_code == 200:
                print(f"  Request {i + 1}: {latency:.0f}ms - ✅ Success")
            else:
                print(
                    f"  Request {i + 1}: {latency:.0f}ms - ❌ Failed ({response.status_code})"
                )

        except Exception as e:
            latency = (time.time() - start_time) * 1000
            latencies.append(latency)
            print(f"  Request {i + 1}: {latency:.0f}ms - ❌ Error: {e}")

    if latencies:
        avg_latency = sum(latencies) / len(latencies)
        min_latency = min(latencies)
        max_latency = max(latencies)

        print("\n📊 Performance Summary:")
        print(f"  Average Latency: {avg_latency:.0f}ms")
        print(f"  Minimum Latency: {min_latency:.0f}ms")
        print(f"  Maximum Latency: {max_latency:.0f}ms")

        # Compare against AWS SLA (typically < 2 seconds)
        if avg_latency < 2000:
            print("  Performance: ✅ Within expected range")
        else:
            print("  Performance: ⚠️ Higher than expected")


def budget_alert_check():
    """Check if any projects are approaching their budget limits."""

    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        query = """
        SELECT 
            p.name,
            p.budget_usd,
            SUM(u.cost_usd) as used_cost,
            p.alert_threshold_pct
        FROM projects p
        LEFT JOIN usages u ON p.id = u.project_id
        WHERE u.provider = 'aws_bedrock'
          AND u.created_at >= DATE('now', '-30 days')
          AND p.budget_usd IS NOT NULL
        GROUP BY p.id
        HAVING used_cost >= p.budget_usd * p.alert_threshold_pct / 100
        """

        cursor.execute(query)
        results = cursor.fetchall()
        conn.close()

        if results:
            print("\n🚨 Budget Alerts:")
            for project_name, budget, used_cost, threshold in results:
                usage_pct = (used_cost / budget) * 100
                print(
                    f"  {project_name}: {usage_pct:.1f}% of ${budget:.2f} budget used"
                )
        else:
            print("\n✅ No budget alerts")

    except Exception as e:
        print(f"❌ Error checking budget alerts: {e}")


def main():
    """Run the monitoring tool."""

    print("=" * 60)
    print("AWS Bedrock Monitoring Tool")
    print("=" * 60)

    # Check database accessibility
    if not os.path.exists(DATABASE_PATH):
        print(f"❌ Database not found: {DATABASE_PATH}")
        print("Please run this tool from the BudgetForge backend directory")
        return

    # Generate usage report
    print("\n📊 Generating Usage Report...")
    stats = get_usage_stats(days=7)

    if stats:
        report = generate_usage_report(stats)
        print(report)

        # Save report to file
        with open("aws_bedrock_report.txt", "w") as f:
            f.write(report)
        print("✅ Report saved as 'aws_bedrock_report.txt'")
    else:
        print("❌ No AWS Bedrock usage data found")

    # Generate plots
    print("\n📈 Generating Usage Plots...")
    plot_usage_trends(days=30)

    # Performance benchmark
    performance_benchmark()

    # Budget alerts
    budget_alert_check()

    print("\n" + "=" * 60)
    print("Monitoring complete!")
    print("Check the generated files for detailed analysis:")
    print("  - aws_bedrock_report.txt (text report)")
    print("  - aws_bedrock_usage_report.png (visual charts)")
    print("=" * 60)


if __name__ == "__main__":
    main()
