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

    # ── Automatic checklist generation ───────────────────────────────────────
    #
    # CHECKLIST_SCHEDULE_HOUR_UTC
    #   Hour of day (UTC, 0-23) when the daily scheduler runs.
    #   Default: 1 = 01:00 UTC, which is 06:00 for Asia/Tashkent (UTC+5).
    #   Set to the UTC hour that corresponds to early morning in your
    #   primary timezone so checklists are ready when the first shift starts.
    #   Example: for UTC+3 use 21 (previous day 21:00 UTC = midnight local).
    CHECKLIST_SCHEDULE_HOUR_UTC: int = 1

    # CHECKLIST_AUTO_SHIFTS
    #   Comma-separated list of shift codes to generate automatically.
    #   Must match values used in Checklist.shift (morning / afternoon / evening).
    #   Remove a shift to stop generating it automatically.
    CHECKLIST_AUTO_SHIFTS: str = "morning,afternoon,evening"

    # ── Overdue checklist escalation ─────────────────────────────────────────
    #
    # OVERDUE_CHECK_INTERVAL_SECONDS
    #   How often (in seconds) the escalation loop polls for overdue checklists.
    #   Default: 60 s.  Decrease for near-real-time alerts; increase to reduce DB load.
    OVERDUE_CHECK_INTERVAL_SECONDS: int = 60

    # OVERDUE_MANAGER_NOTIFY_MINUTES
    #   Minutes after due_at before managers (permission_level == 1) are notified.
    #   ТЗ specifies 10 min: 08:00 overdue → 08:10 manager notified.
    OVERDUE_MANAGER_NOTIFY_MINUTES: int = 10

    # OVERDUE_SUPERVISOR_NOTIFY_MINUTES
    #   Minutes after due_at before supervisors/directors (permission_level >= 2)
    #   are escalated to.  ТЗ specifies 30 min: 08:00 overdue → 08:30 escalation.
    OVERDUE_SUPERVISOR_NOTIFY_MINUTES: int = 30

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

    @field_validator("CHECKLIST_SCHEDULE_HOUR_UTC")
    @classmethod
    def schedule_hour_must_be_valid(cls, v: int) -> int:
        if not 0 <= v <= 23:
            raise ValueError("CHECKLIST_SCHEDULE_HOUR_UTC must be between 0 and 23")
        return v

    @field_validator("OVERDUE_MANAGER_NOTIFY_MINUTES", "OVERDUE_SUPERVISOR_NOTIFY_MINUTES")
    @classmethod
    def notify_minutes_must_be_positive(cls, v: int) -> int:
        if v < 0:
            raise ValueError("Notify minutes must be >= 0")
        return v

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]


settings = Settings()
