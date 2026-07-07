import argparse
import json
import socket
import uuid
from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from playwright.async_api import async_playwright

from src.master import TaskWorker, WorkerConfig


class FetchRequest(BaseModel):
    url: str
    wait_seconds: float | None = Field(default=None, ge=0)
    include_html: bool = True
    include_links: bool = True


class SlaverRuntime:
    def __init__(
        self,
        worker_id: str,
        env_name: str | None = None,
        proxy: dict[str, str] | None = None,
        headful: bool = False,
        browser_channel: str | None = None,
        challenge_wait: float = 0,
        launch_args: list[str] | None = None,
        user_agent: str | None = None,
        locale: str = "pl-PL",
        timezone_id: str | None = None,
        viewport_width: int = 1365,
        viewport_height: int = 768,
        block_images: bool = False,
        block_media: bool = False,
        cookies: list[dict[str, Any]] | None = None,
    ) -> None:
        self.worker_id = worker_id
        self.env_name = env_name
        self.proxy = proxy
        self.headful = headful
        self.browser_channel = browser_channel
        self.challenge_wait = challenge_wait
        self.launch_args = launch_args or []
        self.user_agent = user_agent
        self.locale = locale
        self.timezone_id = timezone_id
        self.viewport_width = viewport_width
        self.viewport_height = viewport_height
        self.block_images = block_images
        self.block_media = block_media
        self.cookies = cookies or []
        self.playwright_manager = None
        self.playwright = None
        self.worker: TaskWorker | None = None

    async def start(self) -> None:
        if self.worker:
            return

        self.playwright_manager = async_playwright()
        self.playwright = await self.playwright_manager.start()
        config = WorkerConfig(
            worker_id=self.worker_id,
            proxy=self.proxy,
            env_name=self.env_name,
            headful=self.headful,
            browser_channel=self.browser_channel,
            challenge_wait=self.challenge_wait,
            launch_args=self.launch_args,
            user_agent=self.user_agent,
            locale=self.locale,
            timezone_id=self.timezone_id,
            viewport_width=self.viewport_width,
            viewport_height=self.viewport_height,
            block_images=self.block_images,
            block_media=self.block_media,
            cookies=self.cookies,
        )
        self.worker = TaskWorker(self.playwright, config)
        await self.worker.start()

    async def stop(self) -> None:
        if self.worker:
            await self.worker.stop()
            self.worker = None
        if self.playwright_manager:
            await self.playwright_manager.stop()
            self.playwright_manager = None
            self.playwright = None

    async def fetch(self, request: FetchRequest) -> dict[str, Any]:
        if not self.worker:
            await self.start()
        if not self.worker:
            raise RuntimeError("slaver worker is not running")

        result = await self.worker.fetch(
            url=request.url,
            wait_seconds=request.wait_seconds,
            include_html=request.include_html,
            include_links=request.include_links,
        )
        result["slaver"] = self.status()
        return result

    def status(self) -> dict[str, Any]:
        if not self.worker:
            return {
                "worker_id": self.worker_id,
                "env_name": self.env_name,
                "running": False,
                "headful": self.headful,
                "browser_channel": self.browser_channel,
                "challenge_wait": self.challenge_wait,
                "config": self.config_public(),
                "stats": {},
            }
        return self.worker.info()

    def config_public(self) -> dict[str, Any]:
        return {
            "env_name": self.env_name,
            "proxy": self.proxy["server"] if self.proxy else "direct",
            "headful": self.headful,
            "browser_channel": self.browser_channel,
            "challenge_wait": self.challenge_wait,
            "launch_args": self.launch_args,
            "user_agent": self.user_agent,
            "locale": self.locale,
            "timezone_id": self.timezone_id,
            "viewport_width": self.viewport_width,
            "viewport_height": self.viewport_height,
            "block_images": self.block_images,
            "block_media": self.block_media,
            "cookies_count": len(self.cookies),
        }


def create_app(runtime: SlaverRuntime) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await app.state.runtime.start()
        try:
            yield
        finally:
            await app.state.runtime.stop()

    app = FastAPI(title="Playwright Slaver Task", version="1.0.0", lifespan=lifespan)
    app.state.runtime = runtime

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {"ok": True, **app.state.runtime.status()}

    @app.get("/status")
    async def status() -> dict[str, Any]:
        return app.state.runtime.status()

    @app.post("/fetch")
    async def fetch(request: FetchRequest) -> dict[str, Any]:
        try:
            return await app.state.runtime.fetch(request)
        except Exception as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    return app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one Playwright slaver task.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8101)
    parser.add_argument("--worker-id")
    parser.add_argument("--headful", action="store_true", help="show browser window")
    parser.add_argument("--browser-channel", choices=("chrome", "msedge"))
    parser.add_argument("--challenge-wait", type=float, default=0)
    parser.add_argument("--config-json", help="full slaver environment config as JSON")
    return parser.parse_args()


def default_worker_id(port: int) -> str:
    host = socket.gethostname().replace(" ", "-")
    return f"{host}-{port}-{uuid.uuid4().hex[:6]}"


def main() -> None:
    args = parse_args()
    config = json.loads(args.config_json) if args.config_json else {}
    runtime = SlaverRuntime(
        worker_id=config.get("worker_id") or args.worker_id or default_worker_id(args.port),
        env_name=config.get("env_name"),
        proxy=config.get("proxy"),
        headful=config.get("headful", args.headful),
        browser_channel=config.get("browser_channel", args.browser_channel),
        challenge_wait=config.get("challenge_wait", args.challenge_wait),
        launch_args=config.get("launch_args") or [],
        user_agent=config.get("user_agent"),
        locale=config.get("locale") or "pl-PL",
        timezone_id=config.get("timezone_id"),
        viewport_width=config.get("viewport_width") or 1365,
        viewport_height=config.get("viewport_height") or 768,
        block_images=bool(config.get("block_images")),
        block_media=bool(config.get("block_media")),
        cookies=config.get("cookies") or [],
    )
    app = create_app(runtime)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
