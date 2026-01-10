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
  ingredients: [],
  nutrients: { kcal: 0, protein: 0, fat: 0, carbs: 0 }
})

const newIngredient = reactive({ name: '', amount: 1, unit: '' })

const addIngredient = () => {
  if (!newIngredient.name) return
  form.ingredients.push({
    id: newIngredient.name,
    amount: parseFloat(newIngredient.amount),
    unit: newIngredient.unit
  })
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
    const response = await api.post('/recipes', {
      title: form.title,
      instructions: form.instructions,
      time: parseInt(form.time),
      vegan: form.vegan,
      vegetarian: form.vegetarian,
      ingredients: form.ingredients,
      nutrients: form.nutrients,
      author: "Web User",
      source: "User Submission",
      image: "https://via.placeholder.com/300?text=New+Recipe"
    })
    alert(`Recipe "${form.title}" created!`)
    emit('created')
    emit('close')
  } catch (error) {
    console.error('Failed to create recipe:', error)
    alert('Error creating recipe. Check console.')
  } finally {
    isSubmitting.value = false
  }
}
</script>

<template>
  <div class="modal-overlay" @click.self="$emit('close')">
    <div class="modal-content">
      
      <div class="modal-header">
        <h3>Create New Recipe</h3>
        <button class="close-btn" @click="$emit('close')">&times;</button>
      </div>

      <div class="modal-body">
        
        <div class="form-group">
          <label>Recipe Title</label>
          <input v-model="form.title" type="text" placeholder="e.g. Grandma's Apple Pie" />
        </div>

        <div class="form-group">
          <label>Instructions</label>
          <textarea v-model="form.instructions" rows="3" placeholder="Mix ingredients..."></textarea>
        </div>

        <div class="row">
          <div class="form-group half">
            <label>Time (min)</label>
            <input v-model="form.time" type="number" />
          </div>
          <div class="form-group half checkboxes">
            <label><input v-model="form.vegan" type="checkbox"> Vegan</label>
            <label><input v-model="form.vegetarian" type="checkbox"> Vegetarian</label>
          </div>
        </div>

        <div class="section">
          <h4>Ingredients</h4>
          <div class="ingredient-input-row">
            <input v-model="newIngredient.name" placeholder="Name (e.g. Flour)" class="ing-name" @keyup.enter="addIngredient"/>
            <input v-model="newIngredient.amount" type="number" placeholder="Qty" class="ing-qty" />
            <input v-model="newIngredient.unit" placeholder="Unit" class="ing-unit" />
            <button @click="addIngredient" type="button" class="add-btn">+</button>
          </div>

          <ul class="ingredient-list">
            <li v-for="(ing, index) in form.ingredients" :key="index">
              <span>{{ ing.amount }} {{ ing.unit }} <b>{{ ing.id }}</b></span>
              <span @click="removeIngredient(index)" class="remove-text">remove</span>
            </li>
            <li v-if="form.ingredients.length === 0" class="empty-msg">No ingredients added yet.</li>
          </ul>
        </div>

        <div class="section">
          <h4>Nutrients (per serving)</h4>
          <div class="row">
            <div class="form-group quarter"><label>Kcal</label><input v-model="form.nutrients.kcal" type="number" /></div>
            <div class="form-group quarter"><label>Protein</label><input v-model="form.nutrients.protein" type="number" /></div>
            <div class="form-group quarter"><label>Fat</label><input v-model="form.nutrients.fat" type="number" /></div>
            <div class="form-group quarter"><label>Carbs</label><input v-model="form.nutrients.carbs" type="number" /></div>
          </div>
        </div>

      </div>

      <div class="modal-footer">
        <button @click="$emit('close')" class="secondary-button">Cancel</button>
        <button @click="submitRecipe" :disabled="isSubmitting" class="primary-button">
          {{ isSubmitting ? 'Creating...' : 'Create Recipe' }}
        </button>
      </div>

    </div>
  </div>
