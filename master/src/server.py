import argparse
import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.master import Master


API_PATH_PREFIXES = (
    "/auth/me",
    "/auth/logout",
    "/health",
    "/environments",
    "/workers",
    "/slaves",
    "/slavers",
    "/jobs",
    "/fetch",
    "/docs",
    "/redoc",
    "/openapi.json",
)


class FetchRequest(BaseModel):
    url: str
    worker_id: str | None = None
    strategy: str | None = None
    wait_seconds: float | None = Field(default=None, ge=0)
    include_html: bool = False
    include_links: bool = True


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterSlaveRequest(BaseModel):
    base_url: str
    worker_id: str | None = None


class SelfRegisterSlaveRequest(BaseModel):
    port: int = Field(ge=1, le=65535)
    worker_id: str | None = None
    base_url: str | None = None


class UpdateSlaveRequest(BaseModel):
    base_url: str | None = None


class ProxyConfigRequest(BaseModel):
    enabled: bool = False
    scheme: str = Field(default="http", pattern="^(http|https|socks5)$")
    host: str | None = None
    port: int | None = Field(default=None, ge=1, le=65535)
    username: str | None = None
    password: str | None = None


class StartSlaveRequest(BaseModel):
    node_id: str | None = None
    env_name: str | None = None
    headful: bool | None = None
    browser_channel: str | None = None
    challenge_wait: float | None = Field(default=None, ge=0)
    platform: str | None = None
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
    start_url: str | None = None
    webrtc: str | None = None
    canvas: str | None = None
    webgl_image: str | None = None
    webgl_info: str | None = None
    webgpu: str | None = None
    audio_context: str | None = None
    speech_voices: str | None = None
    media_devices: str | None = None
    hardware_concurrency: int | None = Field(default=None, ge=1)
    device_memory: int | None = Field(default=None, ge=1)
    do_not_track: str | None = None
    port_scan_protection: str | None = None


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
    app.state.env = os.getenv("SPIDER_ENV", "development")
    app.state.auth_username = os.getenv("SPIDER_MASTER_USERNAME", "admin")
    app.state.auth_password = os.getenv("SPIDER_MASTER_PASSWORD", "admin")
    app.state.session_secret = os.getenv("SPIDER_SESSION_SECRET", "dev-secret")
    app.state.session_ttl_seconds = int(os.getenv("SPIDER_SESSION_TTL_SECONDS", "86400"))
    app.state.internal_api_token = os.getenv("SPIDER_INTERNAL_API_TOKEN")

    @app.middleware("http")
    async def auth_middleware(request: Request, call_next):
        path = request.url.path
        if path.endswith("/register-self"):
            if app.state.internal_api_token:
                token = request.headers.get("x-internal-token")
                if not secrets.compare_digest(token or "", app.state.internal_api_token):
                    return auth_error("invalid or missing internal token")
            return await call_next(request)
        if path.startswith(API_PATH_PREFIXES) and not session_payload(request, app):
            return auth_error("login required")
        return await call_next(request)

    @app.post("/auth/login")
    async def login(request: LoginRequest, response: Response) -> dict[str, Any]:
        username_ok = secrets.compare_digest(request.username, app.state.auth_username)
        password_ok = secrets.compare_digest(request.password, app.state.auth_password)
        if not username_ok or not password_ok:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="invalid username or password",
            )
        expires_at = int(time.time()) + app.state.session_ttl_seconds
        access_token = sign_session_token(
            {"sub": request.username, "exp": expires_at},
            app.state.session_secret,
        )
        response.set_cookie(
            key="spider_session",
            value=access_token,
            httponly=True,
            samesite="lax",
            secure=app.state.env == "production" and env_bool("SPIDER_COOKIE_SECURE", False),
            max_age=app.state.session_ttl_seconds,
        )
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_at": expires_at,
            "username": request.username,
        }

    @app.get("/auth/me")
    async def current_user(request: Request) -> dict[str, Any]:
        payload = session_payload(request, app)
        if not payload:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="login required")
        return {"username": payload["sub"], "expires_at": payload["exp"]}

    @app.post("/auth/logout")
    async def logout(response: Response) -> dict[str, bool]:
        response.delete_cookie("spider_session")
        return {"ok": True}

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {
            "ok": True,
            "env": app.state.env,
            "workers": len(app.state.master.workers),
        }

    @app.get("/workers")
    async def list_workers() -> list[dict[str, Any]]:
        return app.state.master.list_workers()

    @app.get("/slaves/environments", include_in_schema=False)
    @app.get("/environments")
    async def list_environments() -> list[dict[str, Any]]:
        return app.state.master.list_workers()

    @app.post("/slaves/environments", include_in_schema=False)
    @app.post("/environments")
    async def create_environment(request: StartSlaveRequest) -> dict[str, Any]:
        try:
            return await app.state.master.save_browser_environment(
                node_id=request.node_id,
                headful=request.headful,
                browser_channel=request.browser_channel,
                challenge_wait=request.challenge_wait,
                env_config=slave_env_config(request),
            )
        except Exception as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.patch("/slaves/environments/{worker_id}", include_in_schema=False)
    @app.patch("/environments/{worker_id}")
    async def update_environment(worker_id: str, request: StartSlaveRequest) -> dict[str, Any]:
        try:
            return await app.state.master.update_browser_environment(
                worker_id=worker_id,
                headful=request.headful,
                browser_channel=request.browser_channel,
                challenge_wait=request.challenge_wait,
                env_config=slave_env_config(request),
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail="environment not found") from error
        except Exception as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.post("/slaves/environments/{worker_id}/start", include_in_schema=False)
    @app.post("/environments/{worker_id}/start")
    async def start_environment(worker_id: str) -> dict[str, Any]:
        try:
            return await app.state.master.start_browser_environment(worker_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="environment not found") from error
        except Exception as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.post("/slaves/environments/{worker_id}/stop", include_in_schema=False)
    @app.post("/environments/{worker_id}/stop")
    async def stop_environment(worker_id: str) -> dict[str, Any]:
        try:
            return await app.state.master.stop_worker(worker_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="environment not found") from error

    @app.delete("/slaves/environments/{worker_id}", include_in_schema=False)
    @app.delete("/environments/{worker_id}")
    async def delete_environment(worker_id: str) -> dict[str, Any]:
        try:
            return await app.state.master.delete_browser_environment(worker_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="environment not found") from error

    @app.get("/slavers", include_in_schema=False)
    @app.get("/slaves")
    async def list_slaves(refresh: bool = False) -> list[dict[str, Any]]:
        if refresh:
            return await app.state.master.refresh_slaves()
        return app.state.master.list_slaves()

    @app.post("/slavers", include_in_schema=False)
    @app.post("/slaves")
    async def register_slave(request: RegisterSlaveRequest) -> dict[str, Any]:
        try:
            return await app.state.master.register_slave(
                base_url=request.base_url,
                worker_id=request.worker_id,
            )
        except Exception as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.post("/slavers/register-self", include_in_schema=False)
    @app.post("/slaves/register-self")
    async def register_self(request: Request, body: SelfRegisterSlaveRequest) -> dict[str, Any]:
        client_host = request.client.host if request.client else None
        base_url = body.base_url
        if not base_url:
            if not client_host:
                raise HTTPException(status_code=400, detail="missing client host")
            base_url = f"http://{client_host}:{body.port}"

        try:
            return await app.state.master.register_slave(
                base_url=base_url,
                worker_id=body.worker_id,
            )
        except Exception as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.post("/slavers/start", include_in_schema=False)
    @app.post("/slaves/start")
    async def start_slave(request: StartSlaveRequest) -> dict[str, Any]:
        try:
            return await app.state.master.create_browser_environment(
                node_id=request.node_id,
                headful=request.headful,
                browser_channel=request.browser_channel,
                challenge_wait=request.challenge_wait,
                env_config=slave_env_config(request),
            )
        except Exception as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.patch("/slavers/{node_id}", include_in_schema=False)
    @app.patch("/slaves/{node_id}")
    async def update_slave(node_id: str, request: UpdateSlaveRequest) -> dict[str, Any]:
        try:
            return await app.state.master.update_slave(
                worker_id=node_id,
                base_url=request.base_url,
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail="slave not found") from error

    @app.delete("/slavers/{node_id}", include_in_schema=False)
    @app.delete("/slaves/{node_id}")
    async def delete_slave(node_id: str) -> dict[str, Any]:
        try:
            return await app.state.master.stop_slave_node(node_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="slave not found") from error

    @app.delete("/workers/{worker_id}")
    async def stop_worker(worker_id: str) -> dict[str, Any]:
        try:
            return await app.state.master.stop_worker(worker_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="worker not found") from error

    @app.patch("/workers/{worker_id}")
    async def update_worker(worker_id: str, request: StartSlaveRequest) -> dict[str, Any]:
        try:
            return await app.state.master.update_browser_environment(
                worker_id=worker_id,
                headful=request.headful,
                browser_channel=request.browser_channel,
                challenge_wait=request.challenge_wait,
                env_config=slave_env_config(request),
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail="worker not found") from error
        except Exception as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

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

    return app


