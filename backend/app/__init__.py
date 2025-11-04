"""FastAPI application package"""

from fastapi import FastAPI

__all__ = ["create_app"]


def create_app() -> FastAPI:
    """Return the FastAPI application instance."""

    from .main import create_app as _create_app

    return _create_app()
