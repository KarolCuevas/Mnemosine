<template>
  <div class="page"><section class="page-section">
    <p class="eyebrow">A TU RITMO</p><h1 class="mt-2 text-3xl font-semibold">Tus listas</h1>
    <p class="muted mt-3">Una selección para cada momento. Tú pones la banda sonora.</p>
    <form class="create-list-form" @submit.prevent="createList">
      <div><label class="field-label" for="new-list">Nombre de la nueva lista</label><input id="new-list" v-model="newName" maxlength="255" required placeholder="Para un domingo sin prisa…" class="text-input" /></div>
      <button type="submit" class="button button-primary" :disabled="creating || !newName.trim()"><AppIcon name="plus" />{{ creating ? 'Creando…' : 'Crear lista' }}</button>
    </form>
    <p v-if="loading" class="muted py-10" role="status">Cargando tus listas…</p>
    <p v-else-if="error" role="alert" class="mt-6 rounded-lg border border-red-900 bg-red-950/60 p-4 text-red-300">{{ error }}</p>
    <div v-else-if="playlists.length === 0" class="empty-state"><span class="empty-icon"><AppIcon name="list" /></span><h2 class="text-xl font-medium">Un buen momento merece su lista</h2><p>Escribe un nombre arriba y empieza a reunir tus canciones favoritas.</p></div>
    <ul v-else class="catalog-cards"><li v-for="playlist in playlists" :key="playlist.playlist_id"><RouterLink :to="{ name: 'lista', params: { id: playlist.playlist_id } }" class="catalog-card"><TrackArtwork :seed="playlist.name" icon="list" /><strong>{{ playlist.name }}</strong><span v-if="playlist.description">{{ playlist.description }}</span><span class="card-count">{{ playlist.item_count }} {{ playlist.item_count === 1 ? 'canción' : 'canciones' }}</span></RouterLink></li></ul>
  </section></div>
</template>

<script setup>
import AppIcon from '../components/AppIcon.vue'
import TrackArtwork from '../components/TrackArtwork.vue'
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../services/api'

const router = useRouter()
const playlists = ref([])
const newName = ref('')
const creating = ref(false)
const loading = ref(true)
const error = ref('')

async function load() {
  loading.value = true
  try {
    playlists.value = await api.playlists()
  } catch {
    error.value = 'No se pudieron cargar las listas.'
  } finally {
    loading.value = false
  }
}

async function createList() {
  creating.value = true
  try {
    const created = await api.createPlaylist({ name: newName.value.trim() })
    newName.value = ''
    router.push({ name: 'lista', params: { id: created.playlist_id } })
  } catch {
    error.value = 'No se pudo crear la lista.'
  } finally {
    creating.value = false
  }
}

onMounted(load)
</script>
