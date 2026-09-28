import time
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from api.src.config import settings
from api.src.services.cache_service import cache_service
from api.src.services.rate_limiter import rate_limiter
from api.src.services.rabbitmq_service import rabbitmq_service
from api.src.routes.health import router as health_router
from api.src.routes.notifications import router as notifications_router
from api.src.routes.templates import router as templates_router
from api.src.routes.preferences import router as preferences_router

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("api.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup Sequence
    logger.info("Initializing API application resources...")
    await cache_service.connect()
    if cache_service.client:
        rate_limiter.set_client(cache_service.client)
    await rabbitmq_service.connect()
    logger.info("NotifyFlow API Service successfully initialized and ready to receive traffic.")

    yield

    # Shutdown Sequence
    logger.info("Shutting down API application resources...")
    await rabbitmq_service.close()
    await cache_service.close()
    logger.info("NotifyFlow API Service shutdown complete.")


app = FastAPI(
    title="NotifyFlow - Event-Driven Transactional Email Notification Service",
    description=(
        "High-performance, event-driven transactional email notification service powered by "
        "RabbitMQ message queuing, Redis caching & rate limiting, and PostgreSQL persistence."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.perf_counter()
    response = await call_next(request)
    process_time = (time.perf_counter() - start_time) * 1000
    response.headers["X-Process-Time-Ms"] = f"{process_time:.2f}"
    return response


# Global Exception Handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception on {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected error occurred while processing your request.",
            "path": request.url.path,
        },
    )


# Include API Routers
app.include_router(health_router)
app.include_router(notifications_router)
app.include_router(templates_router)
app.include_router(preferences_router)


@app.get("/", tags=["Root"])
async def root():
    return {
        "service": "NotifyFlow Transactional Email Notification Service API",
        "version": "1.0.0",
        "status": "operational",
        "documentation": "/docs",
        "health_check": "/health",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api.src.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=(settings.ENVIRONMENT == "development"),
    )
