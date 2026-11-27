<template>
  <div class="page referencias-page">
    <section class="page-section">
      <h1 class="text-3xl font-semibold">Referencias musicales</h1>
      <p class="mt-3 max-w-2xl text-slate-300">Busca grabaciones y guarda sus datos en tu colección privada. Las referencias no incluyen audio ni cambian los archivos de tu biblioteca.</p>
      <p class="mt-2 text-sm text-slate-400">Metadatos de MusicBrainz · núcleo CC0 · no necesitas conectar una cuenta.</p>

      <search>
        <form action="/referencias" method="get" class="mt-7 rounded-xl border border-slate-700 bg-slate-900 p-5" @submit.prevent="submit">
          <fieldset>
            <legend class="font-medium">Dónde buscar</legend>
            <div class="reference-modes mt-3 flex flex-wrap gap-3">
              <label v-for="option in options" :key="option.value" class="flex min-h-12 items-center gap-2" :for="`mode-${option.value}`">
                <input :id="`mode-${option.value}`" v-model="mode" type="radio" name="mode" :value="option.value" />
                {{ option.label }}
              </label>
            </div>
          </fieldset>
          <div v-if="mode !== 'saved'" class="mt-4 grid gap-4 sm:grid-cols-2">
            <div>
              <label for="reference-title" class="mb-1 block">Título <span v-if="mode === 'remote'">(obligatorio)</span></label>
              <input id="reference-title" v-model="title" name="title" type="search" maxlength="200" :required="mode === 'remote'" enterkeyhint="search" autocorrect="off" autocapitalize="none" :spellcheck="false" class="w-full rounded-lg border border-slate-500 bg-slate-950 px-3 py-3" />
            </div>
            <div>
              <label for="reference-artist" class="mb-1 block">Artista (opcional)</label>
              <input id="reference-artist" v-model="artist" name="artist" type="search" maxlength="200" enterkeyhint="search" autocorrect="off" autocapitalize="none" :spellcheck="false" class="w-full rounded-lg border border-slate-500 bg-slate-950 px-3 py-3" />
            </div>
          </div>
          <p v-if="mode === 'remote' && !remoteEnabled" class="mt-3 text-amber-200">Las consultas a MusicBrainz están deshabilitadas. Puedes consultar el índice local y tus referencias guardadas.</p>
          <button type="submit" :disabled="busy" class="mt-5 rounded-lg bg-teal-400 px-5 py-3 font-semibold text-slate-950 disabled:opacity-50">{{ mode === 'saved' ? 'Ver mi colección' : 'Buscar' }}</button>
        </form>
      </search>

      <p role="status" class="mt-4 min-h-6 text-sm text-teal-200">{{ message }}</p>
      <p v-if="error" role="alert" class="mt-2 rounded-lg border border-red-800 bg-red-950 p-4 text-red-200">{{ error }}</p>
      <progress v-if="busy" aria-label="Consultando referencias" class="progress-teal mt-3 h-2 w-full" />

      <section :aria-busy="busy" class="mt-5">
        <h2 ref="resultsHeading" tabindex="-1" class="text-xl font-semibold">{{ appliedMode === 'saved' ? 'Mi colección privada' : appliedMode === 'remote' ? 'Resultados de MusicBrainz' : 'Índice local' }}</h2>
        <p class="mt-1 text-sm text-slate-400">{{ total }} {{ total === 1 ? 'resultado' : 'resultados' }}<template v-if="origin === 'cache'"> · consulta recuperada de caché</template></p>
        <p v-if="!busy && !items.length" class="mt-6 text-slate-300">{{ appliedMode === 'local' ? 'No hay coincidencias en el índice. Selecciona MusicBrainz y pulsa Buscar para ampliar la consulta.' : appliedMode === 'saved' ? 'Todavía no has guardado referencias.' : 'No se encontraron grabaciones para esta búsqueda.' }}</p>
        <ul v-else role="list" class="reference-results mt-4">
          <li v-for="item in items" :key="`${item.provider}:${item.provider_id}`" class="rounded-xl border border-slate-700 bg-slate-900/50 p-5">
            <h3 class="break-words text-lg font-semibold">{{ item.title }}</h3>
            <p class="mt-1 break-words text-slate-300">{{ artistCredit(item) || 'Artista no informado' }}</p>
            <p v-if="item.disambiguation" class="mt-1 text-amber-200">{{ item.disambiguation }}</p>
            <p class="mt-2 text-sm text-slate-400">{{ duration(item.duration_ms) }} · consultado {{ date(item.fetched_at) }}</p>
            <p class="mt-1 break-all text-xs text-slate-400">MBID: {{ item.provider_id }}</p>
            <p v-if="item.releases.length" class="mt-2 break-words text-sm text-slate-300">Ediciones conocidas: {{ item.releases.map(r => r.title + (r.date ? ` (${r.date})` : '')).join(' · ') }}</p>
            <p v-if="item.isrcs.length" class="mt-2 text-sm text-slate-400">ISRC: {{ item.isrcs.join(', ') }}</p>
            <div class="mt-4 flex flex-wrap items-center gap-3">
              <a :href="item.original_url" target="_blank" rel="noopener noreferrer" :aria-label="`Ver ${item.title} en MusicBrainz (nueva pestaña)`" class="rounded-lg border border-slate-600 px-3 py-3 text-teal-200">Ver en MusicBrainz ↗</a>
              <button v-if="appliedMode !== 'saved'" type="button" :disabled="busy || working !== ''" :aria-label="`Guardar referencia: ${item.title}`" class="rounded-lg bg-teal-400 px-4 py-3 font-medium text-slate-950 disabled:opacity-50" @click="save(item)">Guardar referencia</button>
              <button v-else type="button" :disabled="busy || working !== ''" :aria-label="`Quitar de mi colección: ${item.title}`" class="rounded-lg border border-slate-500 px-4 py-3 disabled:opacity-50" @click="remove(item)">Quitar de mi colección</button>
              <button type="button" :disabled="busy || working !== ''" :aria-label="`Actualizar datos: ${item.title}`" class="rounded-lg border border-slate-500 px-4 py-3 disabled:opacity-50" @click="refresh(item)">Actualizar datos</button>
            </div>
          </li>
        </ul>
        <nav v-if="hasPrevious || hasNext" aria-label="Páginas de referencias" class="mt-5 flex items-center justify-between gap-4">
          <button type="button" :disabled="busy || !hasPrevious" class="rounded-lg border border-slate-500 px-4 py-3 disabled:opacity-50" @click="paginate(-1)">Anterior</button>
          <span>Página {{ page }}</span>
          <button type="button" :disabled="busy || !hasNext" class="rounded-lg border border-slate-500 px-4 py-3 disabled:opacity-50" @click="paginate(1)">Siguiente</button>
        </nav>
      </section>
    </section>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import { api } from '../services/api'

