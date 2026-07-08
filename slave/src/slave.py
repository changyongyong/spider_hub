import argparse
import asyncio
import json
import os
import socket
import uuid
from contextlib import asynccontextmanager, suppress
from typing import Any

import uvicorn
import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from playwright.async_api import async_playwright

from src.browser_worker import TaskWorker, WorkerConfig


class FetchRequest(BaseModel):
    url: str
    wait_seconds: float | None = Field(default=None, ge=0)
    include_html: bool = True
    include_links: bool = True


class BrowserEnvironmentRequest(BaseModel):
    worker_id: str | None = None
    env_name: str | None = None
    proxy: dict[str, str] | None = None
    headful: bool = False
    browser_channel: str | None = None
    challenge_wait: float = Field(default=0, ge=0)
    launch_args: list[str] = Field(default_factory=list)
    user_agent: str | None = None
    locale: str = "pl-PL"
    timezone_id: str | None = None
    viewport_width: int = Field(default=1365, ge=320)
    viewport_height: int = Field(default=768, ge=240)
    block_images: bool = False
    block_media: bool = False
    cookies: list[dict[str, Any]] = Field(default_factory=list)


class SlaveRuntime:
    def __init__(
        self,
        node_id: str,
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
        master_url: str | None = None,
        master_token: str | None = None,
        public_url: str | None = None,
        port: int = 8101,
        max_environments: int = 4,
        create_initial_worker: bool = False,
    ) -> None:
        self.node_id = node_id
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
        self.master_url = master_url.rstrip("/") if master_url else None
        self.master_token = master_token
        self.public_url = public_url.rstrip("/") if public_url else None
        self.port = port
        self.max_environments = max_environments
        self.create_initial_worker = create_initial_worker
        self.playwright_manager = None
        self.playwright = None
        self.workers: dict[str, TaskWorker] = {}

    async def start(self) -> None:
        if self.playwright:
            return

        self.playwright_manager = async_playwright()
        self.playwright = await self.playwright_manager.start()
        if self.create_initial_worker:
            await self.create_environment(
                BrowserEnvironmentRequest(
                    worker_id=self.node_id,
                    env_name=self.env_name,
                    proxy=self.proxy,
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
            )

    async def create_environment(self, request: BrowserEnvironmentRequest) -> dict[str, Any]:
        if len(self.workers) >= self.max_environments:
            raise RuntimeError("slave node capacity reached")
        if not self.playwright:
            await self.start()
        if not self.playwright:
            raise RuntimeError("playwright is not running")

        worker_id = request.worker_id or f"env-{uuid.uuid4().hex[:8]}"
        worker = await self.start_worker(worker_id, request)
        self.workers[worker_id] = worker
        return worker.info()

    async def update_environment(self, worker_id: str, request: BrowserEnvironmentRequest) -> dict[str, Any]:
        old_worker = self.workers[worker_id]
        if not self.playwright:
            await self.start()
        if not self.playwright:
            raise RuntimeError("playwright is not running")

        request.worker_id = worker_id
        preserve_existing_config(old_worker, request)
        new_worker = await self.start_worker(worker_id, request)
        await old_worker.stop()
        self.workers[worker_id] = new_worker
        return new_worker.info()

    async def start_worker(self, worker_id: str, request: BrowserEnvironmentRequest) -> TaskWorker:
        config = WorkerConfig(
            worker_id=worker_id,
            proxy=request.proxy,
            env_name=request.env_name,
            headful=request.headful,
            browser_channel=request.browser_channel,
            challenge_wait=request.challenge_wait,
            launch_args=request.launch_args,
            user_agent=request.user_agent,
            locale=request.locale,
            timezone_id=request.timezone_id,
            viewport_width=request.viewport_width,
            viewport_height=request.viewport_height,
            block_images=request.block_images,
            block_media=request.block_media,
            cookies=request.cookies,
        )
        worker = TaskWorker(self.playwright, config)
        await worker.start()
        return worker

    async def stop(self) -> None:
        for worker in list(self.workers.values()):
            await worker.stop()
        self.workers.clear()
        if self.playwright_manager:
            await self.playwright_manager.stop()
            self.playwright_manager = None
            self.playwright = None

    async def stop_environment(self, worker_id: str) -> dict[str, Any]:
        worker = self.workers.pop(worker_id)
        await worker.stop()
        return {"worker_id": worker_id, "stopped": True}

    async def fetch(self, request: FetchRequest, worker_id: str | None = None) -> dict[str, Any]:
        if worker_id:
            worker = self.workers[worker_id]
        else:
            if not self.workers:
                raise RuntimeError("no browser environments on this slave node")
            worker = next(iter(self.workers.values()))

        result = await worker.fetch(
            url=request.url,
            wait_seconds=request.wait_seconds,
            include_html=request.include_html,
            include_links=request.include_links,
        )
        result["slave"] = self.status()
        return result

    def status(self) -> dict[str, Any]:
        workers = [worker.info() for worker in self.workers.values()]
        return {
            "node_id": self.node_id,
            "running": self.playwright is not None,
            "max_environments": self.max_environments,
            "max_workers": self.max_environments,
            "worker_count": len(self.workers),
            "available_slots": max(0, self.max_environments - len(self.workers)),
            "workers": workers,
        }

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

    async def register_with_master(self) -> None:
        if not self.master_url:
            return

        payload = {
            "port": self.port,
            "worker_id": self.node_id,
            "base_url": self.public_url,
        }
        headers = {"X-Internal-Token": self.master_token} if self.master_token else None
        while True:
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    response = await client.post(
                        f"{self.master_url}/slaves/register-self",
                        json=payload,
                        headers=headers,
                    )
                    response.raise_for_status()
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                raise
            except Exception:
                await asyncio.sleep(5)


def preserve_existing_config(old_worker: TaskWorker, request: BrowserEnvironmentRequest) -> None:
    old_config = old_worker.config
    if not request.cookies and old_config.cookies:
        request.cookies = old_config.cookies

    if request.proxy and old_config.proxy:
        old_server = old_config.proxy.get("server")
        if request.proxy.get("server") == old_server:
            if "username" not in request.proxy and old_config.proxy.get("username"):
                request.proxy["username"] = old_config.proxy["username"]
            if "password" not in request.proxy and old_config.proxy.get("password"):
                request.proxy["password"] = old_config.proxy["password"]


def create_app(runtime: SlaveRuntime) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await app.state.runtime.start()
        register_task = asyncio.create_task(app.state.runtime.register_with_master())
        try:
            yield
        finally:
            register_task.cancel()
            with suppress(asyncio.CancelledError):
                await register_task
            await app.state.runtime.stop()

    app = FastAPI(title="Playwright Slave Task", version="1.0.0", lifespan=lifespan)
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

    @app.get("/environments")
    async def list_environments() -> list[dict[str, Any]]:
        return [worker.info() for worker in app.state.runtime.workers.values()]

    @app.post("/environments")
    async def create_environment(request: BrowserEnvironmentRequest) -> dict[str, Any]:
        try:
            return await app.state.runtime.create_environment(request)
        except Exception as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.patch("/environments/{worker_id}")
    async def update_environment(worker_id: str, request: BrowserEnvironmentRequest) -> dict[str, Any]:
        try:
            return await app.state.runtime.update_environment(worker_id, request)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="environment not found") from error
        except Exception as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.post("/environments/{worker_id}/fetch")
    async def fetch_environment(worker_id: str, request: FetchRequest) -> dict[str, Any]:
        try:
            return await app.state.runtime.fetch(request, worker_id=worker_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="environment not found") from error
        except Exception as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.delete("/environments/{worker_id}")
    async def delete_environment(worker_id: str) -> dict[str, Any]:
        try:
            return await app.state.runtime.stop_environment(worker_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="environment not found") from error

    return app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one Playwright slave task.")
    parser.add_argument("--host", default=os.getenv("SPIDER_SLAVE_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("SPIDER_SLAVE_PORT", "8101")))
    parser.add_argument("--worker-id", default=os.getenv("SPIDER_SLAVE_WORKER_ID"))
    parser.add_argument("--headful", action="store_true", default=env_bool("SPIDER_SLAVE_HEADFUL"), help="show browser window")
    parser.add_argument("--browser-channel", default=os.getenv("SPIDER_SLAVE_BROWSER_CHANNEL"))
    parser.add_argument("--challenge-wait", type=float, default=float(os.getenv("SPIDER_SLAVE_CHALLENGE_WAIT", "0")))
    parser.add_argument("--env-name", default=os.getenv("SPIDER_SLAVE_ENV_NAME"))
    parser.add_argument("--master-url", default=os.getenv("SPIDER_SLAVE_MASTER_URL"))
    parser.add_argument("--master-token", default=os.getenv("SPIDER_SLAVE_MASTER_TOKEN"))
    parser.add_argument("--public-url", default=os.getenv("SPIDER_SLAVE_PUBLIC_URL"))
    parser.add_argument("--max-environments", type=int, default=env_int("SPIDER_SLAVE_MAX_ENVIRONMENTS"), help="max Playwright browser environments on this slave node")
    parser.add_argument("--max-workers", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--create-initial-worker", action="store_true")
    parser.add_argument("--config-json", help="full slave environment config as JSON")
    return parser.parse_args()


def default_worker_id(port: int) -> str:
    host = socket.gethostname().replace(" ", "-")
    return f"{host}-{port}-{uuid.uuid4().hex[:6]}"


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def env_int(name: str) -> int | None:
    value = os.getenv(name)
    return int(value) if value else None


def main() -> None:
    args = parse_args()
    config = json.loads(args.config_json) if args.config_json else {}
    runtime = SlaveRuntime(
        node_id=config.get("node_id") or args.worker_id or default_worker_id(args.port),
        env_name=config.get("env_name") or args.env_name,
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
        master_url=config.get("master_url") or args.master_url,
        master_token=config.get("master_token") or args.master_token or os.getenv("SPIDER_INTERNAL_API_TOKEN"),
        public_url=config.get("public_url") or args.public_url,
        port=args.port,
        max_environments=(
            config.get("max_environments")
            or config.get("max_workers")
            or args.max_environments
            or args.max_workers
            or 4
        ),
        create_initial_worker=bool(config.get("create_initial_worker", args.create_initial_worker)),
    )
    app = create_app(runtime)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
