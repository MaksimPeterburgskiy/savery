# AGENTS.md

## Instructions

Always search for the most up-to-date documentation and resources instead of relying solely on your own knowledge using context7 or alternatively web search.
Make sure to use a venv (one should already exist in the backend folder) when working in the backend folder. If it doesn't exist, create one using the make_env tool. Use bun, not npm when working in the frontend folder.


## Repo Map

- `frontend/` — Expo app.
  - `savery/app/` — screens and routing (Expo Router).
  - `savery/components/` — shared UI components.
  - `savery/lib/` — frontend helpers/utilities.
  - `savery/assets/` — icons/images.
  - Config: `app.json`, `eas.json`, `tailwind.config.js`, `package.json`, `babel.config.js`.
- `backend/` — FastAPI service and supporting code.
  - `app/` — FastAPI entrypoints, SQLModel domain models, configuration, DB utilities.
  - `migrations/` — Alembic environment and revision scripts (uses SQLModel metadata).
  - `workers/` — Celery tasks.
  - `tools/make_env.py` — environment scaffolding.
  - `requirements.txt` — Python dependencies.
- `infra/` — Infrastructure-as-code home (Docker Compose, provisioning, monitoring).
- `project.md` — project plan

## Technologies in Use

- Frontend: Expo SDK, Expo CLI, Expo Router, React Native + React Native Reusables (`@rn-primitives/*`), TypeScript, NativeWind + Tailwind CSS utilities, Bun.
- Backend: FastAPI, SQLModel, Celery, RabbitMQ, DragonflyDB, PostgreSQL + PostGIS + pgvector, Pint.
- DevOps: Docker Compose–driven local stack.

## Where to Add Things

- New screen/route: `frontend/savery/app/`
- Shared UI: `frontend/savery/components/`
- Frontend helpers/state: `frontend/savery/lib/`
- API endpoints/routers: `backend/app/`
- Business logic/domain models/services: `backend/app/`
- Background jobs/tasks: `backend/workers/`
- Python deps: `backend/requirements.txt`
- env scaffolding: `backend/tools/make_env.py`

## Backend Tooling Scripts

- `backend/tools/setup_backend.py`: Verifies Docker is running, ensures the backend virtualenv exists by delegating to `make_env.py`, installs Python dependencies, and warns when Node tooling is missing. Run this before launching services to prep a fresh machine. Optional flag `--force-venv` recreates the environment.
- `backend/tools/run_backend.py`: Starts the supporting Docker containers (Postgres, RabbitMQ, Dragonfly), launches the FastAPI app via uvicorn and the Celery worker, and records state so reruns automatically clean up old processes to prevent port conflicts. Reads environment from `backend/.env`.
- `backend/tools/stop_backend.py`: Convenience helper that reads the saved runner state, terminates uvicorn/Celery, stops the Docker containers, and clears the state file. Useful for manual shutdowns if `run_backend.py` is interrupted.

## Running Backend Tests

- Ensure the backend stack is running first by calling `python backend/tools/run_backend.py` so Postgres, RabbitMQ, Dragonfly, uvicorn, and Celery are up before pytest touches them.
- Activate the backend virtual environment first: `source backend/.venv/bin/activate`. If the environment is missing, recreate it with `python backend/tools/make_env.py`.
- Run the suite from the backend folder: `cd backend && pytest`. Use flags such as `-k <expression>` for filtering or `--cov=app --cov-report=term-missing` for coverage.
- Deactivate the environment when finished with `deactivate`.
