<template>
  <div class="modal-backdrop">
    <div class="modal">
      <h2>Edit Recipe</h2>
      <label>Title</label>
      <input v-model="form.title" />

      <label>Link</label>
      <input v-model="form.link" />

      <label>Image Link</label>
      <input v-model="form.image_link" />

      <label>Time (minutes)</label>
      <input type="number" v-model.number="form.time" />

      <label>Vegan</label>
      <input type="checkbox" v-model="form.vegan" />

      <label>Vegetarian</label>
      <input type="checkbox" v-model="form.vegetarian" />

      <label>Ingredients (one per line)</label>
      <textarea v-model="ingredientsText" rows="5"></textarea>

      <label>Instructions (one step per line)</label>
      <textarea v-model="instructionsText" rows="6"></textarea>

      <div class="actions">
        <button @click="$emit('close')">Cancel</button>
        <button @click="onConfirm">Save</button>
      </div>
    </div>
  </div>
</template>

<script>
import axios from '../../services/axios'

export default {
  props: {
    recipe: { required: true },
  },
  data() {
    return {
      form: {
        title: this.recipe.name || '',
        link: this.recipe.link || '',
        image_link: this.recipe.image_link || '',
        time: this.recipe.time || 0,
        vegan: !!this.recipe.vegan,
        vegetarian: !!this.recipe.vegetarian,
      },
      instructionsText: Array.isArray(this.recipe.instructions) ? this.recipe.instructions.join('\n') : (this.recipe.instructions || ''),
      ingredientsText: Array.isArray(this.recipe.ingredients) ? this.recipe.ingredients.join('\n') : (this.recipe.ingredients || ''),
    }
  },
  methods: {
    _sanitizeName(name) {
      return String(name).toLowerCase().replace(/ /g, '_').replace(/%/g, 'percent').replace(/&/g, 'and')
    },
    async onConfirm() {
      const payload = {
        title: this.form.title,
        link: this.form.link,
        image_link: this.form.image_link,
        time: this.form.time,
        vegan: !!this.form.vegan,
        vegetarian: !!this.form.vegetarian,
        ingredients: this.ingredientsText.split('\n').map(s => s.trim()).filter(Boolean),
        instructions: this.instructionsText.split('\n').map(s => s.trim()).filter(Boolean),
      }

      const id = this._sanitizeName(this.recipe.name || this.recipe.id || '')
      try {
        await axios.patch(`/recipes/crud/${id}`, payload)
        // update local copy
        const updated = Object.assign({}, this.recipe, {
          name: payload.title,
          link: payload.link,
          image_link: payload.image_link,
          time: payload.time,
          vegan: payload.vegan,
          vegetarian: payload.vegetarian,
          ingredients: payload.ingredients,
          instructions: payload.instructions,
        })
        localStorage.setItem('current_recipe', JSON.stringify(updated))
        this.$emit('saved', updated)
        this.$emit('close')
      } catch (err) {
        console.error('Failed to update recipe', err)
        alert('Failed to update recipe')
      }
    }
  }
}
</script>

<style scoped>
.modal-backdrop{position:fixed;left:0;right:0;top:0;bottom:0;display:flex;align-items:center;justify-content:center;background:rgba(0,0,0,0.4)}
.modal{background:#fff;padding:20px;border-radius:8px;max-width:600px;width:90%}
.modal label{display:block;margin-top:8px}
.modal input,.modal textarea{width:100%;padding:8px;margin-top:4px}
.actions{display:flex;justify-content:flex-end;margin-top:12px}
.actions button{margin-left:8px}
</style>