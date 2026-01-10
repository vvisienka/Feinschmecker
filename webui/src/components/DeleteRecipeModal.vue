<script setup>
import { ref } from 'vue'
import api from '../../services/axios'

const props = defineProps({
  recipeTitle: String,
  recipeName: String // Used for the API call
})

const emit = defineEmits(['close', 'deleted'])
const isDeleting = ref(false)

const confirmDelete = async () => {
  isDeleting.value = true
  try {
    // Call the delete endpoint with the recipe name
    // The backend expects the name/slug in the URL
    await api.delete(`/recipes/${encodeURIComponent(props.recipeName)}`)
    
    emit('deleted')
    emit('close')
  } catch (error) {
    console.error('Failed to delete recipe:', error)
    alert('Error deleting recipe. Check console.')
  } finally {
    isDeleting.value = false
  }
}
</script>

<template>
  <div class="modal-overlay" @click.self="$emit('close')">
    <div class="modal-content">
      
      <div class="modal-header">
        <h3>Delete Recipe?</h3>
        <button class="close-btn" @click="$emit('close')">&times;</button>
      </div>

      <div class="modal-body">
        <p>Are you sure you want to delete <strong>{{ recipeTitle }}</strong>?</p>
        <p class="warning-text">This action cannot be undone.</p>
      </div>

      <div class="modal-footer">
        <button @click="$emit('close')" class="secondary-button">Cancel</button>
        <button 
          @click="confirmDelete" 
          :disabled="isDeleting" 
          class="delete-button"
        >
          {{ isDeleting ? 'Deleting...' : 'Delete' }}
        </button>
      </div>

    </div>
  </div>
</template>

<style scoped>
* { font-family: "Poppins", sans-serif; box-sizing: border-box; }

.modal-overlay {
  position: fixed; top: 0; left: 0; width: 100%; height: 100%;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex; justify-content: center; align-items: center; z-index: 1000;
}

.modal-content {
  background: white; width: 90%; max-width: 500px;
  border-radius: 15px; overflow: hidden;
  box-shadow: 0 4px 15px rgba(0,0,0,0.2);
  border: 2px solid #000000;
  display: flex; flex-direction: column;
}

.modal-header {
  padding: 20px; border-bottom: 2px solid #eee;
  display: flex; justify-content: space-between; align-items: center;
  background-color: #F0F8FF;
}

.modal-header h3 { margin: 0; font-size: 24px; font-weight: 700; color: #721c24; }
.close-btn { background: none; border: none; font-size: 28px; cursor: pointer; color: #555; }

.modal-body { padding: 30px 20px; text-align: center; }
.modal-body p { font-size: 18px; margin-bottom: 10px; }
.warning-text { color: #dc3545; font-size: 14px; margin-top: 5px; }

.modal-footer {
  padding: 20px; border-top: 2px solid #eee;
  display: flex; justify-content: flex-end; gap: 10px;
  background-color: #fff;
}

button {
  padding: 10px 20px; font-family: "Poppins"; font-size: 16px;
  border: 2px solid #000000; border-radius: 10px; cursor: pointer; font-weight: 500;
}

.secondary-button { background-color: #fff; transition: 0.3s; }
.secondary-button:hover { background-color: #f0f0f0; }

.delete-button { background-color: #ff4d4d; color: white; transition: 0.3s; }
.delete-button:hover { background-color: #cc0000; }
.delete-button:disabled { opacity: 0.6; cursor: not-allowed; }
</style>