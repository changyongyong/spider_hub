from urllib.parse import urlparse, urlunparse

from playwright.async_api import TimeoutError as AsyncPlaywrightTimeoutError


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)


def normalize_text(text: str) -> str:
    return " ".join(text.split())


def normalize_url(url: str) -> str:
    parsed = urlparse(url)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))


async def accept_cookies(page) -> None:
    for label in ("Accept all", "Accept", "Agree", "I agree"):
        button = page.get_by_role("button", name=label)
        if await button.count():
            try:
                await button.first.click(timeout=5_000)
            except AsyncPlaywrightTimeoutError:
                pass
            return


async def wait_for_page(page) -> None:
    try:
        await page.wait_for_load_state("networkidle", timeout=30_000)
    except AsyncPlaywrightTimeoutError:
        pass


async def collect_links(page) -> list[dict[str, str]]:
    links = await page.locator("a[href]").evaluate_all(
        """
        anchors => anchors.map(anchor => ({
            name: (anchor.textContent || '').replace(/\\s+/g, ' ').trim(),
            url: anchor.href
        }))
        """
    )

    result = []
    for link in links:
        name = normalize_text(link["name"])
        url = link["url"]
        if name:
            result.append({"name": name, "url": normalize_url(url)})
    return result


async def body_text(page) -> str:
    try:
        return await page.locator("body").inner_text(timeout=10_000)
    except AsyncPlaywrightTimeoutError:
        return ""
