"""
Functions for creating and managing individuals (instances) in the ontology.

Individuals are created in knowledge graphs (ABox) while classes are defined in schema_onto (TBox).
Supports multiple knowledge graphs for different data sources.
"""

import json
import re
from owlready2 import Thing
from .setup import kg_onto, schema_onto
from .classes import (
    Recipe, Ingredient, IngredientWithAmount, Author, Source,
    Time, MealType, Difficulty, Calories, Protein, Fat, Carbohydrates
)
from .properties import (
    has_recipe_name, has_instructions, has_ingredient, authored_by, requires_time,
    is_meal_type, is_vegan, is_vegetarian, has_difficulty, has_calories, has_protein,
    has_fat, has_carbohydrates, has_link, has_image_link,
    has_ingredient_with_amount_name, amount_of_ingredient, unit_of_ingredient,
    type_of_ingredient, has_ingredient_name, has_author_name, is_author_of,
    has_source_name, is_website, amount_of_time, has_meal_type_name,
    has_numeric_difficulty, amount_of_calories, amount_of_protein,
    amount_of_fat, amount_of_carbohydrates
)


def onthologifyName(name) -> str:
    """
    Convert a name to a valid ontology identifier.
    
    Args:
        name: The name to convert
    
    Returns:
        Sanitized name suitable for use as an ontology identifier
    """
    return str(name).lower().replace(" ", "_").replace("%", "percent").replace("&", "and")


def createIndividual(name, BaseClass, unique=False, target_kg=None) -> tuple[Thing, bool]:
    """
    Create an individual (instance) of a class or return existing one.
    
    Individuals are created in the target knowledge graph ontology.
    
    Args:
        name: Name of the individual to create
        BaseClass: OWL class the individual should be an instance of
        unique: If True, raise error if individual already exists
        target_kg: Target knowledge graph (defaults to kg_onto)
    
    Returns:
        Tuple of (individual, existed) where existed is True if individual already existed
    
    Raises:
        TypeError: If unique=True and individual already exists, or if existing 
                  individual is of different type
    """
    if target_kg is None:
        target_kg = kg_onto
    
    name = onthologifyName(name)
    individual = target_kg[name]

    # If it doesn't exist, create it
    if individual is None:
        with target_kg:
            return BaseClass(name), False
    
    # If it exists and unique=True was requested, fail
    if unique:
        raise TypeError(
            f"Individual {name} already exists:\n"
            f"Existing: {type(individual)}\n"
            f"Requested: {BaseClass}"
        )
    
    # Return existing individual
    # Note: We removed the strict type(individual) != BaseClass check 
    # to allow for reloaded ontologies where class objects might differ slightly.
    return individual, True


def create_meal_types(target_kg=None):
    """
    Create the standard meal type individuals (Breakfast, Lunch, Dinner).
    
    Args:
        target_kg: Target knowledge graph (defaults to kg_onto)
    
    Returns:
        Dictionary mapping meal type names to their individuals
    """
    meal_type_names = ["Dinner", "Lunch", "Breakfast"]
    meal_types = {}
    for meal_type_name in meal_type_names:
        meal_type, _ = createIndividual(meal_type_name, MealType, unique=False, target_kg=target_kg)
        meal_type.has_meal_type_name.append(meal_type_name)
        meal_types[meal_type_name] = meal_type
    return meal_types


def create_difficulties(target_kg=None):
    """
    Create the standard difficulty level individuals (1, 2, 3).
    
    Args:
        target_kg: Target knowledge graph (defaults to kg_onto)
    
    Returns:
        List of difficulty individuals indexed by difficulty level (1-3)
    """
    difficulties = []
    for i in range(1, 4):
        diff, _ = createIndividual("difficulty_" + str(i), Difficulty, unique=False, target_kg=target_kg)
        diff.has_numeric_difficulty.append(i)
        difficulties.append(diff)
    return difficulties


