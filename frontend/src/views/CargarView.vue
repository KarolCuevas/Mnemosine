<template>
  <main class="min-h-screen bg-slate-950 pb-24 text-slate-100">
    <header class="border-b border-slate-800">
      <div class="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
        <RouterLink :to="{ name: 'biblioteca' }" class="text-lg font-semibold tracking-wide text-teal-300">Mnemosine</RouterLink>
        <RouterLink :to="{ name: 'biblioteca' }" class="text-sm text-slate-400 hover:text-teal-300">Volver a la biblioteca</RouterLink>
      </div>
    </header>

    <section class="mx-auto max-w-2xl px-6 py-8">
      <p class="text-xs font-medium uppercase tracking-[0.3em] text-teal-300">Cargar música</p>
      <h1 class="mt-1 text-3xl font-semibold">Nueva canción</h1>
      <p class="mt-2 text-sm text-slate-400">La carga es privada por defecto. El archivo se valida de verdad (contenido, no solo extensión) y se calcula su SHA-256.</p>

      <form class="mt-6 space-y-4" @submit.prevent="onSubmit">
        <div>
          <label for="archivo" class="mb-1 block text-xs font-medium text-slate-400">Archivo de audio</label>
          <input id="archivo" ref="fileInput" type="file" required
            accept=".mp3,.m4a,.flac,.ogg,.wav,audio/mpeg,audio/flac,audio/ogg,audio/x-wav,audio/x-m4a"
            class="block w-full text-sm text-slate-300 file:mr-4 file:rounded-lg file:border-0 file:bg-slate-800 file:px-4 file:py-2 file:text-slate-200 hover:file:bg-slate-700"
            @change="onFileChange" />
          <p class="mt-1 text-[11px] text-slate-500">MP3, M4A, FLAC, OGG o WAV · máximo 50 MB</p>
        </div>

        <div>
          <label for="titulo" class="mb-1 block text-xs font-medium text-slate-400">Título</label>
          <input id="titulo" v-model="form.title" required maxlength="512"
            class="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 outline-none focus:border-teal-400" />
        </div>
        <div>
          <label for="artista" class="mb-1 block text-xs font-medium text-slate-400">Artista</label>
          <input id="artista" v-model="form.artist" required maxlength="255"
            class="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 outline-none focus:border-teal-400" />
        </div>
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label for="album" class="mb-1 block text-xs font-medium text-slate-400">Álbum (opcional)</label>
            <input id="album" v-model="form.album" maxlength="512"
              class="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 outline-none focus:border-teal-400" />
          </div>
          <div>
            <label for="pista" class="mb-1 block text-xs font-medium text-slate-400">Pista (opcional)</label>
            <input id="pista" v-model.number="form.track_number" type="number" min="1" max="1000"
              class="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 outline-none focus:border-teal-400" />
          </div>
        </div>

        <p v-if="error" role="alert" class="rounded-lg border border-red-900 bg-red-950/60 px-3 py-2 text-sm text-red-300">{{ error }}</p>

        <div v-if="uploading" class="space-y-1">
          <label class="text-xs font-medium text-slate-400" for="progreso">Subiendo… {{ progress }}%</label>
          <progress id="progreso" class="progress-teal h-3 w-full" :value="progress" max="100" aria-label="Progreso de la subida" />
        </div>

        <button type="submit" :disabled="uploading"
          class="w-full rounded-lg bg-teal-500 px-4 py-2.5 font-semibold text-slate-950 transition hover:bg-teal-400 disabled:opacity-60">
          {{ uploading ? 'Subiendo…' : 'Guardar como privada' }}
        </button>
      </form>

      <div v-if="result" class="mt-6 rounded-xl border border-teal-900 bg-teal-950/40 px-4 py-4" role="status">
        <p class="font-medium text-teal-300">“{{ result.title }}” subida correctamente.</p>
        <p class="mt-1 text-sm text-slate-400">Duración {{ formatDuration(result.duration_seconds) }} · {{ formatBytes(result.size_bytes) }} · privada</p>
        <div class="mt-3 flex gap-3">
          <RouterLink :to="{ name: 'detalle', params: { id: result.track_id } }" class="rounded-lg bg-teal-500 px-3 py-1.5 text-sm font-medium text-slate-950 transition hover:bg-teal-400">Ver detalle</RouterLink>
          <RouterLink :to="{ name: 'biblioteca' }" class="rounded-lg border border-slate-700 px-3 py-1.5 text-sm text-slate-300 transition hover:border-teal-400 hover:text-teal-300">Volver a la biblioteca</RouterLink>
        </div>
      </div>
    </section>
  </main>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { api, uploadWithProgress, ApiError } from '../services/api'
import { formatBytes, formatDuration } from '../services/format'

const fileInput = ref(null)
const uploading = ref(false)
const progress = ref(0)
const error = ref('')
const result = ref(null)

const form = reactive({
  title: '',
  artist: '',
  album: '',
  track_number: null
})

function onFileChange(event) {
  const file = event.target.files?.[0]
  if (!file) return
  if (!form.title) {
    const base = file.name.replace(/\.[^.]+$/, '').replace(/[_-]+/g, ' ').trim()
    form.title = base.charAt(0).toUpperCase() + base.slice(1)
  }
}

async function onSubmit() {
  error.value = ''
  result.value = null
  const file = fileInput.value?.files?.[0]
  if (!file) {
    error.value = 'Elige un archivo de audio.'
    return
  }
  if (file.size > 50 * 1024 * 1024) {
    error.value = 'El archivo supera el máximo de 50 MB.'
    return
  }
  const data = new FormData()
  data.append('file', file)
  data.append('title', form.title.trim())
  data.append('artist', form.artist.trim())
  if (form.album?.trim()) data.append('album', form.album.trim())
  if (form.track_number) data.append('track_number', String(form.track_number))

  uploading.value = true
  progress.value = 0
  try {
    result.value = await uploadWithProgress(data, { onProgress: (value) => { progress.value = value } })
    form.title = ''
    form.artist = ''
    form.album = ''
    form.track_number = null
    if (fileInput.value) fileInput.value.value = ''
  } catch (err) {
    if (err instanceof ApiError && err.status === 413) {
      error.value = 'El archivo o tu cuota superan el límite (50 MB / 5 GB).'
    } else if (err instanceof ApiError) {
      error.value = err.message
    } else {
      error.value = 'No se pudo subir el archivo. Revisa tu conexión e inténtalo de nuevo.'
    }
  } finally {
    uploading.value = false
  }
}
</script>
