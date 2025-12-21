"""
Recipe CRUD endpoints.

Create, update and delete recipe individuals in the loaded ontology.
On successful change the endpoints publish an ontology version bump into Redis
so workers can lazily reload the updated ontology.
"""

import logging
import time
import os
from flask import request, current_app
from owlready2 import default_world

from backend.app.api import api_bp
from backend.app.utils.response import success_response, error_response, validation_error_response
from backend.app import limiter

logger = logging.getLogger(__name__)


def _sanitize_name(name: str) -> str:
    return str(name).lower().replace(" ", "_").replace("%", "percent").replace("&", "and")


def _publish_version_to_redis():
    try:
        import redis as _redis
        redis_url = os.getenv('REDIS_URL', 'redis://redis:6379/0')
        r = _redis.from_url(redis_url)
        ver = str(int(time.time()))
        r.set('feinschmecker:ontology_version', ver)
        # If we have a local ontology file configured, publish its path and a readiness flag
        try:
            ontology_local = current_app.config.get('ONTOLOGY_LOCAL_PATH')
            if ontology_local:
                r.set('feinschmecker:ontology_local', str(ontology_local))
                r.set('feinschmecker:ontology_ready', ver)
        except Exception:
            logger.exception('Failed to publish ontology_local/readiness to Redis')

        logger.info("Published ontology_version (and local/readiness if present) to Redis after change")
    except Exception:
        logger.exception("Failed to publish ontology version to Redis")


def _find_class(onto, class_name: str):
    for c in onto.classes():
        if c.name == class_name:
            return c
    return None


def _get_individual(onto, identifier: str):
    # identifier may be an ontology local name (sanitized)
    try:
        return onto[identifier]
    except Exception:
        return None


