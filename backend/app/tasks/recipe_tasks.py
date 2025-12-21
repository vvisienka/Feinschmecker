# backend/app/tasks/recipe_tasks.py
"""
Celery tasks for recipe search.

This module moves the expensive ontology/SPARQL queries to background
Celery workers.
"""

import logging
from typing import Any, Dict
import time
from owlready2 import get_ontology
from urllib.request import urlopen
from urllib.parse import urlparse, unquote
from pathlib import Path
from celery.exceptions import SoftTimeLimitExceeded
from backend.celery_config import celery
from backend.config import get_config
from backend.app.services.recipe_service import RecipeService

logger = logging.getLogger(__name__)

# cache na poziomie workera, żeby nie ładować ontologii przy każdym tasku
_ontology = None
_ontology_version = None
_ontology_uri_cached = None


def _get_ontology_for_tasks():
    """
    Lazily load ontology in Celery worker process.

    This keeps the task stateless from the caller perspective:
    the only inputs are function arguments, ontology is read-only.
    """
    global _ontology, _ontology_version, _ontology_uri_cached

    # Try to read a published ontology URI/version from Redis (published by Flask)
    try:
        import os
        import redis as _redis

        redis_url = os.getenv('REDIS_URL', 'redis://redis:6379/0')
        r = _redis.from_url(redis_url)
        redis_version = r.get('feinschmecker:ontology_version')
        redis_uri = r.get('feinschmecker:ontology_uri')
        if redis_version is not None:
            redis_version = redis_version.decode() if isinstance(redis_version, bytes) else str(redis_version)
        if redis_uri is not None:
            redis_uri = redis_uri.decode() if isinstance(redis_uri, bytes) else str(redis_uri)
    except Exception:
        redis_version = None
        redis_uri = None

    # Determine which ontology URI to use: prefer Redis-published resolved URI
    config = get_config()
    if redis_uri:
        ontology_uri = redis_uri
    else:
        ontology_uri = config.ONTOLOGY_URL

    if not ontology_uri:
        raise RuntimeError("ONTOLOGY_URL is not configured")

    # If we don't have an ontology yet, or the version/URI changed, (re)load
    need_reload = False
    if _ontology is None:
        need_reload = True
    elif redis_version and _ontology_version != redis_version:
        need_reload = True
    elif redis_uri and _ontology_uri_cached != redis_uri:
        need_reload = True

    if need_reload:
        logger.info(f"[Celery] Loading ontology from {ontology_uri} (reload={_ontology is not None})")

        # If ontology is a file:// URI, wait for the file to be present first.
        try:
            cfg = get_config()
            wait_timeout = float(getattr(cfg, 'ONTOLOGY_WAIT_TIMEOUT', 30))
            wait_interval = float(getattr(cfg, 'ONTOLOGY_WAIT_POLL_INTERVAL', 1.0))
        except Exception:
            wait_timeout = 30.0
            wait_interval = 1.0


        if isinstance(ontology_uri, str):
            if ontology_uri.startswith('file://'):
                parsed = urlparse(ontology_uri)
                path = unquote(parsed.path)

                logger.info(f"[Celery] Waiting up to {wait_timeout}s for ontology file {path}")
                waited = 0.0
                while waited < wait_timeout:
                    if Path(path).exists():
                        break
                    time.sleep(wait_interval)
                    waited += wait_interval

                if not Path(path).exists():
                    msg = f"Ontology file not available after waiting {wait_timeout}s: {path}"
                    logger.warning(f"[Celery] {msg}")
                    raise FileNotFoundError(msg)

            elif ontology_uri.startswith('http://') or ontology_uri.startswith('https://'):
                # Wait for the remote URL to be reachable (HEAD/GET) before letting Owlready2 fetch it.
                logger.info(f"[Celery] Waiting up to {wait_timeout}s for ontology URL {ontology_uri}")
                waited = 0.0
                reachable = False
                while waited < wait_timeout:
                    try:
                        resp = urlopen(ontology_uri, timeout=5)
                        # simple check: HTTP 2xx or content present
                        if resp.getcode() and 200 <= resp.getcode() < 400:
                            reachable = True
                            break
                    except Exception:
                        pass
                    time.sleep(wait_interval)
                    waited += wait_interval

                if not reachable:
                    msg = f"Ontology URL not reachable after waiting {wait_timeout}s: {ontology_uri}"
                    logger.warning(f"[Celery] {msg}")
                    raise FileNotFoundError(msg)

        _ontology = get_ontology(ontology_uri).load()
        logger.info("[Celery] Ontology loaded successfully in worker")
        _ontology_version = redis_version
        _ontology_uri_cached = redis_uri or ontology_uri

    return _ontology


