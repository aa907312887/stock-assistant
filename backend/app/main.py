import logging
import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.auth import router as auth_router

# 日志：同时输出到控制台和文件 backend/logs/app.log（文件每次写入后 flush，避免 500 时看不到）
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "app.log")
_fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
_file_handler.setLevel(logging.DEBUG)
_file_handler.setFormatter(logging.Formatter(_fmt))
logging.basicConfig(
    level=logging.INFO,
    format=_fmt,
    handlers=[
        logging.StreamHandler(sys.stdout),
        _file_handler,
    ],
)
def _flush_log_handlers():
    """把 root logger 的 handler 都 flush，确保 500 时 app.log 里立刻能看到"""
    for h in logging.root.handlers:
        if getattr(h, "stream", None) is not None and hasattr(h.stream, "flush"):
            try:
                h.stream.flush()
            except Exception:
                pass
logging.getLogger("uvicorn.access").setLevel(logging.INFO)


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Backend started, logs: %s", LOG_FILE)
    yield
    pass


app = FastAPI(
    title="股票分析助手 API",
    description="本地部署的股票分析、选股与持仓助手",
    version="0.1.0",
    lifespan=lifespan,
)
# 开发环境放宽 CORS（* 与 credentials 不能同开，用 token 时可不带 credentials）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router, prefix="/api")


@app.exception_handler(Exception)
async def debug_exception_handler(request: Request, exc: Exception):
    """全局异常：开发时在 500 里返回具体错误，并写入 app.log（并 flush）"""
    logger.exception("Unhandled exception: %s", exc)
    _flush_log_handlers()
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal Server Error",
            "debug": str(exc),
        },
    )


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """每条请求打一行日志；并在中间件层捕获所有异常并写 app.log，避免漏记"""
    path = request.url.path
    method = request.method
    logger.info(">>> %s %s", method, path)
    _flush_log_handlers()
    try:
        response = await call_next(request)
        logging.getLogger("uvicorn.access").info(f"{method} {path} -> {response.status_code}")
        return response
    except Exception as exc:
        logger.exception("Request failed %s %s: %s", method, path, exc)
        _flush_log_handlers()
        raise


@app.get("/")
def root():
    return {"message": "股票分析助手 API", "docs": "/docs"}


@app.get("/health")
def health():
    return {"status": "ok"}
