"""Routers package export."""
from app.routers.auth import router as auth_router
from app.routers.dashboard import router as dashboard_router
from app.routers.notes import router as notes_router
from app.routers.categories import router as categories_router
from app.routers.tags import router as tags_router
from app.routers.profile import router as profile_router

__all__ = [
    "auth_router",
    "dashboard_router",
    "notes_router",
    "categories_router",
    "tags_router",
    "profile_router",
]
