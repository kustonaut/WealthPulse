"""Capture screenshots for README using Playwright."""
import asyncio
import json
import os
import sys
from pathlib import Path
from datetime import datetime

# Paths
ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output"
DOCS = ROOT / "docs" / "screenshots"
DOCS.mkdir(parents=True, exist_ok=True)

DASHBOARD_FILE = OUTPUT / "WealthPulse_DEMO.html"


async def render_email_preview():
    """Render the email template with sample data into a standalone HTML file."""
    from jinja2 import Environment, FileSystemLoader

    templates_dir = ROOT / "src" / "wealthpulse" / "templates"
    env = Environment(loader=FileSystemLoader(str(templates_dir)))
    template = env.get_template("email_brief.html")

    # Sample context matching what email_sender.py would produce
    sample_ctx = {
        "subject": "WealthPulse Daily Brief — Feb 7, 2026",
        "date_display": "Friday, February 7, 2026",
        "greeting": "Good Morning ☀️",
        "currency": "₹",
        "equity_display": "47,32,850",
        "day_pnl": 18750,
        "day_pnl_display": "18,750",
        "portfolio_movers": [
            {"symbol": "RELIANCE", "price": 2845.30, "change_pct": 2.35, "day_pnl": 4250},
            {"symbol": "TCS", "price": 4120.50, "change_pct": 1.80, "day_pnl": 3600},
            {"symbol": "HDFCBANK", "price": 1685.75, "change_pct": -0.95, "day_pnl": -1425},
            {"symbol": "INFY", "price": 1892.40, "change_pct": 1.45, "day_pnl": 2175},
            {"symbol": "WIPRO", "price": 548.20, "change_pct": -1.20, "day_pnl": -960},
        ],
        "mf_display": "12,45,000",
        "mf_pnl": 8500,
        "mf_pnl_display": "8,500",
        "index_data": {
            "NIFTY 50": type("Idx", (), {"price": 23456.7, "change_pct": 0.85})(),
            "SENSEX": type("Idx", (), {"price": 77234.5, "change_pct": 0.72})(),
            "GOLD": type("Idx", (), {"price": 73250.0, "change_pct": 0.35})(),
            "USD/INR": type("Idx", (), {"price": 85.42, "change_pct": -0.12})(),
        },
        "top_gainers": [
            type("M", (), {"symbol": "TATAPOWER", "change_pct": 5.8})(),
            type("M", (), {"symbol": "ADANIENT", "change_pct": 4.2})(),
            type("M", (), {"symbol": "BAJFINANCE", "change_pct": 3.1})(),
        ],
        "top_losers": [
            type("M", (), {"symbol": "SBIN", "change_pct": -2.4})(),
            type("M", (), {"symbol": "SUNPHARMA", "change_pct": -1.8})(),
            type("M", (), {"symbol": "HINDUNILVR", "change_pct": -1.5})(),
        ],
        "news": {
            "Markets": [
                {"title": "Nifty crosses 23,400 on strong FII inflows", "link": "#"},
                {"title": "RBI keeps repo rate unchanged at 6.5%", "link": "#"},
            ],
            "Stocks": [
                {"title": "Reliance Q3 profit jumps 18% on Jio growth", "link": "#"},
                {"title": "IT sector rally: TCS, Infosys lead gains", "link": "#"},
            ],
        },
    }

    html = template.render(**sample_ctx)
    email_path = OUTPUT / "email_preview.html"
    email_path.write_text(html, encoding="utf-8")
    print(f"✅ Email preview rendered: {email_path}")
    return email_path


