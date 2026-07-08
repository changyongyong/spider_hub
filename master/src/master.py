import asyncio
import subprocess
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx


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


class RemoteBrowserWorker:
    def __init__(
        self,
        worker_id: str,
        base_url: str,
        node_id: str,
        managed: ManagedProcess | None = None,
        status: dict[str, Any] | None = None,
    ) -> None:
        self.worker_id = worker_id
        self.base_url = base_url.rstrip("/")
        self.node_id = node_id
        self.managed = managed
        self.registered_at = datetime.now(timezone.utc).isoformat()
        self.last_seen: str | None = None
        self.last_error: str | None = None
        self.status: dict[str, Any] = status or {}

    async def refresh(self) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"{self.base_url}/environments")
            response.raise_for_status()
            for environment in response.json():
                if environment.get("worker_id") == self.worker_id:
                    self.status = environment
                    break
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
            response = await client.post(f"{self.base_url}/environments/{self.worker_id}/fetch", json=payload)
            response.raise_for_status()
            result = response.json()

        self.last_seen = datetime.now(timezone.utc).isoformat()
        self.last_error = None
        self.status = result.get("slave") or result.get("slaver") or self.status
        return result

    async def stop(self) -> None:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.delete(f"{self.base_url}/environments/{self.worker_id}")

    def info(self) -> dict[str, Any]:
        process_status = None
        if self.managed:
            process_status = self.managed.process.poll()

        return {
            "worker_id": self.worker_id,
            "kind": "remote",
            "node_id": self.node_id,
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
            "slave": self.status,
        }


class SlaveNode:
    def __init__(
        self,
        node_id: str,
        base_url: str,
        managed: ManagedProcess | None = None,
    ) -> None:
        self.node_id = node_id
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
        self.node_id = self.status.get("node_id") or self.node_id
        self.last_seen = datetime.now(timezone.utc).isoformat()
        self.last_error = None
        return self.status

    async def create_environment(self, payload: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(f"{self.base_url}/environments", json=payload)
            raise_for_status(response)
            result = response.json()
        await self.refresh()
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
        process_status = self.managed.process.poll() if self.managed else None
        return {
            "node_id": self.node_id,
            "kind": "node",
            "base_url": self.base_url,
            "registered_at": self.registered_at,
            "last_seen": self.last_seen,
            "last_error": self.last_error,
            "managed": self.managed is not None,
            "process_status": process_status,
            "running": process_status is None if self.managed else True,
            "max_environments": self.status.get("max_environments") or self.status.get("max_workers"),
            "max_workers": self.status.get("max_environments") or self.status.get("max_workers"),
            "worker_count": self.status.get("worker_count", 0),
            "available_slots": self.status.get("available_slots"),
            "workers": self.status.get("workers", []),
        }


def raise_for_status(response: httpx.Response) -> None:
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as error:
        detail = response.text
        try:
            payload = response.json()
            detail = payload.get("detail") or detail
        except ValueError:
            pass
        raise RuntimeError(f"slave {response.status_code}: {detail}") from error


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
        self.nodes: dict[str, SlaveNode] = {}
        self.workers: dict[str, RemoteBrowserWorker] = {}
        self.jobs: dict[str, JobState] = {}
        self.worker_index = 0
        self.node_index = 0

    async def start(self) -> None:
        return

    async def stop(self) -> None:
        for worker in list(self.workers.values()):
            await worker.stop()
        self.workers.clear()
        for node in list(self.nodes.values()):
            await node.stop()
        self.nodes.clear()

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

    def list_slaves(self) -> list[dict[str, Any]]:
        return [node.info() for node in self.nodes.values()]

    def choose_worker(
        self,
        worker_id: str | None = None,
        strategy: str | None = None,
    ) -> RemoteBrowserWorker:
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

    async def register_slave(
        self,
        base_url: str,
        worker_id: str | None = None,
        managed: ManagedProcess | None = None,
    ) -> dict[str, Any]:
        node = SlaveNode(
            node_id=worker_id or f"node-{uuid.uuid4().hex[:8]}",
            base_url=base_url,
            managed=managed,
        )
        try:
            status = await node.refresh()
            if worker_id is None:
                node.node_id = status.get("node_id") or node.node_id
        except Exception as error:
            node.last_error = str(error)

        self.nodes[node.node_id] = node
        self._sync_node_workers(node)
        return node.info()

    async def update_slave(
        self,
        worker_id: str,
        base_url: str | None = None,
    ) -> dict[str, Any]:
        worker = self.nodes[worker_id]
        if base_url:
            worker.base_url = base_url.rstrip("/")
        try:
            await worker.refresh()
        except Exception as error:
            worker.last_error = str(error)
        return worker.info()

    async def stop_slave_node(self, node_id: str) -> dict[str, Any]:
        node = self.nodes.pop(node_id)
        for worker_id, worker in list(self.workers.items()):
            if isinstance(worker, RemoteBrowserWorker) and worker.node_id == node_id:
                self.workers.pop(worker_id, None)
        await node.stop()
        return {"node_id": node_id, "stopped": True}

    async def create_browser_environment(
        self,
        node_id: str | None = None,
        host: str = "127.0.0.1",
        port: int | None = None,
        headful: bool | None = None,
        browser_channel: str | None = None,
        challenge_wait: float | None = None,
        env_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        env_config = {**self.env_config, **(env_config or {})}
        if not node_id:
            raise RuntimeError("node_id is required; choose a slave node before creating an environment")
        node = self.nodes[node_id]
        node_info = node.info()
        if node_info.get("available_slots") == 0:
            raise RuntimeError(f"slave node {node_id} has no available slots")

        worker_id = f"env-{uuid.uuid4().hex[:8]}"
        merged_config = {
            **env_config,
            "worker_id": worker_id,
            "headful": self.headful if headful is None else headful,
            "browser_channel": browser_channel if browser_channel is not None else self.browser_channel,
            "challenge_wait": self.challenge_wait if challenge_wait is None else challenge_wait,
        }
        environment = await node.create_environment(merged_config)
        worker = RemoteBrowserWorker(
            worker_id=environment["worker_id"],
            base_url=node.base_url,
            node_id=node.node_id,
            status=environment,
        )
        self.workers[worker.worker_id] = worker
        return worker.info()

    def _next_slave_port(self) -> int:
        used = {
            worker.managed.port
            for worker in self.nodes.values()
            if worker.managed
        }
        port = 8101
        while port in used:
            port += 1
        return port

    async def refresh_slaves(self) -> list[dict[str, Any]]:
        result = []
        for node in self.nodes.values():
            try:
                await node.refresh()
                self._sync_node_workers(node)
            except Exception as error:
                node.last_error = str(error)
            result.append(node.info())
        return result

    def _sync_node_workers(self, node: SlaveNode) -> None:
        for environment in node.status.get("workers", []):
            worker_id = environment.get("worker_id")
            if not worker_id:
                continue
            self.workers[worker_id] = RemoteBrowserWorker(
                worker_id=worker_id,
                base_url=node.base_url,
                node_id=node.node_id,
                status=environment,
            )

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

    def worker_id_for(self, worker: RemoteBrowserWorker) -> str:
        return worker.worker_id

    def get_job(self, job_id: str) -> JobState:
        return self.jobs[job_id]

    def list_jobs(self) -> list[JobState]:
        return list(self.jobs.values())
