<template>
  <div class="add-recipe-section">
    <button class="add-btn" @click="openModal">Add a recipe</button>

    <div v-if="showModal" class="modal-overlay">
      <div class="modal">
        <h3>Add a recipe</h3>

        <label>Title *</label>
        <input v-model="form.title" />

        <label>Instructions *</label>
        <textarea v-model="form.instructions" rows="4"></textarea>

        <label>Ingredients</label>
        <div v-for="(ing, idx) in ingredients" :key="idx" class="ingredients-row">
          <input placeholder="amount" v-model="ing.amount" />
          <input placeholder="unit" v-model="ing.unit" />
          <input placeholder="ingredient name" v-model="ing.name" />
          <div class="ingredient-actions">
            <button @click="removeIngredientRow(idx)" type="button">-</button>
            <button @click="addIngredientRow" type="button">+</button>
          </div>
        </div>

        <label>Time (minutes) *</label>
        <input type="number" v-model.number="form.time" />

        <label>Meal type</label>
        <select v-model="form.meal_type">
          <option value="">(none)</option>
          <option>Breakfast</option>
          <option>Lunch</option>
          <option>Dinner</option>
        </select>

        <label>Difficulty *</label>
        <select v-model.number="form.difficulty">
          <option :value="1">1 - Easy</option>
          <option :value="2">2 - Moderate</option>
          <option :value="3">3 - Difficult</option>
        </select>

        <label>Author</label>
        <input v-model="form.author" />

        <label>Source name</label>
        <input v-model="form.source_name" />

        <label>Source link</label>
        <input v-model="form.source_link" />

        <label>Image link</label>
        <input v-model="form.image_link" />

        <div class="toggles">
          <label><input type="checkbox" v-model="form.vegan" /> Vegan</label>
          <label><input type="checkbox" v-model="form.vegetarian" /> Vegetarian</label>
        </div>

        <h4>Nutrients (required)</h4>
        <div class="nutrients">
          <label>Calories (kcal) *</label>
          <input type="number" v-model.number="form.calories" />
          <label>Protein (g) *</label>
          <input type="number" v-model.number="form.protein" />
          <label>Fat (g) *</label>
          <input type="number" v-model.number="form.fat" />
          <label>Carbohydrates (g) *</label>
          <input type="number" v-model.number="form.carbohydrates" />
        </div>

        <div class="actions">
          <button class="confirm" @click="submit" :disabled="submitting">Add</button>
          <button class="cancel" @click="closeModal" :disabled="submitting">Cancel</button>
        </div>

        <div v-if="status.message" :class="['status', status.type]">{{ status.message }}</div>
      </div>
    </div>
  </div>
</template>

<script>
import axios from '../../services/axios.js'

export default {
  data() {
    return {
      showModal: false,
      submitting: false,
      // ingredients follow schema: amount, unit, name
      ingredients: [ { amount: '', unit: '', name: '' } ],
      form: {
        title: '',
        instructions: '',
        time: null,
        author: '',
        source_name: '',
        source_link: '',
        meal_type: '',
        difficulty: 1,
        vegan: false,
        vegetarian: false,
        calories: null,
        protein: null,
        fat: null,
        carbohydrates: null,
        image_link: '',
      },
      status: { message: '', type: '' }
    }
  },
  methods: {
    openModal() { this.showModal = true; this.status = { message: '', type: '' } },
    closeModal() { this.showModal = false },
    addIngredientRow() { this.ingredients.push({ amount: '', unit: '', name: '' }) },
    removeIngredientRow(index) {
      if (this.ingredients.length === 1) {
        this.ingredients = [ { amount: '', unit: '', name: '' } ]
      } else {
        this.ingredients.splice(index, 1)
      }
    },
    async submit() {
      // client-side validation according to schema required fields
      const missing = []
      if (!this.form.title) missing.push('title')
      if (!this.form.instructions) missing.push('instructions')
      if (this.form.time == null) missing.push('time')
      if (!this.form.difficulty) missing.push('difficulty')
      if (this.form.calories == null) missing.push('calories')
      if (this.form.protein == null) missing.push('protein')
      if (this.form.fat == null) missing.push('fat')
      if (this.form.carbohydrates == null) missing.push('carbohydrates')

      if (missing.length) {
        this.status = { message: `Missing required: ${missing.join(', ')}`, type: 'error' }
        return
      }

      const ingredients = this.ingredients
        .map(i => {
          const parts = []
          if (i.amount) parts.push(i.amount)
          if (i.unit) parts.push(i.unit)
          if (i.name) parts.push(i.name)
          return parts.join(' ').trim()
        })
        .filter(Boolean)

      const payload = {
        ...this.form,
        ingredients
      }

      this.submitting = true
      this.status = { message: '', type: '' }

      try {
        const resp = await axios.post('/recipes/crud', payload)
        this.status = { message: resp.data.message || 'Recipe added', type: 'success' }
        this.$emit('recipeAdded')
        setTimeout(() => { this.closeModal(); this.resetForm() }, 800)
      } catch (err) {
        this.status = { message: err.response?.data?.error?.message || err.message, type: 'error' }
      } finally {
        this.submitting = false
      }
    },
    resetForm() {
      this.form = {
        title: '', instructions: '', time: null, author: '', source_name: '', source_link: '',
        meal_type: '', difficulty: 1, vegan: false, vegetarian: false,
        calories: null, protein: null, fat: null, carbohydrates: null, image_link: ''
      }
      this.ingredients = [ { amount: '', unit: '', name: '' } ]
    }
  }
}
</script>

<style scoped>
.add-recipe-section { margin: 20px 0; }
.add-btn {
  background: #FFEE8C;
  border: 2px solid #000;
  border-radius: 30px;
  padding: 10px 30px;
  font-weight: 700;
  cursor: pointer;
}
.modal-overlay {
  position: fixed;
  left: 0; right: 0; top: 0; bottom: 0;
  background: rgba(0,0,0,0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}
.modal {
  background: #fff;
  padding: 20px;
  border-radius: 8px;
  width: 90%;
  max-width: 700px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.modal input, .modal textarea, .modal select { padding: 8px; border: 1px solid #ccc; border-radius: 4px }
.ingredients-row { display:flex; gap:8px; align-items:center }
.ingredients-row input { flex: 1 }
.ingredient-actions { display:flex; gap:6px }
.actions { display:flex; gap:10px; margin-top:8px }
.actions .confirm { background: #28a745; color: #fff; padding: 8px 16px; border-radius: 6px; border: none }
.actions .cancel { background: #ccc; padding: 8px 16px; border-radius: 6px; border: none }
.status { padding: 8px; border-radius: 6px; margin-top: 8px }
.status.success { background: #d4edda; color: #155724 }
.status.error { background: #f8d7da; color: #721c24 }
.toggles { display:flex; gap:12px; align-items:center }
.nutrients { display:grid; grid-template-columns: repeat(2, 1fr); gap:8px }
</style>