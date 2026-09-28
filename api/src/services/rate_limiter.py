import logging
from typing import Tuple, Optional
import redis.asyncio as aioredis
from api.src.config import settings

logger = logging.getLogger("api.rate_limiter")


class RateLimiter:
    def __init__(
        self,
        redis_client: Optional[aioredis.Redis] = None,
        max_requests: int = settings.RATE_LIMIT_PER_MINUTE,
        window_seconds: int = settings.RATE_LIMIT_WINDOW_SECONDS,
    ):
        self.client = redis_client
        self.max_requests = max_requests
        self.window_seconds = window_seconds

    def set_client(self, client: aioredis.Redis):
        self.client = client

    async def is_rate_limited(self, client_ip: str) -> Tuple[bool, int, int, int]:
        """
        Check and record an incoming request for rate limiting.
        
        Returns:
            Tuple[is_limited (bool), current_count (int), limit (int), reset_seconds (int)]
        """
        if not self.client:
            logger.warning("Redis client not initialized for rate limiter. Allowing request.")
            return False, 0, self.max_requests, 0

        key = f"rate_limit:ip:{client_ip}"
        try:
            # Atomic pipeline: increment and set TTL if new key
            pipe = self.client.pipeline()
            pipe.incr(key)
            pipe.ttl(key)
            results = await pipe.execute()

            current_count = results[0]
            ttl = results[1]

            # If this is the first request in the window (ttl was -1), set the expiration
            if ttl == -1 or current_count == 1:
                await self.client.expire(key, self.window_seconds)
                ttl = self.window_seconds
            elif ttl == -2:
                # Key expired right between INCR and TTL
                await self.client.expire(key, self.window_seconds)
                ttl = self.window_seconds

            is_limited = current_count > self.max_requests
            if is_limited:
                logger.warning(
                    f"Rate limit exceeded for IP {client_ip}: {current_count}/{self.max_requests} in {self.window_seconds}s"
                )

            return is_limited, current_count, self.max_requests, max(0, ttl)

        except Exception as e:
            logger.error(f"Rate limiting check error for IP {client_ip}: {e}", exc_info=True)
            # Fail-open policy so service remains accessible if cache is temporarily degraded
            return False, 0, self.max_requests, 0


rate_limiter = RateLimiter()
