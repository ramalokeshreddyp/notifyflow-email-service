import json
import logging
from typing import Optional, Any, Dict
import redis.asyncio as aioredis
from api.src.config import settings

logger = logging.getLogger("api.cache")


class CacheService:
    def __init__(self, redis_url: str = settings.REDIS_URL):
        self.redis_url = redis_url
        self.client: Optional[aioredis.Redis] = None

    async def connect(self):
        """Initialize Redis connection pool."""
        try:
            self.client = aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
            )
            await self.client.ping()
            logger.info("Connected successfully to Redis cache.")
        except Exception as e:
            logger.warning(f"Failed to connect to Redis at {self.redis_url}: {e}")

    async def close(self):
        """Close Redis connection."""
        if self.client:
            await self.client.close()
            logger.info("Redis cache connection closed.")

    async def health_check(self) -> bool:
        """Check if Redis connection is active and responsive."""
        if not self.client:
            return False
        try:
            return await self.client.ping()
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return False

    # Template Caching (Key: template:<template_id>)
    async def get_template(self, template_id: str) -> Optional[Dict[str, Any]]:
        if not self.client:
            return None
        try:
            key = f"template:{template_id}"
            data = await self.client.get(key)
            if data:
                logger.debug(f"Cache HIT for template: {template_id}")
                return json.loads(data)
            logger.debug(f"Cache MISS for template: {template_id}")
            return None
        except Exception as e:
            logger.error(f"Error reading template from Redis cache: {e}")
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
            logger.debug(f"Cached template {template_id} with TTL {ttl}s")
            return True
        except Exception as e:
            logger.error(f"Error setting template in Redis cache: {e}")
            return False

    async def delete_template(self, template_id: str) -> bool:
        if not self.client:
            return False
        try:
            key = f"template:{template_id}"
            await self.client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Error invalidating template cache: {e}")
            return False

    # User Preferences Caching (Key: user_prefs:<email>)
    async def get_user_preferences(self, email: str) -> Optional[Dict[str, Any]]:
        if not self.client:
            return None
        try:
            key = f"user_prefs:{email.lower().strip()}"
            data = await self.client.get(key)
            if data:
                logger.debug(f"Cache HIT for user preferences: {email}")
                return json.loads(data)
            logger.debug(f"Cache MISS for user preferences: {email}")
            return None
        except Exception as e:
            logger.error(f"Error reading user preferences from Redis cache: {e}")
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
            logger.debug(f"Cached user preferences for {email} with TTL {ttl}s")
            return True
        except Exception as e:
            logger.error(f"Error setting user preferences in Redis cache: {e}")
            return False

    async def delete_user_preferences(self, email: str) -> bool:
        if not self.client:
            return False
        try:
            key = f"user_prefs:{email.lower().strip()}"
            await self.client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Error invalidating user preferences cache: {e}")
            return False


cache_service = CacheService()
