<script setup>
import { ref, reactive, onMounted } from 'vue'
import api from '../../services/axios'

// We accept the existing recipe object
const props = defineProps({
  initialRecipe: Object
})

const emit = defineEmits(['close', 'updated'])
const isSubmitting = ref(false)

// Form State
const form = reactive({
  title: '',
  instructions: '',
  time: 30,
  author: '',
  source: '',
  meal_type: 'Dinner',
  difficulty: 1,
  vegan: false,
  vegetarian: false,
  ingredients: [],
  nutrients: { kcal: 0, protein: 0, fat: 0, carbs: 0 }
})

const newIngredient = reactive({ name: '', amount: 1, unit: '' })

// Pre-fill form on mount
onMounted(() => {
  if (props.initialRecipe) {
    const r = props.initialRecipe
    form.title = r.name
    form.instructions = Array.isArray(r.instructions) ? r.instructions.join('\n') : r.instructions
    form.time = parseInt(r.time) || 30
    form.author = r.author || ''
    form.source = r.source_name || ''
    form.meal_type = r.type || 'Dinner'
    form.difficulty = parseInt(r.difficulty) || 1
    form.vegan = r.vegan === 'true' || r.vegan === true
    form.vegetarian = r.vegetarian === 'true' || r.vegetarian === true
    form.nutrients.kcal = parseFloat(r.calories) || 0
    form.nutrients.protein = parseFloat(r.protein) || 0
    form.nutrients.fat = parseFloat(r.fat) || 0
    form.nutrients.carbs = parseFloat(r.carbohydrates) || 0

    // Parse ingredients (which might be strings like "100 g Sugar")
    // Simple parser for demonstration. Ideally backend sends structured ingredients.
    if (Array.isArray(r.ingredients)) {
        form.ingredients = r.ingredients.map(ingStr => {
            // Rough heuristic parsing or just pass name if structure lost
            return { id: ingStr, amount: 1, unit: '', name: ingStr } 
        })
    } else if (typeof r.ingredients === 'string') {
         form.ingredients = r.ingredients.split('#').map(s => ({ id: s, amount: 1, unit: '', name: s }))
    }
  }
})

const addIngredient = () => {
  if (!newIngredient.name) return
  form.ingredients.push({
    id: newIngredient.name,
    amount: parseFloat(newIngredient.amount),
    unit: newIngredient.unit,
    ingredient: newIngredient.name // Ensure linkage
  })
  newIngredient.name = ''
  newIngredient.amount = 1
  newIngredient.unit = ''
}

const removeIngredient = (index) => {
  form.ingredients.splice(index, 1)
}

const submitUpdate = async () => {
  if (!form.title) return alert('Title required')
  
  isSubmitting.value = true
  try {
    // We send PUT to the OLD ID (based on old title/slug)
    const oldSlug = props.initialRecipe.name.toLowerCase().replace(/ /g, '_').replace(/%/g, 'percent').replace(/&/g, 'and')
    
    await api.put(`/recipes/${oldSlug}`, {
      title: form.title,
      instructions: form.instructions,
      time: parseInt(form.time),
      author: form.author,
      source: form.source,
      meal_type: form.meal_type,
      difficulty: parseInt(form.difficulty),
      vegan: form.vegan,
      vegetarian: form.vegetarian,
      ingredients: form.ingredients,
      nutrients: form.nutrients,
      image: props.initialRecipe.image_link // Keep existing image
    })

    alert(`Recipe updated!`)
    emit('updated')
    emit('close')
  } catch (error) {
    console.error('Update failed:', error)
    alert('Failed to update. Check console.')
  } finally {
    isSubmitting.value = false
  }
}
</script>

