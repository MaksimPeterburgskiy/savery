"""Route optimization task definitions."""

from __future__ import annotations

from typing import Any

from celery import shared_task


@shared_task(name="workers.optimize.plan_route")
def plan_route(payload: dict[str, Any]) -> dict[str, Any]:
    """Compute a shopping plan given normalized items and pricing data."""

    return {
        "plan": [],
        "totals": {
            "cost": None,
            "distance_km": None,
        },
        "notes": "Optimization algorithm placeholder.",
        "input": payload,
    }
