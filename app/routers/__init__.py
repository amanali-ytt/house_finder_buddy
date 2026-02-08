"""Routers package init."""

from app.routers.properties import router as properties_router
from app.routers.query import router as query_router

__all__ = ["properties_router", "query_router"]