</template>

<style scoped>
/* Fonts and General */
* {
  font-family: "Poppins", sans-serif;
  box-sizing: border-box;
}

/* 1. The Overlay - Makes it a popup */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-color: rgba(0, 0, 0, 0.5); /* Semi-transparent black */
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
}

/* 2. The Modal Box */
.modal-content {
  background: white;
  width: 90%;
  max-width: 600px;
  max-height: 90vh; /* Allow scrolling if screen is small */
  border-radius: 15px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 4px 15px rgba(0,0,0,0.2);
  border: 2px solid #000000; /* Matching your theme */
}

/* Header */
.modal-header {
  padding: 20px;
  border-bottom: 2px solid #eee;
  display: flex;
  justify-content: space-between;
  align-items: center;
  background-color: #F0F8FF;
}

.modal-header h3 {
  margin: 0;
  font-size: 24px;
  font-weight: 700;
}

.close-btn {
  background: none;
  border: none;
  font-size: 28px;
  cursor: pointer;
  color: #555;
}

/* Body */
.modal-body {
  padding: 20px;
  overflow-y: auto;
}

.section {
  margin-top: 20px;
  border-top: 1px solid #eee;
  padding-top: 10px;
}
.section h4 {
  margin-bottom: 10px;
  font-weight: 600;
}

/* Forms */
.form-group {
  margin-bottom: 15px;
  text-align: left;
}
label {
  display: block;
  font-weight: 600;
  font-size: 14px;
  margin-bottom: 5px;
}
input, textarea {
  width: 100%;
  padding: 10px;
  border: 2px solid #ccc;
  border-radius: 8px;
  font-size: 14px;
  transition: border-color 0.2s;
}
input:focus, textarea:focus {
  border-color: #FFEE8C;
  outline: none;
}

/* Layout Helpers */
.row {
  display: flex;
  gap: 15px;
}
.half { width: 50%; }
.quarter { width: 25%; }

.checkboxes {
  display: flex;
  align-items: center;
  gap: 15px;
  padding-top: 25px;
}
.checkboxes label {
  display: flex;
  align-items: center;
  gap: 5px;
  cursor: pointer;
}
.checkboxes input {
  width: auto;
}

/* Ingredients Section */
.ingredient-input-row {
  display: flex;
  gap: 10px;
  margin-bottom: 10px;
}
.ing-name { flex-grow: 2; }
.ing-qty { width: 70px; }
.ing-unit { width: 70px; }

.add-btn {
  background-color: #F0F8FF;
  border: 2px solid #000;
  border-radius: 8px;
  padding: 0 15px;
  font-weight: bold;
  cursor: pointer;
}
.add-btn:hover { background-color: #DCEEFF; }

.ingredient-list {
  list-style: none;
  padding: 0;
  margin: 0;
}
.ingredient-list li {
  background: #f9f9f9;
  padding: 8px;
  margin-bottom: 5px;
  border-radius: 5px;
  display: flex;
  justify-content: space-between;
  font-size: 14px;
}
.remove-text {
  color: #ff4d4d;
  cursor: pointer;
  font-weight: 600;
}
.empty-msg {
  color: #999;
  font-style: italic;
  font-size: 13px;
}

/* Footer & Buttons */
.modal-footer {
  padding: 20px;
  border-top: 2px solid #eee;
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  background-color: #fff;
}

button {
  padding: 10px 20px;
  font-family: "Poppins";
  font-size: 16px;
  border: 2px solid #000000;
  border-radius: 10px;
  cursor: pointer;
  font-weight: 500;
}

.secondary-button {
  background-color: #fff;
  transition: 0.3s;
}
.secondary-button:hover {
  background-color: #f0f0f0;
}

.primary-button {
  background-color: #FFEE8C;
  transition: 0.3s;
}
.primary-button:hover {
  background-color: #ffde4d;
}
.primary-button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>