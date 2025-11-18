"""Planning endpoints for background jobs (plan route, item match, fanout)."""

from __future__ import annotations

from typing import Sequence
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select

from backend.app.dependencies import get_db
from backend.app.models import Job, JobStage, JobStatus, utcnow
from backend.app.tasks import enqueue_job
from backend.workers.celery_app import celery_app

from .planning_helpers import _get_route_plan_or_404
from .planning_schemas import JobResponse

router = APIRouter()


@router.post(
    "/route-plans/{route_plan_id}/plan-route-jobs",
    response_model=JobResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create or restart the route plan job for a route plan",
)
def create_plan_route_job(
    route_plan_id: UUID,
    db: Session = Depends(get_db),
) -> JobResponse:
    _get_route_plan_or_404(db, route_plan_id)

    active_statement = (
        select(Job)
        .where(
            Job.plan_id == route_plan_id,
            Job.stage == JobStage.OPTIMIZE,
            Job.status.in_((JobStatus.PENDING, JobStatus.RUNNING)),
        )
        .order_by(Job.updated_at.desc())
    )
    active_job = db.exec(active_statement).first()
    if active_job is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A route planning job is already running for this route plan",
        )

    job_statement = select(Job).where(Job.plan_id == route_plan_id, Job.stage == JobStage.OPTIMIZE)
    job = db.exec(job_statement).first()
    if job is None:
        job = Job(
            plan_id=route_plan_id,
            stage=JobStage.OPTIMIZE,
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
        job.status = JobStatus.FAILED
        job.message = f"Failed to enqueue job: {exc}"
        job.completed_at = utcnow()
        db.add(job)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        job.status = JobStatus.FAILED
        job.message = "Failed to enqueue job: Celery unavailable"
        job.completed_at = utcnow()
        db.add(job)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to enqueue route planning job",
        ) from exc

    return JobResponse.model_validate(job)


@router.delete(
    "/route-plans/{route_plan_id}/plan-route-jobs/{job_id}",
    response_model=JobResponse,
    summary="Cancel the active route planning task for a route plan",
)
def cancel_plan_route_job(
    route_plan_id: UUID,
    job_id: UUID,
    db: Session = Depends(get_db),
) -> JobResponse:
    _get_route_plan_or_404(db, route_plan_id)

    job = db.get(Job, job_id)
    if job is None or job.plan_id != route_plan_id or job.stage != JobStage.OPTIMIZE:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Route plan job not found")

    if job.status not in (JobStatus.PENDING, JobStatus.RUNNING):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only pending or running route planning jobs can be cancelled",
        )

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
    "/route-plans/{route_plan_id}/plan-route-jobs",
    response_model=Sequence[JobResponse],
    summary="List plan route jobs for a route plan",
)
def list_plan_route_jobs(
    route_plan_id: UUID,
    active_only: bool = Query(
        default=False,
        description="Return only pending or running jobs for the route plan",
    ),
    db: Session = Depends(get_db),
) -> Sequence[JobResponse]:
    _get_route_plan_or_404(db, route_plan_id)

    statement = select(Job).where(Job.plan_id == route_plan_id, Job.stage == JobStage.OPTIMIZE)
    if active_only:
        statement = statement.where(Job.status.in_((JobStatus.PENDING, JobStatus.RUNNING)))

    statement = statement.order_by(Job.created_at.desc())

    results = db.exec(statement).all()
    return results


@router.get(
    "/route-plans/{route_plan_id}/plan-route-jobs/{job_id}",
    response_model=JobResponse,
    summary="Get plan route job by ID",
)
def get_plan_route_job_by_id(
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
            Job.stage == JobStage.OPTIMIZE,
        )
        .order_by(Job.updated_at.desc())
    )
    result = db.exec(statement).first()
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Route plan job not found")

    return JobResponse.model_validate(result)


@router.get(
    "/route-plans/{route_plan_id}/plan-route-jobs/active",
    response_model=JobResponse,
    summary="Get plan route job thats active for the route plan",
)
def get_plan_route_job_active(
    route_plan_id: UUID,
    db: Session = Depends(get_db),
) -> JobResponse:

    _get_route_plan_or_404(db, route_plan_id)

    statement = (
        select(Job)
        .where(
            Job.plan_id == route_plan_id,
            Job.stage == JobStage.OPTIMIZE,
            Job.status.in_((JobStatus.PENDING, JobStatus.RUNNING)),
        )
        .order_by(Job.updated_at.desc())
    )

    result = db.exec(statement).first()
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active plan route job found")
    return JobResponse.model_validate(result)


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
        job.status = JobStatus.FAILED
        job.message = f"Failed to enqueue job: {exc}"
        job.completed_at = utcnow()
        db.add(job)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        job.status = JobStatus.FAILED
        job.message = "Failed to enqueue job: Celery unavailable"
        job.completed_at = utcnow()
        db.add(job)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to enqueue item match job",
        ) from exc

    return JobResponse.model_validate(job)


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
        job.status = JobStatus.FAILED
        job.message = f"Failed to enqueue job: {exc}"
        job.completed_at = utcnow()
        db.add(job)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        job.status = JobStatus.FAILED
        job.message = "Failed to enqueue job: Celery unavailable"
        job.completed_at = utcnow()
        db.add(job)
        db.commit()
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


__all__ = ["router"]
