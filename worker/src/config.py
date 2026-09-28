import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    # PostgreSQL Database
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "notification_db"
    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@postgres:5432/notification_db"
    )

    # Redis Cache
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_URL: str = Field(default="redis://redis:6379/0")
    CACHE_TTL_SECONDS: int = 3600

    # RabbitMQ Message Broker
    RABBITMQ_HOST: str = "rabbitmq"
    RABBITMQ_PORT: int = 5672
    RABBITMQ_USER: str = "guest"
    RABBITMQ_PASSWORD: str = "guest"
    RABBITMQ_URL: str = Field(default="amqp://guest:guest@rabbitmq:5672/")
    RABBITMQ_QUEUE: str = "email_notifications"
    RABBITMQ_EXCHANGE: str = "notifications_exchange"
    RABBITMQ_ROUTING_KEY: str = "notification.email"
    RABBITMQ_DEAD_LETTER_QUEUE: str = "email_notifications_dlq"
    RABBITMQ_DEAD_LETTER_EXCHANGE: str = "notifications_dlx"
    
    # Consumer Settings
    CONSUMER_PREFETCH_COUNT: int = 10
    HEARTBEAT_FILE_PATH: str = "/tmp/worker_heartbeat"


settings = Settings()
