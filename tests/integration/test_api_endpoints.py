import pytest
from httpx import AsyncClient


class TestApiEndpoints:
    @pytest.mark.asyncio
    async def test_health_endpoint(self, client: AsyncClient):
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "database" in data["services"]
        assert "redis" in data["services"]
        assert "rabbitmq" in data["services"]

    @pytest.mark.asyncio
    async def test_send_email_notification_success(self, client: AsyncClient):
        payload = {
            "recipient_email": "john.doe@example.com",
            "template_id": "order-confirmation",
            "dynamic_data": {
                "order_id": "ORD-12345",
                "customer_name": "John Doe",
                "product_name": "Premium Cloud Server",
            },
        }
        response = await client.post("/api/notifications/email", json=payload)
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "queued"
        assert data["recipient_email"] == "john.doe@example.com"
        assert data["template_id"] == "order-confirmation"
        assert "notification_id" in data
        assert "timestamp" in data
        # Check rate limit headers
        assert "x-ratelimit-limit" in response.headers
        assert "x-ratelimit-remaining" in response.headers

    @pytest.mark.asyncio
    async def test_send_email_notification_invalid_template(self, client: AsyncClient):
        payload = {
            "recipient_email": "john.doe@example.com",
            "template_id": "non-existent-template-id",
            "dynamic_data": {},
        }
        response = await client.post("/api/notifications/email", json=payload)
        assert response.status_code == 400
        data = response.json()
        assert "not found" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_send_email_notification_validation_error(self, client: AsyncClient):
        payload = {
            "recipient_email": "invalid-email-address",
            "template_id": "order-confirmation",
        }
        response = await client.post("/api/notifications/email", json=payload)
        assert response.status_code == 422  # FastAPI validation error status

    @pytest.mark.asyncio
    async def test_send_email_notification_rate_limiting(self, client: AsyncClient):
        # We configured RATE_LIMIT_PER_MINUTE=5 in conftest
        payload = {
            "recipient_email": "john.doe@example.com",
            "template_id": "order-confirmation",
            "dynamic_data": {"order_id": "1"},
        }
        
        # Send 5 valid requests
        for _ in range(5):
            res = await client.post("/api/notifications/email", json=payload)
            assert res.status_code == 202

        # 6th request must trigger 429 Too Many Requests
        rate_limited_res = await client.post("/api/notifications/email", json=payload)
        assert rate_limited_res.status_code == 429
        assert "retry-after" in rate_limited_res.headers

    @pytest.mark.asyncio
    async def test_templates_crud(self, client: AsyncClient):
        # List Templates
        res = await client.get("/api/templates")
        assert res.status_code == 200
        templates = res.json()
        assert len(templates) >= 3

        # Create New Template
        new_template = {
            "id": "signup-verification",
            "name": "Sign Up Verification",
            "subject_template": "Verify your email {{ code }}",
            "body_template": "Please use verification code {{ code }} to complete registration.",
            "language": "en",
        }
        create_res = await client.post("/api/templates", json=new_template)
        assert create_res.status_code == 201

        # Get Template by ID
        get_res = await client.get("/api/templates/signup-verification")
        assert get_res.status_code == 200
        assert get_res.json()["name"] == "Sign Up Verification"

        # Update Template
        update_payload = {"name": "Updated Sign Up Verification"}
        update_res = await client.put("/api/templates/signup-verification", json=update_payload)
        assert update_res.status_code == 200
        assert update_res.json()["name"] == "Updated Sign Up Verification"

        # Delete Template
        del_res = await client.delete("/api/templates/signup-verification")
        assert del_res.status_code == 204

    @pytest.mark.asyncio
    async def test_preferences_crud(self, client: AsyncClient):
        # Get Preference
        res = await client.get("/api/preferences/john.doe@example.com")
        assert res.status_code == 200
        assert res.json()["email_opt_out"] is False

        # Update Preference to Opt-Out
        update_res = await client.put(
            "/api/preferences/john.doe@example.com",
            json={"email_opt_out": True},
        )
        assert update_res.status_code == 200
        assert update_res.json()["email_opt_out"] is True
