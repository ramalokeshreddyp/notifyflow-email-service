from api.src.models.db_models import NotificationTemplate, UserPreference
from api.src.models.schemas import (
    EmailNotificationRequest,
    EmailNotificationResponse,
    TemplateCreate,
    TemplateUpdate,
    TemplateResponse,
    UserPreferenceCreate,
    UserPreferenceUpdate,
    UserPreferenceResponse,
)

__all__ = [
    "NotificationTemplate",
    "UserPreference",
    "EmailNotificationRequest",
    "EmailNotificationResponse",
    "TemplateCreate",
    "TemplateUpdate",
    "TemplateResponse",
    "UserPreferenceCreate",
    "UserPreferenceUpdate",
    "UserPreferenceResponse",
]
