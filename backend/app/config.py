from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ── Required secrets — no default.  App will refuse to start if unset. ──
    # The absence of a default value makes pydantic-settings raise a
    # ValidationError at import time, which is far safer than silently using
    # a publicly-committed fallback value.
    #
    # Generate DATABASE_URL password, SECRET_KEY, and BOT_INTERNAL_SECRET with:
    #   python -c "import secrets; print(secrets.token_hex(32))"
    DATABASE_URL: str
    SECRET_KEY: str
    BOT_INTERNAL_SECRET: str

    # ── Non-secret settings — safe defaults are fine. ────────────────────────
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    CORS_ORIGINS: str = "http://localhost:5173"
    # Directory where checklist item photos are stored. Defaults to a path
    # under /data rather than /tmp so it survives container restarts and
    # rebuilds when mounted as a persistent Docker volume — see
    # docker-compose.yml's `uploads_data` volume on the backend service.
    PHOTOS_DIR: str = "/data/uploads"

    # ── Runtime validation ────────────────────────────────────────────────────

    @field_validator("SECRET_KEY")
    @classmethod
    def secret_key_must_be_strong(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError(
                "SECRET_KEY must be at least 32 characters. "
                "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        return v

    @field_validator("BOT_INTERNAL_SECRET")
    @classmethod
    def bot_secret_must_be_strong(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError(
                "BOT_INTERNAL_SECRET must be at least 32 characters. "
                "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        return v

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]


settings = Settings()
