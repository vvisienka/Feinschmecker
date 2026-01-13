<script>
  import Navbar from "../components/Navbar.vue"
  import HeroHeader from "../components/HeroHeader.vue"
  import AboutUs from "../components/AboutUs.vue"
  import SearchSection from "../components/SearchSection.vue"
  import RecipesSection from "../components/RecipesSection.vue"
  import KnowledgeGraphUpload from "../components/KnowledgeGraphUpload.vue"
  // IMPORT THE NEW COMPONENT
  import CreateRecipeModal from "../components/CreateRecipeModal.vue" 

  export default {
    components: {
      Navbar,
      HeroHeader,
      AboutUs,
      SearchSection,
      RecipesSection,
      KnowledgeGraphUpload,
      CreateRecipeModal  // REGISTER IT
    },

    data() {
      return {
        recipes: [],
        maxRecipesShown: 0,
        showCreateModal: false // CONTROL VISIBILITY
      }
    },

    methods: {
      handleSearchAction(recipes){
        this.recipes = recipes;
        this.maxRecipesShown = 6;
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
      },

      handleGraphUploaded() {
        console.log('Graph uploaded successfully');
        this.recipes = [];
      },

      handleRecipeCreated() {
         console.log('Recipe created successfully');
         // Clear recipes to force user to search/see update
         this.recipes = [];
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

  <CreateRecipeModal 
    v-if="showCreateModal" 
    @close="showCreateModal = false"
    @created="handleRecipeCreated"
  />

</template>

<style scoped>
  body {
    background: #F0F8FF;
  }
</style>