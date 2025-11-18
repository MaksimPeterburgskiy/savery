"""Planning domain router composed from plan, job, and candidate endpoints."""

from fastapi import APIRouter

from .planning_candidate_endpoints import router as candidate_router
from .planning_job_endpoints import router as job_router
from .planning_plan_endpoints import router as plan_router

router = APIRouter()
router.include_router(plan_router)
router.include_router(job_router)
router.include_router(candidate_router)

__all__ = ["router"]

