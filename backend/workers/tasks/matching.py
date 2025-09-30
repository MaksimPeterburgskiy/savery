"""Item matching pipeline tasks."""

from __future__ import annotations

from typing import Any
from dataclasses import dataclass
from celery import shared_task




@shared_task(name="workers.matching.match_items")
def match_items(payload: dict[str, Any]) -> dict[str, Any]:
    """Map free-form shopping list items to canonical product candidates."""

    items: list[dict[str, Any]] = payload.get("items", [])
    store_ids: list[str] = payload.get("store_ids", [])

    matched: list[dict[str, Any]] = []
    for item in items:
        normalized_name = item.get("name", "").strip()
        matched.append(
            {
                "list_item": item,
                "normalized_name": normalized_name.lower(),
                "candidates": [
                    {
                        "store_id": store_id,
                        "confidence": 0.0,
                        "product_id": None,
                        "product_name": None,
                        "notes": "Matching logic not yet implemented.",
                    }
                    for store_id in store_ids
                ],
            }
        )

    return {
        "request": payload,
        "matched_items": matched,
    }


