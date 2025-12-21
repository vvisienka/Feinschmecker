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
_ontology_mtime = None


def _get_ontology_for_tasks():
    """
    Lazily load ontology in Celery worker process.

    This keeps the task stateless from the caller perspective:
    the only inputs are function arguments, ontology is read-only.
    """
    global _ontology, _ontology_version, _ontology_uri_cached, _ontology_mtime
    logger.info("[Celery] Checking for ontology updates...")

    # Try to read published ontology metadata from Redis (published by Flask)
    redis_version = None
    redis_uri = None
    redis_local = None
    try:
        import os
        import redis as _redis

        redis_url = os.getenv('REDIS_URL', 'redis://redis:6379/0')
        r = _redis.from_url(redis_url)
        redis_version_bytes = r.get('feinschmecker:ontology_version')
        redis_uri_bytes = r.get('feinschmecker:ontology_uri')
        redis_local_bytes = r.get('feinschmecker:ontology_local')

        if redis_version_bytes:
            redis_version = redis_version_bytes.decode()
        if redis_uri_bytes:
            redis_uri = redis_uri_bytes.decode()
        if redis_local_bytes:
            redis_local = redis_local_bytes.decode()

        logger.info(f"[Celery] Fetched from Redis: version='{redis_version}', uri='{redis_uri}', local_path='{redis_local}'")

    except Exception as e:
        logger.error(f"[Celery] Could not connect to Redis to check for ontology updates: {e}", exc_info=True)


    # Determine which ontology URI to use
    config = get_config()
    if redis_local:
        ontology_uri = Path(redis_local).resolve().as_uri()
    elif redis_uri:
        ontology_uri = redis_uri
    else:
        ontology_uri = config.ONTOLOGY_URL

    if not ontology_uri:
        logger.error("[Celery] Ontology URL/path is not configured and was not found in Redis.")
        raise RuntimeError("ONTOLOGY_URL is not configured")

    # Determine if a reload is needed
    need_reload = False
    reload_reason = ""

    if _ontology is None:
        need_reload = True
        reload_reason = "Ontology not yet loaded in this worker."
    elif redis_version and _ontology_version != redis_version:
        need_reload = True
        reload_reason = f"Redis version changed: old='{_ontology_version}', new='{redis_version}'"
    elif ontology_uri != _ontology_uri_cached:
        need_reload = True
        reload_reason = f"Ontology URI changed: old='{_ontology_uri_cached}', new='{ontology_uri}'"
    else:
        # If using a local file, check its modification time as a fallback
        if redis_local:
            try:
                local_path = Path(redis_local)
                if local_path.exists():
                    mtime = str(int(local_path.stat().st_mtime))
                    if _ontology_mtime != mtime:
                        need_reload = True
                        reload_reason = f"Local file mtime changed: old='{_ontology_mtime}', new='{mtime}'"
                else:
                    logger.warning(f"[Celery] Local ontology file not found at path from Redis: {redis_local}")
            except Exception as e:
                logger.error(f"[Celery] Error checking local file mtime: {e}", exc_info=True)

    if not need_reload:
        logger.info("[Celery] Ontology is up-to-date. No reload needed.")
        return _ontology

    logger.info(f"[Celery] Reloading ontology. Reason: {reload_reason}")
    logger.info(f"[Celery] Loading from URI: {ontology_uri}")
    logger.info(f"[Celery] Previous state: version='{_ontology_version}', uri='{_ontology_uri_cached}', mtime='{_ontology_mtime}'")

    # Wait for the ontology file/URL to be available
    try:
        cfg = get_config()
        wait_timeout = float(getattr(cfg, 'ONTOLOGY_WAIT_TIMEOUT', 10.0))
        wait_interval = float(getattr(cfg, 'ONTOLOGY_WAIT_POLL_INTERVAL', 1.0))

        if ontology_uri.startswith('file://'):
            path = unquote(urlparse(ontology_uri).path)
            start_time = time.time()
            while not Path(path).exists():
                if time.time() - start_time > wait_timeout:
                    raise FileNotFoundError(f"Ontology file not found after waiting {wait_timeout}s: {path}")
                logger.info(f"[Celery] Waiting for ontology file to appear at: {path}")
                time.sleep(wait_interval)
        
        elif ontology_uri.startswith(('http://', 'https://')):
            start_time = time.time()
            while True:
                try:
                    with urlopen(ontology_uri, timeout=5) as resp:
                        if 200 <= resp.getcode() < 400:
                            logger.info(f"[Celery] Ontology URL is reachable: {ontology_uri}")
                            break
                except Exception as e:
                    if time.time() - start_time > wait_timeout:
                        raise ConnectionError(f"Ontology URL not reachable after {wait_timeout}s: {ontology_uri}") from e
                logger.info(f"[Celery] Waiting for ontology URL to be reachable: {ontology_uri}")
                time.sleep(wait_interval)
                
    except Exception as e:
        logger.error(f"[Celery] Failure waiting for ontology source: {e}", exc_info=True)
        raise

    # Load the ontology
    try:
        loaded_ontology = get_ontology(ontology_uri).load()
        logger.info("[Celery] Ontology loaded successfully into memory.")
        
        # Update cache state
        _ontology = loaded_ontology
        _ontology_version = redis_version
        _ontology_uri_cached = ontology_uri
        
        if redis_local:
            try:
                lp = Path(redis_local)
                if lp.exists():
                    _ontology_mtime = str(int(lp.stat().st_mtime))
                    logger.info(f"[Celery] Updated cached mtime to '{_ontology_mtime}' for local file.")
            except Exception:
                 logger.exception('[Celery] Failed to update mtime after loading ontology.')

        return _ontology

    except Exception as e:
        logger.error(f"[Celery] A critical error occurred while loading the ontology: {e}", exc_info=True)
        # Keep the old ontology if loading fails, to not break all subsequent tasks
        if _ontology:
            logger.warning("[Celery] Keeping stale ontology due to load failure.")
            return _ontology
        raise RuntimeError("Failed to load ontology and no cached version is available.")


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
        
        
        
        try:
            ontology = _get_ontology_for_tasks()
            if not ontology:
                # This can happen if loading failed and there was no previous version.
                raise RuntimeError("Ontology could not be loaded and no cached version was available.")
        except Exception as exc:
            logger.error(
                "[Celery] Permanent failure during ontology loading "
                f"(task_id={self.request.id}): {exc}",
                exc_info=True,
            )
            # Do not retry, as this is a configuration or file system issue.
            raise

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
