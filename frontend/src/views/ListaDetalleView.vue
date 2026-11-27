<template>
  <div class="page listadetalle-page">

    <section class="page-section">
      <RouterLink to="/listas" class="text-link mb-6">← Tus listas</RouterLink>
      <p v-if="loading" class="text-slate-400">Cargando…</p>
      <p v-else-if="error" role="alert" class="rounded-lg border border-red-900 bg-red-950/60 px-4 py-3 text-red-300">{{ error }}</p>

      <template v-else-if="detail">
        <div class="flex flex-wrap items-start justify-between gap-3">
          <div class="min-w-0">
            <template v-if="!editing">
              <h1 class="text-3xl font-semibold leading-tight">{{ detail.name }}</h1>
              <p v-if="detail.description" class="mt-1 text-slate-400">{{ detail.description }}</p>
              <button type="button" class="mt-2 text-xs text-slate-500 underline underline-offset-2 hover:text-slate-300" @click="startEdit">Renombrar</button>
            </template>
            <form v-else class="flex flex-wrap items-center gap-2" @submit.prevent="saveRename">
              <label class="sr-only" for="rename">Nuevo nombre</label>
              <input id="rename" v-model="renameValue" required maxlength="255" class="rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 outline-none focus:border-teal-400" />
              <button type="submit" class="rounded-lg bg-teal-500 px-3 py-2 text-sm font-medium text-slate-950 hover:bg-teal-400">Guardar</button>
              <button type="button" class="rounded-lg border border-slate-700 px-3 py-2 text-sm text-slate-300 hover:border-teal-400" @click="editing = false">Cancelar</button>
            </form>
          </div>
          <button type="button" class="rounded-lg border border-red-900 px-3 py-2 text-sm text-red-300 transition hover:bg-red-950" @click="removePlaylist">Eliminar lista</button>
        </div>

        <div class="playlist-layout"><div class="min-w-0"><div class="mt-4 flex flex-wrap gap-2">
          <button type="button" class="rounded-lg bg-teal-500 px-4 py-2 font-medium text-slate-950 transition hover:bg-teal-400 disabled:opacity-50"
            :disabled="detail.tracks.length === 0" @click="playAll">Reproducir lista</button>
        </div>

        <ol v-if="detail.tracks.length" class="mt-4 divide-y divide-slate-800 rounded-xl border border-slate-800">
          <li v-for="(track, index) in orderedTracks" :key="track.track_id" class="playlist-track flex flex-wrap items-center gap-2 px-3 py-3">
            <span class="hidden sm:block w-6 text-right text-xs tabular-nums text-slate-600">{{ index + 1 }}</span>
            <button type="button" class="round-play"
              :aria-label="`Reproducir ${track.title}`" @click="playFrom(index)">
              <svg viewBox="0 0 24 24" class="h-4 w-4" fill="currentColor" aria-hidden="true"><path d="M8 5v14l11-7z"/></svg>
            </button>
            <div class="min-w-0 flex-1">
              <RouterLink :to="{ name: 'detalle', params: { id: track.track_id } }" class="block truncate text-sm font-medium text-slate-100 hover:text-teal-300">{{ track.title }}</RouterLink>
              <span class="block truncate text-xs text-slate-500">{{ track.artists }}</span>
            </div>
            <div class="playlist-track-actions flex items-center gap-1">
              <button type="button" class="rounded-md p-1.5 text-slate-500 transition hover:bg-slate-800 hover:text-teal-300 disabled:opacity-30" :disabled="index === 0" :aria-label="`Subir ${track.title}`" @click="move(index, -1)">
                <svg viewBox="0 0 24 24" class="h-4 w-4" fill="currentColor" aria-hidden="true"><path d="M12 5l7 7-1.4 1.4L12 7.8 6.4 13.4 5 12z"/></svg>
              </button>
              <button type="button" class="rounded-md p-1.5 text-slate-500 transition hover:bg-slate-800 hover:text-teal-300 disabled:opacity-30" :disabled="index === orderedTracks.length - 1" :aria-label="`Bajar ${track.title}`" @click="move(index, 1)">
                <svg viewBox="0 0 24 24" class="h-4 w-4" fill="currentColor" aria-hidden="true"><path d="M12 19l-7-7 1.4-1.4L12 16.2l5.6-5.6L19 12z"/></svg>
              </button>
              <button type="button" class="rounded-md p-1.5 text-slate-500 transition hover:bg-red-950 hover:text-red-300" :aria-label="`Quitar ${track.title} de la lista`" @click="removeTrack(track.track_id)">
                <svg viewBox="0 0 24 24" class="h-4 w-4" fill="currentColor" aria-hidden="true"><path d="M6 6h12v2H6zM9 4h6v2H9zM8 10l1 10h6l1-10z"/></svg>
              </button>
            </div>
          </li>
        </ol>
        <p v-else class="mt-4 rounded-xl border border-dashed border-slate-800 px-4 py-6 text-center text-sm text-slate-500">Lista vacía. Añade canciones desde abajo o desde el detalle de una canción.</p>

        </div><div class="playlist-add form-panel">
          <h2 class="text-lg font-medium text-slate-200">Añadir desde tu biblioteca</h2>
          <label class="sr-only" for="add-search">Buscar en tu biblioteca</label>
          <input id="add-search" v-model="addQuery" type="search" placeholder="Buscar por título, artista o álbum" autocomplete="off"
            class="mt-2 w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 outline-none focus:border-teal-400" />
          <ul class="mt-2 divide-y divide-slate-800 rounded-xl border border-slate-800">
            <li v-for="item in libraryResults" :key="item.track_id" class="flex items-center justify-between gap-3 px-3 py-2">
              <span class="min-w-0"><span class="block truncate text-sm text-slate-200">{{ item.title }}</span><span class="block truncate text-xs text-slate-500">{{ item.artists }}</span></span>
              <button type="button" class="rounded-lg border border-slate-700 px-3 py-1.5 text-xs text-slate-300 transition hover:border-teal-400 hover:text-teal-300 disabled:opacity-40"
                :disabled="isInList(item.track_id)" @click="addTrack(item.track_id)">{{ isInList(item.track_id) ? 'En la lista' : 'Añadir' }}</button>
            </li>
          </ul>
        </div>
      </div></template>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../services/api'
