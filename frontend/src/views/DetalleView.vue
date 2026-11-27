<template>
  <div class="page detalle-page"><section class="page-section">
    <RouterLink to="/biblioteca" class="text-link mb-6"><AppIcon name="back" /> Tu biblioteca</RouterLink>
    <p v-if="loading" class="muted py-10" role="status">Cargando canción…</p>
    <div v-else-if="error" role="alert" class="rounded-xl border border-red-900 bg-red-950/60 p-5 text-red-300">{{ error }}</div>
    <template v-else-if="track">
      <div class="song-hero">
        <TrackArtwork :src="track.cover_url" :seed="track.album || track.title" />
        <div class="min-w-0"><p class="eyebrow">{{ ownCopy ? 'EN TU BIBLIOTECA' : 'COMPARTIDA CONTIGO' }}</p><h1>{{ track.title }}</h1><p class="song-artist">{{ track.artists }}</p><p v-if="track.album" class="muted mt-2">{{ track.album }}<span v-if="track.release_year"> · {{ track.release_year }}</span></p><p class="muted mt-2 text-xs">{{ formatDuration(track.duration_seconds) }}</p>
          <div class="mt-6 flex flex-wrap gap-3"><button type="button" class="button button-primary" :disabled="!track.access.can_stream" :aria-label="`Reproducir ${track.title}`" @click="play"><AppIcon name="play" /> Reproducir</button><a v-if="track.access.can_download" :href="downloadHref" download aria-label="Descargar el archivo original" class="button button-secondary">Descargar</a><span v-else class="muted self-center text-xs">Descarga no autorizada</span></div>
        </div>
      </div>
      <div class="detail-layout">
        <div class="min-w-0">
          <div class="form-panel"><h2 class="text-lg font-medium">Dale un lugar en tus listas</h2><p class="muted mt-2 text-sm">Guarda esta canción para el próximo momento.</p>
            <div class="mt-5 flex flex-wrap items-end gap-3"><div class="min-w-0 flex-1"><label class="field-label" for="add-to-list">Añadir a una lista</label><select id="add-to-list" v-model="selectedPlaylist" class="text-input"><option value="">{{ playlists.length ? 'Elige una lista…' : 'Todavía no tienes listas' }}</option><option v-for="playlist in playlists" :key="playlist.playlist_id" :value="playlist.playlist_id">{{ playlist.name }}</option></select></div><button type="button" class="button button-secondary" :disabled="!selectedPlaylist || addingToList" @click="addToList">{{ addingToList ? 'Añadiendo…' : 'Añadir' }}</button></div><p v-if="listMessage" role="status" class="mt-3 text-sm text-teal-300">{{ listMessage }}</p><RouterLink v-if="!playlists.length" to="/listas" class="text-link mt-4 text-sm">Crear mi primera lista <AppIcon name="arrow" /></RouterLink>
          </div>
          <PermisosPanel v-if="ownCopy" :location-id="ownCopy.location_id" class="mt-6" @updated="load" />
        </div>
        <aside v-if="ownCopy" class="file-panel">
          <p class="eyebrow">TU ARCHIVO</p><h2 class="mt-3 text-xl font-medium">Los detalles también cuentan.</h2>
          <dl v-if="track.album_artist || track.genre || track.track_number || track.disc_number || track.release_year" class="file-facts" aria-label="Etiquetas de la canción">
            <div v-if="track.album_artist"><dt>Artista del álbum</dt><dd>{{ track.album_artist }}</dd></div>
            <div v-if="track.genre"><dt>Género</dt><dd>{{ track.genre }}</dd></div>
            <div v-if="track.release_year"><dt>Año</dt><dd>{{ track.release_year }}</dd></div>
            <div v-if="track.track_number"><dt>Pista</dt><dd>{{ track.track_number }}</dd></div>
            <div v-if="track.disc_number"><dt>Disco</dt><dd>{{ track.disc_number }}</dd></div>
          </dl>
          <dl class="file-facts"><div><dt>Visibilidad</dt><dd>{{ ownCopy.visibility === 'PRIVATE' ? 'Privada' : 'Pública' }}</dd></div><div><dt>Disponibilidad</dt><dd>{{ ownCopy.availability === 'AVAILABLE' ? 'Disponible' : 'No disponible' }}</dd></div><div><dt>Tamaño</dt><dd>{{ formatBytes(ownCopy.size_bytes) }}</dd></div><div><dt>Formato</dt><dd>{{ ownCopy.mime_type }}</dd></div></dl>
          <details class="file-technical"><summary>Información técnica</summary><p class="muted mt-3 text-xs">Huella SHA-256</p><p class="mt-2 break-all font-mono text-xs text-slate-400">{{ ownCopy.sha256 }}</p></details>
          <h3 v-if="track.copies.length" class="mt-6 text-sm font-medium">Copias en tu biblioteca</h3><ul class="mt-3 space-y-3"><li v-for="copy in track.copies" :key="copy.location_id" class="rounded-lg border border-slate-700 p-3 text-xs"><span class="block text-slate-300">Copia #{{ copy.location_id }} · {{ formatBytes(copy.size_bytes) }}</span><span class="mt-1 block" :class="copy.availability === 'AVAILABLE' ? 'text-teal-300' : 'text-amber-300'">{{ copy.availability === 'AVAILABLE' ? 'Disponible' : 'No disponible' }}</span></li></ul>
        </aside>
      </div>
    </template>
  </section></div>
</template>

<script setup>
import AppIcon from '../components/AppIcon.vue'
import TrackArtwork from '../components/TrackArtwork.vue'
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
    cover_url: track.value.cover_url,
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
