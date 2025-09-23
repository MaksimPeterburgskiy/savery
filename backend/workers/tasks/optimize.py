"""Route optimization task definitions."""

from __future__ import annotations

from typing import Any

from celery import shared_task


@shared_task(name="workers.optimize.plan_route")
def plan_route(priced_payload: dict[str, Any]) -> dict[str, Any]:
    """Compute a shopping plan given normalized items and pricing data."""

    request = priced_payload.get("request", {})
    store_ids: list[str] = request.get("store_ids", [])

    stores: list[dict[str, Any]] = []
    for store_id in store_ids:
        stores.append(
            {
                "store_id": store_id,
                "store_name": store_id.replace("-", " ").title(),
                "distance_km": None,
                "estimated_duration_minutes": None,
                "items": [],
            }
        )

    return {
        "request": request,
        "matched_items": priced_payload.get("matched_items", []),
        "priced_items": priced_payload.get("priced_items", []),
        "result": {
            "stores": stores,
            "total_cost": None,
            "total_distance_km": None,
            "currency": "USD",
            "notes": "Optimization algorithm placeholder.",
        },
    }
