"""Recapture light mode hero screenshot matching the user's browser view."""
import asyncio
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DASHBOARD = ROOT / "output" / "WealthPulse_DEMO.html"
OUT = ROOT / "docs" / "screenshots" / "dashboard-light-hero.png"


async def main():
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1440, "height": 900})
        await page.goto(f"file:///{DASHBOARD.as_posix()}")
        await page.wait_for_timeout(2500)

        # Switch to light mode
        btn = page.locator("#themeToggle")
        if await btn.count() > 0:
            await btn.click()
            await page.wait_for_timeout(1500)

        # Capture exactly the visible viewport — header through pie charts
        await page.screenshot(
            path=str(OUT),
            clip={"x": 0, "y": 0, "width": 1440, "height": 900},
        )
        print(f"✅ {OUT.name} — recaptured (1440×900)")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
