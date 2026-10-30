"""Tiny in-memory sliding-window rate limiter for outgoing email.

State lives in the process, so it resets on restart and is per-worker. That is
enough to stop a public form from being used to spam a third party's inbox on a
single self-hosted instance.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Deque, Dict, Optional

WINDOW_SECONDS = 3600
IP_LIMIT = 10  # emails triggered per client IP per window
ADDRESS_LIMIT = 5  # emails sent to one recipient address per window
EVENT_NOTICE_LIMIT = 20  # host "new dish" notices per event per window
LINK_RESEND_LIMIT = 3  # management-link resends per event per window
LOOKUP_IP_LIMIT = 10  # "find my events" requests per client IP per window
LOOKUP_ADDRESS_LIMIT = 2  # lookup emails sent to one address per window

_SWEEP_THRESHOLD = 5000


class RateLimiter:
    def __init__(self) -> None:
        self._hits: Dict[str, Deque[float]] = {}
        self._lock = threading.Lock()

    def allow(
        self,
        key: str,
        limit: int,
        window: float = WINDOW_SECONDS,
        now: Optional[float] = None,
    ) -> bool:
        """Record a hit for ``key`` and return False if it exceeds ``limit``."""

        current = time.monotonic() if now is None else now
        cutoff = current - window
        with self._lock:
            if len(self._hits) > _SWEEP_THRESHOLD:
                self._sweep(cutoff)
            hits = self._hits.setdefault(key, deque())
            while hits and hits[0] <= cutoff:
                hits.popleft()
            if len(hits) >= limit:
                return False
            hits.append(current)
            return True

    def is_limited(self, key: str, limit: int, window: float = WINDOW_SECONDS) -> bool:
        """Return True if ``key`` is at ``limit``, without recording a hit."""

        cutoff = time.monotonic() - window
        with self._lock:
            hits = self._hits.get(key, ())
            return sum(1 for hit in hits if hit > cutoff) >= limit

    def _sweep(self, cutoff: float) -> None:
        for key in [k for k, v in self._hits.items() if not v or v[-1] <= cutoff]:
            del self._hits[key]

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = RateLimiter()
