import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from src.page_extractors import (
    USER_AGENT,
    accept_cookies,
    body_text,
    collect_links,
    wait_for_page,
)
from src.proxy_utils import proxy_label


@dataclass
class WorkerConfig:
    worker_id: str
    proxy: dict[str, str] | None
    env_name: str | None = None
    headful: bool = False
    browser_channel: str | None = None
    challenge_wait: float = 0
    launch_args: list[str] = field(default_factory=list)
    user_agent: str | None = None
    locale: str = "pl-PL"
    timezone_id: str | None = None
    viewport_width: int = 1365
    viewport_height: int = 768
    block_images: bool = False
    block_media: bool = False
    cookies: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class WorkerStats:
    started_at: str
    requests: int = 0
    failures: int = 0
    last_url: str | None = None
    last_error: str | None = None
    busy: bool = False


class TaskWorker:
    def __init__(self, playwright, config: WorkerConfig) -> None:
        self.playwright = playwright
        self.config = config
        self.browser = None
        self.lock = asyncio.Lock()
        self.stats = WorkerStats(started_at=datetime.now(timezone.utc).isoformat())

    async def start(self) -> None:
        if self.browser:
            return

        self.browser = await self.playwright.chromium.launch(
            channel=self.config.browser_channel,
            headless=not self.config.headful,
            args=["--disable-blink-features=AutomationControlled", *self.config.launch_args],
            proxy=self.config.proxy,
        )

    async def stop(self) -> None:
        if self.browser:
            await self.browser.close()
            self.browser = None

    async def fetch(
        self,
        url: str,
        wait_seconds: float | None = None,
        include_html: bool = False,
        include_links: bool = True,
    ) -> dict[str, Any]:
        async with self.lock:
            if not self.browser:
                await self.start()

            self.stats.busy = True
            self.stats.last_url = url
            started = time.monotonic()

            context = await self.browser.new_context(
                locale=self.config.locale,
                timezone_id=self.config.timezone_id,
                user_agent=self.config.user_agent or USER_AGENT,
                viewport={
                    "width": self.config.viewport_width,
                    "height": self.config.viewport_height,
                },
            )
            try:
                if self.config.cookies:
                    await context.add_cookies(self.config.cookies)
                if self.config.block_images or self.config.block_media:
                    await context.route("**/*", self._route_resource)

                page = await context.new_page()
                await page.add_init_script(
                    "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
                )

                response = await page.goto(url, wait_until="commit", timeout=60_000)
                status = response.status if response else None
                await accept_cookies(page)
                await wait_for_page(page)

                wait_after_load = self.config.challenge_wait if wait_seconds is None else wait_seconds
                if wait_after_load:
                    await asyncio.sleep(wait_after_load)

                text = await body_text(page)
                result: dict[str, Any] = {
                    "ok": True,
                    "worker_id": self.config.worker_id,
                    "proxy": proxy_label(self.config.proxy),
                    "url": url,
                    "final_url": page.url,
                    "status": status,
                    "title": await page.title(),
                    "body_text": text,
                    "body_preview": " ".join(text.split())[:500],
                    "elapsed_seconds": round(time.monotonic() - started, 3),
                }

                if include_links:
                    result["links"] = await collect_links(page)
                if include_html:
                    result["html"] = await page.content()

                self.stats.requests += 1
                self.stats.last_error = None
                return result
            except Exception as error:
                self.stats.failures += 1
                self.stats.last_error = str(error)
                raise
            finally:
                self.stats.busy = False
                await context.close()

    async def _route_resource(self, route) -> None:
        resource_type = route.request.resource_type
        if self.config.block_images and resource_type == "image":
            await route.abort()
            return
        if self.config.block_media and resource_type == "media":
            await route.abort()
            return
        await route.continue_()

    def info(self) -> dict[str, Any]:
        return {
            "worker_id": self.config.worker_id,
            "kind": "local",
            "env_name": self.config.env_name,
            "proxy": proxy_label(self.config.proxy),
            "headful": self.config.headful,
            "browser_channel": self.config.browser_channel,
            "challenge_wait": self.config.challenge_wait,
            "config": self.config_public(),
            "running": self.browser is not None,
            "stats": self.stats.__dict__,
        }

    def config_public(self) -> dict[str, Any]:
        return {
            "env_name": self.config.env_name,
            "proxy": proxy_public(self.config.proxy),
            "headful": self.config.headful,
            "browser_channel": self.config.browser_channel,
            "challenge_wait": self.config.challenge_wait,
            "launch_args": self.config.launch_args,
            "user_agent": self.config.user_agent or USER_AGENT,
            "locale": self.config.locale,
            "timezone_id": self.config.timezone_id,
            "viewport_width": self.config.viewport_width,
            "viewport_height": self.config.viewport_height,
            "block_images": self.config.block_images,
            "block_media": self.config.block_media,
            "cookies_count": len(self.config.cookies),
        }


def proxy_public(proxy: dict[str, str] | None) -> dict[str, Any]:
    if not proxy:
        return {"enabled": False}

    result: dict[str, Any] = {
        "enabled": True,
        "server": proxy.get("server", ""),
        "username": proxy.get("username", ""),
        "password_set": bool(proxy.get("password")),
    }
    scheme, host, port = parse_proxy_server(result["server"])
    result.update({"scheme": scheme, "host": host, "port": port})
    return result


def parse_proxy_server(server: str) -> tuple[str, str, int | None]:
    if "://" not in server:
        return "http", "", None

    scheme, rest = server.split("://", 1)
    if ":" not in rest:
        return scheme, rest, None

    host, port_text = rest.rsplit(":", 1)
    try:
        return scheme, host, int(port_text)
    except ValueError:
        return scheme, host, None
