import os
import multiprocessing
from celery import Celery

# Use Docker service name if available, fallback to localhost
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)

# Worker concurrency configuration - defaults to CPU count
CELERY_WORKER_CONCURRENCY = int(os.getenv("CELERY_WORKER_CONCURRENCY", multiprocessing.cpu_count()))

celery = Celery(
    "feinschmecker",
    broker=REDIS_URL,
    backend=RESULT_BACKEND,
)

celery.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    enable_utc=True,
    timezone="Europe/Warsaw",
    # Task discovery - auto-discover tasks from app.tasks module
    imports=("backend.app.tasks.recipe_tasks",),
    # Task routing
    task_routes={
        "recipes.*": {"queue": "celery"},
    },
    task_time_limit=30,        # twardy limit – po 30 s Celery zabije task
    task_soft_time_limit=20,   # miękki limit – task dostaje „ostrzeżenie”
    # Worker concurrency configuration
    worker_concurrency=CELERY_WORKER_CONCURRENCY,
    worker_prefetch_multiplier=1,  # Prevents task hoarding - ensures even distribution across workers
)
