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
    Create OR Update a single recipe individual.
    Ensures all strict SPARQL requirements (Author, Source, Image) are met.
    """
    if target_kg is None:
        target_kg = kg_onto

    # Ensure dependencies exist
    meal_types = create_meal_types(target_kg=target_kg)
    difficulties = create_difficulties(target_kg=target_kg)
    
    # 1. Identify Recipe
    title = recipe_data.get("title") or recipe_data.get("name")
    if not title:
        raise ValueError("Recipe must have a title")

    recipe_name = onthologifyName(title)
    
    # Check if exists
    if target_kg[recipe_name] is not None:
         recipe = target_kg[recipe_name]
         # Clear properties for clean update
         recipe.has_recipe_name = []
         recipe.has_instructions = []
         recipe.has_ingredient = []
         recipe.authored_by = []
         recipe.requires_time = []
         recipe.has_difficulty = []
         recipe.is_meal_type = []
         recipe.is_vegan = []
         recipe.is_vegetarian = []
         recipe.has_calories = []
         recipe.has_protein = []
         recipe.has_fat = []
         recipe.has_carbohydrates = []
         recipe.has_link = []
         recipe.has_image_link = []
    else:
        recipe, _ = createIndividual(title, BaseClass=Recipe, unique=False, target_kg=target_kg)

    # 2. Add Properties
    recipe.has_recipe_name.append(title)
    
    # Instructions default
    instr = recipe_data.get("instructions", "No instructions provided.")
    recipe.has_instructions.append(str(instr))

    # 3. Ingredients
    if "ingredients" in recipe_data:
        for extendedIngredient in recipe_data["ingredients"]:
            ing_id = extendedIngredient.get("id", extendedIngredient.get("name"))
            
            if ing_id and re.search(r'\d', ing_id[0]):
                name_for_ind = ing_id
            else:
                name_for_ind = f"1 {ing_id}"
                
            ingredientWithAmount, existed = createIndividual(name_for_ind, BaseClass=IngredientWithAmount, target_kg=target_kg)
            
            ingredientWithAmount.has_ingredient_with_amount_name = [ing_id]
            try:
                amt = float(extendedIngredient.get("amount", 1))
            except (ValueError, TypeError):
                amt = 1.0
            ingredientWithAmount.amount_of_ingredient = [amt]
            ingredientWithAmount.unit_of_ingredient = [str(extendedIngredient.get("unit", ""))]
            
            ing_name = extendedIngredient.get("ingredient", ing_id)
            base_ingredient, _ = createIndividual(ing_name, BaseClass=Ingredient, target_kg=target_kg)
            if not base_ingredient.has_ingredient_name:
                base_ingredient.has_ingredient_name = [ing_name]
            
            ingredientWithAmount.type_of_ingredient = [base_ingredient]
            recipe.has_ingredient.append(ingredientWithAmount)

    # 4. Author & Source (STRICT QUERY REQUIREMENTS FIX)
    # ---------------------------------------------------------
    # Get values or defaults
    author_name = recipe_data.get("author") or "Unknown Author"
    source_name = recipe_data.get("source") or "User Submission"
    
    # Create Author
    author_ind, _ = createIndividual(author_name, BaseClass=Author, target_kg=target_kg)
    if not author_ind.has_author_name:
        author_ind.has_author_name = [author_name]
    recipe.authored_by = [author_ind]

    # Create Source
    source_ind, _ = createIndividual(source_name, BaseClass=Source, target_kg=target_kg)
    if not source_ind.has_source_name:
        source_ind.has_source_name = [source_name]
    
    # REQUIREMENT: Source MUST have a website link
    if not source_ind.is_website:
        source_ind.is_website = ["http://feinschmecker.local"]

    # REQUIREMENT: Author MUST be linked to Source
    if source_ind not in author_ind.is_author_of:
        author_ind.is_author_of.append(source_ind)
    # ---------------------------------------------------------

    # 5. Recipe Links & Images (STRICT QUERY REQUIREMENTS FIX)
    # ---------------------------------------------------------
    # REQUIREMENT: Recipe MUST have a direct link
    if "link" in recipe_data and recipe_data["link"]:
        recipe.has_link = [recipe_data["link"]]
    else:
        recipe.has_link = [f"http://feinschmecker.local/recipe/{recipe_name}"]

    # REQUIREMENT: Recipe MUST have an image link
    if "image" in recipe_data and recipe_data["image"]:
        recipe.has_image_link = [recipe_data["image"]]
    else:
        # Placeholder image so the query doesn't filter this recipe out
        recipe.has_image_link = ["https://via.placeholder.com/300?text=No+Image"]
    # ---------------------------------------------------------

    # 6. Time & Difficulty
    if "time" in recipe_data:
        try:
            time_val = int(recipe_data["time"])
        except (ValueError, TypeError):
            time_val = 30 
            
        time_ind, _ = createIndividual(f"time_{time_val}", BaseClass=Time, target_kg=target_kg)
        time_ind.amount_of_time = [time_val]
        recipe.requires_time = [time_ind]
        
        if "difficulty" in recipe_data:
            try:
                diff_idx = int(recipe_data["difficulty"]) - 1
                if 0 <= diff_idx < len(difficulties):
                    recipe.has_difficulty = [difficulties[diff_idx]]
            except (ValueError, TypeError):
                pass 
        
        if not recipe.has_difficulty:
            ing_count = len(recipe.has_ingredient)
            if ing_count * 3 + time_val < 20:
                recipe.has_difficulty = [difficulties[0]]
            elif ing_count * 3 + time_val < 60:
                recipe.has_difficulty = [difficulties[1]]
            else:
                recipe.has_difficulty = [difficulties[2]]

    # 7. Meal Type
    if "meal_type" in recipe_data:
        mt_name = recipe_data["meal_type"]
        if mt_name in meal_types:
            recipe.is_meal_type = [meal_types[mt_name]]

    # 8. Dietary Flags
    recipe.is_vegan = [bool(recipe_data.get("vegan", False))]
    recipe.is_vegetarian = [bool(recipe_data.get("vegetarian", False))]

    # 9. Nutrients
    if "nutrients" in recipe_data:
        nutrients = recipe_data["nutrients"]
        # Use 0.0 as default if missing to ensure data consistency
        kcal = float(nutrients.get("kcal", 0))
        prot = float(nutrients.get("protein", 0))
        fat_val = float(nutrients.get("fat", 0))
        carb = float(nutrients.get("carbs", 0))

        calories, _ = createIndividual(f"calories_{kcal}", BaseClass=Calories, target_kg=target_kg)
        calories.amount_of_calories = [kcal]
        recipe.has_calories = [calories]

        protein, _ = createIndividual(f"protein_{prot}", BaseClass=Protein, target_kg=target_kg)
        protein.amount_of_protein = [prot]
        recipe.has_protein = [protein]

        fat, _ = createIndividual(f"fat_{fat_val}", BaseClass=Fat, target_kg=target_kg)
        fat.amount_of_fat = [fat_val]
        recipe.has_fat = [fat]

        carbs, _ = createIndividual(f"carbohydrates_{carb}", BaseClass=Carbohydrates, target_kg=target_kg)
        carbs.amount_of_carbohydrates = [carb]
        recipe.has_carbohydrates = [carbs]

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