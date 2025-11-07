"""Task modules for Celery workers."""

from . import health  # noqa: F401
from . import scraping  # noqa: F401  - ensure scraping tasks are registered by autodiscovery

__all__ = ["health", "scraping"]
