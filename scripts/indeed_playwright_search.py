from __future__ import annotations

import argparse
import asyncio
import json
from urllib.parse import quote_plus, urlencode

from playwright.async_api import async_playwright

BASE_URL = "https://www.indeed.com"


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run an Indeed search via Playwright.")
    parser.add_argument("--query", default="devops", help="Search query, e.g. devops/frontend")
    parser.add_argument("--location", default="", help="Location, e.g. New York, NY")
    parser.add_argument("--max-results", type=int, default=10, help="Max listing rows to extract")
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run headless (by default runs headed to reduce challenge probability)",
    )
    return parser


def _looks_like_challenge(content: str) -> bool:
    lowered = content.lower()
    if "jcs-jobtitle" in lowered or 'aria-label="next page"' in lowered:
        return False
    return (
        "<title>just a moment..." in lowered
        or "checking your browser before accessing" in lowered
        or "cdn-cgi/challenge-platform" in lowered
    )


async def _run_search(query: str, location: str, max_results: int, headless: bool) -> dict:
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
            ],
        )
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36"
            ),
            locale="en-US",
            viewport={"width": 1366, "height": 900},
        )
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )
        page = await context.new_page()

        await page.goto(f"{BASE_URL}/", wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(1000)

        what_input = page.locator('input[name="q"]').first
        await what_input.click()
        await what_input.fill(query)

        where_input = page.locator('input[name="l"]').first
        if await where_input.count() > 0:
            await where_input.click()
            await where_input.fill(location)

        await what_input.press("Enter")
        await page.wait_for_timeout(1500)

        if "/jobs" not in page.url:
            try:
                await page.locator('button:has-text("Search")').first.click()
                await page.wait_for_timeout(1500)
            except Exception:
                pass

        if "/jobs" not in page.url:
            params = {"q": query, "l": location}
            await page.goto(
                f"{BASE_URL}/jobs?{urlencode(params)}",
                wait_until="domcontentloaded",
                timeout=60000,
            )

        try:
            await page.wait_for_selector(
                'a.jcs-JobTitle, a[aria-label="Next Page"], [id^="job_"], [id^="sj_"]',
                timeout=12000,
            )
        except Exception:
            await page.wait_for_timeout(2500)

        content = await page.content()
        title = await page.title()
        current_url = page.url

        listings = []
        cards = page.locator("a.jcs-JobTitle")
        card_count = min(await cards.count(), max_results)
        for idx in range(card_count):
            anchor = cards.nth(idx)
            job_title = (await anchor.inner_text()).strip()
            href = await anchor.get_attribute("href")
            listings.append(
                {
                    "title": job_title,
                    "url": f"{BASE_URL}{href}" if href and href.startswith("/") else href,
                }
            )

        await context.close()
        await browser.close()

    return {
        "query": query,
        "location": location,
        "requested_url": f"{BASE_URL}/jobs?q={quote_plus(query)}&l={quote_plus(location)}",
        "final_url": current_url,
        "page_title": title,
        "challenge_detected": _looks_like_challenge(content),
        "listings_found": len(listings),
        "listings": listings,
    }


async def _main() -> None:
    args = _build_arg_parser().parse_args()
    data = await _run_search(
        query=args.query,
        location=args.location,
        max_results=args.max_results,
        headless=args.headless,
    )
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(_main())
