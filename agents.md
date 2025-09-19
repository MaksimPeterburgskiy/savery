# AGENTS.md

## Repo Map (need-to-know)
- `frontend/` — Expo app.
  - `savery/app/` — screens and routing (Expo Router).
  - `savery/components/` — shared UI components.
  - `savery/lib/` — frontend helpers/utilities.
  - `savery/assets/` — icons/images.
  - Config: `app.json`, `eas.json`, `tailwind.config.js`, `package.json`, `babel.config.js`.
- `backend/` — FastAPI service and supporting code.
  - `app/` — API entrypoints (routers/controllers).
  - `core/` — domain models and business services.
  - `workers/` — Celery tasks (item matching, price fetching, route computation).
  - `tools/make_env.py` — environment scaffolding.
  - `requirements.txt` — Python dependencies.
- `infra/` — Infrastructure-as-code home (Docker Compose, provisioning, monitoring).
- `project.md` — Master project plan; use as the source of truth.
- `agents.md` — This orientation doc for agents.

## Technology
- Frontend: Expo Router, `reactnativereusables`, TypeScript, Tailwind config present.
- Backend: FastAPI, Celery, RabbitMQ, PostgreSQL + PostGIS + pgvector, Pint for unit normalization.
- DevOps: Docker Compose–driven local stack (to live under `infra/`), future monitoring via Prometheus/Grafana and error tracking via Sentry/OpenTelemetry.

## Where to Add Things
- New screen/route: `frontend/savery/app/`
- Shared UI: `frontend/savery/components/`
- Frontend helpers/state: `frontend/savery/lib/`
- API endpoints/routers: `backend/app/`
- Business logic/domain models/services: `backend/core/`
- Background jobs/tasks: `backend/workers/`
- Python deps: `backend/requirements.txt`; 
- env scaffolding: `backend/tools/make_env.py`

## Working Notes for Agents
- Place business logic in `backend/core/`; keep API layers in `backend/app/` thin.
- Use Pint for units, PostGIS for geospatial, and pgvector for embeddings/similarity where relevant.
- `infra/` will house Docker Compose and monitoring as it solidifies; prefer adding infra there when ready.

