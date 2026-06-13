from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./fx_trading.db"
    frontend_origin: str = "http://localhost:3000"
    log_level: str = "INFO"
    enable_live_trading: bool = False
    live_confirmation_phrase: str = "LIVE TRADING ENABLED"
    oanda_api_token: str | None = None
    oanda_account_id: str | None = None
    oanda_environment: str = Field(
        default="practice",
        validation_alias=AliasChoices("OANDA_ENV", "OANDA_ENVIRONMENT"),
    )
    oanda_api_url: str = "https://api-fxpractice.oanda.com"

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
