import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, status, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from api.src.database import get_db
from api.src.services.cache_service import cache_service
from api.src.services.rabbitmq_service import rabbitmq_service
from api.src.models.schemas import HealthResponse, HealthServiceStatus

logger = logging.getLogger("api.health")
router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="System Health Check",
    description="Check the connectivity and operational health of API, Database, Redis, and RabbitMQ.",
)
@router.get(
    "/api/health",
    response_model=HealthResponse,
    include_in_schema=False,
)
async def check_health(response: Response, db: AsyncSession = Depends(get_db)):
    services_status = {}
    is_healthy = True

    # Check Database
    try:
        result = await db.execute(text("SELECT 1"))
        if result.scalar() == 1:
            services_status["database"] = HealthServiceStatus(
                status="healthy", details="PostgreSQL connection active"
            )
        else:
            services_status["database"] = HealthServiceStatus(
                status="degraded", details="Unexpected database response"
            )
            is_healthy = False
    except Exception as e:
        logger.error(f"Health check: Database failure: {e}")
        services_status["database"] = HealthServiceStatus(
            status="unhealthy", details=str(e)
        )
        is_healthy = False

    # Check Redis
    try:
        redis_ok = await cache_service.health_check()
        if redis_ok:
            services_status["redis"] = HealthServiceStatus(
                status="healthy", details="Redis cache connected"
            )
        else:
            services_status["redis"] = HealthServiceStatus(
                status="unhealthy", details="Redis ping failed"
            )
            is_healthy = False
    except Exception as e:
        logger.error(f"Health check: Redis failure: {e}")
        services_status["redis"] = HealthServiceStatus(
            status="unhealthy", details=str(e)
        )
        is_healthy = False

    # Check RabbitMQ
    try:
        rmq_ok = await rabbitmq_service.health_check()
        if rmq_ok:
            services_status["rabbitmq"] = HealthServiceStatus(
                status="healthy", details="RabbitMQ channel open"
            )
        else:
            services_status["rabbitmq"] = HealthServiceStatus(
                status="unhealthy", details="RabbitMQ disconnected"
            )
            is_healthy = False
    except Exception as e:
        logger.error(f"Health check: RabbitMQ failure: {e}")
        services_status["rabbitmq"] = HealthServiceStatus(
            status="unhealthy", details=str(e)
        )
        is_healthy = False

    if not is_healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return HealthResponse(
        status="healthy" if is_healthy else "unhealthy",
        timestamp=datetime.now(timezone.utc),
        services=services_status,
    )
