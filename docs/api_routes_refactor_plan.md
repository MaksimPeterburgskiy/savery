## API Routes Refactor Plan

This document describes a move-only refactor of the backend FastAPI routes to:

- Make large route modules easier to navigate.
- Keep non-HTTP logic close to the routes but in smaller files.
- Align route module boundaries with the domain suggested by `models.py` and `database.dbml`.
- Preserve all existing URLs and behavior.

No URL paths or response shapes are intended to change as part of this refactor; only module/file layout and imports.

---

## High-Level Goals

- Keep the current top-level aggregator `backend/app/api/router.py` intact:
  - It should continue to do:
    - `from .routes import health, shopping_lists, stores, route_plans, item_matches`
    - `api_router.include_router(health.router, ...)`, etc.
- Move each route file towards a “package-style” layout:
  - Group related code into:
    - `*_schemas.py` – Pydantic request/response models.
    - `*_helpers.py` – internal helpers, query builders, validators.
    - `*_endpoints.py` – HTTP endpoints for the primary resource(s).
    - `*_jobs.py` – HTTP endpoints that manage background jobs (where applicable).
  - Use a folder per domain under `backend/app/api/routes/`.
- Keep non-HTTP logic allowed in the routes package, while making the HTTP entrypoints easy to scan.

---

## Target Directory & Naming Conventions

Base routes folder:

- `backend/app/api/routes/`
  - `health.py`
  - `shopping_lists/`
  - `stores/`
  - `planning/`

The existing top-level modules `shopping_lists.py`, `stores.py`, `route_plans.py`, and `item_matches.py` will be replaced by packages with `__init__.py` that expose a `router`.

### Shopping Lists Domain

- Target path: `backend/app/api/routes/shopping_lists/`
- Modules:
  - `__init__.py`
  - `shopping_lists_schemas.py`
  - `shopping_lists_helpers.py`
  - `shopping_lists_endpoints.py`

### Stores / Catalog Domain

- Target path: `backend/app/api/routes/stores/`
- Modules:
  - `__init__.py`
  - `stores_schemas.py` (if/when needed; may be minimal to start)
  - `stores_helpers.py` (any geography/lookup helpers that are specific to stores)
  - `stores_endpoints.py`

### Planning (Route Plans, Item Matching, Jobs) Domain

- Target path: `backend/app/api/routes/planning/`
- Modules:
  - `__init__.py`
  - `planning_schemas.py`
  - `planning_helpers.py`
  - `planning_plan_endpoints.py`
  - `planning_job_endpoints.py`
  - `planning_candidate_endpoints.py`

This combines the responsibilities currently in `route_plans.py` and `item_matches.py` into a single domain package while still keeping code split by concern inside that package.

---

## Router Aggregator (`backend/app/api/router.py`)

### Current

- Imports and includes:
  - `health`
  - `shopping_lists`
  - `stores`
  - `route_plans`
  - `item_matches`

### After Refactor

We keep the public imports the same to avoid touching call sites and tests:

- `backend/app/api/routes/__init__.py` will be updated so that:
  - `shopping_lists` refers to `backend/app/api/routes/shopping_lists/__init__.py`.
  - `stores` refers to `backend/app/api/routes/stores/__init__.py`.
  - `route_plans` and `item_matches` are replaced by a single module `planning` (new), or we keep thin compatibility shims (see below).

Two options for planning:

1. **Preferred (simpler going forward):**
   - Update `router.py` to:
     - `from .routes import health, shopping_lists, stores, planning`
     - `api_router.include_router(planning.router, prefix="", tags=["planning"])`

2. **Compatibility shims (if we want zero change to `router.py` for now):**
   - Keep tiny modules:
     - `backend/app/api/routes/route_plans.py`
     - `backend/app/api/routes/item_matches.py`
   - Each imports `router` from the `planning` package and re-exports it.
   - `router.py` remains exactly as-is.

This plan assumes we adopt option (1) eventually, but we can start with option (2) to keep the first refactor as non-disruptive as possible.

---

## Shopping Lists Package Refactor

### Source File

- `backend/app/api/routes/shopping_lists.py`

### Target Layout

