import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from worker.src.consumer import NotificationWorker
from tests.conftest import MockRedis


class TestWorkerConsumer:
    @pytest.mark.asyncio
    async def test_worker_skips_opted_out_user(self):
        worker = NotificationWorker()
        
        # Mock preferences with email_opt_out = True
        worker.get_user_preferences = AsyncMock(
            return_value={"user_id": "usr-opt", "email": "optedout@example.com", "email_opt_out": True}
        )
        worker.get_template = AsyncMock()

        payload = {
            "notification_id": "test-uuid-1",
            "recipient_email": "optedout@example.com",
            "template_id": "order-confirmation",
            "dynamic_data": {"order_id": "123"},
        }

        result = await worker.process_notification(payload)
        assert result is True
        # Template should not even be fetched if user opted out
        worker.get_template.assert_not_called()

    @pytest.mark.asyncio
    async def test_worker_processes_valid_notification(self):
        worker = NotificationWorker()
        
        worker.get_user_preferences = AsyncMock(
            return_value={"user_id": "usr-active", "email": "active@example.com", "email_opt_out": False}
        )
        worker.get_template = AsyncMock(
            return_value={
                "id": "welcome-email",
                "name": "Welcome",
                "subject_template": "Welcome, {{ user_name }}!",
                "body_template": "Hello {{ user_name }}, glad to have you.",
                "language": "en",
            }
        )

        payload = {
            "notification_id": "test-uuid-2",
            "recipient_email": "active@example.com",
            "template_id": "welcome-email",
            "dynamic_data": {"user_name": "Lokesh"},
        }

        result = await worker.process_notification(payload)
        assert result is True
        worker.get_template.assert_called_once_with("welcome-email")

    @pytest.mark.asyncio
    async def test_worker_handles_missing_template_poison_message(self):
        worker = NotificationWorker()
        
        worker.get_user_preferences = AsyncMock(
            return_value={"user_id": "usr-1", "email": "user@example.com", "email_opt_out": False}
        )
        # Template does not exist in cache or DB
        worker.get_template = AsyncMock(return_value=None)

        payload = {
            "notification_id": "test-uuid-3",
            "recipient_email": "user@example.com",
            "template_id": "non-existent-template",
            "dynamic_data": {},
        }

        # Should return False and not raise an unhandled exception
        result = await worker.process_notification(payload)
        assert result is False

    @pytest.mark.asyncio
    async def test_worker_handles_malformed_payload(self):
        worker = NotificationWorker()
        
        # Missing recipient_email and template_id
        payload = {"notification_id": "test-uuid-4"}
        result = await worker.process_notification(payload)
        assert result is False
