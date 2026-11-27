<template>
  <div class="page"><section class="page-section">
    <p class="eyebrow">OTRAS FORMAS DE ESCUCHAR</p><h1 class="mt-2 text-3xl font-semibold">Bibliotecas públicas</h1>
    <p class="mt-3 max-w-2xl text-slate-400">Explora la música que otras personas han compartido con la comunidad de Mnemosine.</p>
    <p v-if="loading" class="muted py-10" role="status">Buscando nuevas colecciones…</p>
    <p v-else-if="error" role="alert" class="mt-6 rounded-lg border border-red-900 bg-red-950/60 p-4 text-red-300">{{ error }}</p>
    <div v-else-if="accounts.length === 0" class="empty-state mt-8"><span class="empty-icon"><AppIcon name="compass" /></span><h2 class="text-xl font-medium">Lo próximo por descubrir</h2><p>Aquí aparecerán las colecciones que la comunidad comparta. Mientras tanto, dale forma a la tuya.</p><RouterLink to="/biblioteca" class="button button-secondary">Volver a mi biblioteca</RouterLink></div>
    <ul v-else class="catalog-cards"><li v-for="account in accounts" :key="account.username"><RouterLink :to="{ name: 'coleccion', params: { username: account.username } }" class="catalog-card"><TrackArtwork :seed="account.username" icon="headphones" /><strong>{{ account.display_name || account.username }}</strong><span>@{{ account.username }}</span><span class="card-count">{{ account.public_copies }} {{ account.public_copies === 1 ? 'canción pública' : 'canciones públicas' }}</span></RouterLink></li></ul>
  </section></div>
</template>

<script setup>
import AppIcon from '../components/AppIcon.vue'
import TrackArtwork from '../components/TrackArtwork.vue'
import { onMounted, ref } from 'vue'
import { api } from '../services/api'

const accounts = ref([])
const loading = ref(true)
const error = ref('')

onMounted(async () => {
  try {
    accounts.value = (await api.discovery()).accounts
  } catch {
    error.value = 'No se pudo cargar Descubrir. Inténtalo de nuevo.'
  } finally {
    loading.value = false
  }
})
</script>
