from datetime import datetime
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, EmailStr, Field, ConfigDict


class EmailNotificationRequest(BaseModel):
    recipient_email: EmailStr = Field(
        ...,
        description="The destination email address for the notification",
        examples=["user@example.com"],
    )
    template_id: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Identifier of the pre-configured email template",
        examples=["order-confirmation"],
    )
    dynamic_data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Key-value dynamic parameters to inject into the template",
        examples=[{"order_id": "#12345", "product_name": "Widget Pro", "customer_name": "John Doe"}],
    )


class EmailNotificationResponse(BaseModel):
    notification_id: str = Field(..., description="Unique UUID tracking ID for the notification")
    status: str = Field(default="queued", description="Status of the notification request")
    message: str = Field(..., description="Human-readable processing status message")
    recipient_email: str = Field(..., description="Target recipient email")
    template_id: str = Field(..., description="Template ID applied")
    timestamp: datetime = Field(..., description="ISO 8601 timestamp when the request was accepted")


class TemplateCreate(BaseModel):
    id: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=255)
    subject_template: str = Field(..., min_length=1)
    body_template: str = Field(..., min_length=1)
    language: str = Field(default="en", max_length=10)


class TemplateUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    subject_template: Optional[str] = None
    body_template: Optional[str] = None
    language: Optional[str] = None


class TemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    subject_template: str
    body_template: str
    language: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class UserPreferenceCreate(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    email_opt_out: bool = False
    preferred_language: str = Field(default="en", max_length=10)


class UserPreferenceUpdate(BaseModel):
    email_opt_out: Optional[bool] = None
    preferred_language: Optional[str] = None


class UserPreferenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: str
    email: str
    email_opt_out: bool
    preferred_language: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class HealthServiceStatus(BaseModel):
    status: str
    details: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    timestamp: datetime
    services: Dict[str, HealthServiceStatus]
