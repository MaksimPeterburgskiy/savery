"""Item matching pipeline tasks."""

from __future__ import annotations

from typing import Any

from celery import shared_task


@shared_task(name="workers.matching.match_items")
def match_items(payload: dict[str, Any]) -> dict[str, Any]:
    """Map free-form shopping list items to canonical product candidates."""

    items: list[dict[str, Any]] = payload.get("items", [])

    matched = []
    for item in items:
        matched.append(
            {
                "query": item,
                "candidates": [],
                "notes": "Matching not yet implemented.",
            }
        )

    return {"matched": matched}
