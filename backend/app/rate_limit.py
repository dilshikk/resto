"""
Rate-limiting utilities for the MADO Checklist API.

Two protection layers:

1. Per-IP limiter (slowapi)
   Applied as @limiter.limit("N/minute") on individual endpoints.
   SlowAPI reads the client IP from the request and returns HTTP 429
   when the limit is exceeded.

2. Per-email lockout (DbLoginAttemptTracker)
   Tracks consecutive failed password attempts per email address in the
   `login_attempts` PostgreSQL table.  After MAX_FAILURES failures the
   account is locked for LOCKOUT_SECONDS.  A successful login removes the
   row.

   Storing state in the database (rather than process memory) means:
     - lockouts survive backend restarts and deployments;
     - all replicas share the same counters, so a distributed attacker
       that hits different pods still hits the same limit.

   The counter increment uses a PostgreSQL INSERT … ON CONFLICT DO UPDATE
   so concurrent requests update the counter atomically without races.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from sqlalchemy import case, delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from slowapi import Limiter
from slowapi.util import get_remote_address

if TYPE_CHECKING:
    pass

# ── Layer 1: per-IP SlowAPI limiter ──────────────────────────────────────────
# Attach to the FastAPI app in main.py:
#   app.state.limiter = limiter
#   app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
# Then decorate endpoints:
#   @limiter.limit("10/minute")
#   async def login(request: Request, ...): ...
limiter = Limiter(key_func=get_remote_address)


# ── Layer 2: per-email DB-backed lockout ──────────────────────────────────────
_MAX_FAILURES: int = 5         # consecutive wrong passwords before lockout
_LOCKOUT_SECONDS: float = 900  # 15 minutes


class DbLoginAttemptTracker:
    """
    Persistent, multi-replica-safe per-email failure counter.

    State lives in the ``login_attempts`` PostgreSQL table so it survives
    process restarts and is consistent across all backend replicas.

    Call :meth:`configure` once at application startup (after the engine
    is ready) to inject the session factory before any endpoint is served.

    Usage::

        # in lifespan / startup:
        login_attempt_tracker.configure(AsyncSessionLocal)

        # in the login endpoint:
        if await login_attempt_tracker.is_locked(email):
            raise HTTPException(429, ...)
        ...
        await login_attempt_tracker.record_failure(email)   # wrong password
        await login_attempt_tracker.record_success(email)   # correct password
    """

    def __init__(
        self,
        max_failures: int = _MAX_FAILURES,
        lockout_seconds: float = _LOCKOUT_SECONDS,
    ) -> None:
        self._max_failures = max_failures
        self._lockout_seconds = lockout_seconds
        # Injected at startup via configure(); typed loosely to avoid a
        # circular import at module load time.
        self._session_factory: async_sessionmaker[AsyncSession] | None = None

    def configure(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        """Inject the async session factory.  Must be called before any login attempt."""
        self._session_factory = session_factory

    def _get_factory(self) -> async_sessionmaker[AsyncSession]:
        if self._session_factory is None:
            raise RuntimeError(
                "DbLoginAttemptTracker has not been configured. "
                "Call login_attempt_tracker.configure(AsyncSessionLocal) at startup."
            )
        return self._session_factory

    async def is_locked(self, email: str) -> bool:
        """Return True if the account is currently locked out."""
        from app.models.login_attempt import LoginAttempt  # local import avoids circular dep

        async with self._get_factory()() as db:
            row = await db.get(LoginAttempt, email)
            if row is None or row.locked_until is None:
                return False
            return datetime.now(timezone.utc) < row.locked_until

    async def seconds_remaining(self, email: str) -> int:
        """Seconds until the lockout expires (0 if not locked)."""
        from app.models.login_attempt import LoginAttempt

        async with self._get_factory()() as db:
            row = await db.get(LoginAttempt, email)
            if row is None or row.locked_until is None:
                return 0
            remaining = (row.locked_until - datetime.now(timezone.utc)).total_seconds()
            return max(0, int(remaining))

    async def record_failure(self, email: str) -> None:
        """
        Atomically increment the failure counter.

        Uses a PostgreSQL upsert so concurrent requests from different
        workers/replicas never race on the same row: the increment happens
        inside the database engine, not in application code.

        When the counter reaches the threshold the locked_until column is
        set in the same statement, so there is no window between counting
        and locking.
        """
        from app.models.login_attempt import LoginAttempt

        now = datetime.now(timezone.utc)
        lock_at = now + timedelta(seconds=self._lockout_seconds)

        async with self._get_factory()() as db:
            stmt = (
                pg_insert(LoginAttempt)
                .values(
                    email=email,
                    failures=1,
                    last_failure=now,
                    locked_until=None,
                )
                .on_conflict_do_update(
                    index_elements=["email"],
                    set_={
                        "failures": LoginAttempt.failures + 1,
                        "last_failure": now,
                        # Set locked_until only when we cross the threshold;
                        # preserve any existing lockout otherwise.
                        "locked_until": case(
                            (
                                LoginAttempt.failures + 1 >= self._max_failures,
                                lock_at,
                            ),
                            else_=LoginAttempt.locked_until,
                        ),
                    },
                )
            )
            await db.execute(stmt)
            await db.commit()

    async def record_success(self, email: str) -> None:
        """Remove the failure record after a successful login."""
        from app.models.login_attempt import LoginAttempt

        async with self._get_factory()() as db:
            await db.execute(
                delete(LoginAttempt).where(LoginAttempt.email == email)
            )
            await db.commit()


# Module-level singleton — shared across all coroutines in the same process.
# configure() must be called in the FastAPI lifespan before any request is handled.
login_attempt_tracker = DbLoginAttemptTracker()
