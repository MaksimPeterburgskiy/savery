"""Aggregate API routers for the application."""

from fastapi import APIRouter

from .routes import health, shopping_lists, stores

api_router = APIRouter()
api_router.include_router(health.router, prefix="", tags=["health"])
api_router.include_router(shopping_lists.router, prefix="", tags=["shopping_lists"])
api_router.include_router(stores.router, prefix="", tags=["stores"])

