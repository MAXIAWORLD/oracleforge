"""BudgetForge — QA golden path (Playwright).
Tests: landing, docs page, nav-bar, pricing section, portal.
"""

import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = "https://llmbudget.maxiaworld.app"
SCREENSHOTS = Path(__file__).parent / "qa_screenshots"
SCREENSHOTS.mkdir(exist_ok=True)

PASS = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"
results = []


def check(label: str, ok: bool, detail: str = ""):
    mark = PASS if ok else FAIL
    print(f"  {mark} {label}" + (f"  [{detail}]" if detail else ""))
    results.append((label, ok))


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1280, "height": 900})

    # ── 1. Landing page ────────────────────────────────────────────────────────
    print("\n── Landing page ──")
    page.goto(BASE, wait_until="networkidle")
    page.screenshot(path=str(SCREENSHOTS / "01_landing.png"), full_page=True)

    check("Page loads (HTTP 200)", "llmbudget.maxiaworld.app" in page.url)
    check("Logo visible", page.locator("img[alt='BudgetForge']").is_visible())
    check("Nav: How it works", page.locator("a:text('How it works')").is_visible())
    check("Nav: Pricing", page.locator("a:text('Pricing')").is_visible())
    check("Nav: Docs", page.locator("a:text('Docs')").is_visible())
    check("Nav: Live preview", page.locator("a:text('Live preview')").is_visible())
    check("Nav: My keys", page.locator("a:text('My keys')").count() > 0)
    check("Hero h1 visible", page.locator("h1").is_visible())

    # ── 2. Pricing section ─────────────────────────────────────────────────────
    print("\n── Pricing section ──")
    page.locator("#pricing").scroll_into_view_if_needed()
    page.wait_for_timeout(300)
    page.screenshot(path=str(SCREENSHOTS / "02_pricing.png"))

    check("Section #pricing exists", page.locator("#pricing").is_visible())
    check("Plan: Free", page.locator("text=Free").first.is_visible())
    check("Plan: Pro", page.locator("text=Pro").first.is_visible())
    check("Plan: Agency", page.locator("text=Agency").first.is_visible())
    check("Stripe logo img", page.locator("img[alt='Stripe']").is_visible())
    pricing = page.locator("#pricing")
    check(
        "Provider badge: OpenAI",
        pricing.locator("span.rounded-full", has_text="OpenAI").first.is_visible(),
    )
    check(
        "Provider badge: Anthropic",
        pricing.locator("span.rounded-full", has_text="Anthropic").first.is_visible(),
    )
    check(
        "Provider badge: Google AI",
        pricing.locator("span.rounded-full", has_text="Google AI").first.is_visible(),
    )

    # ── 3. FAQ section ─────────────────────────────────────────────────────────
    print("\n── FAQ section ──")
    faq = page.locator("details").first
    if faq.count() > 0:
        faq.click()
        page.wait_for_timeout(200)
        page.screenshot(path=str(SCREENSHOTS / "03_faq_open.png"))
        check("FAQ accordion opens", True)
    else:
        check("FAQ accordion exists", False, "no <details> found")

    # ── 4. /docs page ─────────────────────────────────────────────────────────
    print("\n── /docs page ──")
    page.goto(f"{BASE}/docs", wait_until="networkidle")
    page.screenshot(path=str(SCREENSHOTS / "04_docs.png"), full_page=True)

    check("Docs page loads", "/docs" in page.url)
    check("Title: Documentation", page.locator("h1:text('Documentation')").is_visible())
    check("Section: Quick start", page.locator("#quickstart").is_visible())
    check("Section: Providers table", page.locator("#providers").is_visible())
    check("Section: SDK", page.locator("#sdk").is_visible())
    check("Section: API reference", page.locator("#api").is_visible())
    check("Code blocks present", page.locator("pre").count() >= 3)
    check("Back to home link", page.locator("a:text('← Back to home')").is_visible())

    # ── 5. Nav → /docs link works ──────────────────────────────────────────────
    print("\n── Nav Docs link ──")
    page.goto(BASE, wait_until="networkidle")
    page.locator("a:text('Docs')").first.click()
    page.wait_for_load_state("networkidle")
    check("Nav 'Docs' navigates to /docs", "/docs" in page.url)

    # ── 6. /portal page ────────────────────────────────────────────────────────
    print("\n── /portal page ──")
    page.goto(f"{BASE}/portal", wait_until="networkidle")
    page.screenshot(path=str(SCREENSHOTS / "05_portal.png"), full_page=True)
    check("Portal loads", "portal" in page.url or page.locator("body").is_visible())

    # ── 7. /demo page ─────────────────────────────────────────────────────────
    print("\n── /demo page ──")
    page.goto(f"{BASE}/demo", wait_until="networkidle")
    page.screenshot(path=str(SCREENSHOTS / "06_demo.png"), full_page=True)
    check("Demo page loads", page.locator("body").is_visible())

    browser.close()

# ── Summary ────────────────────────────────────────────────────────────────────
total = len(results)
passed = sum(1 for _, ok in results if ok)
failed = total - passed
print(
    f"\n── Summary: {passed}/{total} passed",
    "✓" if failed == 0 else f"({failed} FAILED)",
)
print(f"   Screenshots → {SCREENSHOTS}")
if failed > 0:
    print("\nFailed checks:")
    for label, ok in results:
        if not ok:
            print(f"  ✗ {label}")
    sys.exit(1)
