import os
import json
import pytest
from typing import AsyncGenerator, Dict, Any, Optional
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import StaticPool

# Set test environment
os.environ["ENVIRONMENT"] = "testing"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["RABBITMQ_URL"] = "amqp://guest:guest@localhost:5672/"
os.environ["RATE_LIMIT_PER_MINUTE"] = "5"

from api.src.database import Base, get_db
from api.src.models.db_models import NotificationTemplate, UserPreference
from api.src.services.cache_service import cache_service
from api.src.services.rate_limiter import rate_limiter
from api.src.services.rabbitmq_service import rabbitmq_service
from api.src.main import app


class MockRedis:
    def __init__(self):
        self.store: Dict[str, str] = {}
        self.ttls: Dict[str, int] = {}

    async def get(self, key: str) -> Optional[str]:
        return self.store.get(key)

    async def set(self, key: str, value: str, ex: Optional[int] = None) -> bool:
        self.store[key] = str(value)
        if ex:
            self.ttls[key] = ex
        return True

    async def delete(self, key: str) -> int:
        if key in self.store:
            del self.store[key]
            self.ttls.pop(key, None)
            return 1
        return 0

    async def ping(self) -> bool:
        return True

    async def expire(self, key: str, seconds: int) -> bool:
        if key in self.store:
            self.ttls[key] = seconds
            return True
        return False

    def pipeline(self):
        return MockRedisPipeline(self)


class MockRedisPipeline:
    def __init__(self, redis: MockRedis):
        self.redis = redis
        self.ops = []

    def incr(self, key: str):
        self.ops.append(("incr", key))
        return self

    def ttl(self, key: str):
        self.ops.append(("ttl", key))
        return self

    async def execute(self):
        results = []
        for op, key in self.ops:
            if op == "incr":
                val = int(self.redis.store.get(key, 0)) + 1
                self.redis.store[key] = str(val)
                results.append(val)
            elif op == "ttl":
                ttl = self.redis.ttls.get(key, -1)
                results.append(ttl)
        self.ops = []
        return results


@pytest.fixture
def mock_redis():
    return MockRedis()


@pytest.fixture
async def test_db_session():
    # In-memory SQLite async engine
    test_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    test_async_session = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Seed initial test data
    async with test_async_session() as session:
        t1 = NotificationTemplate(
            id="order-confirmation",
            name="Order Confirmation",
            subject_template="Order Confirmation #{{ order_id }}",
            body_template="Hello {{ customer_name }}, your order for {{ product_name }} is confirmed!",
            language="en",
        )
        t2 = NotificationTemplate(
            id="password-reset",
            name="Password Reset",
            subject_template="Password Reset Request",
            body_template="Hi {{ user_name }}, reset your password at {{ reset_link }}.",
            language="en",
        )
        t3 = NotificationTemplate(
            id="account-alert",
            name="Account Alert",
            subject_template="Security Alert: {{ alert_type }}",
            body_template="Dear {{ user_name }}, login from {{ device }} at {{ location }}.",
            language="en",
        )
        u1 = UserPreference(
            user_id="usr-1",
            email="john.doe@example.com",
            email_opt_out=False,
            preferred_language="en",
        )
        u2 = UserPreference(
            user_id="usr-2",
            email="optedout.user@example.com",
            email_opt_out=True,
            preferred_language="en",
        )
        session.add_all([t1, t2, t3, u1, u2])
        await session.commit()

    async with test_async_session() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest.fixture
async def client(test_db_session: AsyncSession, mock_redis: MockRedis) -> AsyncGenerator[AsyncClient, None]:
    # Mock Redis client
    cache_service.client = mock_redis
    rate_limiter.client = mock_redis

    # Mock RabbitMQ service
    rabbitmq_service.publish_notification = AsyncMock(return_value=True)
    rabbitmq_service.health_check = AsyncMock(return_value=True)

    async def override_get_db():
        yield test_db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