def load_recipes_from_json(json_path: str, target_kg=None):
    """
    Load recipe individuals from a JSON file into a knowledge graph.
    
    Args:
        json_path: Path to the JSON file containing recipe data
        target_kg: Target knowledge graph (defaults to kg_onto)
    
    Returns:
        Number of recipes loaded
    
    Example:
        # Load into default KG
        load_recipes_from_json('recipes.json')
        
        # Load into specific KG
        from ontology import create_kg
        kg_bbc = create_kg("bbc")
        load_recipes_from_json('bbc_recipes.json', target_kg=kg_bbc)
    """
    if target_kg is None:
        target_kg = kg_onto
    
    # Create static meal types and difficulties
    meal_types = create_meal_types(target_kg=target_kg)
    difficulties = create_difficulties(target_kg=target_kg)
    
    # Load recipes from JSON
    with open(json_path, "r") as json_file:
        recipes = json.load(json_file)
    
    # Create or get the main source
    mainSource = ("BBC GoodFood", "https://bbcgoodfood.com")
    source, _ = createIndividual(mainSource[0], BaseClass=Source, unique=True, target_kg=target_kg)
    source.has_source_name.append(mainSource[0])
    source.is_website.append(mainSource[1])
    
    recipes_created = 0
    
    for json_recipe in recipes:
        if target_kg[onthologifyName(json_recipe["title"])] is not None:
            continue
        
        recipe, _ = createIndividual(json_recipe["title"], BaseClass=Recipe, unique=True, target_kg=target_kg)
        recipe.has_recipe_name.append(json_recipe["title"])
        recipe.has_instructions.append(str(json_recipe["instructions"]))

        # Create IngredientWithAmount individuals
        for extendedIngredient in json_recipe["ingredients"]:
            if re.search(r'\d', extendedIngredient["id"][0]):  # Check if first character is digit
                ingredientWithAmount, existed = createIndividual(extendedIngredient["id"], BaseClass=IngredientWithAmount, target_kg=target_kg)
            else:
                ingredientWithAmount, existed = createIndividual("1 " + extendedIngredient["id"], BaseClass=IngredientWithAmount, target_kg=target_kg)
            
            if existed:
                recipe.has_ingredient.append(ingredientWithAmount)
                continue
            
            ingredientWithAmount.has_ingredient_with_amount_name.append(extendedIngredient["id"])
            if extendedIngredient["amount"] is not None:
                ingredientWithAmount.amount_of_ingredient.append(float(extendedIngredient["amount"]))
            else:
                ingredientWithAmount.amount_of_ingredient.append(1)
            ingredientWithAmount.unit_of_ingredient.append(str(extendedIngredient["unit"]))
            
            ingredient, existed = createIndividual(extendedIngredient["ingredient"], BaseClass=Ingredient, target_kg=target_kg)
            if not existed:
                ingredient.has_ingredient_name.append(extendedIngredient["ingredient"])
            ingredientWithAmount.type_of_ingredient.append(ingredient)
            recipe.has_ingredient.append(ingredientWithAmount)

        # Create or get author
        author, existed = createIndividual(json_recipe["author"], BaseClass=Author, target_kg=target_kg)
        if not existed:
            author.has_author_name.append(json_recipe["author"])
            author.is_author_of.append(source)
        recipe.authored_by.append(author)

        # Create or get time
        time, existed = createIndividual("time_" + str(json_recipe["time"]), BaseClass=Time, target_kg=target_kg)
        if not existed:
            time.amount_of_time.append(json_recipe["time"])
        recipe.requires_time.append(time)

        # Assign meal type
        if "meal type" in json_recipe and json_recipe["meal type"] != "misc":
            recipe.is_meal_type.append(meal_types[json_recipe["meal type"]])
        
        # Assign dietary properties
        recipe.is_vegan.append(json_recipe["vegan"])
        recipe.is_vegetarian.append(json_recipe["vegetarian"])
        
        # Calculate and assign difficulty
        if len(recipe.has_ingredient) * 3 + time.amount_of_time[0] < 20:  # Easy
            recipe.has_difficulty.append(difficulties[0])
        elif len(recipe.has_ingredient) * 3 + time.amount_of_time[0] < 60:  # Moderate
            recipe.has_difficulty.append(difficulties[1])
        else:  # Difficult
            recipe.has_difficulty.append(difficulties[2])

        # Create nutrient individuals
        nutrients = json_recipe["nutrients"]
        
        calories, existed = createIndividual("calories_" + str(nutrients["kcal"]), BaseClass=Calories, target_kg=target_kg)
        if not existed:
            calories.amount_of_calories.append(float(nutrients["kcal"]))
        recipe.has_calories.append(calories)

        protein, existed = createIndividual("protein_" + str(nutrients["protein"]), BaseClass=Protein, target_kg=target_kg)
        if not existed:
            protein.amount_of_protein.append(float(nutrients["protein"]))
        recipe.has_protein.append(protein)

        fat, existed = createIndividual("fat_" + str(nutrients["fat"]), BaseClass=Fat, target_kg=target_kg)
        if not existed:
            fat.amount_of_fat.append(float(nutrients["fat"]))
        recipe.has_fat.append(fat)

        carbohydrates, existed = createIndividual("carbohydrates_" + str(nutrients["carbs"]), BaseClass=Carbohydrates, target_kg=target_kg)
        if not existed:
            carbohydrates.amount_of_carbohydrates.append(float(nutrients["carbs"]))
        recipe.has_carbohydrates.append(carbohydrates)

        # Add links
        recipe.has_link.append(json_recipe["source"])
        recipe.has_image_link.append(json_recipe["image"])
        
        recipes_created += 1
    
    return recipes_created


