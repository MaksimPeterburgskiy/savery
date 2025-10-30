# Worker Task Guide

Reference for adding a new Celery task to the backend worker.

1. **Create a module** under `workers/tasks/` and define a `@shared_task` function. Bind the task (`bind=True`) if it needs to call `self.update_state`.
2. **Update the job helpers** in `backend/app/tasks.py` by adding your `JobStage` → task-name mapping inside `_task_name_for_stage` so the API can enqueue it.
3. **Record progress** inside the task using `mark_job_running`, `record_job_progress`, `mark_job_success`, and `mark_job_failed` to persist status in the database.
4. **Expose routing** by importing the new module in `workers/tasks/__init__.py` if you want autodiscovery to pick it up.
5. **Add API support** (optional) by creating endpoints that call `enqueue_job` and `get_job_status` with the appropriate job IDs.

That is all that is required for the worker to discover and execute the new task.
