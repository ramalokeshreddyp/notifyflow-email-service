import json
import logging
from typing import Optional, Any, Dict
import redis.asyncio as aioredis
from worker.src.config import settings

logger = logging.getLogger("worker.cache")


class WorkerCacheService:
    def __init__(self, redis_url: str = settings.REDIS_URL):
        self.redis_url = redis_url
        self.client: Optional[aioredis.Redis] = None

    async def connect(self):
        try:
            self.client = aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
            )
            await self.client.ping()
            logger.info("Worker connected successfully to Redis cache.")
        except Exception as e:
            logger.warning(f"Worker failed to connect to Redis at {self.redis_url}: {e}")

    async def close(self):
        if self.client:
            await self.client.close()
            logger.info("Worker Redis connection closed.")

    async def get_template(self, template_id: str) -> Optional[Dict[str, Any]]:
        if not self.client:
            return None
        try:
            key = f"template:{template_id}"
            data = await self.client.get(key)
            if data:
                logger.debug(f"Worker Cache HIT for template: {template_id}")
                return json.loads(data)
            logger.debug(f"Worker Cache MISS for template: {template_id}")
            return None
        except Exception as e:
            logger.error(f"Worker error reading template from Redis cache: {e}")
            return None

    async def set_template(
        self,
        template_id: str,
        template_data: Dict[str, Any],
        ttl: int = settings.CACHE_TTL_SECONDS,
    ) -> bool:
        if not self.client:
            return False
        try:
            key = f"template:{template_id}"
            await self.client.set(key, json.dumps(template_data), ex=ttl)
            return True
        except Exception as e:
            logger.error(f"Worker error setting template in Redis cache: {e}")
            return False

    async def get_user_preferences(self, email: str) -> Optional[Dict[str, Any]]:
        if not self.client:
            return None
        try:
            key = f"user_prefs:{email.lower().strip()}"
            data = await self.client.get(key)
            if data:
                logger.debug(f"Worker Cache HIT for user preferences: {email}")
                return json.loads(data)
            logger.debug(f"Worker Cache MISS for user preferences: {email}")
            return None
        except Exception as e:
            logger.error(f"Worker error reading user preferences from Redis cache: {e}")
            return None

    async def set_user_preferences(
        self,
        email: str,
        prefs_data: Dict[str, Any],
        ttl: int = settings.CACHE_TTL_SECONDS,
    ) -> bool:
        if not self.client:
            return False
        try:
            key = f"user_prefs:{email.lower().strip()}"
            await self.client.set(key, json.dumps(prefs_data), ex=ttl)
            return True
        except Exception as e:
            logger.error(f"Worker error setting user preferences in Redis cache: {e}")
            return False


worker_cache_service = WorkerCacheService()
