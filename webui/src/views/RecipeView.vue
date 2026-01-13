<script>
  import MacronutrientsSummary from "../components/MacronutrientsSummary.vue"
  import DeleteRecipeModal from "../components/DeleteRecipeModal.vue"
  import UpdateRecipeModal from "../components/UpdateRecipeModal.vue" // 1. Import
  
  export default {
    components: {
      MacronutrientsSummary,
      DeleteRecipeModal,
      UpdateRecipeModal // 2. Register
    },
    data() {
      return {
        recipe: null,
        recipeNotFound: false,
        showDeleteModal: false,
        showUpdateModal: false // 3. State
      }
    },
    methods: {
      goBack(){ this.$router.push({name: "Home", hash:'#search-section'}); },
      loadRecipe() {
        try {
          const storedRecipe = localStorage.getItem('current_recipe');
          if (storedRecipe) {
            this.recipe = JSON.parse(storedRecipe);
          } else { this.recipeNotFound = true; }
        } catch (error) { this.recipeNotFound = true; }
      },
      getIngredients() {
        if (!this.recipe || !this.recipe.ingredients) return [];
        if (Array.isArray(this.recipe.ingredients)) return this.recipe.ingredients;
        if (typeof this.recipe.ingredients === 'string') return this.recipe.ingredients.split('#');
        return [];
      },
      handleDeleted() {
        localStorage.removeItem('current_recipe');
        alert("Recipe deleted successfully!");
        this.$router.push({ name: "Home" });
      },
      // 4. Handle Update Success
      handleUpdated() {
        // Since we don't have a GET by ID API that is reliable immediately after rename,
        // we force the user back to Home to search again (simplest robust approach).
        alert("Recipe updated! Please search for it again.");
        this.$router.push({ name: "Home" });
      }
    },
    mounted() {
      window.scrollTo(0, 0);
      this.loadRecipe();
    }
  }
</script>

<template>
  <div class="container" v-if="recipe">
    <div class="left-container">
      <div class="button-container">
        <button @click="goBack">Back</button>
      </div>
      
      <div class="recipe-info-box">
        <img :src="recipe.image_link" :alt="recipe.name"/>
        <MacronutrientsSummary 
          :calories="recipe.calories" 
          :protein="recipe.protein" 
          :carbohydrates="recipe.carbohydrates" 
          :fat="recipe.fat"
        />
        <p><strong>Authored by:</strong> {{recipe.author}}</p>
        <p><strong>Scraped from:</strong> <a :href="recipe.source_link">{{recipe.source_name}}</a></p>
      </div>

      <div class="delete-container"> <button class="update-btn-main" @click="showUpdateModal = true">
          Update Recipe
        </button>
        
        <button class="delete-btn-main" @click="showDeleteModal = true">
          Delete Recipe
        </button>
      </div>

    </div>
    
    <div class ="right-container">
      <h1>{{recipe.name}}</h1>
      <div class="ingredients-box">
        <h2>Ingredients</h2>
        <div class="ingredients-names-box">
          <p v-for="(ingredient, index) in getIngredients()" :key="index">{{ingredient}}</p>
        </div>
      </div>
      <div class="instructions-box">
        <h2>Instructions</h2>
        <div class="instructions-paragraphs-box">
          <p v-for="(step, index) in recipe.instructions" :key="index">
            <span class="instruction-index">{{index+1}}</span> {{step}}
          </p>
        </div> 
      </div>
    </div>
  </div>

  <div class="error-container" v-else-if="recipeNotFound">
    <h1>Recipe Not Found</h1>
    <button @click="goBack">Back to Search</button>
  </div>
  <div class="loading-container" v-else><p>Loading recipe...</p></div>

  <DeleteRecipeModal 
    v-if="showDeleteModal"
    :recipeTitle="recipe.name"
    :recipeName="recipe.name"
    @close="showDeleteModal = false"
    @deleted="handleDeleted"
  />
  
  <UpdateRecipeModal 
    v-if="showUpdateModal"
    :initialRecipe="recipe"
    @close="showUpdateModal = false"
    @updated="handleUpdated"
  />
</template>

<style scoped>
/* (Keep existing styles) */
  body { background: #F0F8FF; }
  .container { display: flex; width: 100%; min-height: 90vh; padding-top: 20px; align-items: flex-start; }
  .left-container { width: 30%; display: flex; flex-direction: column; align-items: center; }
  .right-container { width: 60%; }
  .button-container { width: 90%; }
  .recipe-info-box { padding: 50px 50px 20px 50px; }
  
  /* Action Buttons Styling */
  .delete-container { margin-top: 20px; display: flex; flex-direction: column; gap: 15px; width: 100%; align-items: center; }
  
  .delete-btn-main {
    padding: 10px 20px; font-family: "Poppins"; font-size: 20px;
    border: 2px solid #000; border-radius: 10px; cursor: pointer;
    background-color: #ffeaea; color: #d32f2f;
    width: 80%; /* Make them consistent width */
    transition: 0.3s;
  }
  .delete-btn-main:hover { background-color: #ffcccc; }

  .update-btn-main {
    padding: 10px 20px; font-family: "Poppins"; font-size: 20px;
    border: 2px solid #000; border-radius: 10px; cursor: pointer;
    background-color: #fff8cc; color: #856404; /* Yellowish theme */
    width: 80%;
    transition: 0.3s;
  }
  .update-btn-main:hover { background-color: #fff3cd; }

  /* Rest of styles... */
  .ingredients-box { border: 3px solid #000; border-radius: 30px; padding: 30px 20px; background-color: #FFEE8C; margin-bottom: 30px; }
  .instructions-box { border: 3px solid #000; border-radius: 30px; padding: 30px 20px; margin-bottom: 50px; }
  h1 { font-family: "Poppins"; font-size: 64px; }
  button { padding: 10px 20px; border: 2px solid #000; border-radius: 10px; cursor: pointer; background: #F0F8FF; }
</style>