import pytest
from pydantic import ValidationError
from api.src.models.schemas import (
    EmailNotificationRequest,
    EmailNotificationResponse,
    TemplateCreate,
    UserPreferenceCreate,
)


class TestApiValidation:
    def test_valid_notification_request(self):
        payload = {
            "recipient_email": "customer@example.com",
            "template_id": "order-confirmation",
            "dynamic_data": {"order_id": "12345", "customer_name": "Alice"},
        }
        req = EmailNotificationRequest(**payload)
        assert req.recipient_email == "customer@example.com"
        assert req.template_id == "order-confirmation"
        assert req.dynamic_data["order_id"] == "12345"

    def test_invalid_email_format_raises_error(self):
        invalid_emails = [
            "not-an-email",
            "@missingusername.com",
            "user@.com",
            "user@com",
            "",
        ]
        for email in invalid_emails:
            with pytest.raises(ValidationError):
                EmailNotificationRequest(
                    recipient_email=email,
                    template_id="order-confirmation",
                    dynamic_data={},
                )

    def test_missing_template_id_raises_error(self):
        with pytest.raises(ValidationError):
            EmailNotificationRequest(
                recipient_email="valid@example.com",
                template_id="",
                dynamic_data={},
            )

    def test_dynamic_data_defaults_to_dict(self):
        req = EmailNotificationRequest(
            recipient_email="user@example.com",
            template_id="welcome-email",
        )
        assert isinstance(req.dynamic_data, dict)
        assert req.dynamic_data == {}

    def test_template_create_validation(self):
        valid_template = TemplateCreate(
            id="new-tmpl",
            name="New Template",
            subject_template="Subject {{ var }}",
            body_template="Body {{ var }}",
            language="en",
        )
        assert valid_template.id == "new-tmpl"

        with pytest.raises(ValidationError):
            TemplateCreate(
                id="",
                name="",
                subject_template="",
                body_template="",
            )

    def test_user_preference_create_validation(self):
        valid_pref = UserPreferenceCreate(
            user_id="usr-123",
            email="user@domain.com",
            email_opt_out=False,
            preferred_language="en",
        )
        assert valid_pref.email == "user@domain.com"
        assert valid_pref.email_opt_out is False

        with pytest.raises(ValidationError):
            UserPreferenceCreate(
                user_id="",
                email="invalid-email",
            )
