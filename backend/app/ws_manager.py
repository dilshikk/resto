"""
WebSocket connection manager for real-time push notifications.

Usage
-----
  # In a WebSocket endpoint
  await ws_manager.connect(employee_id, websocket)
  try:
      while True:
          await websocket.receive_text()   # keep alive / handle pings
  except Exception:
      pass
  finally:
      await ws_manager.disconnect(employee_id, websocket)

  # From any async context (e.g. the notify() helper in notifications.py)
  await ws_manager.send(employee_id, {"event": "notification", ...})
"""

import asyncio
from collections import defaultdict

from fastapi import WebSocket


class ConnectionManager:
    """
    asyncio-safe registry of active WebSocket connections.

    One employee can have multiple concurrent sessions (multiple browser
    tabs, mobile + desktop, etc.).  Each is tracked individually so a
    disconnect on one tab does not affect the others.
    """

    def __init__(self) -> None:
        # employee_id → set of live WebSocket connections
        self._connections: dict[int, set[WebSocket]] = defaultdict(set)
        # Single lock guards all reads + writes to _connections so that
        # concurrent coroutines cannot corrupt the sets.
        self._lock = asyncio.Lock()

    async def connect(self, employee_id: int, ws: WebSocket) -> None:
        """Accept the WebSocket handshake and register the connection."""
        await ws.accept()
        async with self._lock:
            self._connections[employee_id].add(ws)

    async def disconnect(self, employee_id: int, ws: WebSocket) -> None:
        """Remove a closed/errored socket from the registry."""
        async with self._lock:
            sockets = self._connections.get(employee_id)
            if sockets:
                sockets.discard(ws)
                if not sockets:
                    del self._connections[employee_id]

    async def send(self, employee_id: int, payload: dict) -> None:
        """
        Broadcast *payload* as JSON to every active connection for *employee_id*.

        Dead sockets (connection closed between registration and this call)
        are silently removed from the registry.
        """
        async with self._lock:
            # Copy the set so we can iterate without holding the lock during I/O.
            sockets = list(self._connections.get(employee_id, []))

        dead: list[WebSocket] = []
        for ws in sockets:
            try:
                await ws.send_json(payload)
            except Exception:
                # Socket was closed or otherwise broken — clean it up below.
                dead.append(ws)

        if dead:
            async with self._lock:
                existing = self._connections.get(employee_id)
                if existing:
                    existing -= set(dead)
                    if not existing:
                        del self._connections[employee_id]

    def is_connected(self, employee_id: int) -> bool:
        """Return True if at least one active socket exists for *employee_id*."""
        return bool(self._connections.get(employee_id))

    @property
    def active_count(self) -> int:
        """Total number of live WebSocket connections across all employees."""
        return sum(len(s) for s in self._connections.values())


# ── Module-level singleton ────────────────────────────────────────────────────
#
# Imported by both notifications.py (for the WS endpoint and notify helper)
# and any other router that needs to push real-time events.
ws_manager = ConnectionManager()
