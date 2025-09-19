# Savery Backend Map

## Overview
The backend combines a FastAPI web service, SQLAlchemy-powered persistence scaffolding, and Celery workers for asynchronous optimization jobs. Configuration is centralized through Pydantic settings so the HTTP API and background workers share a common environment.

## Directory Guide
- `app/`
  - `main.py` – FastAPI application factory and ASGI entrypoint (`app = create_app()`).
  - `lifecycle.py` – lifespan context manager that initializes the database connection during startup.
  - `api/` – top-level API router aggregation (`router.py`) and route modules under `routes/`.
  - `dependencies/` – FastAPI dependency providers such as `get_db` wrapping SQLAlchemy sessions.
  - `models.py` – Pydantic request/response schemas exposed by the HTTP layer.
- `core/`
  - `config.py` – Pydantic `Settings` object that reads environment variables (prefixed with `SAVERY_`).
  - `db.py` – Lazy SQLAlchemy engine/session bootstrap, database initialization helper, and request/session scope.
  - `schema.py` – SQLAlchemy ORM models for stores, products, prices, and optimization jobs.
  - `tasks.py` – Thin interface for enqueuing Celery jobs and querying task status from the API layer.
- `workers/`
  - `celery_app.py` – Celery application configuration and health check task (`workers.health.ping`).
  - `tasks/` – Namespaced Celery task modules (optimization, matching, scraping, etc.).
- `tools/`
  - `make_env.py` – Utility script for creating a local virtual environment and installing `requirements.txt`.
- `tests/`
  - FastAPI integration tests (e.g., `test_health.py`) that exercise the public API contract.

## Runtime Entrypoints
- **ASGI app:** Uvicorn/Gunicorn should target `backend.app.main:app`. `create_app()` applies the project settings, registers routers, and wires the lifespan hook for bootstrapping resources.
- **Lifespan:** `backend.app.lifecycle.lifespan` runs during startup/shutdown to initialize the database via `core.db.init_db()` and log service lifecycle messages.
- **HTTP routes:**
  - `GET /api/health` (`backend.app.api.routes.health.health_check`) – liveness/readiness probe exposing environment and version.
  - `GET /api/stores` (`backend.app.api.routes.stores.list_supported_stores`) – placeholder catalog endpoint returning demo stores.
  - `POST /api/optimize` (`backend.app.api.routes.optimization.request_optimization`) – queues a Celery optimization job and returns a task identifier plus polling URL.
  - `GET /api/tasks/{task_id}` (`backend.app.api.routes.tasks.read_task_status`) – surfaces Celery task status for clients polling job progress.
- **Celery worker:** Run Celery with the application path `backend.workers.celery_app:celery_app`. This registers shared tasks under the `backend.workers` namespace and configures broker/result backends from settings.
- **Optimization task:** `workers.optimize.plan_route` receives the payload enqueued by `/api/optimize` and currently returns a placeholder plan structure. The default Celery route name is controlled by `SAVERY_CELERY_ROUTE_TASK`.

## Supporting Components
- **Database access:** `backend.app.dependencies.get_db` yields SQLAlchemy sessions backed by `core.db.session_scope`, allowing future routes to interact with Postgres while ensuring proper commit/rollback handling.
- **Configuration:** All services import `backend.core.config.settings` so runtime behaviour can be tuned via environment variables (URLs, debug flags, docs endpoints, task routing, etc.).
- **Testing harness:** `backend/tests` relies on `create_app()` to build an in-process FastAPI client, ensuring the documented entrypoints remain stable.
