<script>
  import MacronutrientsSummary from "../components/MacronutrientsSummary.vue"
  import DeleteRecipeModal from "../components/DeleteRecipeModal.vue" // 1. Import Modal
  
  export default {
    components: {
      MacronutrientsSummary,
      DeleteRecipeModal // 2. Register Modal
    },
    data() {
      return {
        recipe: null,
        recipeNotFound: false,
        showDeleteModal: false // 3. State for modal visibility
      }
    },

    methods: {
      goBack(){
        this.$router.push({name: "Home", hash:'#search-section'});
      },
      loadRecipe() {
        try {
          const storedRecipe = localStorage.getItem('current_recipe');
          if (storedRecipe) {
            this.recipe = JSON.parse(storedRecipe);
          } else {
            this.recipeNotFound = true;
          }
        } catch (error) {
          console.error('Error loading recipe:', error);
          this.recipeNotFound = true;
        }
      },
      getIngredients() {
        if (!this.recipe || !this.recipe.ingredients) return [];
        if (Array.isArray(this.recipe.ingredients)) return this.recipe.ingredients;
        if (typeof this.recipe.ingredients === 'string') return this.recipe.ingredients.split('#');
        return [];
      },
      // 4. Handle successful deletion
      handleDeleted() {
        localStorage.removeItem('current_recipe'); // Clean up
        alert("Recipe deleted successfully!");
        this.$router.push({ name: "Home" }); // Redirect
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

      <div class="delete-container">
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
  <div class="loading-container" v-else>
    <p>Loading recipe...</p>
  </div>

  <DeleteRecipeModal 
    v-if="showDeleteModal"
    :recipeTitle="recipe.name"
    :recipeName="recipe.name"
    @close="showDeleteModal = false"
    @deleted="handleDeleted"
  />
</template>

<style scoped>
  body { background: #F0F8FF; }

  .container {
    display: flex; justify-content: flex-start; align-items: flex-start; /* Changed to flex-start for long recipes */
    width: 100%; min-height: 90vh; padding-top: 20px;
  }

  .left-container {
    display: flex; flex-direction: column; justify-content: flex-start; align-items: center;
    width: 30%; height: 100%;
  }

  .button-container { display: flex; justify-content: flex-start; width: 90%; }

  .recipe-info-box { padding: 50px 50px 20px 50px; }

  /* New Delete Button Style */
  .delete-container { margin-top: 20px; }
  .delete-btn-main {
    padding: 10px 20px; font-family: "Poppins"; font-size: 20px;
    border: 2px solid #000000; border-radius: 10px; cursor: pointer;
    background-color: #ffeaea; color: #d32f2f;
    transition: 0.3s all ease-in-out;
  }
  .delete-btn-main:hover { background-color: #ffcccc; }

  .right-container {
    display: flex; flex-direction: column; justify-content: flex-start;
    width: 60%; height: 100%;
  }

  .ingredients-box {
    display: flex; flex-direction: column; justify-content: space-around;
    border: 3px solid #000; border-radius: 30px; padding: 30px 20px;
    background-color: #FFEE8C;
  }

  .ingredients-names-box { display: flex; flex-wrap: wrap; justify-content: space-around; align-items: center; }

  .instructions-box {
    margin: 50px 0; padding: 30px 20px;
    border: 3px solid #000; border-radius: 30px;
  }

  h1 { font-family: "Poppins"; font-size: 64px; }
  h2 { font-family: "Poppins"; font-size: 32px; margin: 0; padding: 0; }
  p { font-family: "Poppins"; font-size: 18px; text-align: justify; }
  .instruction-index { font-size: 22px; font-weight: 700; }

  button {
    padding: 10px 20px; margin: 20px; /* Reduced margin slightly */
    font-family: "Poppins"; font-size: 24px;
    border: 2px solid #000000; border-radius: 10px; cursor: pointer;
    background-color: #F0F8FF; transition: 0.3s all ease-in-out;
  }
  button:hover { background-color: #DCEEFF }

  img { max-width: 400px; }

  .error-container, .loading-container {
    display: flex; flex-direction: column; justify-content: center; align-items: center;
    width: 100%; height: 90vh; font-family: "Poppins";
  }
  .error-container h1 { font-size: 48px; color: #721c24; }
  .error-container p, .loading-container p { font-size: 24px; margin: 20px 0; }
</style>