"""Store data ingestion and pricing tasks."""

from __future__ import annotations

from typing import Any

from celery import shared_task


@shared_task(name="workers.scraping.fetch_prices")
def fetch_prices(matched_payload: dict[str, Any]) -> dict[str, Any]:
    """Retrieve pricing information for matched items from external providers."""

    # Placeholder implementation: propagate input data forward for now.
    return {
        "prices": [],
        "source": "unimplemented",
        "input": matched_payload,
    }
