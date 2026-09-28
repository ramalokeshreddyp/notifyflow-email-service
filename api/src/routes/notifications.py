import uuid
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from api.src.database import get_db
from api.src.models.db_models import NotificationTemplate, UserPreference
from api.src.models.schemas import EmailNotificationRequest, EmailNotificationResponse
from api.src.services.cache_service import cache_service
from api.src.services.rate_limiter import rate_limiter
from api.src.services.rabbitmq_service import rabbitmq_service
from api.src.config import settings

logger = logging.getLogger("api.notifications")
router = APIRouter(prefix="/api/notifications", tags=["Notifications"])


def get_client_ip(request: Request) -> str:
    """Extract client IP address considering proxy headers."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    if request.client and request.client.host:
        return request.client.host
    return "127.0.0.1"


@router.post(
    "/email",
    response_model=EmailNotificationResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Send Transactional Email Notification",
    description=(
        "Validates input payload, verifies template & user preferences with Redis cache, "
        "enforces rate limiting, and queues notification message asynchronously to RabbitMQ."
    ),
)
async def send_email_notification(
    payload: EmailNotificationRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    client_ip = get_client_ip(request)

    # 1. Rate Limiting Check via Redis
    is_limited, current_count, limit, reset_seconds = await rate_limiter.is_rate_limited(client_ip)

    if is_limited:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "Rate limit exceeded",
                "message": f"Maximum allowed requests ({limit} per minute) exceeded. Please retry in {reset_seconds} seconds.",
                "limit": limit,
                "current_count": current_count,
                "reset_in_seconds": reset_seconds,
            },
            headers={
                "Retry-After": str(reset_seconds),
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(reset_seconds),
            },
        )

    # Set standard RateLimit headers for accepted requests
    response.headers["X-RateLimit-Limit"] = str(limit)
    response.headers["X-RateLimit-Remaining"] = str(max(0, limit - current_count))
    response.headers["X-RateLimit-Reset"] = str(reset_seconds)

    # 2. Template Caching & Validation Logic
    template_data = await cache_service.get_template(payload.template_id)
    if not template_data:
        # Cache Miss: Query database
        result = await db.execute(
            select(NotificationTemplate).where(NotificationTemplate.id == payload.template_id)
        )
        template_obj = result.scalar_one_or_none()
        if not template_obj:
            logger.warning(f"Notification request rejected: Template '{payload.template_id}' not found.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Email template '{payload.template_id}' was not found in the system.",
            )
        template_data = template_obj.to_dict()
        # Warm cache
        await cache_service.set_template(payload.template_id, template_data)
    else:
        logger.debug(f"Retrieved template '{payload.template_id}' from Redis cache.")

    # 3. User Preferences Caching & Validation Logic
    recipient_email = payload.recipient_email.lower().strip()
    user_prefs = await cache_service.get_user_preferences(recipient_email)
    if not user_prefs:
        # Cache Miss: Query database
        result = await db.execute(
            select(UserPreference).where(UserPreference.email == recipient_email)
        )
        prefs_obj = result.scalar_one_or_none()
        if prefs_obj:
            user_prefs = prefs_obj.to_dict()
            await cache_service.set_user_preferences(recipient_email, user_prefs)
        else:
            # Default preferences for unregistered/new emails
            user_prefs = {
                "user_id": None,
                "email": recipient_email,
                "email_opt_out": False,
                "preferred_language": "en",
            }
            # Cache default to prevent DB hammering
            await cache_service.set_user_preferences(recipient_email, user_prefs, ttl=300)

    # 4. Construct Asynchronous Message Payload
    notification_id = str(uuid.uuid4())
    accepted_at = datetime.now(timezone.utc)

    message_payload = {
        "notification_id": notification_id,
        "recipient_email": recipient_email,
        "template_id": payload.template_id,
        "dynamic_data": payload.dynamic_data,
        "preferred_language": user_prefs.get("preferred_language", "en"),
        "email_opt_out": user_prefs.get("email_opt_out", False),
        "timestamp": accepted_at.isoformat(),
    }

    # 5. Publish to RabbitMQ Message Queue
    try:
        await rabbitmq_service.publish_notification(message_payload)
    except Exception as e:
        logger.error(f"Failed to publish notification to RabbitMQ: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to queue email notification for processing. Please try again later.",
        )

    # 6. Return HTTP 202 Accepted immediately
    return EmailNotificationResponse(
        notification_id=notification_id,
        status="queued",
        message="Notification request accepted and queued for asynchronous processing.",
        recipient_email=recipient_email,
        template_id=payload.template_id,
        timestamp=accepted_at,
    )