- `backend/app/api/routes/shopping_lists/__init__.py`
- `backend/app/api/routes/shopping_lists/shopping_lists_schemas.py`
- `backend/app/api/routes/shopping_lists/shopping_lists_helpers.py`
- `backend/app/api/routes/shopping_lists/shopping_lists_endpoints.py`

### Responsibilities

#### `shopping_lists_schemas.py`

- Pydantic models:
  - `ShoppingListCreate`
  - `ShoppingListUpdate`
  - `ShoppingListResponse`
  - `ListItemResponse`
  - `ListItemCreate`
  - `ListItemUpdate`

#### `shopping_lists_helpers.py`

- DB helper functions:
  - `_get_shopping_list_or_404(session, shopping_list_id) -> ShoppingList`
  - `_get_list_item_or_404(session, shopping_list_id, item_id) -> ListItem`
  - `_apply_parsed_fields(item: ListItem, parsed: ParsedItem) -> None`
    - This keeps parsing-related logic near routes but out of the HTTP handlers.

#### `shopping_lists_endpoints.py`

- Define:
  - `router = APIRouter()`
- All FastAPI route handlers currently in `shopping_lists.py`:
  - `/shopping-lists`
    - `list_shopping_lists`
    - `create_shopping_list`
  - `/shopping-lists/{shopping_list_id}`
    - `get_shopping_list`
    - `update_shopping_list`
    - `delete_shopping_list`
  - `/shopping-lists/{shopping_list_id}/items`
    - `list_items`
    - `create_item`
  - `/shopping-lists/{shopping_list_id}/items/{item_id}`
    - `update_item`
    - `delete_item`
- These handlers import:
  - Schemas from `.shopping_lists_schemas`.
  - Helpers from `.shopping_lists_helpers`.
  - Models and dependencies from existing locations (`backend.app.models`, `backend.app.dependencies`, `backend.app.parsing`).

#### `__init__.py`

- Re-export the router:

```python
from .shopping_lists_endpoints import router
```

This keeps `from backend.app.api.routes import shopping_lists` working.

---

## Stores Package Refactor

### Source File

- `backend/app/api/routes/stores.py`

### Target Layout

- `backend/app/api/routes/stores/__init__.py`
- `backend/app/api/routes/stores/stores_schemas.py`
- `backend/app/api/routes/stores/stores_helpers.py`
- `backend/app/api/routes/stores/stores_endpoints.py`

### Responsibilities

#### `stores_schemas.py`

- Pydantic models:
  - `StoreResponse`
  - `StoreChainsWithStoresResponse`

#### `stores_helpers.py`

- Any store-specific utility logic that is currently inline in route handlers, if/when it grows.
  - Initial refactor might keep this file minimal or empty aside from future helpers.

#### `stores_endpoints.py`

- Define:
  - `router = APIRouter()`
- All FastAPI route handlers currently in `stores.py`:
  - `/store-chains`
    - `get_store_chains`
  - `/store-chains/{store_chain_id}/stores`
    - `get_stores_by_store_chain`
  - `/store-chains/nearby`
    - `get_nearby_store_chains`
- These handlers import:
  - Schemas from `.stores_schemas`.
  - Any future helpers from `.stores_helpers`.
  - Models from `backend.app.models` and geography helpers from `backend.app.api.utils.geography`.

#### `__init__.py`

- Re-export the router:

```python
from .stores_endpoints import router
```

---

## Planning Package Refactor

This package covers:

- Route plans and their associated store visits/items.
- Selection of stores for a plan.
- Item match candidates and item matches.
- Jobs for matching, fanout, optimization, and related background work.

### Source Files

- `backend/app/api/routes/route_plans.py`
- `backend/app/api/routes/item_matches.py`

### Target Layout

- `backend/app/api/routes/planning/__init__.py`
- `backend/app/api/routes/planning/planning_schemas.py`
- `backend/app/api/routes/planning/planning_helpers.py`
- `backend/app/api/routes/planning/planning_plan_endpoints.py`
- `backend/app/api/routes/planning/planning_job_endpoints.py`
- `backend/app/api/routes/planning/planning_candidate_endpoints.py`

### Responsibilities

#### `planning_schemas.py`

From `route_plans.py`:

