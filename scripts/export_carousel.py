"""Export LinkedIn carousel slides as individual PNGs."""
import asyncio
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CAROUSEL_HTML = ROOT / "scripts" / "linkedin_carousel.html"
OUT = ROOT / "output" / "linkedin_carousel"
OUT.mkdir(parents=True, exist_ok=True)


async def main():
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1080, "height": 8000})
        await page.goto(f"file:///{CAROUSEL_HTML.as_posix()}")
        await page.wait_for_timeout(2000)

        for i in range(1, 7):
            el = page.locator(f"#slide{i}")
            await el.screenshot(path=str(OUT / f"slide_{i}.png"))
            print(f"  ✅ slide_{i}.png")

        await browser.close()

    print(f"\n🎉 Carousel exported to: {OUT}")
    print("Upload these 6 images to LinkedIn as a document/carousel post.")


if __name__ == "__main__":
    asyncio.run(main())
