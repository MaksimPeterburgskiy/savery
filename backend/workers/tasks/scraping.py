"""Store data ingestion and pricing tasks."""

from __future__ import annotations

from typing import Any

from celery import shared_task


@shared_task(name="workers.scraping.fetch_prices")
def fetch_prices(matched_payload: dict[str, Any]) -> dict[str, Any]:
    """Retrieve pricing information for matched items from external providers."""

    request = matched_payload.get("request", {})
    store_ids: list[str] = request.get("store_ids", [])
    matched_items: list[dict[str, Any]] = matched_payload.get("matched_items", [])

    priced_items: list[dict[str, Any]] = []
    for item in matched_items:
        priced_items.append(
            {
                **item,
                "offers": [
                    {
                        "store_id": store_id,
                        "price": None,
                        "currency": "USD",
                        "last_fetched": None,
                        "source": "not-implemented",
                    }
                    for store_id in store_ids
                ],
            }
        )

    return {
        "request": request,
        "matched_items": matched_items,
        "priced_items": priced_items,
    }