- `PriceEntryResponse`
- `ProductResponse`
- `StoreProductResponse`
- `PlanItemResponse`
- `PlanItemUpdate`
- `PlanStoreVisitResponse`
- `RoutePlanResponse`
- `RoutePlanStatus` (Enum)
- `RoutePlanCreate`
- `RoutePlanUpdate`
- `SelectedStoreCreate`

From `item_matches.py`:

- `ProductResponse` (reconciled with the one above; if they diverge, keep separate names)
- `JobResponse`
- `ItemMatchCandidateResponse`
- `ItemMatchCandidateUpdate`

Note: where names collide (`ProductResponse`), decide whether to:

- Share a single model used by both route plans and item matches, or
- Keep two variants with clearer names, e.g., `PlanningProductResponse` vs `ItemMatchProductResponse`.

The plan is to unify them into one shared `ProductResponse` unless there is a behavioral reason not to.

#### `planning_helpers.py`

From `route_plans.py`:

- `_get_plan_store_visit_or_404(session, route_plan_id, plan_store_visit_id) -> PlanStoreVisit`
- `_get_plan_item_or_404(session, route_plan_id, plan_item_id) -> PlanItem`
- `_fetch_plan_items_by_visit(session, plan_store_visit_ids) -> dict[UUID, list[PlanItem]]`
- `_serialize_plan_items(plan_items) -> list[PlanItemResponse]`
- `_build_route_plan_responses(session, plans: Sequence[RoutePlan]) -> list[RoutePlanResponse]`

From `item_matches.py`:

- `_get_route_plan_or_404(session, route_plan_id) -> RoutePlan`

These helpers will be reused across all planning-related endpoint modules.

#### `planning_plan_endpoints.py`

- Define:
  - `router = APIRouter()`
- Endpoints from `route_plans.py` that deal with:
  - Route plan lifecycle:
    - `/shopping-lists/{shopping_list_id}/route-plans`
      - Create/list/whatever exists in the current file.
    - `/route-plans/{route_plan_id}`
      - Get/update/delete a single plan.
  - Selected stores for a plan:
    - `/route-plans/{route_plan_id}/selected-stores`
      - Add/remove selected stores.
  - Store visits and plan items:
    - `/route-plans/{route_plan_id}/plan-store-visits`
      - `list_plan_store_visits`
    - `/route-plans/{route_plan_id}/plan-store-visits/{plan_store_visit_id}/plan-items`
      - `list_plan_items_for_visit`
    - `/route-plans/{route_plan_id}/plan-items/{plan_item_id}`
      - `update_plan_item_checked_status`

These endpoints will import:

- Schemas from `.planning_schemas`.
- Helpers from `.planning_helpers`.
- Models and dependencies from existing modules.

#### `planning_job_endpoints.py`

- Endpoints that operate on `Job` records and background tasks.

From `route_plans.py`:

- `/route-plans/{route_plan_id}/plan-route-jobs`
  - `create_plan_route_job`
  - `cancel_plan_route_job`
  - `list_plan_route_jobs`
  - `get_plan_route_job_by_id`
  - `get_plan_route_job_active`

From `item_matches.py`:

- `/route-plans/{route_plan_id}/item-match-jobs`
  - `create_item_match_job`
  - `cancel_item_match_job`
  - `list_item_match_jobs`
  - `get_item_match_job_by_id`
  - `get_item_match_job_active`
- `/route-plans/{route_plan_id}/item-fanout-jobs`
  - `create_item_fanout_job`
  - `cancel_item_fanout_job`
  - `list_item_fanout_jobs`
  - `get_item_fanout_job_by_id`
  - `get_item_fanout_job_active`

All of these routes share the same `Job` model and `JobStage` enum, so consolidating them into one module clarifies the job domain.

These endpoints import:

- `Job`, `JobStage`, `JobStatus`, `RoutePlan`, and `utcnow` from `backend.app.models`.
- `enqueue_job` from `backend.app.tasks`.
- `celery_app` from `backend.workers.celery_app`.
- `_get_route_plan_or_404` from `.planning_helpers`.
- Schemas like `JobResponse` from `.planning_schemas`.

#### `planning_candidate_endpoints.py`

- Endpoints that operate on candidates and matches.

From `item_matches.py`:

