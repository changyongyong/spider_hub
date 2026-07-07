import asyncio
import json
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
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


@dataclass
class ManagedProcess:
    process: subprocess.Popen
    port: int


@dataclass
class JobState:
    job_id: str
    status: str
    url: str
    worker_id: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    result: dict[str, Any] | None = None
    error: str | None = None

    def mark_running(self, worker_id: str) -> None:
        self.status = "running"
        self.worker_id = worker_id
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def mark_done(self, result: dict[str, Any]) -> None:
        self.status = "done"
        self.result = result
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def mark_failed(self, error: Exception) -> None:
        self.status = "failed"
        self.error = str(error)
        self.updated_at = datetime.now(timezone.utc).isoformat()


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
            "proxy": proxy_label(self.config.proxy),
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


class RemoteSlaverWorker:
    def __init__(
        self,
        worker_id: str,
        base_url: str,
        managed: ManagedProcess | None = None,
    ) -> None:
        self.worker_id = worker_id
        self.base_url = base_url.rstrip("/")
        self.managed = managed
        self.registered_at = datetime.now(timezone.utc).isoformat()
        self.last_seen: str | None = None
        self.last_error: str | None = None
        self.status: dict[str, Any] = {}

    async def refresh(self) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"{self.base_url}/status")
            response.raise_for_status()
            self.status = response.json()
        self.last_seen = datetime.now(timezone.utc).isoformat()
        self.last_error = None
        return self.status

    async def fetch(
        self,
        url: str,
        wait_seconds: float | None = None,
        include_html: bool = False,
        include_links: bool = True,
    ) -> dict[str, Any]:
        payload = {
            "url": url,
            "wait_seconds": wait_seconds,
            "include_html": include_html,
            "include_links": include_links,
        }
        async with httpx.AsyncClient(timeout=None) as client:
            response = await client.post(f"{self.base_url}/fetch", json=payload)
            response.raise_for_status()
            result = response.json()

        self.last_seen = datetime.now(timezone.utc).isoformat()
        self.last_error = None
        self.status = result.get("slaver", self.status)
        return result

    async def stop(self) -> None:
        if self.managed:
            self.managed.process.terminate()
            try:
                self.managed.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.managed.process.kill()
            self.managed = None

    def info(self) -> dict[str, Any]:
        process_status = None
        if self.managed:
            process_status = self.managed.process.poll()

        return {
            "worker_id": self.worker_id,
            "kind": "remote",
            "env_name": self.status.get("env_name") or self.status.get("config", {}).get("env_name"),
            "base_url": self.base_url,
            "registered_at": self.registered_at,
            "last_seen": self.last_seen,
            "last_error": self.last_error,
            "managed": self.managed is not None,
            "process_status": process_status,
            "running": process_status is None if self.managed else True,
            "stats": self.status.get("stats", {}),
            "config": self.status.get("config", {}),
            "slaver": self.status,
        }


