# Savery Backend Map

## Overview
The backend now unifies FastAPI, SQLModel-powered persistence, and Celery workers inside a single `backend/app` package. SQLModel reduces duplicate schema definitions by serving both as the ORM layer and as the request/response models exposed by the HTTP API. Application configuration continues to flow through Pydantic settings so web and worker processes share a common environment.

## Directory Guide
- `app/`
  - `main.py` – FastAPI application factory and ASGI entrypoint (`app = create_app()`).
  - `lifecycle.py` – lifespan context manager that lazily creates the SQLModel engine and optionally ensures tables exist on startup.
  - `config.py` – Pydantic `Settings` object that reads environment variables (prefixed with `SAVERY_`).
  - `db.py` – SQLModel engine/session helpers plus `create_db_and_tables()` for quick bootstrap when Alembic migrations are not required.
  - `models.py` – SQLModel definitions for both API payloads and database tables (stores, products, prices, optimization jobs).
  - `tasks.py` – Thin interface for enqueuing Celery jobs and querying task status from the API layer.
  - `api/` – top-level router (`router.py`) and individual route modules under `routes/`.
  - `dependencies/` – FastAPI dependency providers such as `get_db` wrapping SQLModel sessions.
- `migrations/`
  - Alembic environment configured to autogenerate migrations from the SQLModel metadata (`env.py`, `versions/`). Run commands with `alembic -c backend/alembic.ini ...`.
- `workers/`
  - `celery_app.py` – Celery application configuration and health check task (`workers.health.ping`). The Celery app is wired to RabbitMQ queues for matching, scraping, and optimization stages.
  - `tasks/` – Namespaced Celery task modules (optimization, matching, scraping, etc.) representing the background workflow orchestrated through RabbitMQ.
- `tools/`
  - `make_env.py` – Utility script for creating a local virtual environment and installing `requirements.txt`.
- `tests/`
  - FastAPI integration tests (e.g., `test_health.py`) that exercise the public API contract.

## Runtime Entrypoints
- **ASGI app:** Uvicorn/Gunicorn should target `backend.app.main:app`. `create_app()` applies the project settings, registers routers, and wires the lifespan hook for bootstrapping resources.
- **Lifespan:** `backend.app.lifecycle.lifespan` runs during startup/shutdown to initialize the SQLModel metadata (when `SAVERY_VERIFY_SCHEMA_ON_STARTUP` is true) and log service lifecycle messages.
- **HTTP routes:**
  - `GET /api/health` (`backend.app.api.routes.health.health_check`) – liveness/readiness probe exposing environment and version.
  - `GET /api/stores` (`backend.app.api.routes.stores.list_supported_stores`) – placeholder catalog endpoint returning demo stores.
  - `POST /api/optimize` (`backend.app.api.routes.optimization.request_optimization`) – queues a Celery optimization job and returns a task identifier plus polling URL.
  - `GET /api/tasks/{task_id}` (`backend.app.api.routes.tasks.read_task_status`) – surfaces Celery task status for clients polling job progress.
- **Celery worker:** Run Celery with the application path `backend.workers.celery_app:celery_app`. This registers shared tasks under the `backend.workers` namespace and configures broker/result backends from settings.
- **Optimization pipeline:** `/api/optimize` triggers a Celery chain of `workers.matching.match_items → workers.scraping.fetch_prices → workers.optimize.plan_route`. RabbitMQ carries the messages between each queue and the default task names can be overridden via `SAVERY_CELERY_*` settings.

## Supporting Components
- **Database access:** `backend.app.dependencies.get_db` yields SQLModel sessions backed by `backend.app.db.session_scope`, allowing future routes to interact with Postgres while ensuring proper scope handling.
- **Configuration:** All services import `backend.app.config.settings` so runtime behaviour can be tuned via environment variables (URLs, debug flags, docs endpoints, task routing, etc.).
- **Testing harness:** `backend/tests` relies on `create_app()` to build an in-process FastAPI client, ensuring the documented entrypoints remain stable.
