import time
from collections import defaultdict, deque

import redis

from app.core.config import Settings


class RateLimiter:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._fallback: dict[str, deque[float]] = defaultdict(deque)
        try:
            self.redis = redis.Redis.from_url(settings.redis_url, decode_responses=True)
            self.redis.ping()
        except Exception:
            self.redis = None

    def allow(self, key: str) -> bool:
        now = time.time()
        window = 1.0
        if self.redis:
            rkey = f"ratelimit:{key}"
            pipe = self.redis.pipeline()
            pipe.zremrangebyscore(rkey, 0, now - window)
            pipe.zcard(rkey)
            pipe.zadd(rkey, {str(now): now})
            pipe.expire(rkey, 2)
            _, count, _, _ = pipe.execute()
            return int(count) < self.settings.rate_limit_qps

        dq = self._fallback[key]
        while dq and dq[0] < now - window:
            dq.popleft()
        if len(dq) >= self.settings.rate_limit_qps:
            return False
        dq.append(now)
        return True
