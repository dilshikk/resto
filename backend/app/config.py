from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "postgresql+asyncpg://mado:password@localhost:5432/mado_checklist"
    SECRET_KEY: str = "change-this-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    CORS_ORIGINS: str = "http://localhost:5173"
    # Shared secret the Telegram bot service sends on every request to /api/v1/bot/*.
    # Must match BOT_INTERNAL_SECRET set on the bot service. Keeps the bot-only
    # endpoints (which trust a telegram_id instead of a JWT) from being called by anyone else.
    BOT_INTERNAL_SECRET: str = "change-this-bot-secret-in-production"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]


settings = Settings()
