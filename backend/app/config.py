from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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


settings = Settings()
