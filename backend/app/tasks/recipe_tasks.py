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
from ontology.individuals import create_single_recipe, delete_recipe_individual
import os
from ontology.individuals import onthologifyName

logger = logging.getLogger(__name__)

# cache na poziomie workera, żeby nie ładować ontologii przy każdym tasku
_ontology = None
_ontology_version = None
_ontology_uri_cached = None
_ontology_mtime = None


def _get_ontology_for_tasks():
    """
    Load ontology with 'Reset on Reload' logic.
    
    Every time the worker starts (App Reload), it will:
    1. Fetch the fresh base ontology from the URL (RDF/XML).
    2. Overwrite the local .nt file (Factory Reset).
    3. Load it into memory for the session.
    """
    global _ontology
    if _ontology is None:
        config = get_config()
        file_path = config.ONTOLOGY_PATH
        
        logger.info(f"[Celery] 🔄 FRESH START: Fetching base ontology from {config.ONTOLOGY_URL}")
        
        try:
            # 1. Always load from the Source URL first (ignoring local file)
            # This creates an in-memory ontology from the clean RDF source
            _ontology = get_ontology(config.ONTOLOGY_URL).load()
            
            # 2. Immediately overwrite the local 'database' file
            # This wipes any previous deletions/additions from the last session
            logger.info(f"[Celery] 💾 RESETTING local database at {file_path}")
            _ontology.save(file=file_path, format="ntriples")
            
        except Exception as e:
            logger.error(f"[Celery] ⚠️ Failed to fetch remote ontology: {e}")
            # Fallback: If internet fails, try to load the local file if it exists
            if os.path.exists(file_path):
                logger.warning("[Celery] Using existing local file as fallback.")
                _ontology = get_ontology(f"file://{file_path}").load()
            else:
                raise e

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


@celery.task(name="recipes.create_recipe", bind=True)
def create_recipe_async(self, recipe_data: dict):
    """
    Creates a new recipe and SAVES to the .nt file.
    """
    try:
        logger.info(f"[Celery] Creating recipe: {recipe_data.get('title')}")
        onto = _get_ontology_for_tasks()
        config = get_config()

        # 1. Modify the ontology in memory
        with onto:
            create_single_recipe(recipe_data, target_kg=onto)

        # 2. Persist changes to disk
        # This is the Critical Step for CRUD
        onto.save(file=config.ONTOLOGY_PATH, format="ntriples")
        logger.info(f"[Celery] Saved changes to {config.ONTOLOGY_PATH}")

        return {"status": "created", "title": recipe_data.get("title")}

    except Exception as exc:
        logger.error(f"[Celery] Create failed: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=5, max_retries=3)


@celery.task(name="recipes.delete_recipe", bind=True)
def delete_recipe_async(self, recipe_name: str):
    """
    Deletes a recipe and SAVES to the .nt file.
    """
    try:
        logger.info(f"[Celery] Deleting recipe: {recipe_name}")
        onto = _get_ontology_for_tasks()
        config = get_config()

        with onto:
            success = delete_recipe_individual(recipe_name, target_kg=onto)

        if success:
            onto.save(file=config.ONTOLOGY_PATH, format="ntriples")
            logger.info(f"[Celery] Saved deletion to {config.ONTOLOGY_PATH}")
            return {"status": "deleted", "name": recipe_name}
        else:
            return {"status": "not_found", "name": recipe_name}

    except Exception as exc:
        logger.error(f"[Celery] Delete failed: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=5, max_retries=3)
    
    
@celery.task(name="recipes.update_recipe", bind=True)
def update_recipe_async(self, old_slug: str, recipe_data: dict):
    """
    Update a recipe. If title changed, delete old individual and create new one.
    """
    try:
        logger.info(f"[Celery] Updating recipe: {old_slug} -> {recipe_data.get('title')}")
        onto = _get_ontology_for_tasks()
        config = get_config()

        new_title = recipe_data.get("title")
        if not new_title:
             raise ValueError("Recipe title is missing")

        new_slug = onthologifyName(new_title)

        with onto:
            # 1. Handle Rename: If title changed, the ID changes, so delete the old one.
            if old_slug != new_slug:
                logger.info(f"[Celery] Title changed. Deleting old ID: {old_slug}")
                delete_recipe_individual(old_slug, target_kg=onto)

            # 2. Create/Overwrite the recipe with new data
            create_single_recipe(recipe_data, target_kg=onto)

        # 3. Persist
        onto.save(file=config.ONTOLOGY_PATH, format="ntriples")
        logger.info(f"[Celery] Update saved to {config.ONTOLOGY_PATH}")

        return {"status": "updated", "slug": new_slug, "title": new_title}

    except Exception as exc:
        logger.error(f"[Celery] Update failed: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=5, max_retries=3)
    