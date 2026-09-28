import asyncio
import json
import logging
import os
import signal
import sys
import time
from typing import Optional, Dict, Any

import aio_pika
from sqlalchemy import select

from worker.src.config import settings
from worker.src.database import async_session_factory
from worker.src.models import NotificationTemplate, UserPreference
from worker.src.cache_service import worker_cache_service
from worker.src.template_engine import template_engine

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("worker.consumer")


class NotificationWorker:
    def __init__(self):
        self.is_running = False
        self.connection: Optional[aio_pika.RobustConnection] = None
        self.channel: Optional[aio_pika.RobustChannel] = None
        self.queue: Optional[aio_pika.RobustQueue] = None

    def update_heartbeat(self):
        """Write current timestamp to heartbeat file for container healthcheck."""
        try:
            os.makedirs(os.path.dirname(settings.HEARTBEAT_FILE_PATH), exist_ok=True)
            with open(settings.HEARTBEAT_FILE_PATH, "w") as f:
                f.write(str(time.time()))
        except Exception as e:
            logger.debug(f"Could not write heartbeat file: {e}")

    async def get_template(self, template_id: str) -> Optional[Dict[str, Any]]:
        """Fetch template from Redis cache or database."""
        # 1. Try Redis Cache
        cached = await worker_cache_service.get_template(template_id)
        if cached:
            return cached

        # 2. Database Fallback
        async with async_session_factory() as session:
            try:
                result = await session.execute(
                    select(NotificationTemplate).where(NotificationTemplate.id == template_id)
                )
                template_obj = result.scalar_one_or_none()
                if template_obj:
                    template_dict = template_obj.to_dict()
                    await worker_cache_service.set_template(template_id, template_dict)
                    return template_dict
            except Exception as e:
                logger.error(f"Error fetching template from DB: {e}")
        return None

    async def get_user_preferences(self, email: str) -> Dict[str, Any]:
        """Fetch user preferences from Redis cache or database."""
        clean_email = email.lower().strip()
        # 1. Try Redis Cache
        cached = await worker_cache_service.get_user_preferences(clean_email)
        if cached:
            return cached

        # 2. Database Fallback
        async with async_session_factory() as session:
            try:
                result = await session.execute(
                    select(UserPreference).where(UserPreference.email == clean_email)
                )
                pref_obj = result.scalar_one_or_none()
                if pref_obj:
                    pref_dict = pref_obj.to_dict()
                    await worker_cache_service.set_user_preferences(clean_email, pref_dict)
                    return pref_dict
            except Exception as e:
                logger.error(f"Error fetching user preferences from DB: {e}")

        # Default preferences if not recorded
        default_pref = {
            "user_id": None,
            "email": clean_email,
            "email_opt_out": False,
            "preferred_language": "en",
        }
        await worker_cache_service.set_user_preferences(clean_email, default_pref, ttl=300)
        return default_pref

    async def process_notification(self, payload: Dict[str, Any]) -> bool:
        """
        Process a single notification event.
        Returns True on successful handling (including valid opt-out skips).
        """
        notification_id = payload.get("notification_id", "UNKNOWN")
        recipient_email = payload.get("recipient_email", "").strip()
        template_id = payload.get("template_id", "").strip()
        dynamic_data = payload.get("dynamic_data", {})

        logger.info(f"Processing notification [ID: {notification_id}] for recipient '{recipient_email}'")

        if not recipient_email or not template_id:
            logger.error(
                f"[POISON_MESSAGE] Missing required fields in notification {notification_id}. "
                f"Payload: {payload}"
            )
            return False

        # 1. Check User Notification Preferences & Opt-Out Status
        user_prefs = await self.get_user_preferences(recipient_email)
        if user_prefs.get("email_opt_out", False):
            logger.info(
                f"[NOTIFICATION_SKIPPED] Recipient '{recipient_email}' has opted out of email notifications. "
                f"(Notification ID: {notification_id})"
            )
            return True

        # 2. Retrieve Email Template
        template_data = await self.get_template(template_id)
        if not template_data:
            logger.error(
                f"[POISON_MESSAGE] Template '{template_id}' could not be resolved for Notification ID: {notification_id}."
            )
            return False

        subject_template = template_data.get("subject_template", "")
        body_template = template_data.get("body_template", "")

        # 3. Render Template with Dynamic Data
        try:
            rendered_subject, rendered_body = template_engine.render(
                subject_template=subject_template,
                body_template=body_template,
                dynamic_data=dynamic_data,
            )
        except Exception as e:
            logger.error(
                f"[RENDERING_ERROR] Failed to render template '{template_id}' for Notification ID {notification_id}: {e}"
            )
            return False

        # 4. Simulate Email Dispatch
        separator = "=" * 60
        logger.info(
            f"\n{separator}\n"
            f"[EMAIL_DISPATCHED] Simulated Transactional Email Sent Successfully\n"
            f"Notification ID: {notification_id}\n"
            f"Recipient:       {recipient_email}\n"
            f"Template ID:     {template_id} ({template_data.get('name', 'Template')})\n"
            f"Subject:         {rendered_subject}\n"
            f"------------------- Email Body -------------------\n"
            f"{rendered_body}\n"
            f"{separator}"
        )
        return True

    async def on_message_received(self, message: aio_pika.IncomingMessage):
        """Handler for incoming messages with poison message protection."""
        self.update_heartbeat()
        async with message.process(requeue=False, ignore_processed=True):
            try:
                body_str = message.body.decode("utf-8")
                payload = json.loads(body_str)
                await self.process_notification(payload)
            except json.JSONDecodeError as e:
                logger.error(f"[POISON_MESSAGE] Malformed JSON payload received: {e}. Body: {message.body}")
            except Exception as e:
                logger.error(f"Unexpected error handling message: {e}", exc_info=True)
            # Message is acknowledged automatically at the end of the context manager block
            # requeue=False ensures failed/poison messages are not requeued indefinitely

    async def start(self):
        """Main consumer loop with robust reconnection."""
        self.is_running = True
        await worker_cache_service.connect()

        retry_count = 0
        while self.is_running:
            try:
                logger.info(f"Connecting to RabbitMQ broker at {settings.RABBITMQ_URL}...")
                self.connection = await aio_pika.connect_robust(
                    settings.RABBITMQ_URL,
                    timeout=10,
                )
                self.channel = await self.connection.channel()
                await self.channel.set_qos(prefetch_count=settings.CONSUMER_PREFETCH_COUNT)

                # Ensure queue declaration matches API service
                self.queue = await self.channel.declare_queue(
                    settings.RABBITMQ_QUEUE,
                    durable=True,
                    arguments={
                        "x-dead-letter-exchange": settings.RABBITMQ_DEAD_LETTER_EXCHANGE,
                        "x-dead-letter-routing-key": "dead_letter",
                    },
                )

                logger.info(f"Worker listening for messages on queue '{settings.RABBITMQ_QUEUE}'...")
                retry_count = 0
                self.update_heartbeat()

                await self.queue.consume(self.on_message_received)

                # Keep worker running and emitting heartbeats
                while self.is_running and not self.connection.is_closed:
                    self.update_heartbeat()
                    await asyncio.sleep(5)

            except asyncio.CancelledError:
                logger.info("Worker consumer task cancelled.")
                break
            except Exception as e:
                retry_count += 1
                wait_time = min(2 ** retry_count, 15)
                logger.warning(
                    f"RabbitMQ connection lost or error occurred ({e}). Reconnecting in {wait_time}s..."
                )
                await asyncio.sleep(wait_time)

    async def stop(self):
        """Gracefully stop worker."""
        logger.info("Stopping Worker consumer...")
        self.is_running = False
        if self.connection and not self.connection.is_closed:
            await self.connection.close()
        await worker_cache_service.close()
        logger.info("Worker consumer shutdown complete.")


async def main():
    worker = NotificationWorker()

    def signal_handler():
        logger.info("Received termination signal. Initiating shutdown...")
        asyncio.create_task(worker.stop())

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, signal_handler)
        except NotImplementedError:
            # Signal handling on Windows
            pass

    try:
        await worker.start()
    except (KeyboardInterrupt, SystemExit):
        await worker.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        sys.exit(0)