@api_bp.route('/recipes/crud', methods=['POST'])
@limiter.limit('20 per minute')
def create_recipe():
    """Create a new recipe individual.

    Body JSON (partial example):
    {
      "title": "My Recipe",
      "instructions": "Mix and bake.",
      "ingredients": ["1 egg", "200g flour"],
      "time": 25,
      "vegan": false,
      "vegetarian": true,
      "author": "Alice"
    }
    """
    data = request.get_json(force=True, silent=True)
    if not data:
        return validation_error_response([{'field': 'body', 'message': 'JSON body required'}])

    title = data.get('title')
    if not title:
        return validation_error_response([{'field': 'title', 'message': 'Title is required'}])

    from backend.app import get_ontology_instance

    onto = get_ontology_instance()
    if onto is None:
        return error_response('No ontology loaded', code='NO_ONTOLOGY', status_code=500)

    local_name = _sanitize_name(title)
    if _get_individual(onto, local_name) is not None:
        return validation_error_response([{'field': 'title', 'message': 'Recipe already exists'}])

    RecipeClass = _find_class(onto, 'Recipe')
    if RecipeClass is None:
        return error_response('Recipe class not found in ontology', code='NO_CLASS', status_code=500)

    try:
        with onto:
            recipe = RecipeClass(local_name)

            # Required data properties
            if hasattr(recipe, 'has_recipe_name'):
                recipe.has_recipe_name.append(title)
            if hasattr(recipe, 'has_instructions') and data.get('instructions'):
                recipe.has_instructions.append(str(data.get('instructions')))
            if hasattr(recipe, 'is_vegan'):
                recipe.is_vegan.append(bool(data.get('vegan', False)))
            if hasattr(recipe, 'is_vegetarian'):
                recipe.is_vegetarian.append(bool(data.get('vegetarian', False)))

            # Time (required)
            if hasattr(recipe, 'requires_time') and 'time' in data:
                TimeClass = _find_class(onto, 'Time')
                if TimeClass:
                    tname = f"time_{int(data.get('time'))}"
                    tinst_name = tname if onto[tname] is None else tname + '_' + str(int(time.time()))
                    tinst = TimeClass(tinst_name)
                    if hasattr(tinst, 'amount_of_time'):
                        tinst.amount_of_time.append(int(data.get('time')))
                    recipe.requires_time.append(tinst)

            # Difficulty (required)
            if hasattr(recipe, 'has_difficulty') and 'difficulty' in data:
                DifficultyClass = _find_class(onto, 'Difficulty')
                if DifficultyClass:
                    dname = f"difficulty_{int(data.get('difficulty'))}"
                    # try to reuse existing difficulty individual if present
                    dinst = onto[dname] if onto[dname] is not None else DifficultyClass(dname)
                    if hasattr(dinst, 'has_numeric_difficulty') and not getattr(dinst, 'has_numeric_difficulty'):
                        dinst.has_numeric_difficulty.append(int(data.get('difficulty')))
                    recipe.has_difficulty.append(dinst)

            # Meal type (optional)
            if 'meal_type' in data and data.get('meal_type'):
                MealTypeClass = _find_class(onto, 'MealType')
                if MealTypeClass:
                    mtname = _sanitize_name(data.get('meal_type'))
                    mtinst = onto[mtname] if onto[mtname] is not None else MealTypeClass(mtname)
                    if hasattr(mtinst, 'has_meal_type_name') and not getattr(mtinst, 'has_meal_type_name'):
                        mtinst.has_meal_type_name.append(data.get('meal_type'))
                    recipe.is_meal_type.append(mtinst)

            # Ingredients (IngredientWithAmount linked to Ingredient)
            if 'ingredients' in data and hasattr(recipe, 'has_ingredient'):
                IngredientClass = _find_class(onto, 'Ingredient')
                IngredientWithAmount = _find_class(onto, 'IngredientWithAmount')
                for ing in data.get('ingredients'):
                    # parse string into amount/unit/name loosely
                    ing_text = str(ing)
                    parts = ing_text.split()
                    amount = None
                    unit = None
                    name_parts = []
                    if parts:
                        # if first token is numeric-looking
                        try:
                            amount = float(parts[0])
                            rest = parts[1:]
                        except Exception:
                            # no numeric amount
                            rest = parts
                        if rest:
                            # if second token is a short unit (e.g., g, cup), treat as unit
                            if len(rest[0]) <= 4 and not any(c.isalpha() == False for c in rest[0]):
                                unit = rest[0]
                                name_parts = rest[1:]
                            else:
                                name_parts = rest
                    name = ' '.join(name_parts) if name_parts else ing_text

                    # create/find base Ingredient
                    if IngredientClass:
                        iname = _sanitize_name(name)
                        ingredient_inst = onto[iname] if onto[iname] is not None else IngredientClass(iname)
                        if hasattr(ingredient_inst, 'has_ingredient_name') and not getattr(ingredient_inst, 'has_ingredient_name'):
                            ingredient_inst.has_ingredient_name.append(name)
                    else:
                        ingredient_inst = None

                    if IngredientWithAmount:
                        iwam_name = _sanitize_name(str(ing_text))
                        iwam_inst = onto[iwam_name] if onto[iwam_name] is not None else IngredientWithAmount(iwam_name)
                        if hasattr(iwam_inst, 'has_ingredient_with_amount_name') and not getattr(iwam_inst, 'has_ingredient_with_amount_name'):
                            iwam_inst.has_ingredient_with_amount_name.append(ing_text)
                        if amount is not None and hasattr(iwam_inst, 'amount_of_ingredient'):
                            try:
                                iwam_inst.amount_of_ingredient.append(float(amount))
                            except Exception:
                                pass
                        if unit and hasattr(iwam_inst, 'unit_of_ingredient'):
                            iwam_inst.unit_of_ingredient.append(unit)
                        if ingredient_inst and hasattr(iwam_inst, 'type_of_ingredient'):
                            iwam_inst.type_of_ingredient.append(ingredient_inst)
                        recipe.has_ingredient.append(iwam_inst)

            # Nutrients (required)
            NutrientsMap = [
                ('Calories', 'has_calories', 'amount_of_calories'),
                ('Protein', 'has_protein', 'amount_of_protein'),
                ('Fat', 'has_fat', 'amount_of_fat'),
                ('Carbohydrates', 'has_carbohydrates', 'amount_of_carbohydrates'),
            ]
            for cls_name, prop_name, amount_prop in NutrientsMap:
                cls = _find_class(onto, cls_name)
                if cls:
                    # map to fields
                    val = None
                    if cls_name == 'Calories':
                        val = data.get('calories')
                    elif cls_name == 'Protein':
                        val = data.get('protein')
                    elif cls_name == 'Fat':
                        val = data.get('fat')
                    elif cls_name == 'Carbohydrates':
                        val = data.get('carbohydrates')
                    if val is not None:
                        iname = f"{cls_name.lower()}_{str(val).replace('.', '_')}"
                        inst = onto[iname] if onto[iname] is not None else cls(iname)
                        if hasattr(inst, amount_prop) and not getattr(inst, amount_prop):
                            try:
                                getattr(inst, amount_prop).append(float(val))
                            except Exception:
                                pass
                        # attach to recipe
                        if hasattr(recipe, prop_name):
                            getattr(recipe, prop_name).append(inst)

            # Author and Source
            if 'author' in data and (hasattr(recipe, 'authored_by') or hasattr(recipe, 'has_author')):
                AuthorClass = _find_class(onto, 'Author')
                SourceClass = _find_class(onto, 'Source')
                source_inst = None
                if data.get('source_name') and SourceClass:
                    sname = _sanitize_name(data.get('source_name'))
                    source_inst = onto[sname] if onto[sname] is not None else SourceClass(sname)
                    if hasattr(source_inst, 'has_source_name') and not getattr(source_inst, 'has_source_name'):
                        source_inst.has_source_name.append(data.get('source_name'))
                    if data.get('source_link') and hasattr(source_inst, 'is_website'):
                        source_inst.is_website.append(data.get('source_link'))
                if AuthorClass:
                    aname = _sanitize_name(data.get('author'))
                    author_inst = onto[aname] if onto[aname] is not None else AuthorClass(aname)
                    if hasattr(author_inst, 'has_author_name') and not getattr(author_inst, 'has_author_name'):
                        author_inst.has_author_name.append(data.get('author'))
                    if source_inst and hasattr(author_inst, 'is_author_of'):
                        author_inst.is_author_of.append(source_inst)
                    if hasattr(recipe, 'authored_by'):
                        recipe.authored_by.append(author_inst)

            # Links (optional)
            if 'link' in data and hasattr(recipe, 'has_link') and data.get('link'):
                recipe.has_link.append(data.get('link'))
            if 'image_link' in data and hasattr(recipe, 'has_image_link') and data.get('image_link'):
                recipe.has_image_link.append(data.get('image_link'))

        # Persist ontology to disk if we have a resolved local path (downloaded or configured)
        # Persist ontology to disk atomically if we have a resolved local path (downloaded or configured)
        try:
            ontology_local = current_app.config.get('ONTOLOGY_LOCAL_PATH')
            if ontology_local:
                from pathlib import Path
                import os
                abs_path = Path(ontology_local).resolve()
                tmp_path = abs_path.with_suffix(abs_path.suffix + f'.part.{os.getpid()}')
                try:
                    onto.save(file=str(tmp_path))
                    os.replace(str(tmp_path), str(abs_path))
                    logger.info(f'Persisted ontology atomically to {abs_path}')
                except Exception:
                    logger.exception('Failed to atomically persist ontology after create')
                finally:
                    try:
                        if tmp_path.exists():
                            tmp_path.unlink()
                    except Exception:
                        pass
        except Exception:
            logger.exception('Failed to persist ontology to file after create')

        # Publish version bump (and local/readiness) to Redis
        _publish_version_to_redis()

        return success_response(data={'id': local_name}, message='Recipe created')

    except Exception as e:
        logger.exception('Failed to create recipe')
        return error_response(message=str(e), code='CREATE_FAILED', status_code=500)


