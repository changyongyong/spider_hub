import asyncio
import subprocess
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx

from src.environment_store import EnvironmentRecord, SqliteEnvironmentStore


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

    def info(self, saved_config: dict[str, Any] | None = None, saved_status: str | None = None) -> dict[str, Any]:
        process_status = None
        if self.managed:
            process_status = self.managed.process.poll()
        config = saved_config or self.status.get("config", {})

        return {
            "worker_id": self.worker_id,
            "kind": "remote",
            "node_id": self.node_id,
            "env_name": config.get("env_name") or self.status.get("env_name") or self.status.get("config", {}).get("env_name"),
            "base_url": self.base_url,
            "registered_at": self.registered_at,
            "last_seen": self.last_seen,
            "last_error": self.last_error,
            "managed": self.managed is not None,
            "process_status": process_status,
            "running": process_status is None if self.managed else True,
            "status": saved_status or "running",
            "stats": self.status.get("stats", {}),
            "config": config,
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


def preserve_saved_proxy_password(old_config: dict[str, Any], new_config: dict[str, Any]) -> None:
    old_proxy = old_config.get("proxy")
    new_proxy = new_config.get("proxy")
    if not isinstance(old_proxy, dict) or not isinstance(new_proxy, dict):
        return
    if new_proxy.get("password") or old_proxy.get("server") != new_proxy.get("server"):
        return
    if old_proxy.get("password"):
        new_proxy["password"] = old_proxy["password"]


def proxy_for_runtime(proxy: dict[str, Any] | None) -> dict[str, str] | None:
    if not proxy or proxy.get("enabled") is False:
        return None

    server = proxy.get("server")
    if not server and proxy.get("host") and proxy.get("port"):
        scheme = proxy.get("scheme") or "http"
        server = f"{scheme}://{proxy['host']}:{proxy['port']}"
    if not server:
        return None

    result = {"server": server}
    if proxy.get("username"):
        result["username"] = proxy["username"]
    if proxy.get("password"):
        result["password"] = proxy["password"]
    return result


class Master:
    def __init__(
        self,
        strategy: str = "round_robin",
        headful: bool = False,
        browser_channel: str | None = None,
        challenge_wait: float = 0,
        env_config: dict[str, Any] | None = None,
        environment_store: SqliteEnvironmentStore | None = None,
    ) -> None:
        self.strategy = strategy
        self.headful = headful
        self.browser_channel = browser_channel
        self.challenge_wait = challenge_wait
        self.env_config = env_config or {}
        self.environment_store = environment_store or SqliteEnvironmentStore.from_env()
        self.environments: dict[str, EnvironmentRecord] = {}
        self.nodes: dict[str, SlaveNode] = {}
        self.workers: dict[str, RemoteBrowserWorker] = {}
        self.jobs: dict[str, JobState] = {}
        self.worker_index = 0
        self.node_index = 0

    async def start(self) -> None:
        self.environment_store.initialize()
        self.environments = {
            record.worker_id: record
            for record in self.environment_store.list()
        }

    async def stop(self) -> None:
        for worker in list(self.workers.values()):
            await worker.stop()
            self._mark_environment_status(worker.worker_id, "stopped")
        self.workers.clear()
        for node in list(self.nodes.values()):
            await node.stop()
        self.nodes.clear()

    async def stop_worker(self, worker_id: str) -> dict[str, Any]:
        worker = self.workers.pop(worker_id, None)
        if not worker and worker_id not in self.environments:
            raise KeyError(worker_id)
        if worker:
            await worker.stop()
        if worker_id in self.environments:
            self._mark_environment_status(worker_id, "stopped")
        return {"worker_id": worker_id, "stopped": True}

    async def stop_all_workers(self) -> dict[str, Any]:
        count = len(self.workers)
        for worker in list(self.workers.values()):
            await worker.stop()
            self._mark_environment_status(worker.worker_id, "stopped")
        self.workers.clear()
        return {"stopped": count}

    def list_workers(self) -> list[dict[str, Any]]:
        result = []
        for record in self.environments.values():
            worker = self.workers.get(record.worker_id)
            if worker:
                result.append(worker.info(saved_config=record.config, saved_status="running"))
            else:
                result.append(self._environment_info(record))
        return result

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
        self._sync_environment_status(node)
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
            self._sync_node_workers(worker)
            self._sync_environment_status(worker)
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
        saved = await self.save_browser_environment(
            node_id=node_id,
            host=host,
            port=port,
            headful=headful,
            browser_channel=browser_channel,
            challenge_wait=challenge_wait,
            env_config=env_config,
        )
        return await self.start_browser_environment(saved["worker_id"])

    async def save_browser_environment(
        self,
        node_id: str | None = None,
        host: str = "127.0.0.1",
        port: int | None = None,
        headful: bool | None = None,
        browser_channel: str | None = None,
        challenge_wait: float | None = None,
        env_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not node_id:
            raise RuntimeError("node_id is required; choose a slave node before creating an environment")
        if node_id not in self.nodes:
            raise RuntimeError(f"slave node {node_id} not found")

        worker_id = f"env-{uuid.uuid4().hex[:8]}"
        config = self._environment_config(
            worker_id=worker_id,
            headful=headful,
            browser_channel=browser_channel,
            challenge_wait=challenge_wait,
            env_config=env_config,
        )
        self._ensure_unique_env_name(config.get("env_name"), worker_id)
        record = EnvironmentRecord(
            worker_id=worker_id,
            node_id=node_id,
            env_name=config.get("env_name"),
            status="stopped",
            config=config,
        )
        record = self.environment_store.save(record)
        self.environments[record.worker_id] = record
        return self._environment_info(record)

    async def start_browser_environment(self, worker_id: str) -> dict[str, Any]:
        if worker_id in self.workers:
            record = self.environments.get(worker_id)
            return self.workers[worker_id].info(
                saved_config=record.config if record else None,
                saved_status="running",
            )

        record = self.environments[worker_id]
        if record.node_id not in self.nodes:
            raise RuntimeError(f"slave node {record.node_id} not found")
        node = self.nodes[record.node_id]
        node_info = node.info()
        if node_info.get("available_slots") == 0:
            raise RuntimeError(f"slave node {record.node_id} has no available slots")

        environment = await node.create_environment(self._runtime_config(record.config))
        worker = RemoteBrowserWorker(
            worker_id=environment["worker_id"],
            base_url=node.base_url,
            node_id=node.node_id,
            status=environment,
        )
        self.workers[worker.worker_id] = worker
        self._mark_environment_status(worker_id, "running")
        return worker.info(saved_config=record.config, saved_status="running")

    async def update_browser_environment(
        self,
        worker_id: str,
        headful: bool | None = None,
        browser_channel: str | None = None,
        challenge_wait: float | None = None,
        env_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        old_record = self.environments.get(worker_id)
        if not old_record:
            raise KeyError(worker_id)

        merged_config = self._environment_config(
            worker_id=worker_id,
            headful=headful,
            browser_channel=browser_channel,
            challenge_wait=challenge_wait,
            env_config=env_config,
        )
        preserve_saved_proxy_password(old_record.config, merged_config)
        self._ensure_unique_env_name(merged_config.get("env_name"), worker_id)

        worker = self.workers.get(worker_id)
        if worker:
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.patch(f"{worker.base_url}/environments/{worker_id}", json=self._runtime_config(merged_config))
                raise_for_status(response)
                environment = response.json()

            worker.status = environment
            node = self.nodes.get(worker.node_id)
            if node:
                await node.refresh()
                self._sync_node_workers(node)

        record = EnvironmentRecord(
            worker_id=worker_id,
            node_id=old_record.node_id,
            env_name=merged_config.get("env_name"),
            status="running" if worker else "stopped",
            config=merged_config,
            created_at=old_record.created_at,
            updated_at=old_record.updated_at,
        )
        record = self.environment_store.save(record)
        self.environments[worker_id] = record
        if worker:
            return worker.info(saved_config=record.config, saved_status="running")
        return self._environment_info(record)

    async def delete_browser_environment(self, worker_id: str) -> dict[str, Any]:
        await self.stop_worker(worker_id)
        self.environment_store.delete(worker_id)
        self.environments.pop(worker_id, None)
        return {"worker_id": worker_id, "deleted": True}

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
                self._sync_environment_status(node)
            except Exception as error:
                node.last_error = str(error)
            result.append(node.info())
        return result

    def _sync_node_workers(self, node: SlaveNode) -> None:
        node_worker_ids = {
            environment.get("worker_id")
            for environment in node.status.get("workers", [])
            if environment.get("worker_id")
        }
        for worker_id, worker in list(self.workers.items()):
            if worker.node_id == node.node_id and worker_id not in node_worker_ids:
                self.workers.pop(worker_id, None)

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

    def _sync_environment_status(self, node: SlaveNode) -> None:
        running_ids = {
            environment.get("worker_id")
            for environment in node.status.get("workers", [])
            if environment.get("worker_id")
        }
        for record in list(self.environments.values()):
            if record.node_id != node.node_id:
                continue
            next_status = "running" if record.worker_id in running_ids else "stopped"
            if record.status != next_status:
                self._mark_environment_status(record.worker_id, next_status)

    def _environment_config(
        self,
        worker_id: str,
        headful: bool | None = None,
        browser_channel: str | None = None,
        challenge_wait: float | None = None,
        env_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        env_config = env_config or {}
        env_name = env_config.get("env_name")
        if isinstance(env_name, str):
            env_config = {**env_config, "env_name": env_name.strip()}
        return {
            **self.env_config,
            **env_config,
            "worker_id": worker_id,
            "headful": self.headful if headful is None else headful,
            "browser_channel": browser_channel if browser_channel is not None else self.browser_channel,
            "challenge_wait": self.challenge_wait if challenge_wait is None else challenge_wait,
        }

    def _runtime_config(self, config: dict[str, Any]) -> dict[str, Any]:
        return {
            **config,
            "proxy": proxy_for_runtime(config.get("proxy")),
        }

    def _ensure_unique_env_name(self, env_name: str | None, worker_id: str) -> None:
        if not env_name:
            return
        normalized = env_name.strip().lower()
        for record in self.environments.values():
            if record.worker_id != worker_id and (record.env_name or "").strip().lower() == normalized:
                raise ValueError("环境名称已存在，请换一个名称")
        if self.environment_store.env_name_exists(env_name, exclude_worker_id=worker_id):
            raise ValueError("环境名称已存在，请换一个名称")

    def _environment_info(self, record: EnvironmentRecord) -> dict[str, Any]:
        node = self.nodes.get(record.node_id)
        return {
            "worker_id": record.worker_id,
            "kind": "remote",
            "node_id": record.node_id,
            "env_name": record.env_name or record.config.get("env_name") or record.worker_id,
            "base_url": node.base_url if node else "",
            "registered_at": record.created_at,
            "last_seen": None,
            "last_error": None,
            "managed": False,
            "process_status": None,
            "running": False,
            "status": record.status,
            "stats": {},
            "config": record.config,
            "slave": {},
        }

    def _mark_environment_status(self, worker_id: str, status: str) -> None:
        record = self.environments.get(worker_id)
        if not record:
            return
        record.status = status
        self.environment_store.set_status(worker_id, status)

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
