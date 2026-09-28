import pytest
import json
from unittest.mock import AsyncMock
from httpx import AsyncClient
from api.src.services.rabbitmq_service import rabbitmq_service
from worker.src.consumer import NotificationWorker
from worker.src.template_engine import template_engine
from tests.conftest import MockRedis


class TestNotificationFlow:
    @pytest.mark.asyncio
    async def test_full_end_to_end_notification_flow(self, client: AsyncClient, mock_redis: MockRedis):
        # Intercept messages published to RabbitMQ
        published_messages = []

        async def fake_publish(payload, routing_key=None):
            published_messages.append(payload)
            return True

        rabbitmq_service.publish_notification = AsyncMock(side_effect=fake_publish)

        # 1. API receives request
        request_data = {
            "recipient_email": "john.doe@example.com",
            "template_id": "order-confirmation",
            "dynamic_data": {
                "order_id": "ORD-554433",
                "customer_name": "Lokesh",
                "product_name": "Ultra Cloud Instance",
            },
        }

        response = await client.post("/api/notifications/email", json=request_data)
        assert response.status_code == 202
        resp_json = response.json()
        assert resp_json["status"] == "queued"
        assert len(published_messages) == 1

        # 2. Worker receives message from queue
        queued_message = published_messages[0]
        assert queued_message["recipient_email"] == "john.doe@example.com"
        assert queued_message["template_id"] == "order-confirmation"

        worker = NotificationWorker()
        worker.get_user_preferences = AsyncMock(
            return_value={"user_id": "usr-1", "email": "john.doe@example.com", "email_opt_out": False}
        )
        worker.get_template = AsyncMock(
            return_value={
                "id": "order-confirmation",
                "name": "Order Confirmation",
                "subject_template": "Order #{{ order_id }} Confirmed",
                "body_template": "Hello {{ customer_name }}, order for {{ product_name }} is ready.",
                "language": "en",
            }
        )

        # 3. Worker processes message
        process_result = await worker.process_notification(queued_message)
        assert process_result is True

        # 4. Verify rendered output
        subj, body = template_engine.render(
            "Order #{{ order_id }} Confirmed",
            "Hello {{ customer_name }}, order for {{ product_name }} is ready.",
            queued_message["dynamic_data"],
        )
        assert subj == "Order #ORD-554433 Confirmed"
        assert "Hello Lokesh, order for Ultra Cloud Instance is ready." in body