@api_bp.route('/recipes/crud/<recipe_id>', methods=['PATCH'])
@limiter.limit('30 per minute')
def update_recipe(recipe_id):
    data = request.get_json(force=True, silent=True)
    if not data:
        return validation_error_response([{'field': 'body', 'message': 'JSON body required'}])

    from backend.app import get_ontology_instance
    onto = get_ontology_instance()
    if onto is None:
        return error_response('No ontology loaded', code='NO_ONTOLOGY', status_code=500)

    individual = _get_individual(onto, recipe_id)
    if individual is None:
        return validation_error_response([{'field': 'id', 'message': 'Recipe not found'}])

    try:
        with onto:
            # Update simple fields
            if 'title' in data and hasattr(individual, 'has_recipe_name'):
                individual.has_recipe_name = [data.get('title')]
            if 'instructions' in data and hasattr(individual, 'has_instructions'):
                individual.has_instructions = [str(data.get('instructions'))]
            if 'vegan' in data and hasattr(individual, 'is_vegan'):
                individual.is_vegan = [bool(data.get('vegan'))]
            if 'vegetarian' in data and hasattr(individual, 'is_vegetarian'):
                individual.is_vegetarian = [bool(data.get('vegetarian'))]

            # Update time
            if 'time' in data and hasattr(individual, 'requires_time'):
                # remove existing time links (and possibly instances)
                old_times = list(individual.requires_time)
                for ot in old_times:
                    try:
                        individual.requires_time.remove(ot)
                    except Exception:
                        pass
                TimeClass = _find_class(onto, 'Time')
                if TimeClass:
                    tname = f"time_{int(data.get('time'))}"
                    tinst = onto[tname] if onto[tname] is not None else TimeClass(tname)
                    if hasattr(tinst, 'amount_of_time') and not getattr(tinst, 'amount_of_time'):
                        tinst.amount_of_time.append(int(data.get('time')))
                    individual.requires_time.append(tinst)

            # Update difficulty
            if 'difficulty' in data and hasattr(individual, 'has_difficulty'):
                old_diffs = list(individual.has_difficulty)
                for od in old_diffs:
                    try:
                        individual.has_difficulty.remove(od)
                    except Exception:
                        pass
                DifficultyClass = _find_class(onto, 'Difficulty')
                if DifficultyClass:
                    dname = f"difficulty_{int(data.get('difficulty'))}"
                    dinst = onto[dname] if onto[dname] is not None else DifficultyClass(dname)
                    if hasattr(dinst, 'has_numeric_difficulty') and not getattr(dinst, 'has_numeric_difficulty'):
                        dinst.has_numeric_difficulty.append(int(data.get('difficulty')))
                    individual.has_difficulty.append(dinst)

            # Update meal type
            if 'meal_type' in data and hasattr(individual, 'is_meal_type'):
                old_mts = list(individual.is_meal_type)
                for om in old_mts:
                    try:
                        individual.is_meal_type.remove(om)
                    except Exception:
                        pass
                if data.get('meal_type'):
                    MealTypeClass = _find_class(onto, 'MealType')
                    if MealTypeClass:
                        mtname = _sanitize_name(data.get('meal_type'))
                        mtinst = onto[mtname] if onto[mtname] is not None else MealTypeClass(mtname)
                        if hasattr(mtinst, 'has_meal_type_name') and not getattr(mtinst, 'has_meal_type_name'):
                            mtinst.has_meal_type_name.append(data.get('meal_type'))
                        individual.is_meal_type.append(mtinst)

            # Update nutrients
            NutrientsMap = [
                ('Calories', 'has_calories', 'amount_of_calories', 'calories'),
                ('Protein', 'has_protein', 'amount_of_protein', 'protein'),
                ('Fat', 'has_fat', 'amount_of_fat', 'fat'),
                ('Carbohydrates', 'has_carbohydrates', 'amount_of_carbohydrates', 'carbohydrates'),
            ]
            for cls_name, prop_name, amount_prop, field in NutrientsMap:
                if field in data and hasattr(individual, prop_name):
                    # detach old
                    old_vals = list(getattr(individual, prop_name))
                    for ov in old_vals:
                        try:
                            getattr(individual, prop_name).remove(ov)
                        except Exception:
                            pass
                    cls = _find_class(onto, cls_name)
                    if cls:
                        val = data.get(field)
                        iname = f"{cls_name.lower()}_{str(val).replace('.', '_')}"
                        inst = onto[iname] if onto[iname] is not None else cls(iname)
                        if hasattr(inst, amount_prop) and not getattr(inst, amount_prop):
                            try:
                                getattr(inst, amount_prop).append(float(val))
                            except Exception:
                                pass
                        getattr(individual, prop_name).append(inst)

            # Update links
            if 'link' in data and hasattr(individual, 'has_link'):
                individual.has_link = [data.get('link')]
            if 'image_link' in data and hasattr(individual, 'has_image_link'):
                individual.has_image_link = [data.get('image_link')]

            # Update ingredients: remove old IngredientWithAmount entries linked to this recipe, then add new
            if 'ingredients' in data and hasattr(individual, 'has_ingredient'):
                old_ings = list(individual.has_ingredient)
                for oi in old_ings:
                    try:
                        individual.has_ingredient.remove(oi)
                    except Exception:
                        pass
                    try:
                        default_world.remove_entity(oi)
                    except Exception:
                        pass
                IngredientClass = _find_class(onto, 'Ingredient')
                IngredientWithAmount = _find_class(onto, 'IngredientWithAmount')
                for ing in data.get('ingredients'):
                    ing_text = str(ing)
                    parts = ing_text.split()
                    amount = None
                    unit = None
                    name_parts = []
                    if parts:
                        try:
                            amount = float(parts[0])
                            rest = parts[1:]
                        except Exception:
                            rest = parts
                        if rest:
                            if len(rest[0]) <= 4 and not any(c.isalpha() == False for c in rest[0]):
                                unit = rest[0]
                                name_parts = rest[1:]
                            else:
                                name_parts = rest
                    name = ' '.join(name_parts) if name_parts else ing_text
                    if IngredientClass:
                        iname = _sanitize_name(name)
                        ingredient_inst = onto[iname] if onto[iname] is not None else IngredientClass(iname)
                        if hasattr(ingredient_inst, 'has_ingredient_name') and not getattr(ingredient_inst, 'has_ingredient_name'):
                            ingredient_inst.has_ingredient_name.append(name)
                    else:
                        ingredient_inst = None
                    if IngredientWithAmount:
                        iwam_name = _sanitize_name(str(ing_text))
                        iwam_inst = onto[iwam_name] if onto[iwam_name] is not None else IngredientWithAmount(iwam_name)
                        if hasattr(iwam_inst, 'has_ingredient_with_amount_name') and not getattr(iwam_inst, 'has_ingredient_with_amount_name'):
                            iwam_inst.has_ingredient_with_amount_name.append(ing_text)
                        if amount is not None and hasattr(iwam_inst, 'amount_of_ingredient'):
                            try:
                                iwam_inst.amount_of_ingredient.append(float(amount))
                            except Exception:
                                pass
                        if unit and hasattr(iwam_inst, 'unit_of_ingredient'):
                            iwam_inst.unit_of_ingredient.append(unit)
                        if ingredient_inst and hasattr(iwam_inst, 'type_of_ingredient'):
                            iwam_inst.type_of_ingredient.append(ingredient_inst)
                        individual.has_ingredient.append(iwam_inst)

        try:
            ontology_local = current_app.config.get('ONTOLOGY_LOCAL_PATH')
            if ontology_local:
                from pathlib import Path
                import os
                abs_path = Path(ontology_local).resolve()
                tmp_path = abs_path.with_suffix(abs_path.suffix + f'.part.{os.getpid()}')
                try:
                    onto.save(file=str(tmp_path))
                    os.replace(str(tmp_path), str(abs_path))
                    logger.info(f'Persisted ontology atomically to {abs_path}')
                except Exception:
                    logger.exception('Failed to atomically persist ontology after update')
                finally:
                    try:
                        if tmp_path.exists():
                            tmp_path.unlink()
                    except Exception:
                        pass
        except Exception:
            logger.exception('Failed to persist ontology to file after update')

        _publish_version_to_redis()

        return success_response(message='Recipe updated')

    except Exception as e:
        logger.exception('Failed to update recipe')
        return error_response(message=str(e), code='UPDATE_FAILED', status_code=500)


