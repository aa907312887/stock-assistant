from pathlib import Path
from typing import Self

from dotenv import dotenv_values
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _backend_env_file() -> Path:
    """backend/.env（本文件位于 backend/app/config.py）。"""
    return Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    database_url: str = Field(
        default="mysql+pymysql://root:password@localhost:3306/stock_assistant",
        validation_alias="DATABASE_URL",
    )
    secret_key: str = Field(
        default="dev-secret-key-change-in-production",
        validation_alias="SECRET_KEY",
    )
    algorithm: str = Field(default="HS256", validation_alias="ALGORITHM")
    access_token_expire_days: int = Field(default=7, validation_alias="ACCESS_TOKEN_EXPIRE_DAYS")
    default_password: str = Field(default="", validation_alias="DEFAULT_PASSWORD")

    # Tushare Pro Token：仅由下方 validator 从 backend/.env 读取，不使用进程环境变量 TUSHARE_TOKEN
    tushare_token: str = Field(default="", validation_alias="TUSHARE_TOKEN")
    # 手动触发同步时的鉴权（Header X-Admin-Secret 需与此一致）
    admin_secret: str = Field(default="", validation_alias="ADMIN_SECRET")

    # 每次调用 Tushare Pro 前的最小间隔（秒），降低触发限流概率；可按账号额度调大（如 0.2）
    tushare_rate_pause_sec: float = Field(default=0.12, validation_alias="TUSHARE_RATE_PAUSE_SEC")
    # 日线未复权 ``daily``、``adj_factor`` 区间请求前的休眠（秒）；并发回灌时总 QPS 上升，若遇限流可适当调大
    tushare_rate_pause_sec_daily: float = Field(
        default=0.025,
        validation_alias="TUSHARE_RATE_PAUSE_SEC_DAILY",
    )
    # 日线回灌：``pro.daily`` 多标的合并时每批最多几只（逗号分隔 ts_code，受单次约 6000 行上限约束，宜 8～20）
    stock_daily_backfill_daily_batch_size: int = Field(
        default=12,
        ge=1,
        le=80,
        validation_alias="STOCK_DAILY_BACKFILL_DAILY_BATCH_SIZE",
    )
    # 日线回灌：同一自然年窗口内并行处理标的的线程数（每只独立 DB Session）；为 1 时退化为串行
    stock_daily_backfill_workers: int = Field(
        default=4,
        ge=1,
        le=32,
        validation_alias="STOCK_DAILY_BACKFILL_WORKERS",
    )

    @model_validator(mode="after")
    def _tushare_token_from_env_file_only(self) -> Self:
        """Tushare Token 只认 backend/.env 中的 TUSHARE_TOKEN，忽略 export 与 tushare 的 ~/tk.csv。"""
        p = _backend_env_file()
        if p.is_file():
            val = (dotenv_values(p).get("TUSHARE_TOKEN") or "").strip()
            object.__setattr__(self, "tushare_token", val)
        else:
            object.__setattr__(self, "tushare_token", "")
        return self


settings = Settings()
