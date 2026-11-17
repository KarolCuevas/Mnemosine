<template>
  <main class="min-h-screen bg-slate-950 pb-24 text-slate-100">
    <header class="border-b border-slate-800">
      <div class="mx-auto flex max-w-5xl items-center justify-between gap-4 px-6 py-4">
        <span class="text-lg font-semibold tracking-wide text-teal-300">Mnemosine</span>
        <nav aria-label="Principal" class="flex items-center gap-3 text-sm">
          <RouterLink :to="{ name: 'biblioteca' }" class="rounded-lg px-3 py-1.5 text-slate-300 transition hover:text-teal-300">Mi biblioteca</RouterLink>
          <RouterLink :to="{ name: 'descubrir' }" class="rounded-lg px-3 py-1.5 text-slate-300 transition hover:text-teal-300">Descubrir</RouterLink>
        </nav>
      </div>
    </header>

    <section class="mx-auto max-w-5xl px-6 py-6">
      <p class="text-xs font-medium uppercase tracking-[0.3em] text-teal-300">Biblioteca pública de</p>
      <h1 class="mt-1 text-3xl font-semibold">@{{ username }}</h1>
      <p class="mt-1 text-sm text-slate-400">{{ items.length }} {{ items.length === 1 ? 'canción pública' : 'canciones públicas' }}</p>

      <p v-if="loading" class="mt-10 text-center text-slate-400">Cargando…</p>
      <p v-else-if="error" role="alert" class="mt-10 rounded-lg border border-red-900 bg-red-950/60 px-4 py-3 text-center text-red-300">{{ error }}</p>
      <p v-else-if="items.length === 0" class="mt-10 text-center text-slate-400">Esta cuenta no tiene música pública.</p>

      <ul v-else class="mt-4 divide-y divide-slate-800 rounded-xl border border-slate-800">
        <li v-for="(item, index) in items" :key="item.location_id" class="flex items-center gap-3 px-4 py-3 transition hover:bg-slate-900/60">
          <button type="button" class="rounded-full bg-slate-800 p-2 text-teal-300 transition hover:bg-teal-500 hover:text-slate-950"
            :aria-label="`Reproducir ${item.title}`" @click="playFromList(index)">
            <svg viewBox="0 0 24 24" class="h-4 w-4" fill="currentColor" aria-hidden="true"><path d="M8 5v14l11-7z"/></svg>
          </button>
          <RouterLink :to="{ name: 'detalle', params: { id: item.track_id } }" class="min-w-0 flex-1">
            <span class="block truncate font-medium text-slate-100">{{ item.title }}</span>
            <span class="block truncate text-xs text-slate-400">{{ item.artists }}<template v-if="item.album"> · {{ item.album }}</template></span>
          </RouterLink>
          <span class="text-xs tabular-nums text-slate-500">{{ formatDuration(item.duration_seconds) }}</span>
          <a v-if="item.public_download_allowed" class="rounded-lg border border-slate-700 px-3 py-1.5 text-xs text-slate-300 transition hover:border-teal-400 hover:text-teal-300"
            :href="api.downloadUrl(item.track_id)" download :aria-label="`Descargar ${item.title}`">Descargar</a>
        </li>
      </ul>
    </section>
  </main>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../services/api'
import { formatDuration } from '../services/format'
import { usePlayerStore } from '../stores/player'

const route = useRoute()
const player = usePlayerStore()

const username = route.params.username
const items = ref([])
const loading = ref(true)
const error = ref('')

function playFromList(index) {
  player.setQueue(items.value.map((item) => ({ ...item, available: true })), index)
}

onMounted(async () => {
  try {
    const catalog = await api.discoveryCatalog(username)
    items.value = catalog.items
  } catch (err) {
    error.value = err?.status === 404
      ? 'Esta cuenta no existe o está desactivada.'
      : 'No se pudo cargar la colección. Inténtalo de nuevo.'
  } finally {
    loading.value = false
  }
})
</script>
