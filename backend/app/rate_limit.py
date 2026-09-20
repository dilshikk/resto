"""
Rate-limiting utilities for the MADO Checklist API.

Two protection layers:

1. Per-IP limiter (slowapi)
   Applied as @limiter.limit("N/minute") on individual endpoints.
   SlowAPI reads the client IP from the request and returns HTTP 429
   when the limit is exceeded.

2. Per-email lockout (LoginAttemptTracker)
   Tracks consecutive failed password attempts per email address.
   After MAX_FAILURES failures the account is locked for LOCKOUT_SECONDS.
   A successful login resets the counter.  This catches distributed
   brute-force attacks that rotate IPs to stay under the per-IP limit.

State for layer 2 is held in process memory.  This is sufficient for
a single-replica deployment (the common case here).  If the service
is ever scaled to multiple replicas, replace LoginAttemptTracker with
a Redis-backed counter using the `limits` library's RedisStorage.
"""

import time
import threading
from collections import defaultdict
from dataclasses import dataclass, field

from slowapi import Limiter
from slowapi.util import get_remote_address

# ── Layer 1: per-IP SlowAPI limiter ──────────────────────────────────────────
# Attach to the FastAPI app in main.py:
#   app.state.limiter = limiter
#   app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
# Then decorate endpoints:
#   @limiter.limit("10/minute")
#   async def login(request: Request, ...):
limiter = Limiter(key_func=get_remote_address)


# ── Layer 2: per-email in-process lockout ─────────────────────────────────────
_MAX_FAILURES: int = 5        # consecutive wrong passwords before lockout
_LOCKOUT_SECONDS: float = 900  # 15 minutes
_CLEANUP_INTERVAL: float = 3600  # purge stale entries every hour


@dataclass
class _AccountState:
    failures: int = 0
    locked_until: float = 0.0
    last_failure: float = field(default_factory=time.monotonic)


class LoginAttemptTracker:
    """
    Thread-safe per-email failure counter with automatic timed lockout.

    Usage::

        tracker = LoginAttemptTracker()

        # Before checking the password:
        if tracker.is_locked(email):
            raise HTTPException(429, f"Locked for {tracker.seconds_remaining(email)}s")

        # After a wrong password:
        tracker.record_failure(email)

        # After a correct password:
        tracker.record_success(email)
    """

    def __init__(
        self,
        max_failures: int = _MAX_FAILURES,
        lockout_seconds: float = _LOCKOUT_SECONDS,
    ) -> None:
        self._max_failures = max_failures
        self._lockout_seconds = lockout_seconds
        self._state: dict[str, _AccountState] = defaultdict(_AccountState)
        self._lock = threading.Lock()
        self._last_cleanup = time.monotonic()

    def is_locked(self, email: str) -> bool:
        """Return True if the account is currently locked out."""
        with self._lock:
            s = self._state.get(email)
            if s is None:
                return False
            return time.monotonic() < s.locked_until

    def seconds_remaining(self, email: str) -> int:
        """Seconds until the lockout expires (0 if not locked)."""
        with self._lock:
            s = self._state.get(email)
            if s is None:
                return 0
            remaining = s.locked_until - time.monotonic()
            return max(0, int(remaining))

    def record_failure(self, email: str) -> None:
        """Increment the failure counter; impose a lockout when the threshold is reached."""
        with self._lock:
            self._maybe_cleanup()
            s = self._state[email]
            s.failures += 1
            s.last_failure = time.monotonic()
            if s.failures >= self._max_failures:
                s.locked_until = time.monotonic() + self._lockout_seconds

    def record_success(self, email: str) -> None:
        """Clear the failure state after a successful login."""
        with self._lock:
            self._state.pop(email, None)

    def _maybe_cleanup(self) -> None:
        """Remove entries that have been inactive long enough to never lock again."""
        now = time.monotonic()
        if now - self._last_cleanup < _CLEANUP_INTERVAL:
            return
        # Keep entries whose lockout window could still be active.
        cutoff = now - self._lockout_seconds
        stale = [k for k, v in self._state.items() if v.last_failure < cutoff]
        for k in stale:
            del self._state[k]
        self._last_cleanup = now


# Module-level singleton — shared across all requests in the same process.
login_attempt_tracker = LoginAttemptTracker()
