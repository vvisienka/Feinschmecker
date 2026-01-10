<script>
  import Navbar from "../components/Navbar.vue"
  import HeroHeader from "../components/HeroHeader.vue"
  import AboutUs from "../components/AboutUs.vue"
  import SearchSection from "../components/SearchSection.vue"
  import RecipesSection from "../components/RecipesSection.vue"
  import KnowledgeGraphUpload from "../components/KnowledgeGraphUpload.vue"
  import CreateRecipeModal from "../components/CreateRecipeModal.vue" 
  export default {
    components: {
      Navbar,
      HeroHeader,
      AboutUs,
      SearchSection,
      RecipesSection,
      KnowledgeGraphUpload,
      CreateRecipeModal
    },

    data() {
      return {
        recipes: [],
        maxRecipesShown: 0,
        showCreateModal: false
      }
    },

    methods: {
      handleSearchAction(recipes){
        this.recipes = recipes;
        this.maxRecipesShown = 6;
        console.log(this.recipes)
      },

      scrollToAboutUs(){
        this.$refs.aboutUs.$el.scrollIntoView({behavior: "smooth"})
      },

      scrollToSearchSection(){
        this.$refs.searchSection.$el.scrollIntoView({behavior: "smooth"})
      },

      handleLoadMoreRecipes(){
        if(this.maxRecipesShown < this.recipes.length) {
          this.maxRecipesShown += 6
        }
        console.log(this.maxRecipesShown)
      },

      handleGraphUploaded() {
        console.log('Graph uploaded successfully');
        // Clear current recipes and force a new search
        this.recipes = [];
      },

      handleRecipeCreated() {
         console.log('Recipe created successfully');
         // We can reuse the same logic as upload - clear the list or refresh
         this.recipes = [];
         
         // Optional: If you want to auto-refresh the search instead of clearing:
         // if (this.$refs.searchSection && this.$refs.searchSection.performSearch) {
         //    this.$refs.searchSection.performSearch();
         // }
      }
    }
  }
</script>

<template>
  <Navbar @scrollToAboutUs="scrollToAboutUs" @scrollToSearchSection="scrollToSearchSection" v-motion-slide-left />
  <HeroHeader @scrollToAboutUs="scrollToAboutUs" @scrollToSearchSection="scrollToSearchSection" v-motion-slide-right/>
  <AboutUs ref="aboutUs"/>

  <div class="container mx-auto px-4 py-4 flex flex-col sm:flex-row justify-center items-center gap-4">
    
    <button 
      @click="showCreateModal = true"
      class="flex items-center gap-2 px-6 py-2 bg-green-600 text-white font-medium rounded-lg hover:bg-green-700 transition-colors shadow-md"
    >
      <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
        <path fill-rule="evenodd" d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z" clip-rule="evenodd" />
      </svg>
      Create Recipe
    </button>

    <KnowledgeGraphUpload @graphUploaded="handleGraphUploaded" />
  </div>

  <SearchSection id="search-section" ref="searchSection" @searched="handleSearchAction"/>
  <RecipesSection @loadMoreRecipes="handleLoadMoreRecipes" :recipes="this.recipes" :maxRecipesShown="maxRecipesShown"/>

  <RecipeCreateForm 
    :is-open="showCreateModal" 
    @close="showCreateModal = false"
    @refresh="handleRecipeCreated"
  />

</template>
<style scoped>
  body {
    background: #F0F8FF;
  }
  

</style>

