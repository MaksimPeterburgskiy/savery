"""Task modules for Celery workers."""

from . import example, matching, optimize, scraping  # noqa: F401

__all__ = ["example", "matching", "optimize", "scraping"]
