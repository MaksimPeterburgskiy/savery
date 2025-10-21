# AGENTS.md

## Instructions
Always search for the most up-to-date documentation and resources instead of relying solely on your own knowledge using context7 or alternatively web search.


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

## Technology
- Frontend: Expo Router, `reactnativereusables`, TypeScript, Tailwind 
- Backend: FastAPI, SQLModel, Celery, RabbitMQ, PostgreSQL + PostGIS + pgvector, Pint.
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
