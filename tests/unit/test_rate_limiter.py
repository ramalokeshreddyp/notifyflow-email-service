import pytest
from api.src.services.rate_limiter import RateLimiter
from tests.conftest import MockRedis


class TestRateLimiter:
    @pytest.mark.asyncio
    async def test_rate_limiter_allows_under_limit(self):
        redis = MockRedis()
        limiter = RateLimiter(redis_client=redis, max_requests=3, window_seconds=60)

        # 1st request
        is_limited, count, limit, ttl = await limiter.is_rate_limited("192.168.1.1")
        assert not is_limited
        assert count == 1
        assert limit == 3

        # 2nd request
        is_limited, count, limit, ttl = await limiter.is_rate_limited("192.168.1.1")
        assert not is_limited
        assert count == 2

        # 3rd request (at threshold)
        is_limited, count, limit, ttl = await limiter.is_rate_limited("192.168.1.1")
        assert not is_limited
        assert count == 3

    @pytest.mark.asyncio
    async def test_rate_limiter_blocks_exceeding_limit(self):
        redis = MockRedis()
        limiter = RateLimiter(redis_client=redis, max_requests=2, window_seconds=60)

        await limiter.is_rate_limited("10.0.0.1")  # count: 1
        await limiter.is_rate_limited("10.0.0.1")  # count: 2

        # 3rd request (exceeds limit 2)
        is_limited, count, limit, ttl = await limiter.is_rate_limited("10.0.0.1")
        assert is_limited
        assert count == 3
        assert limit == 2
        assert ttl > 0

    @pytest.mark.asyncio
    async def test_rate_limiter_differentiates_ips(self):
        redis = MockRedis()
        limiter = RateLimiter(redis_client=redis, max_requests=1, window_seconds=60)

        # IP 1 uses quota
        is_limited1, count1, _, _ = await limiter.is_rate_limited("1.1.1.1")
        assert not is_limited1
        assert count1 == 1

        # IP 1 exceeds
        is_limited1_2, count1_2, _, _ = await limiter.is_rate_limited("1.1.1.1")
        assert is_limited1_2

        # IP 2 has separate quota
        is_limited2, count2, _, _ = await limiter.is_rate_limited("2.2.2.2")
        assert not is_limited2
        assert count2 == 1

    @pytest.mark.asyncio
    async def test_rate_limiter_handles_none_redis(self):
        limiter = RateLimiter(redis_client=None, max_requests=5, window_seconds=60)
        is_limited, count, limit, ttl = await limiter.is_rate_limited("127.0.0.1")
        assert not is_limited
        assert limit == 5
