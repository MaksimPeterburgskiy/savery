"""Aggregate API routers for the application."""

from fastapi import APIRouter

from .routes import health, optimization, stores, tasks

api_router = APIRouter()
api_router.include_router(health.router, prefix="", tags=["health"])
api_router.include_router(stores.router, prefix="", tags=["stores"])
api_router.include_router(optimization.router, prefix="", tags=["optimization"])
api_router.include_router(tasks.router, prefix="", tags=["tasks"])