class Master:
    def __init__(
        self,
        strategy: str = "round_robin",
        headful: bool = False,
        browser_channel: str | None = None,
        challenge_wait: float = 0,
        env_config: dict[str, Any] | None = None,
    ) -> None:
        self.strategy = strategy
        self.headful = headful
        self.browser_channel = browser_channel
        self.challenge_wait = challenge_wait
        self.env_config = env_config or {}
        self.workers: dict[str, TaskWorker | RemoteSlaverWorker] = {}
        self.jobs: dict[str, JobState] = {}
        self.worker_index = 0

    async def start(self) -> None:
        return

    async def stop(self) -> None:
        for worker in list(self.workers.values()):
            await worker.stop()
        self.workers.clear()

    async def stop_worker(self, worker_id: str) -> dict[str, Any]:
        worker = self.workers.pop(worker_id)
        await worker.stop()
        return {"worker_id": worker_id, "stopped": True}

    async def stop_all_workers(self) -> dict[str, Any]:
        count = len(self.workers)
        for worker in list(self.workers.values()):
            await worker.stop()
        self.workers.clear()
        return {"stopped": count}

    def list_workers(self) -> list[dict[str, Any]]:
        return [worker.info() for worker in self.workers.values()]

    def choose_worker(
        self,
        worker_id: str | None = None,
        strategy: str | None = None,
    ) -> TaskWorker | RemoteSlaverWorker:
        if worker_id:
            return self.workers[worker_id]
        if not self.workers:
            raise RuntimeError("no running workers")

        workers = list(self.workers.values())
        selected_strategy = strategy or self.strategy
        if selected_strategy == "random":
            return workers[uuid.uuid4().int % len(workers)]
        if selected_strategy == "sticky":
            return workers[0]

        worker = workers[self.worker_index % len(workers)]
        self.worker_index += 1
        return worker

    async def register_slaver(
        self,
        base_url: str,
        worker_id: str | None = None,
        managed: ManagedProcess | None = None,
    ) -> dict[str, Any]:
        worker = RemoteSlaverWorker(
            worker_id=worker_id or f"slaver-{uuid.uuid4().hex[:8]}",
            base_url=base_url,
            managed=managed,
        )
        try:
            status = await worker.refresh()
            if worker_id is None:
                worker.worker_id = status.get("worker_id") or worker.worker_id
        except Exception as error:
            worker.last_error = str(error)

        self.workers[worker.worker_id] = worker
        return worker.info()

    async def update_slaver(
        self,
        worker_id: str,
        base_url: str | None = None,
    ) -> dict[str, Any]:
        worker = self.workers[worker_id]
        if not isinstance(worker, RemoteSlaverWorker):
            raise TypeError("worker is not a remote slaver")
        if base_url:
            worker.base_url = base_url.rstrip("/")
        try:
            await worker.refresh()
        except Exception as error:
            worker.last_error = str(error)
        return worker.info()

    async def start_managed_slaver(
        self,
        host: str = "127.0.0.1",
        port: int | None = None,
        headful: bool | None = None,
        browser_channel: str | None = None,
        challenge_wait: float | None = None,
        env_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        selected_port = port or self._next_slaver_port()
        worker_id = f"slaver-{selected_port}"
        merged_config = {
            **self.env_config,
            **(env_config or {}),
            "worker_id": worker_id,
            "headful": self.headful if headful is None else headful,
            "browser_channel": browser_channel if browser_channel is not None else self.browser_channel,
            "challenge_wait": self.challenge_wait if challenge_wait is None else challenge_wait,
        }
        command = [
            sys.executable,
            "-m",
            "src.slaver",
            "--host",
            host,
            "--port",
            str(selected_port),
            "--config-json",
            json.dumps(merged_config),
        ]

        process = subprocess.Popen(command, cwd=Path(__file__).resolve().parents[1])
        managed = ManagedProcess(process=process, port=selected_port)
        base_url = f"http://{host}:{selected_port}"

        for _ in range(30):
            info = await self.register_slaver(base_url=base_url, worker_id=worker_id, managed=managed)
            if not info.get("last_error"):
                return info
            await asyncio.sleep(0.5)

        return self.workers[worker_id].info()

    def _next_slaver_port(self) -> int:
        used = {
            worker.managed.port
            for worker in self.workers.values()
            if isinstance(worker, RemoteSlaverWorker) and worker.managed
        }
        port = 8101
        while port in used:
            port += 1
        return port

    async def refresh_slavers(self) -> list[dict[str, Any]]:
        result = []
        for worker in self.workers.values():
            if isinstance(worker, RemoteSlaverWorker):
                try:
                    await worker.refresh()
                except Exception as error:
                    worker.last_error = str(error)
                result.append(worker.info())
        return result

    async def fetch(
        self,
        url: str,
        worker_id: str | None = None,
        strategy: str | None = None,
        wait_seconds: float | None = None,
        include_html: bool = False,
        include_links: bool = True,
    ) -> dict[str, Any]:
        worker = self.choose_worker(worker_id=worker_id, strategy=strategy)
        return await worker.fetch(
            url=url,
            wait_seconds=wait_seconds,
            include_html=include_html,
            include_links=include_links,
        )

    def submit_job(
        self,
        url: str,
        worker_id: str | None = None,
        strategy: str | None = None,
        wait_seconds: float | None = None,
        include_html: bool = False,
        include_links: bool = True,
    ) -> JobState:
        job_id = uuid.uuid4().hex
        job = JobState(job_id=job_id, status="queued", url=url)
        self.jobs[job_id] = job

        async def run_job() -> None:
            try:
                worker = self.choose_worker(worker_id=worker_id, strategy=strategy)
                job.mark_running(self.worker_id_for(worker))
                result = await worker.fetch(
                    url=url,
                    wait_seconds=wait_seconds,
                    include_html=include_html,
                    include_links=include_links,
                )
                job.mark_done(result)
            except Exception as error:
                job.mark_failed(error)

        asyncio.create_task(run_job())
        return job

    def worker_id_for(self, worker: TaskWorker | RemoteSlaverWorker) -> str:
        if isinstance(worker, RemoteSlaverWorker):
            return worker.worker_id
        return worker.config.worker_id

    def get_job(self, job_id: str) -> JobState:
        return self.jobs[job_id]

    def list_jobs(self) -> list[JobState]:
        return list(self.jobs.values())
