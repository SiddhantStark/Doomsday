"""Read-only headed Chromium access diagnostic; no credentials or state access."""

import json
from pathlib import Path

from playwright.sync_api import sync_playwright

from .bookmyshow import BookMyShowProvider, PageSnapshot
from .config import load_config
from .district import DistrictProvider
from .time_utils import now_ist


def main() -> int:
    config = load_config(Path("config/monitor.yml"))
    pages = []
    with sync_playwright() as engine:
        browser = engine.chromium.launch(headless=False)
        try:

            def fetch(url: str) -> PageSnapshot:
                context = browser.new_context(
                    locale="en-IN", timezone_id="Asia/Kolkata"
                )
                try:
                    page = context.new_page()
                    response = page.goto(
                        url, wait_until="domcontentloaded", timeout=25000
                    )
                    status = response.status if response else 0
                    if status == 200:
                        page.locator(
                            'h1, [role="grid"], script#__NEXT_DATA__'
                        ).first.wait_for(state="attached", timeout=15000)
                    html = page.content()
                    pages.append(
                        {
                            "url": url,
                            "final_url": page.url,
                            "http_status": status,
                            "heading_present": page.locator("h1").count() > 0,
                            "book_controls": page.locator(
                                '[aria-label^="Book "]'
                            ).count(),
                            "district_data_present": page.locator(
                                "script#__NEXT_DATA__"
                            ).count()
                            > 0,
                        }
                    )
                    return PageSnapshot(page.url, html, status)
                finally:
                    context.close()

            settings = config.bookmyshow
            providers = [
                BookMyShowProvider(
                    settings.movie_url,
                    settings.cinema_url,
                    settings.movie_id,
                    settings.venue_id,
                    fetch,
                ),
                DistrictProvider(config.district, fetch),
            ]
            results = [p.check_availability(config.target) for p in providers]
            # Independently test current cinema pages even if the movie request failed.
            for url in [
                settings.cinema_url + f"/{now_ist():%Y%m%d}",
                config.district.cinema_url + f"?fromdate={now_ist():%Y-%m-%d}",
            ]:
                try:
                    fetch(url)
                except Exception:
                    pages.append({"url": url, "error": "BROWSER_OR_RENDER_FAILURE"})
            print(
                json.dumps(
                    {
                        "mode": "headed_cloud_diagnostic",
                        "browser_version": browser.version,
                        "pages": pages,
                        "results": [r.model_dump(mode="json") for r in results],
                        "messages_sent": 0,
                        "production_state_changed": False,
                    },
                    indent=2,
                )
            )
            return 1 if any(r.error for r in results) else 0
        finally:
            browser.close()


if __name__ == "__main__":
    raise SystemExit(main())
