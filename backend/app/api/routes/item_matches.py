"""Item Matching endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Sequence
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from backend.app.api.routes.shopping_lists import ListItemResponse
from backend.app.dependencies import get_db
from backend.app.models import ItemMatchCandidate, Job, JobStage, JobStatus, RoutePlan, utcnow
from backend.app.tasks import enqueue_job
from backend.workers.celery_app import celery_app

router = APIRouter()


class ProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    brand: str
    name: str
    upc: str | None = None
    size_text: str | None = None
    pkg_qty_value: float | None = None
    pkg_qty_unit: str | None = None
    base_qty_value: float | None = None
    base_qty_unit: str | None = None
    image_url: str | None = None


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    plan_id: UUID
    status: str
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    progress_current: int | None = None
    progress_total: int | None = None
    message: str | None = None


class ItemMatchCandidateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    plan_id: UUID
    list_item: ListItemResponse
    product: ProductResponse
    score: float
    rejected_by_user: bool


class ItemMatchCandidateUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rejected_by_user: bool


def _get_route_plan_or_404(session: Session, route_plan_id: UUID) -> RoutePlan:
    route_plan = session.get(RoutePlan, route_plan_id)
    if route_plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Route Plan not found")
    return route_plan


# start item matching task
# should only allow one active task at a time per route plan
# POST /route-plans/{route_plan_id}/item-match-jobs
@router.post(
    "/route-plans/{route_plan_id}/item-match-jobs",
    response_model=JobResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create or restart the item match job for a route plan",
)
def create_item_match_job(
    route_plan_id: UUID,
    db: Session = Depends(get_db),
) -> JobResponse:
    _get_route_plan_or_404(db, route_plan_id)

    active_statement = (
        select(Job)
        .where(
            Job.plan_id == route_plan_id,
            Job.stage == JobStage.MATCH,
            Job.status.in_((JobStatus.PENDING, JobStatus.RUNNING)),
        )
        .order_by(Job.updated_at.desc())
    )
    active_job = db.exec(active_statement).first()
    if active_job is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An item match job is already running for this route plan",
        )

    job_statement = select(Job).where(Job.plan_id == route_plan_id, Job.stage == JobStage.MATCH)
    job = db.exec(job_statement).first()
    if job is None:
        job = Job(
            plan_id=route_plan_id,
            stage=JobStage.MATCH,
            status=JobStatus.PENDING,
            task_id="",
        )
    else:
        job.status = JobStatus.PENDING
        job.progress_current = 0
        job.progress_total = None
        job.message = None
        job.started_at = None
        job.completed_at = None
        if job.task_id is None:
            job.task_id = ""

    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        enqueue_job(job.id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to enqueue item match job",
        ) from exc

    return JobResponse.model_validate(job)


# cancel active item matching task, only works if its running or pending
# DELETE /route-plans/{route_plan_id}/item-match-jobs/{job_id}
@router.delete(
    "/route-plans/{route_plan_id}/item-match-jobs/{job_id}",
    response_model=JobResponse,
    summary="Cancel the active item match job for a route plan",
)
def cancel_item_match_job(
    route_plan_id: UUID,
    job_id: UUID,
    db: Session = Depends(get_db),
) -> JobResponse:
    _get_route_plan_or_404(db, route_plan_id)

    job = db.get(Job, job_id)
    if job is None or job.plan_id != route_plan_id or job.stage != JobStage.MATCH:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item match job not found")

    if job.status not in (JobStatus.PENDING, JobStatus.RUNNING):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only pending or running item match jobs can be cancelled",
        )

    # Revoke the Celery task to prevent it from continuing execution
    if job.task_id:
        celery_app.control.revoke(job.task_id, terminate=True)

    job.status = JobStatus.FAILED
    if job.message:
        job.message = f"{job.message}; Cancelled by user"
    else:
        job.message = "Cancelled by user"
    job.completed_at = utcnow()
    db.add(job)
    db.commit()
    db.refresh(job)

    return JobResponse.model_validate(job)


# Return job history for the plan
# query params so clients can list just the active task or the full history
# GET /route-plans/{route_plan_id}/item-match-jobs
@router.get(
    "/route-plans/{route_plan_id}/item-match-jobs",
    response_model=Sequence[JobResponse],
    summary="List item match jobs for a route plan",
)
def list_item_match_jobs(
    route_plan_id: UUID,
    active_only: bool = Query(
        default=False,
        description="Return only pending or running jobs for the route plan",
    ),
    db: Session = Depends(get_db),
) -> Sequence[JobResponse]:
    _get_route_plan_or_404(db, route_plan_id)

    statement = select(Job).where(Job.plan_id == route_plan_id, Job.stage == JobStage.MATCH)
    if active_only:
        statement = statement.where(Job.status.in_((JobStatus.PENDING, JobStatus.RUNNING)))

    statement = statement.order_by(Job.created_at.desc())

    results = db.exec(statement).all()
    return results


@router.get(
    "/route-plans/{route_plan_id}/item-match-jobs/{job_id}",
    response_model=JobResponse,
    summary="Get item match job by ID",
)
def get_item_match_job_by_id(
    route_plan_id: UUID,
    job_id: UUID,
    db: Session = Depends(get_db),
) -> JobResponse:

    _get_route_plan_or_404(db, route_plan_id)

    statement = (
        select(Job)
        .where(
            Job.plan_id == route_plan_id,
            Job.id == job_id,
            Job.stage == JobStage.MATCH,
        )
        .order_by(Job.updated_at.desc())
    )
    result = db.exec(statement).first()
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item match job not found")

    return JobResponse.model_validate(result)


@router.get(
    "/route-plans/{route_plan_id}/item-match-jobs/active",
    response_model=JobResponse,
    summary="Get item match job thats active for the route plan",
)
def get_item_match_job_active(
    route_plan_id: UUID,
    db: Session = Depends(get_db),
) -> JobResponse:

    _get_route_plan_or_404(db, route_plan_id)

    # Only consider matcher jobs that are still running or waiting to start.
    statement = (
        select(Job)
        .where(
            Job.plan_id == route_plan_id,
            Job.stage == JobStage.MATCH,
            Job.status.in_((JobStatus.PENDING, JobStatus.RUNNING)),
        )
        .order_by(Job.updated_at.desc())
    )

    result = db.exec(statement).first()
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active item match job found")

    return JobResponse.model_validate(result)


@router.post(
    "/route-plans/{route_plan_id}/item-fanout-jobs",
    response_model=JobResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create or restart the item match fanout job for a route plan",
)
def create_item_fanout_job(
    route_plan_id: UUID,
    db: Session = Depends(get_db),
) -> JobResponse:
    _get_route_plan_or_404(db, route_plan_id)

    active_statement = (
        select(Job)
        .where(
            Job.plan_id == route_plan_id,
            Job.stage == JobStage.FANOUT,
            Job.status.in_((JobStatus.PENDING, JobStatus.RUNNING)),
        )
        .order_by(Job.updated_at.desc())
    )
    active_job = db.exec(active_statement).first()
    if active_job is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An item fanout job is already running for this route plan",
        )

    job_statement = select(Job).where(Job.plan_id == route_plan_id, Job.stage == JobStage.FANOUT)
    job = db.exec(job_statement).first()
    if job is None:
        job = Job(
            plan_id=route_plan_id,
            stage=JobStage.FANOUT,
            status=JobStatus.PENDING,
            task_id="",
        )
    else:
        job.status = JobStatus.PENDING
        job.progress_current = 0
        job.progress_total = None
        job.message = None
        job.started_at = None
        job.completed_at = None
        if job.task_id is None:
            job.task_id = ""

    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        enqueue_job(job.id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to enqueue item match fanout job",
        ) from exc

    return JobResponse.model_validate(job)


@router.delete(
    "/route-plans/{route_plan_id}/item-fanout-jobs/{job_id}",
    response_model=JobResponse,
    summary="Cancel the active item match fanout job for a route plan",
)
def cancel_item_fanout_job(
    route_plan_id: UUID,
    job_id: UUID,
    db: Session = Depends(get_db),
) -> JobResponse:
    _get_route_plan_or_404(db, route_plan_id)

    job = db.get(Job, job_id)
    if job is None or job.plan_id != route_plan_id or job.stage != JobStage.FANOUT:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item fanout job not found")

    if job.status not in (JobStatus.PENDING, JobStatus.RUNNING):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only pending or running item fanout jobs can be cancelled",
        )

    # Revoke the Celery task to prevent it from continuing execution
    if job.task_id:
        celery_app.control.revoke(job.task_id, terminate=True)

    job.status = JobStatus.FAILED
    if job.message:
        job.message = f"{job.message}; Cancelled by user"
    else:
        job.message = "Cancelled by user"
    job.completed_at = utcnow()
    db.add(job)
    db.commit()
    db.refresh(job)

    return JobResponse.model_validate(job)


@router.get(
    "/route-plans/{route_plan_id}/item-fanout-jobs",
    response_model=Sequence[JobResponse],
    summary="List item match fanout jobs for a route plan",
)
def list_item_fanout_jobs(
    route_plan_id: UUID,
    active_only: bool = Query(
        default=False,
        description="Return only pending or running jobs for the route plan",
    ),
    db: Session = Depends(get_db),
) -> Sequence[JobResponse]:
    _get_route_plan_or_404(db, route_plan_id)

    statement = select(Job).where(Job.plan_id == route_plan_id, Job.stage == JobStage.FANOUT)
    if active_only:
        statement = statement.where(Job.status.in_((JobStatus.PENDING, JobStatus.RUNNING)))

    statement = statement.order_by(Job.created_at.desc())

    results = db.exec(statement).all()
    return results


@router.get(
    "/route-plans/{route_plan_id}/item-fanout-jobs/{job_id}",
    response_model=JobResponse,
    summary="Get item match fanout job by ID",
)
def get_item_fanout_job_by_id(
    route_plan_id: UUID,
    job_id: UUID,
    db: Session = Depends(get_db),
) -> JobResponse:

    _get_route_plan_or_404(db, route_plan_id)

    statement = (
        select(Job)
        .where(
            Job.plan_id == route_plan_id,
            Job.id == job_id,
            Job.stage == JobStage.FANOUT,
        )
        .order_by(Job.updated_at.desc())
    )
    result = db.exec(statement).first()
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item fanout job not found")

    return JobResponse.model_validate(result)


@router.get(
    "/route-plans/{route_plan_id}/item-fanout-jobs/active",
    response_model=JobResponse,
    summary="Get item match fanout job thats active for the route plan",
)
def get_item_fanout_job_active(
    route_plan_id: UUID,
    db: Session = Depends(get_db),
) -> JobResponse:

    _get_route_plan_or_404(db, route_plan_id)

    statement = (
        select(Job)
        .where(
            Job.plan_id == route_plan_id,
            Job.stage == JobStage.FANOUT,
            Job.status.in_((JobStatus.PENDING, JobStatus.RUNNING)),
        )
        .order_by(Job.updated_at.desc())
    )

    result = db.exec(statement).first()
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active item fanout job found")

    return JobResponse.model_validate(result)


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
