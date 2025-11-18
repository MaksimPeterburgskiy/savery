"""Planning endpoints for item match candidates."""

from __future__ import annotations

from typing import Sequence
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from backend.app.dependencies import get_db
from backend.app.models import ItemMatchCandidate

from .planning_helpers import _get_route_plan_or_404
from .planning_schemas import ItemMatchCandidateResponse, ItemMatchCandidateUpdate

router = APIRouter()


@router.get(
    "/route-plans/{route_plan_id}/item-match-candidates",
    response_model=Sequence[ItemMatchCandidateResponse],
    summary="Get item match candidates for a route plan",
)
def get_item_match_candidates_for_route_plan(
    route_plan_id: UUID,
    db: Session = Depends(get_db),
) -> Sequence[ItemMatchCandidateResponse]:

    _get_route_plan_or_404(db, route_plan_id)

    statement = (
        select(ItemMatchCandidate)
        .where(ItemMatchCandidate.plan_id == route_plan_id)
        .options(
            selectinload(ItemMatchCandidate.list_item),
            selectinload(ItemMatchCandidate.product),
        )
        .order_by(ItemMatchCandidate.score.desc())
    )
    results = db.exec(statement).all()
    return results


@router.get(
    "/item-match-candidates/{candidate_id}",
    response_model=ItemMatchCandidateResponse,
    summary="Get item match candidate by ID",
)
def get_item_match_candidate_by_id(
    candidate_id: UUID,
    db: Session = Depends(get_db),
) -> ItemMatchCandidateResponse:

    statement = (
        select(ItemMatchCandidate)
        .where(ItemMatchCandidate.id == candidate_id)
        .options(
            selectinload(ItemMatchCandidate.list_item),
            selectinload(ItemMatchCandidate.product),
        )
    )
    result = db.exec(statement).first()
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item match candidate not found")

    return result


@router.patch(
    "/item-match-candidates/{candidate_id}",
    response_model=ItemMatchCandidateResponse,
    summary="Update item match candidate",
)
def update_item_match_candidate(
    candidate_id: UUID,
    payload: ItemMatchCandidateUpdate,
    db: Session = Depends(get_db),
) -> ItemMatchCandidateResponse:

    candidate = db.get(ItemMatchCandidate, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item match candidate not found")

    candidate.rejected_by_user = payload.rejected_by_user
    db.add(candidate)
    db.commit()

    statement = (
        select(ItemMatchCandidate)
        .where(ItemMatchCandidate.id == candidate_id)
        .options(
            selectinload(ItemMatchCandidate.list_item),
            selectinload(ItemMatchCandidate.product),
        )
    )
    updated_candidate = db.exec(statement).first()
    if updated_candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item match candidate not found after update")

    return updated_candidate


__all__ = ["router"]
