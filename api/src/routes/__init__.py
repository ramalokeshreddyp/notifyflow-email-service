from api.src.routes.health import router as health_router
from api.src.routes.notifications import router as notifications_router
from api.src.routes.templates import router as templates_router
from api.src.routes.preferences import router as preferences_router

__all__ = [
    "health_router",
    "notifications_router",
    "templates_router",
    "preferences_router",
]
