<template>
  <div class="page"><section class="page-section">
    <p class="eyebrow">HAZ CRECER TU COLECCIÓN</p>
    <h1 class="mt-2 text-3xl font-semibold">Nueva canción</h1>
    <p class="mt-3 text-slate-400">Sube tu audio con sus etiquetas y su portada.</p>
    <div class="upload-layout">
      <div class="min-w-0">
        <form action="/api/tracks/upload" method="post" enctype="multipart/form-data" class="form-panel space-y-6" @submit.prevent="onSubmit">
          <div class="upload-file">
            <AppIcon name="upload" />
            <label for="archivo" class="font-medium">Archivo de audio <span class="text-xs">(obligatorio)</span></label>
            <p id="audio-help">MP3, M4A, FLAC, OGG o WAV · hasta 50 MB</p>
            <input id="archivo" ref="fileInput" name="file" type="file" required :disabled="uploading" aria-describedby="audio-help"
              accept=".mp3,.m4a,.flac,.ogg,.wav,audio/mpeg,audio/flac,audio/ogg,audio/wav,audio/x-wav,audio/mp4,audio/x-m4a" @change="onFileChange" />
          </div>
          <p id="metadata-help" class="metadata-help">Leeremos las etiquetas y la portada al guardar. Puedes escribir correcciones abajo: los campos vacíos se completan con los datos del archivo.</p>
          <fieldset class="upload-metadata" :disabled="uploading" aria-describedby="metadata-help">
            <legend>Etiquetas (opcional)</legend>
            <div><label for="titulo" class="field-label">Título</label><input id="titulo" v-model="form.title" name="title" maxlength="512" class="text-input" placeholder="Usar el título del archivo" /></div>
            <div><label for="artista" class="field-label">Artista</label><input id="artista" v-model="form.artist" name="artist" maxlength="255" class="text-input" placeholder="Usar el artista del archivo" /></div>
            <div><label for="album" class="field-label">Álbum (opcional)</label><input id="album" v-model="form.album" name="album" maxlength="512" class="text-input" placeholder="Usar el álbum del archivo" /></div>
            <div><label for="pista" class="field-label">Pista (opcional)</label><input id="pista" v-model.number="form.track_number" name="track_number" type="number" min="1" max="1000" class="text-input" /></div>
            <details class="upload-extra">
              <summary>Más etiquetas</summary>
              <div class="fields">
                <div><label for="album-artist" class="field-label">Artista del álbum</label><input id="album-artist" v-model="form.album_artist" name="album_artist" maxlength="255" class="text-input" /></div>
                <div><label for="genre" class="field-label">Género</label><input id="genre" v-model="form.genre" name="genre" maxlength="255" class="text-input" /></div>
                <div><label for="disc-number" class="field-label">Disco</label><input id="disc-number" v-model.number="form.disc_number" name="disc_number" type="number" min="1" max="100" class="text-input" /></div>
                <div><label for="release-year" class="field-label">Año</label><input id="release-year" v-model.number="form.release_year" name="release_year" type="number" min="1000" max="9999" class="text-input" /></div>
              </div>
            </details>
          </fieldset>
          <p v-if="error" ref="errorPanel" tabindex="-1" role="alert" class="rounded-lg border border-red-900 bg-red-950/60 p-3 text-sm text-red-300">{{ error }}</p>
          <div v-if="uploading" class="space-y-2">
            <label class="field-label" for="progreso">{{ progress === 100 ? 'Leyendo etiquetas y preparando la portada…' : `Subiendo… ${progress}%` }}</label>
            <progress id="progreso" class="progress-teal h-2 w-full" :value="progress" max="100" aria-label="Progreso de la subida" />
          </div>
          <button type="submit" :disabled="uploading" class="button button-primary w-full"><AppIcon name="lock" />{{ uploading ? 'Guardando…' : 'Guardar como privada' }}</button>
        </form>
        <div v-if="result" ref="resultPanel" tabindex="-1" class="upload-result mt-6 rounded-xl border border-teal-800 bg-teal-950/40 p-5" role="status">
          <TrackArtwork :src="result.cover_url" :seed="result.album || result.title" />
          <div class="min-w-0">
            <p class="font-medium text-teal-300">“{{ result.title }}” subida correctamente.</p>
            <p class="mt-2 text-sm">{{ result.artist }}<span v-if="result.album"> · {{ result.album }}</span></p>
            <p class="mt-2 text-sm text-slate-400">{{ formatDuration(result.duration_seconds) }} · {{ formatBytes(result.size_bytes) }} · privada</p>
            <p v-if="!result.cover_url && !result.warnings?.length" class="mt-2 text-xs text-slate-400">El archivo no contiene una portada incrustada.</p>
            <p v-for="warning in result.warnings" :key="warning" class="mt-2 text-sm text-amber-200">{{ warning }}</p>
            <div class="mt-4 flex flex-wrap gap-3"><RouterLink :to="{ name: 'detalle', params: { id: result.track_id } }" class="button button-primary">Ver detalle</RouterLink><RouterLink to="/biblioteca" class="button button-secondary">Volver a la biblioteca</RouterLink></div>
          </div>
        </div>
      </div>
      <aside class="upload-tips">
        <AppIcon name="music" /><h2>Su historia viene con ella.</h2>
        <p>Importamos título, artistas, álbum, pista, disco, año y género cuando estén incluidos en el audio. La portada aparecerá en tu biblioteca y en el reproductor.</p>
        <hr /><h3 class="font-medium">¿Faltan etiquetas?</h3>
        <p>Puedes completarlas en el formulario. Si no hay título, usaremos el nombre del archivo; si no hay artista, aparecerá «Artista desconocido».</p>
        <p>Tu canción se guarda como privada. Dispones de hasta 5 GB para tu colección, con un máximo de 50 MB por archivo.</p>
      </aside>
    </div>
  </section></div>
