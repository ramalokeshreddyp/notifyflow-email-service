import pytest
from api.src.services.cache_service import CacheService
from tests.conftest import MockRedis


class TestCacheService:
    @pytest.mark.asyncio
    async def test_template_caching_and_retrieval(self):
        redis = MockRedis()
        service = CacheService()
        service.client = redis

        template_data = {
            "id": "order-confirmation",
            "name": "Order Confirmation",
            "subject_template": "Order {{ id }}",
            "body_template": "Body {{ id }}",
            "language": "en",
        }

        # Cache Miss initially
        miss = await service.get_template("order-confirmation")
        assert miss is None

        # Set in cache
        success = await service.set_template("order-confirmation", template_data, ttl=3600)
        assert success is True

        # Cache Hit
        hit = await service.get_template("order-confirmation")
        assert hit is not None
        assert hit["id"] == "order-confirmation"
        assert hit["name"] == "Order Confirmation"

    @pytest.mark.asyncio
    async def test_template_cache_invalidation(self):
        redis = MockRedis()
        service = CacheService()
        service.client = redis

        await service.set_template("temp-id", {"name": "Temp"})
        assert await service.get_template("temp-id") is not None

        # Delete
        await service.delete_template("temp-id")
        assert await service.get_template("temp-id") is None

    @pytest.mark.asyncio
    async def test_user_preferences_caching_and_case_insensitivity(self):
        redis = MockRedis()
        service = CacheService()
        service.client = redis

        prefs = {
            "user_id": "usr-99",
            "email": "user@example.com",
            "email_opt_out": False,
            "preferred_language": "en",
        }

        await service.set_user_preferences("User@Example.COM", prefs, ttl=1800)

        # Retrieval with mixed case
        hit = await service.get_user_preferences("user@example.com")
        assert hit is not None
        assert hit["user_id"] == "usr-99"

        # Invalidation
        await service.delete_user_preferences("USER@EXAMPLE.COM")
        assert await service.get_user_preferences("user@example.com") is None