async def capture_screenshots():
    from playwright.async_api import async_playwright

    email_path = await render_email_preview()

    async with async_playwright() as p:
        browser = await p.chromium.launch()

        # ── 1. Full Dashboard (dark mode) ──
        print("📸 Capturing dashboard (dark mode)...")
        page = await browser.new_page(viewport={"width": 1440, "height": 900})
        await page.goto(f"file:///{DASHBOARD_FILE.as_posix()}")
        await page.wait_for_timeout(2000)  # Let charts render

        # Full page screenshot
        await page.screenshot(
            path=str(DOCS / "dashboard-dark-full.png"),
            full_page=True,
        )
        print("  ✅ dashboard-dark-full.png")

        # Hero area (top section with marquee + KPIs)
        await page.screenshot(
            path=str(DOCS / "dashboard-hero.png"),
            clip={"x": 0, "y": 0, "width": 1440, "height": 900},
        )
        print("  ✅ dashboard-hero.png")

        # ── 2. Dashboard (light mode) ──
        print("📸 Capturing dashboard (light mode)...")
        theme_btn = page.locator("#themeToggle")
        if await theme_btn.count() > 0:
            await theme_btn.click()
            await page.wait_for_timeout(1500)

        await page.screenshot(
            path=str(DOCS / "dashboard-light-full.png"),
            full_page=True,
        )
        print("  ✅ dashboard-light-full.png")

        await page.screenshot(
            path=str(DOCS / "dashboard-light-hero.png"),
            clip={"x": 0, "y": 0, "width": 1440, "height": 900},
        )
        print("  ✅ dashboard-light-hero.png")

        await page.close()

        # ── 3. Zoomed sections (dark mode) ──
        print("📸 Capturing individual sections...")
        page = await browser.new_page(viewport={"width": 1440, "height": 900})
        await page.goto(f"file:///{DASHBOARD_FILE.as_posix()}")
        await page.wait_for_timeout(2000)

        # Charts section
        charts = page.locator(".chart-section, .charts-grid, .chart-row").first
        if await charts.count() > 0:
            await charts.screenshot(path=str(DOCS / "dashboard-charts.png"))
            print("  ✅ dashboard-charts.png")

        # Holdings table
        tables = page.locator(".holdings-section, .table-section, table").first
        if await tables.count() > 0:
            await tables.screenshot(path=str(DOCS / "dashboard-holdings.png"))
            print("  ✅ dashboard-holdings.png")

        # Try to capture the marquee strip
        marquee = page.locator(".marquee-wrap, .marquee-container, .stock-marquee").first
        if await marquee.count() > 0:
            await marquee.screenshot(path=str(DOCS / "dashboard-marquee.png"))
            print("  ✅ dashboard-marquee.png")

        await page.close()

        # ── 4. Email Brief ──
        print("📸 Capturing email brief...")
        page = await browser.new_page(viewport={"width": 720, "height": 900})
        await page.goto(f"file:///{email_path.as_posix()}")
        await page.wait_for_timeout(1000)

        await page.screenshot(
            path=str(DOCS / "email-brief.png"),
            full_page=True,
        )
        print("  ✅ email-brief.png")

        await page.close()

        # ── 5. CLI output ──
        print("📸 Capturing CLI demo output...")
        page = await browser.new_page(viewport={"width": 800, "height": 500})
        # Create a styled terminal-like HTML
        cli_html = """
        <html><body style="margin:0;padding:24px;background:#0d1117;font-family:'Cascadia Code','Fira Code',monospace;font-size:14px;color:#e6edf3;">
        <div style="background:#161b22;border-radius:12px;padding:20px;border:1px solid #30363d;">
        <div style="margin-bottom:12px;">
            <span style="color:#f85149;">●</span>
            <span style="color:#d29922;">●</span>
            <span style="color:#3fb950;">●</span>
            <span style="color:#8b949e;margin-left:12px;font-size:12px;">PowerShell — WealthPulse</span>
        </div>
        <pre style="margin:0;line-height:1.6;color:#b1bac4;">
<span style="color:#8b949e;">PS C:\\WealthPulse&gt;</span> <span style="color:#79c0ff;">wealthpulse demo</span>

<span style="color:#d2a8ff;">╭──────────────────────────────────────╮</span>
<span style="color:#d2a8ff;">│</span> 💰 <span style="color:#79c0ff;font-weight:bold;">WealthPulse v1.0.0</span>                <span style="color:#d2a8ff;">│</span>
<span style="color:#d2a8ff;">│</span> Your Open-Source Portfolio Dashboard <span style="color:#d2a8ff;">│</span>
<span style="color:#d2a8ff;">╰──────────────────────────────────────╯</span>

<span style="color:#8b949e;">🎬 Running demo with sample data...</span>
<span style="color:#3fb950;">✅ Demo dashboard generated:</span>
   <span style="color:#58a6ff;">output/WealthPulse_DEMO.html</span>

<span style="color:#3fb950;">🌐 Opening in your browser...</span>
</pre>
        </div>
        </body></html>
        """
        await page.set_content(cli_html)
        await page.wait_for_timeout(500)
        await page.screenshot(path=str(DOCS / "cli-demo.png"))
        print("  ✅ cli-demo.png")

        await page.close()
        await browser.close()

    print(f"\n🎉 All screenshots saved to: {DOCS}")


if __name__ == "__main__":
    asyncio.run(capture_screenshots())