</template>

<script setup>
import { nextTick, reactive, ref } from 'vue'
import AppIcon from '../components/AppIcon.vue'
import TrackArtwork from '../components/TrackArtwork.vue'
import { uploadWithProgress, ApiError } from '../services/api'
import { formatBytes, formatDuration } from '../services/format'

const fileInput = ref(null), uploading = ref(false), progress = ref(0)
const error = ref(''), result = ref(null), errorPanel = ref(null), resultPanel = ref(null)
const emptyForm = () => ({ title: '', artist: '', album: '', track_number: null, disc_number: null, release_year: null, album_artist: '', genre: '' })
const form = reactive(emptyForm())

function onFileChange() {
  error.value = ''
  result.value = null
}

async function showError(message) {
  error.value = message
  await nextTick()
  errorPanel.value?.focus()
}

async function onSubmit() {
  if (uploading.value) return
  error.value = ''
  result.value = null
  const file = fileInput.value?.files?.[0]
  if (!file) return showError('Elige un archivo de audio.')
  if (file.size > 50 * 1024 * 1024) return showError('El archivo supera el máximo de 50 MB.')
  const data = new FormData()
  data.append('file', file)
  for (const [key, value] of Object.entries(form)) {
    const text = value == null ? '' : String(value).trim()
    if (text) data.append(key, text)
  }
  uploading.value = true
  progress.value = 0
  try {
    result.value = await uploadWithProgress(data, { onProgress: value => { progress.value = value } })
    Object.assign(form, emptyForm())
    if (fileInput.value) fileInput.value.value = ''
    await nextTick()
    resultPanel.value?.focus()
  } catch (err) {
    await showError(err instanceof ApiError && err.status === 413
      ? 'El archivo o tu cuota superan el límite (50 MB / 5 GB).'
      : err instanceof ApiError ? err.message : 'No se pudo subir el archivo. Revisa tu conexión e inténtalo de nuevo.')
  } finally {
    uploading.value = false
  }
}
</script>
