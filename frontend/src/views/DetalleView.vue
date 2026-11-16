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
            :disabled="!anyAvailable" :aria-label="`Reproducir ${track.title}`" @click="play">
            Reproducir
          </button>
          <a class="rounded-lg border border-slate-700 px-4 py-2 text-slate-300 transition hover:border-teal-400 hover:text-teal-300"
            :href="downloadHref" download aria-label="Descargar el archivo original">Descargar</a>
        </div>

        <dl class="mt-6 grid grid-cols-2 gap-4 rounded-xl border border-slate-800 bg-slate-900/50 p-4 text-sm">
          <div><dt class="text-xs text-slate-500">Visibilidad</dt><dd class="mt-0.5 text-slate-200">{{ firstCopy?.visibility === 'PRIVATE' ? 'Privada' : 'Pública' }}</dd></div>
          <div><dt class="text-xs text-slate-500">Disponibilidad</dt><dd class="mt-0.5 text-slate-200">{{ firstCopy?.availability === 'AVAILABLE' ? 'Disponible' : 'No disponible' }}</dd></div>
          <div><dt class="text-xs text-slate-500">Tamaño</dt><dd class="mt-0.5 text-slate-200">{{ formatBytes(firstCopy?.size_bytes) }}</dd></div>
          <div><dt class="text-xs text-slate-500">Formato</dt><dd class="mt-0.5 text-slate-200">{{ firstCopy?.mime_type }}</dd></div>
          <div class="col-span-2"><dt class="text-xs text-slate-500">SHA-256</dt><dd class="mt-0.5 break-all font-mono text-xs text-slate-400">{{ firstCopy?.sha256 }}</dd></div>
        </dl>

        <h2 class="mt-6 text-sm font-medium text-slate-400">Copias en tu biblioteca</h2>
        <ul class="mt-2 divide-y divide-slate-800 rounded-xl border border-slate-800">
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
import { useRoute, useRouter } from 'vue-router'
import { api } from '../services/api'
import { formatBytes, formatDuration } from '../services/format'
import { usePlayerStore } from '../stores/player'

const route = useRoute()
const router = useRouter()
const player = usePlayerStore()

const track = ref(null)
const loading = ref(true)
const error = ref('')

const firstCopy = computed(() => track.value?.copies?.[0] ?? null)
const anyAvailable = computed(() => (track.value?.copies ?? []).some((copy) => copy.availability === 'AVAILABLE'))
const downloadHref = computed(() => (track.value ? api.downloadUrl(track.value.track_id) : '#'))

async function load() {
  loading.value = true
  error.value = ''
  try {
    track.value = await api.getTrack(route.params.id)
  } catch (err) {
    if (err?.status === 404) {
      error.value = 'Esta canción no existe o no tienes permiso para verla.'
    } else {
      error.value = 'No se pudo cargar la canción. Inténtalo de nuevo.'
    }
  } finally {
    loading.value = false
  }
}

function play() {
  if (!track.value || !anyAvailable.value) return
  player.playSingle({
    track_id: track.value.track_id,
    title: track.value.title,
    artists: track.value.artists,
    album: track.value.album,
    duration_seconds: track.value.duration_seconds,
    available: true
  })
}

onMounted(load)
</script>