const options = [{ value: 'local', label: 'Índice local' }, { value: 'remote', label: 'MusicBrainz' }, { value: 'saved', label: 'Mi colección privada' }]
const mode = ref('local'), appliedMode = ref('local'), title = ref(''), artist = ref('')
const items = ref([]), total = ref(0), page = ref(1), origin = ref('local')
const busy = ref(false), working = ref(''), error = ref(''), message = ref(''), remoteEnabled = ref(false)
const resultsHeading = ref(null)
let appliedQuery = { title: '', artist: '' }
let cursors = [null]
const nextCursor = ref(null)
const hasPrevious = computed(() => page.value > 1)
const hasNext = computed(() => appliedMode.value === 'remote' ? Boolean(nextCursor.value) : page.value * 20 < total.value)
const artistCredit = (item) => item.artists.map(a => a.credit + a.join_phrase).join('')
const duration = (ms) => ms == null ? 'Duración no informada' : `${Math.floor(ms / 60000)}:${String(Math.floor(ms / 1000) % 60).padStart(2, '0')}`
const date = (value) => new Intl.DateTimeFormat('es', { dateStyle: 'medium' }).format(new Date(value))

async function load(targetPage = page.value, focus = false) {
  if (busy.value) return
  busy.value = true
  error.value = ''
  message.value = ''
  try {
    const data = appliedMode.value === 'saved' ? await api.externalReferences(targetPage)
      : appliedMode.value === 'remote' ? await api.externalSearch({ ...appliedQuery, cursor: cursors[targetPage - 1] })
        : await api.catalogSearch({ ...appliedQuery, page: targetPage })
    items.value = data.items
    total.value = data.total
    page.value = targetPage
    nextCursor.value = data.next_cursor || null
    origin.value = data.origin || 'private'
    message.value = `${data.total} ${data.total === 1 ? 'resultado' : 'resultados'}. Página ${targetPage}.`
    if (focus) { await nextTick(); resultsHeading.value?.focus() }
  } catch (err) {
    error.value = err.message || 'No se pudo completar la consulta.'
  } finally { busy.value = false }
}

async function submit() {
  if (busy.value || working.value) return
  appliedMode.value = mode.value
  appliedQuery = { title: title.value.trim(), artist: artist.value.trim() }
  cursors = [null]
  items.value = []
  total.value = 0
  nextCursor.value = null
  page.value = 1
  await load(1, true)
}

function paginate(direction) {
  if (direction > 0 && appliedMode.value === 'remote') cursors[page.value] = nextCursor.value
  load(page.value + direction, true)
}

async function mutate(item, action) {
  if (working.value || busy.value) return
  working.value = item.provider_id
  error.value = ''
  message.value = ''
  try { await action() } catch (err) { error.value = err.message || 'No se pudo completar la acción.' }
  finally { working.value = '' }
}

const save = (item) => mutate(item, async () => {
  await api.saveReference(item)
  message.value = `“${item.title}” guardada en tu colección privada.`
})
const remove = (item) => mutate(item, async () => {
  await api.deleteReference(item.reference_id)
  await load(items.value.length === 1 && page.value > 1 ? page.value - 1 : page.value, true)
  message.value = 'Referencia retirada de tu colección. El catálogo y tus archivos se conservan.'
})
const refresh = (item) => mutate(item, async () => {
  const updated = await api.refreshReference(item)
  items.value = items.value.map(row => row.provider_id === item.provider_id ? { ...row, ...updated } : row)
  message.value = `Datos de “${updated.title}” actualizados.`
})

onMounted(async () => {
  await load()
  try { remoteEnabled.value = (await api.integrationProviders()).items.some(p => p.code === 'musicbrainz' && p.enabled) }
  catch { remoteEnabled.value = false }
})
</script>

<style scoped>
.references :where(button, input, a):focus-visible { outline: 3px solid #5eead4; outline-offset: 3px; }
.references button, .references input:not([type="radio"]), .references nav a { min-block-size: 3rem; }
.references input[type="radio"] { accent-color: #2dd4bf; }
</style>
