import logging
import time
from collections import defaultdict, deque

from upstash_ratelimit import SlidingWindow
from upstash_ratelimit.asyncio import Ratelimit
from upstash_redis.asyncio import Redis


logger = logging.getLogger(__name__)
WINDOW_SECONDS = 60


class RateLimiter:
    """Per-user sliding window: Upstash when configured, otherwise in memory."""

    def __init__(self, limit: int, upstash_url: str = "", upstash_token: str = ""):
        self.limit = limit
        self.upstash = None
        if upstash_url and upstash_token:
            self.upstash = Ratelimit(redis=Redis(url=upstash_url, token=upstash_token),
                                     limiter=SlidingWindow(max_requests=limit, window=WINDOW_SECONDS), prefix="layer")
        self.recent: dict[str, deque[float]] = defaultdict(deque)

    async def allow(self, user_id: str) -> bool:
        if self.upstash:
            try:
                return (await self.upstash.limit(user_id)).allowed
            except Exception:
                logger.warning("Upstash rate limit failed; using the in-memory limit", exc_info=True)
        return self._allow_in_memory(user_id)

    def _allow_in_memory(self, user_id: str) -> bool:
        # ponytail: per-process memory, so each server instance counts separately; Upstash covers multiple instances
        now = time.monotonic()
        recent = self.recent[user_id]
        while recent and now - recent[0] >= WINDOW_SECONDS:
            recent.popleft()
        if len(recent) >= self.limit:
            return False
        recent.append(now)
        return True
