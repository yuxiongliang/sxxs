from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.proxy_amap import router as proxy_amap_router
from app.api.v1.router import api_router
from app.core import billing_scheduler, im_bus
from app.core.config import settings
from app.core.db import engine
from app.core.migrations import ensure_schema_at_head
from app.core.rate_limit import RateLimitMiddleware
from app.core.request_context import (
    RequestMeta,
    clear_request_meta,
    client_ip_from,
    new_trace_id,
    set_request_meta,
)
from app.seed import seed_demo_data

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await ensure_schema_at_head()
    await seed_demo_data()
    await im_bus.start_subscriber()
    billing_scheduler.start()
    logger.info("admin_api_started", prefix=settings.api_v1_prefix)
    yield
    await billing_scheduler.stop()
    await im_bus.stop_subscriber()
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="FastAPI backend for the Ant Design Pro admin console.",
    lifespan=lifespan,
)


@app.middleware("http")
async def request_metadata(request: Request, call_next):
    """Attach a trace id and the client IP so audit rows can be correlated."""
    trace_id = request.headers.get("x-request-id") or new_trace_id()
    fallback_ip = request.client.host if request.client else ""
    set_request_meta(
        RequestMeta(
            ip=client_ip_from(dict(request.headers), fallback_ip),
            trace_id=trace_id,
            method=request.method,
            path=request.url.path,
            user_agent=request.headers.get("user-agent", ""),
        )
    )
    try:
        response = await call_next(request)
    finally:
        clear_request_meta()
    response.headers["X-Trace-Id"] = trace_id
    return response


app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_v1_prefix)
# 高德 JS API 安全密钥代理：浏览器只拿到 serviceHost，密钥留在服务端
app.include_router(proxy_amap_router)
app.mount("/uploads", StaticFiles(directory=str(settings.upload_path)), name="uploads")


@app.get("/health", tags=["system"])
async def health() -> dict:
    return {"status": "ok", "service": settings.app_name}


@app.exception_handler(HTTPException)
async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.status_code, "message": str(exc.detail), "data": None},
    )


def _json_safe_errors(exc: RequestValidationError) -> list[dict]:
    """Make validation errors serialisable.

    ``exc.errors()`` may contain non-JSON values: when a custom validator raises
    ``ValueError`` the original exception ends up in ``ctx["error"]``, and an
    exotic request body can put arbitrary objects in ``input``. Serialising them
    naively used to crash the handler itself and turn a 422 into a 500.
    """
    safe: list[dict] = []
    for error in exc.errors():
        item = {
            "type": str(error.get("type", "")),
            "loc": [str(part) for part in error.get("loc", ())],
            "msg": str(error.get("msg", "")),
        }
        ctx = error.get("ctx")
        if ctx:
            item["ctx"] = {str(key): str(value) for key, value in ctx.items()}
        safe.append(item)
    return safe


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "code": 422,
            "message": "参数校验失败",
            "data": {"errors": _json_safe_errors(exc)},
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled_exception", error=str(exc))
    return JSONResponse(
        status_code=500,
        content={"code": 500, "message": "服务端内部错误", "data": None},
    )