<template>
  <div class="modal-overlay" @click.self="$emit('close')">
    <div class="modal-content">
      <div class="modal-header">
        <h3>Update Recipe</h3>
        <button class="close-btn" @click="$emit('close')">&times;</button>
      </div>

      <div class="modal-body">
        <div class="form-group">
            <label>Title</label>
            <input v-model="form.title" />
        </div>
        
        <div class="row">
           <div class="form-group half"><label>Author</label><input v-model="form.author"></div>
           <div class="form-group half"><label>Source</label><input v-model="form.source"></div>
        </div>
        
        <div class="row">
             <div class="form-group quarter"><label>Time</label><input type="number" v-model="form.time"></div>
             <div class="form-group quarter">
                <label>Difficulty</label>
                <select v-model="form.difficulty">
                    <option :value="1">Easy</option><option :value="2">Medium</option><option :value="3">Hard</option>
                </select>
             </div>
             <div class="form-group quarter">
                 <label>Meal</label>
                 <select v-model="form.meal_type">
                     <option>Breakfast</option><option>Lunch</option><option>Dinner</option>
                 </select>
             </div>
        </div>

        <div class="checkboxes">
            <label><input type="checkbox" v-model="form.vegan"> Vegan</label>
            <label><input type="checkbox" v-model="form.vegetarian"> Vegetarian</label>
        </div>

        <div class="form-group"><label>Instructions</label><textarea v-model="form.instructions" rows="3"></textarea></div>

        <div class="section">
            <h4>Ingredients</h4>
            <div class="ingredient-input-row">
                <input v-model="newIngredient.name" placeholder="Name" class="ing-name" @keyup.enter="addIngredient">
                <input v-model="newIngredient.amount" type="number" placeholder="Qty" class="ing-qty">
                <input v-model="newIngredient.unit" placeholder="Unit" class="ing-unit">
                <button @click="addIngredient" type="button" class="add-btn">+</button>
            </div>
            <ul class="ingredient-list">
                <li v-for="(ing, idx) in form.ingredients" :key="idx">
                    {{ ing.amount }} {{ ing.unit }} {{ ing.id || ing.name }}
                    <span @click="removeIngredient(idx)" class="remove-text">x</span>
                </li>
            </ul>
        </div>
        
        <div class="section">
            <h4>Nutrients</h4>
            <div class="row">
                <div class="form-group quarter"><label>Kcal</label><input type="number" v-model="form.nutrients.kcal"></div>
                <div class="form-group quarter"><label>Prot</label><input type="number" v-model="form.nutrients.protein"></div>
                <div class="form-group quarter"><label>Fat</label><input type="number" v-model="form.nutrients.fat"></div>
                <div class="form-group quarter"><label>Carb</label><input type="number" v-model="form.nutrients.carbs"></div>
            </div>
        </div>
      </div>

      <div class="modal-footer">
        <button @click="$emit('close')" class="secondary-button">Cancel</button>
        <button @click="submitUpdate" :disabled="isSubmitting" class="primary-button">
            {{ isSubmitting ? 'Saving...' : 'Save Changes' }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Copy styles exactly from CreateRecipeModal.vue */
* { font-family: "Poppins", sans-serif; box-sizing: border-box; }
.modal-overlay { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); display: flex; justify-content: center; align-items: center; z-index: 1000; }
.modal-content { background: white; width: 90%; max-width: 600px; max-height: 90vh; border-radius: 15px; display: flex; flex-direction: column; overflow: hidden; border: 2px solid #000; }
.modal-header { padding: 20px; background: #F0F8FF; display: flex; justify-content: space-between; border-bottom: 2px solid #eee; }
.modal-header h3 { margin: 0; font-size: 24px; }
.close-btn { background: none; border: none; font-size: 28px; cursor: pointer; }
.modal-body { padding: 20px; overflow-y: auto; }
.form-group { margin-bottom: 10px; }
input, select, textarea { width: 100%; padding: 8px; border: 2px solid #ccc; border-radius: 6px; }
.row { display: flex; gap: 10px; }
.half { width: 50%; } .quarter { width: 25%; }
.checkboxes { display: flex; gap: 15px; margin: 10px 0; }
.ingredient-input-row { display: flex; gap: 5px; margin-bottom: 5px; }
.ing-name { flex-grow: 1; } .ing-qty, .ing-unit { width: 60px; }
.add-btn { background: #F0F8FF; border: 2px solid #000; font-weight: bold; cursor: pointer; }
.ingredient-list { list-style: none; padding: 0; }
.ingredient-list li { background: #f9f9f9; padding: 5px; margin-bottom: 2px; display: flex; justify-content: space-between; }
.remove-text { color: red; cursor: pointer; font-weight: bold; }
.modal-footer { padding: 20px; border-top: 2px solid #eee; display: flex; justify-content: flex-end; gap: 10px; }
button { padding: 10px 20px; border: 2px solid #000; border-radius: 8px; cursor: pointer; font-family: "Poppins"; }
.primary-button { background: #FFEE8C; } .primary-button:hover { background: #ffde4d; }
.secondary-button { background: white; }
</style>