"""Aggregate API routers for the application."""

from fastapi import APIRouter

from .routes import health, route_plans, shopping_lists, stores

api_router = APIRouter()
api_router.include_router(health.router, prefix="", tags=["health"])
api_router.include_router(shopping_lists.router, prefix="", tags=["shopping_lists"])
api_router.include_router(stores.router, prefix="", tags=["stores"])
api_router.include_router(route_plans.router, prefix="", tags=["route_plans"])