@api_bp.route('/recipes/crud/<recipe_id>', methods=['DELETE'])
@limiter.limit('10 per minute')
def delete_recipe(recipe_id):
    from backend.app import get_ontology_instance
    onto = get_ontology_instance()
    if onto is None:
        return error_response('No ontology loaded', code='NO_ONTOLOGY', status_code=500)

    individual = _get_individual(onto, recipe_id)
    if individual is None:
        return validation_error_response([{'field': 'id', 'message': 'Recipe not found'}])

    try:
        # Collect linked instances to possibly cleanup (nutrients, time, ingredientWithAmount)
        linked = {
            'ingredients': list(individual.has_ingredient) if hasattr(individual, 'has_ingredient') else [],
            'calories': list(individual.has_calories) if hasattr(individual, 'has_calories') else [],
            'protein': list(individual.has_protein) if hasattr(individual, 'has_protein') else [],
            'fat': list(individual.has_fat) if hasattr(individual, 'has_fat') else [],
            'carbohydrates': list(individual.has_carbohydrates) if hasattr(individual, 'has_carbohydrates') else [],
            'time': list(individual.requires_time) if hasattr(individual, 'requires_time') else [],
        }

        # remove individual from ontology
        with onto:
            # detach links first
            try:
                # clear relationships from recipe
                if hasattr(individual, 'has_ingredient'):
                    for i in list(individual.has_ingredient):
                        try:
                            individual.has_ingredient.remove(i)
                        except Exception:
                            pass
                for prop in ('has_calories', 'has_protein', 'has_fat', 'has_carbohydrates', 'requires_time'):
                    if hasattr(individual, prop):
                        for v in list(getattr(individual, prop)):
                            try:
                                getattr(individual, prop).remove(v)
                            except Exception:
                                pass
            except Exception:
                logger.exception('Error detaching linked instances')

            default_world.remove_entity(individual)

        # cleanup orphaned linked instances if they have no backrefs
        def _cleanup(inst, inverse_attr_names):
            try:
                for inv in inverse_attr_names:
                    if hasattr(inst, inv) and list(getattr(inst, inv)):
                        return
                # no inverse links -> remove
                default_world.remove_entity(inst)
            except Exception:
                pass

        # cleanup ingredientWithAmount entries
        for i in linked['ingredients']:
            try:
                # IngredientWithAmount has inverse 'used_for'
                if hasattr(i, 'used_for') and not list(i.used_for):
                    default_world.remove_entity(i)
            except Exception:
                pass

        # cleanup nutrients and time if orphaned
        for n in linked['calories'] + linked['protein'] + linked['fat'] + linked['carbohydrates']:
            try:
                # check inverse property (e.g., calories_of)
                invs = [a for a in dir(n.__class__) if a.endswith('_of')]
                orphan = True
                for inv in invs:
                    if hasattr(n, inv) and list(getattr(n, inv)):
                        orphan = False
                        break
                if orphan:
                    default_world.remove_entity(n)
            except Exception:
                pass

        for t in linked['time']:
            try:
                if hasattr(t, 'time_required_by') and not list(t.time_required_by):
                    default_world.remove_entity(t)
            except Exception:
                pass

        try:
            ontology_local = current_app.config.get('ONTOLOGY_LOCAL_PATH')
            if ontology_local:
                from pathlib import Path
                import os
                abs_path = Path(ontology_local).resolve()
                tmp_path = abs_path.with_suffix(abs_path.suffix + f'.part.{os.getpid()}')
                try:
                    onto.save(file=str(tmp_path))
                    os.replace(str(tmp_path), str(abs_path))
                    logger.info(f'Persisted ontology atomically to {abs_path}')
                except Exception:
                    logger.exception('Failed to atomically persist ontology after delete')
                finally:
                    try:
                        if tmp_path.exists():
                            tmp_path.unlink()
                    except Exception:
                        pass
        except Exception:
            logger.exception('Failed to persist ontology to file after delete')

        _publish_version_to_redis()

        return success_response(message='Recipe deleted')

    except Exception as e:
        logger.exception('Failed to delete recipe')
        return error_response(message=str(e), code='DELETE_FAILED', status_code=500)
