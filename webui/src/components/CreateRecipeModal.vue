<script setup>
import { ref, reactive } from 'vue'
import api from '../../services/axios'

const emit = defineEmits(['close', 'created'])

const isSubmitting = ref(false)

// Form State
const form = reactive({
  title: '',
  instructions: '',
  time: 30,
  vegan: false,
  vegetarian: false,
  ingredients: [], // Will hold objects like { id: 'Flour', amount: 500, unit: 'g' }
  nutrients: {
    kcal: 0,
    protein: 0,
    fat: 0,
    carbs: 0
  }
})

// Temporary state for the "Add Ingredient" inputs
const newIngredient = reactive({
  name: '',
  amount: 1,
  unit: ''
})

const addIngredient = () => {
  if (!newIngredient.name) return
  
  form.ingredients.push({
    id: newIngredient.name, // The backend uses 'id' for the ingredient name
    amount: parseFloat(newIngredient.amount),
    unit: newIngredient.unit
  })
  
  // Reset input
  newIngredient.name = ''
  newIngredient.amount = 1
  newIngredient.unit = ''
}

const removeIngredient = (index) => {
  form.ingredients.splice(index, 1)
}

const submitRecipe = async () => {
  if (!form.title || !form.instructions) {
    alert('Please fill in the title and instructions.')
    return
  }

  isSubmitting.value = true
  try {
    // Send POST request to your new Celery-backed endpoint
    const response = await api.post('/recipes', {
      title: form.title,
      instructions: form.instructions,
      time: parseInt(form.time),
      vegan: form.vegan,
      vegetarian: form.vegetarian,
      ingredients: form.ingredients,
      nutrients: form.nutrients,
      // Default author if none provided
      author: "Web User", 
      source: "User Submission",
      image: "https://via.placeholder.com/300?text=New+Recipe" 
    })

    alert(`Recipe "${form.title}" created! (Task ID: ${response.data.data.task_id})`)
    emit('created') // Tell parent to refresh list
    emit('close')   // Close modal
  } catch (error) {
    console.error('Failed to create recipe:', error)
    alert('Error creating recipe. Check console for details.')
  } finally {
    isSubmitting.value = false
  }
}
</script>

<template>
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50 p-4" @click.self="$emit('close')">
    <div class="bg-white rounded-lg shadow-xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
      
      <div class="flex justify-between items-center p-6 border-b">
        <h3 class="text-2xl font-bold text-gray-800">Create New Recipe</h3>
        <button @click="$emit('close')" class="text-gray-500 hover:text-gray-700 text-xl">&times;</button>
      </div>

      <div class="p-6 space-y-4">
        
        <div>
          <label class="block text-sm font-medium text-gray-700">Recipe Title</label>
          <input v-model="form.title" type="text" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm p-2 border" placeholder="e.g. Grandma's Apple Pie" />
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-700">Instructions</label>
          <textarea v-model="form.instructions" rows="3" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm p-2 border" placeholder="Mix ingredients..."></textarea>
        </div>

        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="block text-sm font-medium text-gray-700">Time (minutes)</label>
            <input v-model="form.time" type="number" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm p-2 border" />
          </div>
          <div class="flex items-center space-x-4 mt-6">
            <label class="inline-flex items-center">
              <input v-model="form.vegan" type="checkbox" class="form-checkbox text-green-600">
              <span class="ml-2">Vegan</span>
            </label>
            <label class="inline-flex items-center">
              <input v-model="form.vegetarian" type="checkbox" class="form-checkbox text-green-600">
              <span class="ml-2">Vegetarian</span>
            </label>
          </div>
        </div>

        <div class="border-t pt-4">
          <h4 class="font-bold text-gray-700 mb-2">Ingredients</h4>
          
          <div class="flex space-x-2 mb-2">
            <input v-model="newIngredient.name" placeholder="Name (e.g. Flour)" class="flex-grow rounded-md border-gray-300 border p-2 text-sm" @keyup.enter="addIngredient"/>
            <input v-model="newIngredient.amount" type="number" placeholder="Qty" class="w-20 rounded-md border-gray-300 border p-2 text-sm" />
            <input v-model="newIngredient.unit" placeholder="Unit" class="w-20 rounded-md border-gray-300 border p-2 text-sm" />
            <button @click="addIngredient" type="button" class="bg-blue-100 text-blue-700 px-3 py-1 rounded hover:bg-blue-200">+</button>
          </div>

          <ul class="space-y-1 text-sm text-gray-600">
            <li v-for="(ing, index) in form.ingredients" :key="index" class="flex justify-between bg-gray-50 p-2 rounded">
              <span>{{ ing.amount }} {{ ing.unit }} <b>{{ ing.id }}</b></span>
              <button @click="removeIngredient(index)" class="text-red-500 hover:text-red-700">remove</button>
            </li>
            <li v-if="form.ingredients.length === 0" class="text-gray-400 italic">No ingredients added yet.</li>
          </ul>
        </div>

        <div class="border-t pt-4">
          <h4 class="font-bold text-gray-700 mb-2">Nutrients (per serving)</h4>
          <div class="grid grid-cols-4 gap-2">
            <div><label class="text-xs">Calories</label><input v-model="form.nutrients.kcal" type="number" class="w-full border p-1 rounded" /></div>
            <div><label class="text-xs">Protein (g)</label><input v-model="form.nutrients.protein" type="number" class="w-full border p-1 rounded" /></div>
            <div><label class="text-xs">Fat (g)</label><input v-model="form.nutrients.fat" type="number" class="w-full border p-1 rounded" /></div>
            <div><label class="text-xs">Carbs (g)</label><input v-model="form.nutrients.carbs" type="number" class="w-full border p-1 rounded" /></div>
          </div>
        </div>

      </div>

      <div class="p-6 border-t bg-gray-50 flex justify-end space-x-3">
        <button @click="$emit('close')" class="px-4 py-2 text-gray-600 hover:text-gray-800">Cancel</button>
        <button 
          @click="submitRecipe" 
          :disabled="isSubmitting"
          class="bg-green-600 hover:bg-green-700 text-white font-bold py-2 px-6 rounded transition-colors disabled:opacity-50"
        >
          {{ isSubmitting ? 'Creating...' : 'Create Recipe' }}
        </button>
      </div>

    </div>
  </div>
</template>