# typy błędów, które traktujemy jako „chwilowe” i warto spróbować ponownie
TRANSIENT_EXCEPTIONS = (
    TimeoutError,
    ConnectionError,
    OSError,
)


@celery.task(
    name="recipes.search_recipes",
    bind=True,
    max_retries=3,  # maksymalnie 3 próby
)
def search_recipes_async(
    self,
    filters: Dict[str, Any],
    page: int,
    per_page: int,
) -> Dict[str, Any]:
    """
    Asynchronous recipe search task with retries and logging.

    Returns a JSON-serializable dict with recipes and pagination metadata.

    Retries:
    - for TRANSIENT_EXCEPTIONS: exponential backoff, max 3 attempts
    """
    try:
        logger.info(
            "[Celery] Starting recipe search task "
            f"(task_id={self.request.id}, page={page}, per_page={per_page})"
        )
        
        
        # === TEST HOOKS (DEV ONLY) ===
        # 1) wymuszenie chwilowego błędu -> sprawdzamy retry
        # if filters.get("force_transient_error") == "1":
        #     raise TimeoutError("Simulated transient error for retry testing")

        # # 2) wymuszenie timeoutu -> sprawdzamy SoftTimeLimitExceeded
        # if filters.get("force_soft_timeout") == "1":
        #     # śpimy dłużej niż soft_time_limit (20s), żeby Celery zabił task
        #     time.sleep(25)
        # === KONIEC TEST HOOKS ===
        
        
        
        ontology = _get_ontology_for_tasks()
        service = RecipeService(ontology)

        recipes, total_count = service.get_recipes(filters, page, per_page)

        logger.info(
            "[Celery] Recipe search completed "
            f"(task_id={self.request.id}, total={total_count})"
        )

        return {
            "recipes": recipes,
            "page": page,
            "per_page": per_page,
            "total": total_count,
        }

    except TRANSIENT_EXCEPTIONS as exc:
        # FEIN-68 + FEIN-69: log i retry przy chwilowych problemach
        retry_no = self.request.retries + 1
        # prosty exponential backoff: 2,4,8 sekund (max 30)
        countdown = min(2 ** retry_no, 30)

        logger.warning(
            "[Celery] Transient error in recipe search "
            f"(task_id={self.request.id}, retry={retry_no}/{self.max_retries}, "
            f"countdown={countdown}s): {exc}"
        )

        # jeśli przekroczymy max_retries, Celery podbije MaxRetriesExceededError
        raise self.retry(exc=exc, countdown=countdown)

    except SoftTimeLimitExceeded as exc:
        # czas taska się skończył – logujemy i zwracamy FAILURE
        logger.error(
            "[Celery] Soft time limit exceeded in recipe search "
            f"(task_id={self.request.id}): {exc}",
            exc_info=True,
        )
        # nie retryujemy, bo już przekroczyliśmy limit czasu
        raise

    except Exception as exc:
        # FEIN-69: logowanie wszystkich innych błędów jako permanent failure
        logger.error(
            "[Celery] Permanent failure in recipe search "
            f"(task_id={self.request.id}): {exc}",
            exc_info=True,
        )
        # nie retry – to raczej bug w logice niż chwilowy problem
        raise
