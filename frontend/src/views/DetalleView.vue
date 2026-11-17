<template>
  <main class="min-h-screen bg-slate-950 pb-24 text-slate-100">
    <header class="border-b border-slate-800">
      <div class="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
        <RouterLink :to="{ name: 'biblioteca' }" class="text-lg font-semibold tracking-wide text-teal-300">Mnemosine</RouterLink>
        <RouterLink :to="{ name: 'biblioteca' }" class="text-sm text-slate-400 hover:text-teal-300">Volver a la biblioteca</RouterLink>
      </div>
    </header>

    <section class="mx-auto max-w-2xl px-6 py-8">
      <p v-if="loading" class="text-slate-400">Cargando…</p>
      <div v-else-if="error" role="alert" class="rounded-lg border border-red-900 bg-red-950/60 px-4 py-4 text-center text-red-300">{{ error }}</div>

      <template v-else-if="track">
        <div class="flex items-start gap-5">
          <div class="flex h-28 w-28 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-teal-500/30 to-slate-800" aria-hidden="true">
            <svg viewBox="0 0 24 24" class="h-12 w-12 text-teal-300" fill="currentColor"><path d="M12 3v10.55A4 4 0 1 0 14 17V7h4V3h-6z"/></svg>
          </div>
          <div class="min-w-0">
            <h1 class="text-2xl font-semibold leading-tight">{{ track.title }}</h1>
            <p class="mt-1 text-lg text-slate-300">{{ track.artists }}</p>
            <p v-if="track.album" class="text-sm text-slate-400">{{ track.album }}<span v-if="track.release_year"> · {{ track.release_year }}</span></p>
            <p class="mt-2 text-xs text-slate-500">Duración {{ formatDuration(track.duration_seconds) }}</p>
          </div>
        </div>

        <div class="mt-6 flex flex-wrap gap-3">
          <button type="button" class="rounded-lg bg-teal-500 px-4 py-2 font-medium text-slate-950 transition hover:bg-teal-400 disabled:cursor-not-allowed disabled:opacity-40"
            :disabled="!track.access.can_stream" :aria-label="`Reproducir ${track.title}`" @click="play">
            Reproducir
          </button>
          <a v-if="track.access.can_download" class="rounded-lg border border-slate-700 px-4 py-2 text-slate-300 transition hover:border-teal-400 hover:text-teal-300"
            :href="downloadHref" download aria-label="Descargar el archivo original">Descargar</a>
          <span v-else class="rounded-lg border border-slate-800 px-4 py-2 text-slate-600">Descarga no autorizada</span>
        </div>

        <div class="mt-4 flex flex-wrap items-center gap-2">
          <label class="text-xs text-slate-400" for="add-to-list">Añadir a una lista</label>
          <select id="add-to-list" v-model="selectedPlaylist" class="max-w-48 rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm outline-none focus:border-teal-400">
            <option value="">Elige…</option>
            <option v-for="playlist in playlists" :key="playlist.playlist_id" :value="playlist.playlist_id">{{ playlist.name }}</option>
          </select>
          <button type="button" class="rounded-lg border border-slate-700 px-3 py-2 text-sm text-slate-300 transition hover:border-teal-400 hover:text-teal-300 disabled:opacity-50"
            :disabled="!selectedPlaylist || addingToList" @click="addToList">Añadir</button>
          <span v-if="listMessage" role="status" class="text-xs text-teal-300">{{ listMessage }}</span>
        </div>

        <PermisosPanel v-if="ownCopy" :location-id="ownCopy.location_id" class="mt-6" @updated="load" />

        <dl v-if="ownCopy" class="mt-6 grid grid-cols-2 gap-4 rounded-xl border border-slate-800 bg-slate-900/50 p-4 text-sm">
          <div><dt class="text-xs text-slate-500">Visibilidad</dt><dd class="mt-0.5 text-slate-200">{{ ownCopy.visibility === 'PRIVATE' ? 'Privada' : 'Pública' }}</dd></div>
          <div><dt class="text-xs text-slate-500">Disponibilidad</dt><dd class="mt-0.5 text-slate-200">{{ ownCopy.availability === 'AVAILABLE' ? 'Disponible' : 'No disponible' }}</dd></div>
          <div><dt class="text-xs text-slate-500">Tamaño</dt><dd class="mt-0.5 text-slate-200">{{ formatBytes(ownCopy.size_bytes) }}</dd></div>
          <div><dt class="text-xs text-slate-500">Formato</dt><dd class="mt-0.5 text-slate-200">{{ ownCopy.mime_type }}</dd></div>
          <div class="col-span-2"><dt class="text-xs text-slate-500">SHA-256</dt><dd class="mt-0.5 break-all font-mono text-xs text-slate-400">{{ ownCopy.sha256 }}</dd></div>
        </dl>

        <h2 v-if="track.copies.length" class="mt-6 text-sm font-medium text-slate-400">Copias en tu biblioteca</h2>
        <ul v-if="track.copies.length" class="mt-2 divide-y divide-slate-800 rounded-xl border border-slate-800">
          <li v-for="copy in track.copies" :key="copy.location_id" class="flex items-center justify-between gap-4 px-4 py-2 text-xs text-slate-400">
            <span>Copia #{{ copy.location_id }} · {{ formatBytes(copy.size_bytes) }} · {{ copy.mime_type }}</span>
            <span :class="copy.availability === 'AVAILABLE' ? 'text-teal-400' : 'text-amber-400'">{{ copy.availability === 'AVAILABLE' ? 'Disponible' : 'No disponible' }}</span>
          </li>
        </ul>
      </template>
    </section>
  </main>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { api, ApiError } from '../services/api'
import { formatBytes, formatDuration } from '../services/format'
import { usePlayerStore } from '../stores/player'
import PermisosPanel from '../components/PermisosPanel.vue'

const route = useRoute()
const player = usePlayerStore()

const track = ref(null)
const loading = ref(true)
const error = ref('')
const playlists = ref([])
const selectedPlaylist = ref('')
const addingToList = ref(false)
const listMessage = ref('')

const ownCopy = computed(() => track.value?.copies?.[0] ?? null)
const downloadHref = computed(() => (track.value ? api.downloadUrl(track.value.track_id) : '#'))

async function load() {
  loading.value = true
  error.value = ''
  try {
    track.value = await api.getTrack(route.params.id)
  } catch (err) {
    error.value = err?.status === 404
      ? 'Esta canción no existe o no tienes permiso para verla.'
      : 'No se pudo cargar la canción. Inténtalo de nuevo.'
    track.value = null
  } finally {
    loading.value = false
  }
}

async function loadPlaylists() {
  try {
    playlists.value = await api.playlists()
  } catch {
    playlists.value = []
  }
}

function play() {
  if (!track.value || !track.value.access.can_stream) return
  player.playSingle({
    track_id: track.value.track_id,
    title: track.value.title,
    artists: track.value.artists,
    album: track.value.album,
    duration_seconds: track.value.duration_seconds,
    available: true
  })
}

async function addToList() {
  if (!selectedPlaylist.value || !track.value) return
  addingToList.value = true
  listMessage.value = ''
  try {
    await api.addTrackToPlaylist(Number(selectedPlaylist.value), track.value.track_id)
    listMessage.value = 'Añadida a la lista.'
  } catch (err) {
    listMessage.value = err instanceof ApiError ? err.message : 'No se pudo añadir a la lista.'
  } finally {
    addingToList.value = false
  }
}

onMounted(async () => {
  await load()
  await loadPlaylists()
})
</script>
