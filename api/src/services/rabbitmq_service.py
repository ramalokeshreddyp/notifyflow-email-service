import json
import logging
from typing import Optional, Dict, Any
import aio_pika
from aio_pika import Message, DeliveryMode, ExchangeType
from api.src.config import settings

logger = logging.getLogger("api.rabbitmq")


class RabbitMQService:
    def __init__(self, rabbitmq_url: str = settings.RABBITMQ_URL):
        self.rabbitmq_url = rabbitmq_url
        self.connection: Optional[aio_pika.RobustConnection] = None
        self.channel: Optional[aio_pika.RobustChannel] = None
        self.exchange: Optional[aio_pika.RobustExchange] = None
        self.queue: Optional[aio_pika.RobustQueue] = None

    async def connect(self):
        """Establish connection, channel, exchanges, and queues with RabbitMQ."""
        try:
            self.connection = await aio_pika.connect_robust(
                self.rabbitmq_url,
                timeout=10,
            )
            self.channel = await self.connection.channel()
            await self.channel.set_qos(prefetch_count=10)

            # Declare Dead Letter Exchange and Dead Letter Queue
            dlx = await self.channel.declare_exchange(
                settings.RABBITMQ_DEAD_LETTER_EXCHANGE,
                ExchangeType.DIRECT,
                durable=True,
            )
            dlq = await self.channel.declare_queue(
                settings.RABBITMQ_DEAD_LETTER_QUEUE,
                durable=True,
            )
            await dlq.bind(dlx, routing_key="dead_letter")

            # Declare Main Notifications Topic Exchange
            self.exchange = await self.channel.declare_exchange(
                settings.RABBITMQ_EXCHANGE,
                ExchangeType.TOPIC,
                durable=True,
            )

            # Declare Main Notifications Queue with Dead Letter routing
            self.queue = await self.channel.declare_queue(
                settings.RABBITMQ_QUEUE,
                durable=True,
                arguments={
                    "x-dead-letter-exchange": settings.RABBITMQ_DEAD_LETTER_EXCHANGE,
                    "x-dead-letter-routing-key": "dead_letter",
                },
            )

            # Bind Queue to Exchange
            await self.queue.bind(self.exchange, routing_key=settings.RABBITMQ_ROUTING_KEY)

            logger.info(
                f"RabbitMQ connected and initialized: Exchange='{settings.RABBITMQ_EXCHANGE}', "
                f"Queue='{settings.RABBITMQ_QUEUE}', RoutingKey='{settings.RABBITMQ_ROUTING_KEY}'"
            )
        except Exception as e:
            logger.warning(f"Failed to connect to RabbitMQ broker at {self.rabbitmq_url}: {e}")

    async def close(self):
        """Close connection and channel."""
        if self.connection and not self.connection.is_closed:
            await self.connection.close()
            logger.info("RabbitMQ connection closed.")

    async def health_check(self) -> bool:
        """Check if RabbitMQ connection and channel are open, reconnecting if needed."""
        if not self.connection or self.connection.is_closed or not self.channel or self.channel.is_closed:
            try:
                await self.connect()
            except Exception:
                return False
        return bool(self.connection and not self.connection.is_closed and self.channel and not self.channel.is_closed)

    async def publish_notification(
        self,
        payload: Dict[str, Any],
        routing_key: str = settings.RABBITMQ_ROUTING_KEY,
    ) -> bool:
        """
        Publish a persistent notification event to RabbitMQ with automatic reconnect.
        """
        if not self.exchange or (self.connection and self.connection.is_closed) or not self.channel or self.channel.is_closed:
            logger.info("RabbitMQ exchange not ready. Attempting reconnect...")
            await self.connect()

        if not self.exchange or (self.connection and self.connection.is_closed):
            logger.error("Cannot publish notification: RabbitMQ exchange is not available.")
            raise RuntimeError("RabbitMQ broker service is currently unavailable.")

        try:
            body = json.dumps(payload, default=str).encode("utf-8")
            notification_id = payload.get("notification_id", "")

            message = Message(
                body=body,
                delivery_mode=DeliveryMode.PERSISTENT,
                content_type="application/json",
                content_encoding="utf-8",
                message_id=notification_id,
                headers={"source": "api-service", "version": "1.0"},
            )

            await self.exchange.publish(
                message,
                routing_key=routing_key,
            )
            logger.info(
                f"Published notification event [ID: {notification_id}] to exchange '{settings.RABBITMQ_EXCHANGE}' "
                f"with routing key '{routing_key}'"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to publish notification message to RabbitMQ: {e}", exc_info=True)
            raise


rabbitmq_service = RabbitMQService()