- `/route-plans/{route_plan_id}/item-match-candidates`
  - `get_item_match_candidates_for_route_plan`
- `/item-match-candidates/{candidate_id}`
  - `get_item_match_candidate_by_id`
  - `update_item_match_candidate`

These endpoints import:

- `ItemMatchCandidate` from `backend.app.models`.
- `ItemMatchCandidateResponse`, `ItemMatchCandidateUpdate` from `.planning_schemas`.
- `_get_route_plan_or_404` from `.planning_helpers` where needed.

#### `__init__.py`

- Compose the planning router:

```python
from fastapi import APIRouter

from .planning_plan_endpoints import router as plan_router
from .planning_job_endpoints import router as job_router
from .planning_candidate_endpoints import router as candidate_router

router = APIRouter()
router.include_router(plan_router)
router.include_router(job_router)
router.include_router(candidate_router)
```

This `router` is what `backend/app/api/router.py` will include under the `"planning"` tag (or via compatibility shims).

---

## Health Route

- `backend/app/api/routes/health.py` remains a single file for now:
  - It is small and focused.
  - If it grows, we can later introduce:
    - `health_schemas.py`
    - `health_helpers.py`
    - `health_endpoints.py`

---

## Migration Steps

1. **Create new package directories:**
   - `backend/app/api/routes/shopping_lists/`
   - `backend/app/api/routes/stores/`
   - `backend/app/api/routes/planning/`

2. **Move and split code for `shopping_lists`:**
   - Copy Pydantic models → `shopping_lists_schemas.py`.
   - Copy helpers → `shopping_lists_helpers.py`.
   - Copy route handlers + `router = APIRouter()` → `shopping_lists_endpoints.py`.
   - Add `__init__.py` that re-exports `router`.
   - Remove or reduce the old `shopping_lists.py` to a thin shim (or delete once imports are updated).

3. **Move and split code for `stores`:**
   - Copy Pydantic models → `stores_schemas.py`.
   - Copy route handlers + `router = APIRouter()` → `stores_endpoints.py`.
   - Introduce `stores_helpers.py` (even if initially empty).
   - Add `__init__.py` that re-exports `router`.
   - Remove or reduce the old `stores.py` to a thin shim.

4. **Move and split code for planning (`route_plans` + `item_matches`):**
   - Collect all planning-related Pydantic models into `planning_schemas.py`.
   - Collect shared helpers into `planning_helpers.py`.
   - Move plan CRUD/selection/visit/item endpoints into `planning_plan_endpoints.py`.
   - Move job-related endpoints (match, fanout, optimize) into `planning_job_endpoints.py`.
   - Move candidate endpoints into `planning_candidate_endpoints.py`.
   - Compose `planning/__init__.py` as a combined router.
   - Add temporary shims in `route_plans.py` and `item_matches.py` if we want backwards-compatible imports during the transition.

5. **Update `backend/app/api/routes/__init__.py`:**
   - Export the new packages:
     - `from . import shopping_lists, stores, planning`
   - Optionally maintain `route_plans` and `item_matches` shims temporarily.

6. **Update `backend/app/api/router.py`:**
   - Swap to the planning router (preferred):
     - `from .routes import health, shopping_lists, stores, planning`
     - `api_router.include_router(planning.router, prefix="", tags=["planning"])`
   - Ensure tags used in OpenAPI remain consistent or update them deliberately.

7. **Run backend tests and smoke test routes:**
   - Run `python backend/tools/run_backend.py`.
   - Run `cd backend && pytest`.
   - Hit key endpoints manually or via existing tests to confirm behavior:
     - `/shopping-lists`, `/shopping-lists/{id}/items`
     - `/store-chains`, `/store-chains/nearby`
     - `/shopping-lists/{id}/route-plans`, `/route-plans/{id}`
     - `/route-plans/{id}/item-match-jobs`, `/route-plans/{id}/plan-route-jobs`
     - `/route-plans/{id}/item-match-candidates`

8. **Clean up shims (optional final step):**
   - Once all code references use the new package modules, remove any thin compatibility modules (`route_plans.py`, `item_matches.py`) that only re-export the planning router.

---

This plan is intentionally incremental: you can implement it in stages (shopping lists → stores → planning) while keeping the external API stable and tests green at each step.