def auth_error(message: str) -> JSONResponse:
    return JSONResponse({"detail": message}, status_code=status.HTTP_401_UNAUTHORIZED)


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


def slave_env_config(request: StartSlaveRequest) -> dict[str, Any]:
    return {
        "env_name": request.env_name,
        "proxy": proxy_to_playwright(request.proxy),
        "platform": request.platform,
        "launch_args": request.launch_args,
        "user_agent": request.user_agent,
        "locale": request.locale,
        "timezone_id": request.timezone_id,
        "viewport_width": request.viewport_width,
        "viewport_height": request.viewport_height,
        "block_images": request.block_images,
        "block_media": request.block_media,
        "cookies": request.cookies,
        "start_url": request.start_url,
        "webrtc": request.webrtc,
        "canvas": request.canvas,
        "webgl_image": request.webgl_image,
        "webgl_info": request.webgl_info,
        "webgpu": request.webgpu,
        "audio_context": request.audio_context,
        "speech_voices": request.speech_voices,
        "media_devices": request.media_devices,
        "hardware_concurrency": request.hardware_concurrency,
        "device_memory": request.device_memory,
        "do_not_track": request.do_not_track,
        "port_scan_protection": request.port_scan_protection,
    }


def sign_session_token(payload: dict[str, Any], secret: str) -> str:
    body = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":")).encode()
    ).decode().rstrip("=")
    signature = hmac.new(secret.encode(), body.encode(), hashlib.sha256).digest()
    signed = base64.urlsafe_b64encode(signature).decode().rstrip("=")
    return f"{body}.{signed}"


