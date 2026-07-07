import argparse
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src.master import Master


class FetchRequest(BaseModel):
    url: str
    worker_id: str | None = None
    strategy: str | None = None
    wait_seconds: float | None = Field(default=None, ge=0)
    include_html: bool = False
    include_links: bool = True


class RegisterSlaverRequest(BaseModel):
    base_url: str
    worker_id: str | None = None


class SelfRegisterSlaverRequest(BaseModel):
    port: int = Field(ge=1, le=65535)
    worker_id: str | None = None
    base_url: str | None = None


class UpdateSlaverRequest(BaseModel):
    base_url: str | None = None


class ProxyConfigRequest(BaseModel):
    enabled: bool = False
    scheme: str = Field(default="http", pattern="^(http|https|socks5)$")
    host: str | None = None
    port: int | None = Field(default=None, ge=1, le=65535)
    username: str | None = None
    password: str | None = None


class StartSlaverRequest(BaseModel):
    node_id: str | None = None
    host: str = "127.0.0.1"
    port: int | None = Field(default=None, ge=1, le=65535)
    env_name: str | None = None
    headful: bool | None = None
    browser_channel: str | None = None
    challenge_wait: float | None = Field(default=None, ge=0)
    proxy: ProxyConfigRequest | None = None
    launch_args: list[str] = Field(default_factory=list)
    user_agent: str | None = None
    locale: str | None = None
    timezone_id: str | None = None
    viewport_width: int | None = Field(default=None, ge=320)
    viewport_height: int | None = Field(default=None, ge=240)
    block_images: bool = False
    block_media: bool = False
    cookies: list[dict[str, Any]] = Field(default_factory=list)


def job_to_dict(job) -> dict[str, Any]:
    return {
        "job_id": job.job_id,
        "status": job.status,
        "url": job.url,
        "worker_id": job.worker_id,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
        "result": job.result,
        "error": job.error,
    }


def model_data(model: BaseModel) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def proxy_to_playwright(proxy: ProxyConfigRequest | None) -> dict[str, str] | None:
    if not proxy or not proxy.enabled:
        return None
    if not proxy.host or not proxy.port:
        raise ValueError("proxy host and port are required")

    result = {"server": f"{proxy.scheme}://{proxy.host}:{proxy.port}"}
    if proxy.username:
        result["username"] = proxy.username
    if proxy.password:
        result["password"] = proxy.password
    return result


def slaver_env_config(request: StartSlaverRequest) -> dict[str, Any]:
    return {
        "env_name": request.env_name,
        "proxy": proxy_to_playwright(request.proxy),
        "launch_args": request.launch_args,
        "user_agent": request.user_agent,
        "locale": request.locale,
        "timezone_id": request.timezone_id,
        "viewport_width": request.viewport_width,
        "viewport_height": request.viewport_height,
        "block_images": request.block_images,
        "block_media": request.block_media,
        "cookies": request.cookies,
    }


def create_app(master: Master) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await app.state.master.start()
        try:
            yield
        finally:
            await app.state.master.stop()

    app = FastAPI(title="Spider Master", version="1.0.0", lifespan=lifespan)
    app.state.master = master

    webui_root = Path(__file__).resolve().parents[2] / "webui"
    webui_dir = webui_root / "dist" if (webui_root / "dist").exists() else webui_root
    if webui_dir.exists():
        app.mount("/ui", StaticFiles(directory=webui_dir, html=True), name="ui")

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {
            "ok": True,
            "workers": len(app.state.master.workers),
        }

    @app.get("/workers")
    async def list_workers() -> list[dict[str, Any]]:
        return app.state.master.list_workers()

    @app.get("/slavers")
    async def list_slavers(refresh: bool = False) -> list[dict[str, Any]]:
        if refresh:
            return await app.state.master.refresh_slavers()
        return app.state.master.list_slavers()

    @app.post("/slavers")
    async def register_slaver(request: RegisterSlaverRequest) -> dict[str, Any]:
        try:
            return await app.state.master.register_slaver(
                base_url=request.base_url,
                worker_id=request.worker_id,
            )
        except Exception as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.post("/slavers/register-self")
    async def register_self(
        request: Request,
        body: SelfRegisterSlaverRequest,
    ) -> dict[str, Any]:
        client_host = request.client.host if request.client else None
        base_url = body.base_url
        if not base_url:
            if not client_host:
                raise HTTPException(status_code=400, detail="missing client host")
            base_url = f"http://{client_host}:{body.port}"

        try:
            return await app.state.master.register_slaver(
                base_url=base_url,
                worker_id=body.worker_id,
            )
        except Exception as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.post("/slavers/start")
    async def start_slaver(request: StartSlaverRequest) -> dict[str, Any]:
        try:
            return await app.state.master.create_browser_environment(
                node_id=request.node_id,
                host=request.host,
                port=request.port,
                headful=request.headful,
                browser_channel=request.browser_channel,
                challenge_wait=request.challenge_wait,
                env_config=slaver_env_config(request),
            )
        except Exception as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.patch("/slavers/{worker_id}")
    async def update_slaver(worker_id: str, request: UpdateSlaverRequest) -> dict[str, Any]:
        try:
            return await app.state.master.update_slaver(
                worker_id=worker_id,
                base_url=request.base_url,
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail="slaver not found") from error
        except TypeError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.delete("/slavers/{worker_id}")
    async def delete_slaver(worker_id: str) -> dict[str, Any]:
        try:
            return await app.state.master.stop_slaver_node(worker_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="slaver not found") from error

    @app.delete("/workers/{worker_id}")
    async def stop_worker(worker_id: str) -> dict[str, Any]:
        try:
            return await app.state.master.stop_worker(worker_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="worker not found") from error

    @app.delete("/workers")
    async def stop_all_workers() -> dict[str, Any]:
        return await app.state.master.stop_all_workers()

    @app.post("/fetch")
    async def fetch(request: FetchRequest) -> dict[str, Any]:
        try:
            return await app.state.master.fetch(**model_data(request))
        except KeyError as error:
            raise HTTPException(status_code=404, detail="worker not found") from error
        except Exception as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.post("/jobs")
    async def submit_job(request: FetchRequest) -> dict[str, Any]:
        try:
            job = app.state.master.submit_job(**model_data(request))
            return job_to_dict(job)
        except Exception as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.get("/jobs")
    async def list_jobs() -> list[dict[str, Any]]:
        return [job_to_dict(job) for job in app.state.master.list_jobs()]

    @app.get("/jobs/{job_id}")
    async def get_job(job_id: str) -> dict[str, Any]:
        try:
            return job_to_dict(app.state.master.get_job(job_id))
        except KeyError as error:
            raise HTTPException(status_code=404, detail="job not found") from error

    @app.get("/")
    async def index() -> FileResponse:
        index_file = webui_dir / "index.html"
        if not index_file.exists():
            raise HTTPException(status_code=404, detail="webui not found")
        return FileResponse(index_file)

    return app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Playwright master service.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--strategy", default="round_robin", choices=("round_robin", "random", "sticky"))
    parser.add_argument("--headful", action="store_true", help="show browser windows")
    parser.add_argument("--browser-channel", choices=("chrome", "msedge"))
    parser.add_argument("--challenge-wait", type=float, default=0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    master = Master(
        strategy=args.strategy,
        headful=args.headful,
        browser_channel=args.browser_channel,
        challenge_wait=args.challenge_wait,
    )
    app = create_app(master=master)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