import { usePlayerStore } from '../stores/player'

const route = useRoute()
const router = useRouter()
const player = usePlayerStore()

const playlistId = Number(route.params.id)
const detail = ref(null)
const loading = ref(true)
const error = ref('')
const editing = ref(false)
const renameValue = ref('')
const addQuery = ref('')
const libraryRaw = ref([])

const orderedTracks = computed(() => detail.value?.tracks ?? [])
const inListIds = computed(() => new Set(orderedTracks.value.map((track) => track.track_id)))
const isInList = (trackId) => inListIds.value.has(trackId)

let libraryTimer = null
const libraryResults = ref([])
watch(addQuery, () => {
  clearTimeout(libraryTimer)
  libraryTimer = setTimeout(loadLibrary, 300)
})

async function load() {
  loading.value = true
  error.value = ''
  try {
    detail.value = await api.playlistDetail(playlistId)
  } catch (err) {
    error.value = err?.status === 404 ? 'Esta lista no existe o no tienes permiso para verla.' : 'No se pudo cargar la lista.'
  } finally {
    loading.value = false
  }
}

async function loadLibrary() {
  try {
    const data = await api.library({ q: addQuery.value.trim(), page: 1, pageSize: 8 })
    libraryResults.value = data.items
  } catch {
    libraryResults.value = []
  }
}

function playAll() {
  player.setQueue(orderedTracks.value.map((track) => ({ ...track, available: true })), 0)
}

function playFrom(index) {
  player.setQueue(orderedTracks.value.map((track) => ({ ...track, available: true })), index)
}

async function move(index, direction) {
  const tracks = [...orderedTracks.value]
  const target = index + direction
  const [moved] = tracks.splice(index, 1)
  tracks.splice(target, 0, moved)
  detail.value = { ...detail.value, tracks }
  try {
    await api.reorderPlaylist(playlistId, tracks.map((track) => track.track_id))
  } catch {
    await load()
  }
}

async function removeTrack(trackId) {
  try {
    await api.removeTrackFromPlaylist(playlistId, trackId)
    await load()
  } catch (err) {
    error.value = 'No se pudo quitar la canción de la lista.'
  }
}

async function addTrack(trackId) {
  try {
    await api.addTrackToPlaylist(playlistId, trackId)
    await load()
  } catch (err) {
    error.value = 'No se pudo añadir la canción (quizá ya está en la lista).'
  }
}

function startEdit() {
  renameValue.value = detail.value.name
  editing.value = true
}

async function saveRename() {
  try {
    await api.renamePlaylist(playlistId, { name: renameValue.value.trim() })
    editing.value = false
    await load()
  } catch {
    error.value = 'No se pudo renombrar la lista.'
  }
}

async function removePlaylist() {
  const confirmed = window.confirm('¿Eliminar esta lista? Las canciones no se borrarán, solo la lista.')
  if (!confirmed) return
  try {
    await api.deletePlaylist(playlistId)
    router.push({ name: 'listas' })
  } catch {
    error.value = 'No se pudo eliminar la lista.'
  }
}

onMounted(async () => {
  await load()
  await loadLibrary()
})
onUnmounted(() => clearTimeout(libraryTimer))
</script>
