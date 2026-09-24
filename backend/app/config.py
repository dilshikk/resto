from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ── Required secrets — no default.  App will refuse to start if unset. ──
    DATABASE_URL: str
    SECRET_KEY: str
    BOT_INTERNAL_SECRET: str

    # ── Telegram bot token ────────────────────────────────────────────────────
    # Optional: when set the backend can push Telegram messages directly
    # (e.g. approve / reject notifications).  If unset, those pushes are
    # silently skipped — all other functionality is unaffected.
    BOT_TOKEN: str | None = None

    # ── Application identity ─────────────────────────────────────────────────
    APP_NAME: str = "MADO Checklist"

    # ── Non-secret settings — safe defaults are fine. ────────────────────────
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    CORS_ORIGINS: str = "http://localhost:5173"
    PHOTOS_DIR: str = "/data/uploads"

    # ── Cookie security ───────────────────────────────────────────────────────
    # Set COOKIE_SECURE=false in local .env when running over plain HTTP.
    # In production (HTTPS) leave at the default True.
    # When COOKIE_SECURE is False the SameSite attribute is forced to "lax"
    # because browsers reject SameSite=None without Secure.
    COOKIE_SECURE: bool = True
    # "none" is required for cross-origin setups (separate API domain).
    # "lax" is used automatically when COOKIE_SECURE=False.
    COOKIE_SAMESITE: str = "none"

    # ── Automatic checklist generation ───────────────────────────────────────
    CHECKLIST_SCHEDULE_HOUR_UTC: int = 1
    CHECKLIST_AUTO_SHIFTS: str = "morning,afternoon,evening"

    # ── Overdue checklist escalation ─────────────────────────────────────────
    OVERDUE_CHECK_INTERVAL_SECONDS: int = 60
    OVERDUE_MANAGER_NOTIFY_MINUTES: int = 10
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

    @field_validator("COOKIE_SAMESITE")
    @classmethod
    def samesite_must_be_valid(cls, v: str) -> str:
        if v.lower() not in ("strict", "lax", "none"):
            raise ValueError("COOKIE_SAMESITE must be 'strict', 'lax', or 'none'")
        return v.lower()

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]

    @property
    def effective_samesite(self) -> str:
        """SameSite=None requires Secure; fall back to Lax for plain-HTTP dev."""
        if not self.COOKIE_SECURE and self.COOKIE_SAMESITE == "none":
            return "lax"
        return self.COOKIE_SAMESITE


settings = Settings()
