"""Celery task that performs item matching for a route plan job."""

from __future__ import annotations

import unicodedata
from uuid import UUID

from celery import shared_task
from sqlalchemy.orm import selectinload
from sqlmodel import delete, select

from backend.app.db import session_scope
from backend.app.models import ItemMatch, ItemMatchCandidate, Job, JobStage, Product, RoutePlan, ShoppingList, StoreProduct
from backend.app.tasks import mark_job_failed, mark_job_running, mark_job_success, record_job_progress

# Scoring feature flags
ENABLE_BRAND_EXCLUSION = True
ENABLE_POSITION_WEIGHTING = True

# Position weights for position weighting
POSITION_WEIGHTS = [1.0, 0.9, 0.8, 0.7, 0.6]
DEFAULT_WEIGHT = 0.5


def normalize_text_for_matching(text: str) -> str:
    """Normalize text for matching, handling non-ASCII characters.

    Handles brands like "Häagen-Dazs", "José Olé" by:
    1. NFKD normalization to decompose characters
    2. Removing combining marks (accents)
    3. Lowercasing and normalizing separators
    """
    # NFKD normalization decomposes characters (é -> e + combining accent)
    normalized = unicodedata.normalize("NFKD", text)
    # Remove combining marks (accents, umlauts, etc.)
    ascii_compatible = "".join(c for c in normalized if not unicodedata.combining(c))
    # Lowercase and normalize common separators
    return ascii_compatible.lower().replace("-", " ").replace("'", "")


def should_exclude_brand(canon_terms: list[str], brand: str | None) -> bool:
    """
    Determine if brand should be excluded from scoring.

    Returns False (don't exclude) if user's search terms overlap with brand.
    Handles genericized trademarks like "kleenex", "bandaid", etc.
    Also handles non-ASCII brand names like "Häagen-Dazs", "José Olé".
    """
    if not brand:
        return False

    # Normalize brand: handle non-ASCII, lowercase, split hyphenated/apostrophe words
    brand_normalized = normalize_text_for_matching(brand)
    brand_terms = set(brand_normalized.split())
    canon_lower = {normalize_text_for_matching(t) for t in canon_terms}

    # Check 1: Direct term overlap (e.g., "kleenex" in ["kleenex"])
    if brand_terms & canon_lower:
        return False

    # Check 2: Substring match for compound terms
    # Handles "bandaid" matching "Band-Aid" (brand_normalized = "band aid")
    for canon_term in canon_lower:
        if canon_term in brand_normalized or brand_normalized.replace(" ", "") in canon_term:
            return False

    return True


def remove_brand_from_name(product_name: str, brand: str | None) -> str:
    """Remove brand prefix from product name for scoring purposes.

    Handles non-ASCII characters by using normalized comparison.
    """
    if not brand:
        return product_name

    name_normalized = normalize_text_for_matching(product_name)
    brand_normalized = normalize_text_for_matching(brand)

    if name_normalized.startswith(brand_normalized):
        # Find the actual position to cut by matching normalized prefix length
        # We need to find where in the original string the brand ends
        chars_consumed = 0
        normalized_pos = 0
        target_normalized_len = len(brand_normalized)

        for i, char in enumerate(product_name):
            char_normalized = normalize_text_for_matching(char)
            if char_normalized:  # Skip if char normalizes to empty (e.g., combining marks)
                normalized_pos += len(char_normalized)
            chars_consumed = i + 1
            if normalized_pos >= target_normalized_len:
                break

        return product_name[chars_consumed:].strip()

    return product_name


def get_position_weight(position: int) -> float:
    """Get weight for a term at given position (0-indexed)."""
    if position < len(POSITION_WEIGHTS):
        return POSITION_WEIGHTS[position]
    return DEFAULT_WEIGHT


def calculate_match_score(
    canon_terms: list[str],
    product_name: str,
    product_brand: str | None = None,
) -> float:
    """
    Calculate match score for a product candidate.

    Args:
        canon_terms: Normalized search terms from user's list item
        product_name: Product name to score against
        product_brand: Product brand (optional, for brand exclusion)

    Returns:
        Score from 0-100 where 100 is a perfect match
    """
    # Only exclude brand if user isn't searching for it
    scoring_name = product_name
    if ENABLE_BRAND_EXCLUSION and should_exclude_brand(canon_terms, product_brand):
        scoring_name = remove_brand_from_name(product_name, product_brand)

    product_terms = [t.lower() for t in scoring_name.split() if t]
    if not product_terms:
        return 0.0

    canon_terms_lower = {t.lower() for t in canon_terms}

    if ENABLE_POSITION_WEIGHTING:
        total_weight = sum(get_position_weight(i) for i in range(len(product_terms)))
        matched_weight = sum(get_position_weight(i) for i, term in enumerate(product_terms) if term in canon_terms_lower)
        score = (matched_weight / total_weight) * 100
    else:
        coverage = len(canon_terms) / len(product_terms)
        score = min(coverage, 1.0) * 100

    return round(score, 2)


@shared_task(bind=True, name="workers.item_matches.create_item_match_candidates", track_started=True)
def create_item_match_candidates(self, job_id: str | UUID) -> dict[str, str]:
    """Create Item Match Candidates for each List Item in a route plan."""

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
            session.exec(delete(ItemMatchCandidate).where(ItemMatchCandidate.plan_id == plan.id).execution_options(synchronize_session=False))
            session.flush()

            # item matching
            for idx, item in enumerate(list_items, start=1):
                if item.item_name is None:
                    raise ValueError(f"Item {item.id} has no canonical name for matching")
                canon_terms = [term for term in item.item_name.split(" ") if term]
                if not canon_terms:
                    raise ValueError(f"Item {item.id} has no usable canonical terms for matching")

                matched_products: dict[UUID, tuple[str, str | None]] = {}
                for store in selected_stores:
                    # select products at this store where name contains all canon terms
                    statement = (
                        select(Product.id, Product.name, Product.brand)
                        .join(StoreProduct, StoreProduct.product_id == Product.id)
                        .where(
                            StoreProduct.store_id == store.store_id,
                            *[Product.name.ilike(f"%{term}%") for term in canon_terms if term],
                        )
                    )
                    matches = session.exec(statement).all()
                    for product_id, product_name, product_brand in matches:
                        if product_id not in matched_products:
                            matched_products[product_id] = (product_name, product_brand)

                # create item match candidates for matched products
                for product_id, (product_name, product_brand) in matched_products.items():
                    score = calculate_match_score(canon_terms, product_name, product_brand)
                    item_match_candidate = ItemMatchCandidate(
                        plan_id=plan.id,
                        list_item_id=item.id,
                        product_id=product_id,
                        score=score,
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

            session.exec(delete(ItemMatch).where(ItemMatch.plan_id == plan.id).execution_options(synchronize_session=False))
            session.flush()

            total_candidates = len(match_candidates)
            for idx, candidate in enumerate(match_candidates, start=1):
                for selected_store in selected_stores:
                    statement = select(StoreProduct).where(
                        StoreProduct.product_id == candidate.product_id,
                        StoreProduct.store_id == selected_store.store_id,
                    )
                    store_products = session.exec(statement).all()
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
