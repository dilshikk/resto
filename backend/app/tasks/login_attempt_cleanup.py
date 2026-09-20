"""
Background task: periodically purge stale rows from the login_attempts table.

A row can be safely deleted once its last_failure timestamp is older than
the lockout window — at that point the lockout (if any) has already expired
and the row no longer affects anything.  Keeping the table trimmed prevents
unbounded growth from automated scanners that target many email addresses.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete

from app.database import AsyncSessionLocal
from app.models.login_attempt import LoginAttempt
from app.rate_limit import _LOCKOUT_SECONDS

_CLEANUP_INTERVAL_SECONDS: float = 3600  # run once per hour

logger = logging.getLogger(__name__)


async def run_login_attempt_cleanup_loop() -> None:
    """
    Infinite loop: sleep, then delete rows whose last_failure is old enough
    that their lockout window has certainly passed.
    """
    while True:
        await asyncio.sleep(_CLEANUP_INTERVAL_SECONDS)
        try:
            # Add a small buffer so rows that are right on the boundary are
            # not deleted before the lockout has fully expired.
            cutoff = datetime.now(timezone.utc) - timedelta(seconds=_LOCKOUT_SECONDS + 60)
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    delete(LoginAttempt).where(LoginAttempt.last_failure < cutoff)
                )
                await db.commit()
                if result.rowcount:
                    logger.info(
                        "login_attempt_cleanup: removed %d stale row(s)",
                        result.rowcount,
                    )
        except Exception:
            logger.exception("login_attempt_cleanup: error during cleanup")
