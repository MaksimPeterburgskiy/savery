"""Celery task that performs item matching for a route plan job."""

from __future__ import annotations

from uuid import UUID

from celery import shared_task
from sqlalchemy.orm import selectinload
from sqlmodel import delete, select

from backend.app.db import session_scope
from backend.app.models import ItemMatchCandidate, ItemMatch, Job, JobStage, Product, RoutePlan, ShoppingList, StoreProduct
from backend.app.tasks import mark_job_failed, mark_job_running, mark_job_success, record_job_progress


@shared_task(bind=True, name="workers.item_matches.create_item_match_candidates", track_started=True)
def create_item_match_candidates(self, job_id: str | UUID) -> dict[str, str]:
    """Create Item Matche Candidates for each List Item job."""

    try:
        # get job details from DB and preload related data
        with session_scope() as session:
            statement = (
                select(Job)
                .where(Job.id == job_id, Job.stage == JobStage.MATCH)
                .options(
                    selectinload(Job.plan).selectinload(RoutePlan.list).selectinload(ShoppingList.list_items),
                    selectinload(Job.plan).selectinload(RoutePlan.selected_stores),
                )
            )
            result = session.exec(statement)
            job = result.one()
            plan = job.plan
            if plan is None:
                raise ValueError("Job has no associated route plan")
            shopping_list = plan.list
            if shopping_list is None:
                raise ValueError("Route plan has no associated shopping list")
            list_items = shopping_list.list_items
            if list_items is None:
                raise ValueError("Shopping List has no associated list items")
            selected_stores = plan.selected_stores or []
            if not selected_stores:
                raise ValueError("Route plan has no selected stores for item matching")

            progress_total = len(list_items)
            mark_job_running(
                job_id,
                total=progress_total or None,
                message="Item matching task started",
                task=self,
            )

            # remove existing candidates so reruns don't violate unique constraints
            session.exec(delete(ItemMatchCandidate).where(ItemMatchCandidate.plan_id == plan.id))
            session.flush()

            # item matching
            for idx, item in enumerate(list_items, start=1):
                if item.item_name is None:
                    raise ValueError(f"Item {item.id} has no canonical name for matching")
                canon_terms = [term for term in item.item_name.split(" ") if term]
                if not canon_terms:
                    raise ValueError(f"Item {item.id} has no usable canonical terms for matching")

                matched_product_ids: set[UUID] = set()
                for store in selected_stores:
                    # select products at this store where name contains all canon terms
                    statement = (
                        select(Product.id)
                        .join(StoreProduct, StoreProduct.product_id == Product.id)
                        .where(
                            StoreProduct.store_id == store.store_id,
                            *[Product.name.ilike(f"%{term}%") for term in canon_terms if term],
                        )
                    )
                    matches = session.exec(statement).scalars().all()
                    matched_product_ids.update(matches)

                # create item match candidates for matched products
                for product_id in matched_product_ids:
                    item_match_candidate = ItemMatchCandidate(
                        plan_id=plan.id,
                        list_item_id=item.id,
                        product_id=product_id,
                        score=100,  # placeholder score
                    )
                    session.add(item_match_candidate)
                session.commit()

                record_job_progress(
                    job_id,
                    current=idx,
                    total=progress_total,
                    task=self,
                    include_status=True,
                )

        mark_job_success(job_id, message="Item matching task completed", task=self)
        return {"job_id": str(job_id)}
    except Exception as exc:
        mark_job_failed(
            job_id,
            message=str(exc),
            task=self,
            extra_meta={"error": str(exc)},
        )
        raise


@shared_task(bind=True, name="workers.item_matches.fanout_candidates_to_item_matches", track_started=True)
def fanout_candidates_to_item_matches(self, job_id: str | UUID) -> dict[str, str]:
    """Create Item Matches for each selected candidate job."""

    try:
        with session_scope() as session:
            statement = (
                select(Job)
                .where(Job.id == job_id, Job.stage == JobStage.FANOUT)
                .options(
                    selectinload(Job.plan).selectinload(RoutePlan.match_candidates),
                    selectinload(Job.plan).selectinload(RoutePlan.selected_stores),
                )
            )
            result = session.exec(statement)
            job = result.one()
            plan = job.plan
            if plan is None:
                raise ValueError("Job has no associated route plan")
            selected_stores = plan.selected_stores or []
            if not selected_stores:
                raise ValueError("Route plan has no selected stores for item matching")

            match_candidates = [candidate for candidate in (plan.match_candidates or []) if not candidate.rejected_by_user]
            if not match_candidates:
                raise ValueError("Route plan has no acceptable match candidates to fan out")

            mark_job_running(
                job_id,
                total=len(match_candidates),
                message="Item match fanout task started",
                task=self,
            )

            session.exec(delete(ItemMatch).where(ItemMatch.plan_id == plan.id))
            session.flush()

            total_candidates = len(match_candidates)
            for idx, candidate in enumerate(match_candidates, start=1):
                for selected_store in selected_stores:
                    statement = (
                        select(StoreProduct)
                        .where(
                            StoreProduct.product_id == candidate.product_id,
                            StoreProduct.store_id == selected_store.store_id,
                        )
                    )
                    store_products = session.exec(statement).scalars().all()
                    for store_product in store_products:
                        item_match = ItemMatch(
                            plan_id=plan.id,
                            list_item_id=candidate.list_item_id,
                            store_id=selected_store.store_id,
                            item_match_candidate_id=candidate.id,
                            store_product_id=store_product.id,
                            price_entry_id=None,  # TODO: fill when price entries exist
                        )
                        session.add(item_match)

                session.commit()
                record_job_progress(
                    job_id,
                    current=idx,
                    total=total_candidates,
                    task=self,
                    include_status=True,
                )

        mark_job_success(job_id, message="Item match fanout task completed", task=self)
        return {"job_id": str(job_id)}
    except Exception as exc:
        mark_job_failed(
            job_id,
            message=str(exc),
            task=self,
            extra_meta={"error": str(exc)},
        )
        raise
