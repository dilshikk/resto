"""
Background cleanup of the JWT revocation denylist (see app.models.revoked_token).

Every revoked token keeps its expires_at, mirroring the token's own `exp`
claim. Once that time has passed, the token would be rejected by normal JWT
expiry checks anyway, so the denylist row is no longer needed for security -
it only exists to catch tokens that were revoked before they naturally
expired. Without this cleanup, revoked_tokens grows forever (one row per
logout/refresh) and its index gets scanned on every authenticated request.

Runs as a plain asyncio background task started from the FastAPI lifespan in
app.main, not a cron job or extra process, since it only touches this app's
own database, needs no external scheduling, and runs at most a few times a
day. This avoids adding a scheduler dependency.
"""
import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import delete

from app.database import AsyncSessionLocal
from app.models.revoked_token import RevokedToken

logger = logging.getLogger(__name__)

# How often to sweep. Revoked-but-not-yet-expired rows only need to disappear
# well before they'd accumulate meaningfully, not instantly - once every few
# hours keeps the table small without adding meaningful query load.
CLEANUP_INTERVAL_SECONDS = 6 * 60 * 60


async def purge_expired_revoked_tokens() -> int:
    """Delete denylist rows whose underlying token has already expired. Returns count removed."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            delete(RevokedToken).where(RevokedToken.expires_at < datetime.now(timezone.utc))
        )
        await session.commit()
        return result.rowcount or 0


async def run_revoked_token_cleanup_loop() -> None:
    """Sweep expired denylist rows on a fixed interval until cancelled."""
    while True:
        try:
            removed = await purge_expired_revoked_tokens()
            if removed:
                logger.info("revoked_tokens cleanup: removed %d expired row(s)", removed)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - never let a transient DB error kill the loop
            logger.exception("revoked_tokens cleanup failed; will retry next interval")
        await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
