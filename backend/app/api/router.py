"""Aggregate API routers for the application."""

from fastapi import APIRouter

from .routes import catalog, health, lists, planning

api_router = APIRouter()
api_router.include_router(health.router, prefix="", tags=["health"])
api_router.include_router(lists.router, prefix="", tags=["lists"])
api_router.include_router(catalog.router, prefix="", tags=["catalog"])
api_router.include_router(planning.router, prefix="", tags=["planning"])
