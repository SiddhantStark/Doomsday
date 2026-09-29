"""Normal ephemeral Chromium transport; no evasion or authenticated profiles."""

from playwright.sync_api import Error, TimeoutError, sync_playwright

from .bookmyshow import CheckError, PageSnapshot, page_root


def fetch_page(url: str, timeout_ms: int = 20000) -> PageSnapshot:
    try:
        with sync_playwright() as engine:
            browser = engine.chromium.launch()
            try:
                page = browser.new_page(locale="en-IN", timezone_id="Asia/Kolkata")
                response = page.goto(
                    url, wait_until="domcontentloaded", timeout=timeout_ms
                )
                if response is None:
                    raise CheckError("NO_HTTP_RESPONSE")
                if response.status >= 400:
                    return PageSnapshot(page.url, "", response.status)
                page_root(PageSnapshot(page.url, page.content(), response.status))
                page.locator("#main-content").wait_for(timeout=timeout_ms)
                # Wait for rendered movie/schedule evidence, not a fixed sleep.
                page.locator('h1, [role="grid"]').first.wait_for(timeout=timeout_ms)
                return PageSnapshot(page.url, page.content(), response.status)
            finally:
                browser.close()
    except TimeoutError as error:
        raise CheckError("BROWSER_TIMEOUT") from error
    except Error as error:
        raise CheckError("BROWSER_UNAVAILABLE_OR_NETWORK_ERROR") from error
