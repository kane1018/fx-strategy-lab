from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./fx_trading.db"
    frontend_origin: str = "http://localhost:3000"
    log_level: str = "INFO"
    enable_live_trading: bool = False
    live_confirmation_phrase: str = "LIVE TRADING ENABLED"
    # Recognized for completeness, but intentionally inert: automation never auto-starts.
    # The bot always requires an explicit start and does not auto-resume after restart.
    auto_trade_default_enabled: bool = False
    oanda_api_token: str | None = None
    oanda_account_id: str | None = None
    oanda_environment: str = Field(
        default="practice",
        validation_alias=AliasChoices("OANDA_ENV", "OANDA_ENVIRONMENT"),
    )
    oanda_api_url: str = "https://api-fxpractice.oanda.com"

    # Broker selection. "oanda" is the only wired order path; GMO is a Public
    # read-only scaffold this phase (no real orders, no Private connection).
    broker_provider: str = "oanda"
    # GMO 外国為替FX. Secrets are read for a future Private phase but are NEVER
    # logged or sent in the current read-only phase. Defaults keep orders OFF.
    gmo_fx_api_key: str | None = None
    gmo_fx_api_secret: str | None = None
    gmo_fx_env: str = "production"
    gmo_fx_readonly: bool = True
    gmo_fx_order_enabled: bool = False
    gmo_fx_max_units: float = 100
    gmo_fx_public_url: str = "https://forex-api.coin.z.com/public"

    # Read-only report viewer: directory holding analysis_exports/<run_id>/ runs.
    # Server-fixed; the /api/reports routes never accept a caller-supplied path.
    analysis_exports_root: str = "analysis_exports"

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