def create_single_recipe(recipe_data: dict, target_kg=None) -> Thing:
    """
    Create a single recipe individual from a data dictionary.
    Reuses existing logic but for one item.
    """
    if target_kg is None:
        target_kg = kg_onto

    # Ensure dependencies exist
    meal_types = create_meal_types(target_kg=target_kg)
    difficulties = create_difficulties(target_kg=target_kg)
    
    # 1. Basic Info
    title = recipe_data.get("title") or recipe_data.get("name")
    if not title:
        raise ValueError("Recipe must have a title")

    recipe_name = onthologifyName(title)
    
    # Check if exists
    if target_kg[recipe_name] is not None:
         recipe = target_kg[recipe_name]
    else:
        recipe, _ = createIndividual(title, BaseClass=Recipe, unique=False, target_kg=target_kg)

    # 2. Add Properties (Clear old ones first if updating)
    recipe.has_recipe_name = []
    recipe.has_recipe_name.append(title)
    
    if "instructions" in recipe_data:
        recipe.has_instructions = []
        recipe.has_instructions.append(str(recipe_data["instructions"]))

    # 3. Ingredients
    if "ingredients" in recipe_data:
        recipe.has_ingredient = []
        for extendedIngredient in recipe_data["ingredients"]:
            # Handle ID generation
            ing_id = extendedIngredient.get("id", extendedIngredient.get("name"))
            
            # Simple check for leading digit to prevent invalid URIs
            if ing_id and re.search(r'\d', ing_id[0]):
                name_for_ind = ing_id
            else:
                name_for_ind = f"1 {ing_id}"
                
            ingredientWithAmount, existed = createIndividual(name_for_ind, BaseClass=IngredientWithAmount, target_kg=target_kg)
            
            # Update properties of the Amount instance
            ingredientWithAmount.has_ingredient_with_amount_name = [ing_id]
            # Convert to float safely
            try:
                amt = float(extendedIngredient.get("amount", 1))
            except (ValueError, TypeError):
                amt = 1.0
            ingredientWithAmount.amount_of_ingredient = [amt]
            ingredientWithAmount.unit_of_ingredient = [str(extendedIngredient.get("unit", ""))]
            
            # Link to the base Ingredient Class/Individual
            ing_name = extendedIngredient.get("ingredient", ing_id)
            base_ingredient, _ = createIndividual(ing_name, BaseClass=Ingredient, target_kg=target_kg)
            if not base_ingredient.has_ingredient_name:
                base_ingredient.has_ingredient_name = [ing_name]
            
            ingredientWithAmount.type_of_ingredient = [base_ingredient]
            recipe.has_ingredient.append(ingredientWithAmount)

    # 4. Author & Source
    if "author" in recipe_data:
        author, _ = createIndividual(recipe_data["author"], BaseClass=Author, target_kg=target_kg)
        if not author.has_author_name:
            author.has_author_name = [recipe_data["author"]]
        recipe.authored_by = [author]

    # 5. Time & Difficulty
    if "time" in recipe_data:
        try:
            time_val = int(recipe_data["time"])
        except (ValueError, TypeError):
            time_val = 30 # Default
            
        time_ind, _ = createIndividual(f"time_{time_val}", BaseClass=Time, target_kg=target_kg)
        time_ind.amount_of_time = [time_val]
        recipe.requires_time = [time_ind]
        
        # Calc Difficulty logic
        ing_count = len(recipe.has_ingredient)
        if ing_count * 3 + time_val < 20:
            recipe.has_difficulty = [difficulties[0]]
        elif ing_count * 3 + time_val < 60:
            recipe.has_difficulty = [difficulties[1]]
        else:
            recipe.has_difficulty = [difficulties[2]]

    # 6. Dietary Flags
    if "vegan" in recipe_data:
        recipe.is_vegan = [bool(recipe_data["vegan"])]
    if "vegetarian" in recipe_data:
        recipe.is_vegetarian = [bool(recipe_data["vegetarian"])]

    # 7. Nutrients
    if "nutrients" in recipe_data:
        nutrients = recipe_data["nutrients"]
        
        # Calories
        if "kcal" in nutrients:
            val = nutrients["kcal"]
            calories, _ = createIndividual(f"calories_{val}", BaseClass=Calories, target_kg=target_kg)
            calories.amount_of_calories = [float(val)]
            recipe.has_calories = [calories]

        # Protein
        if "protein" in nutrients:
            val = nutrients["protein"]
            protein, _ = createIndividual(f"protein_{val}", BaseClass=Protein, target_kg=target_kg)
            protein.amount_of_protein = [float(val)]
            recipe.has_protein = [protein]

        # Fat
        if "fat" in nutrients:
            val = nutrients["fat"]
            fat, _ = createIndividual(f"fat_{val}", BaseClass=Fat, target_kg=target_kg)
            fat.amount_of_fat = [float(val)]
            recipe.has_fat = [fat]

        # Carbs
        if "carbs" in nutrients:
            val = nutrients["carbs"]
            carbs, _ = createIndividual(f"carbohydrates_{val}", BaseClass=Carbohydrates, target_kg=target_kg)
            carbs.amount_of_carbohydrates = [float(val)]
            recipe.has_carbohydrates = [carbs]

    # 8. Links and Images
    if "source" in recipe_data:
        recipe.has_link = [recipe_data["source"]]
    if "image" in recipe_data:
        recipe.has_image_link = [recipe_data["image"]]

    return recipe

def delete_recipe_individual(recipe_name: str, target_kg=None):
    if target_kg is None:
        target_kg = kg_onto
    
    name = onthologifyName(recipe_name)
    individual = target_kg[name]
    
    if individual:
        from owlready2 import destroy_entity
        destroy_entity(individual)
        return True
    return False