"""API v1 router — aggregates all sub-routers."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.connectors import router as connectors_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.discovery import router as discovery_router
from app.api.v1.faculty import router as faculty_router
from app.api.v1.faculty_discover import router as faculty_discover_router
from app.api.v1.public_search import router as public_search_router
from app.api.v1.reviews import router as reviews_router

api_router = APIRouter()

api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(faculty_router, prefix="/faculty", tags=["faculty"])
api_router.include_router(faculty_discover_router, prefix="/faculty", tags=["discovery"])
api_router.include_router(discovery_router, prefix="/discovery-jobs", tags=["discovery"])
api_router.include_router(connectors_router, prefix="/connectors", tags=["connectors"])
api_router.include_router(reviews_router, prefix="/reviews", tags=["reviews"])
api_router.include_router(dashboard_router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(public_search_router, prefix="", tags=["public-search"])
