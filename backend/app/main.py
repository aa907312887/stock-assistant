from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 可在此启动 APScheduler 等
    yield
    # 关闭时清理
    pass


app = FastAPI(
    title="股票分析助手 API",
    description="本地部署的股票分析、选股与持仓助手",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router, prefix="/api")


@app.get("/")
def root():
    return {"message": "股票分析助手 API", "docs": "/docs"}


@app.get("/health")
def health():
    return {"status": "ok"}