def session_payload(request: Request, app: FastAPI) -> dict[str, Any] | None:
    authorization = request.headers.get("authorization", "")
    token = authorization.removeprefix("Bearer ") if authorization.startswith("Bearer ") else None
    token = token or request.cookies.get("spider_session")
    if not token:
        return None
    try:
        body, signature = token.split(".", 1)
        payload = json.loads(base64_url_decode(body).decode())
        expected = sign_session_token(payload, app.state.session_secret).split(".", 1)[1]
    except Exception:
        return None
    if not secrets.compare_digest(signature, expected):
        return None
    if int(payload.get("exp", 0)) < int(time.time()):
        return None
    return payload


def base64_url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run spider master service.")
    parser.add_argument("--host", default=os.getenv("SPIDER_MASTER_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("SPIDER_MASTER_PORT", "8000")))
    parser.add_argument(
        "--strategy",
        default=os.getenv("SPIDER_MASTER_STRATEGY", "round_robin"),
        choices=("round_robin", "random", "sticky"),
    )
    parser.add_argument(
        "--headful",
        action="store_true",
        default=env_bool("SPIDER_MASTER_HEADFUL"),
        help="show browser windows",
    )
    parser.add_argument("--browser-channel", default=os.getenv("SPIDER_MASTER_BROWSER_CHANNEL"))
    parser.add_argument(
        "--challenge-wait",
        type=float,
        default=float(os.getenv("SPIDER_MASTER_CHALLENGE_WAIT", "0")),
    )
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
