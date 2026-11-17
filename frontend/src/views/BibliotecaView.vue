<template>
  <main class="min-h-screen bg-slate-950 pb-24 text-slate-100">
    <header class="border-b border-slate-800">
      <div class="mx-auto flex max-w-5xl items-center justify-between gap-4 px-6 py-4">
        <span class="text-lg font-semibold tracking-wide text-teal-300">Mnemosine</span>
        <nav aria-label="Principal" class="flex items-center gap-3">
          <RouterLink :to="{ name: 'biblioteca' }" class="rounded-lg px-3 py-1.5 text-sm text-slate-300 transition hover:text-teal-300">Mi biblioteca</RouterLink>
          <RouterLink :to="{ name: 'descubrir' }" class="rounded-lg px-3 py-1.5 text-sm text-slate-300 transition hover:text-teal-300">Descubrir</RouterLink>
          <RouterLink :to="{ name: 'listas' }" class="rounded-lg px-3 py-1.5 text-sm text-slate-300 transition hover:text-teal-300">Listas</RouterLink>
          <RouterLink v-if="auth.user?.role === 'ADMIN'" :to="{ name: 'admin' }" class="rounded-lg border border-teal-900 px-3 py-1.5 text-sm text-teal-300 transition hover:border-teal-600">Administración</RouterLink>
          <RouterLink :to="{ name: 'cargar' }" class="rounded-lg bg-teal-500 px-3 py-1.5 text-sm font-medium text-slate-950 transition hover:bg-teal-400">Cargar</RouterLink>
          <span class="hidden text-sm text-slate-500 sm:inline">{{ auth.user?.display_name || auth.user?.username }}</span>
          <button type="button" class="rounded-lg border border-slate-700 px-3 py-1.5 text-sm text-slate-300 transition hover:border-teal-400 hover:text-teal-300" @click="onLogout">
            Cerrar sesión
          </button>
        </nav>
      </div>
    </header>

    <section class="mx-auto max-w-5xl px-6 py-6">
      <div class="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p class="text-xs font-medium uppercase tracking-[0.3em] text-teal-300">Mi biblioteca</p>
          <h1 class="mt-1 text-3xl font-semibold">Tus canciones</h1>
        </div>
        <p class="text-sm text-slate-400">{{ total }} {{ total === 1 ? 'canción' : 'canciones' }}</p>
      </div>

      <form class="mt-5" role="search" @submit.prevent>
        <label class="mb-1 block text-xs font-medium text-slate-400" for="buscar">Buscar por título, artista o álbum</label>
        <div class="flex gap-2">
          <input id="buscar" v-model="query" type="search" autocomplete="off" maxlength="200"
            placeholder="p. ej. Kältmare" class="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 outline-none focus:border-teal-400" />
          <button v-if="query" type="button" class="rounded-lg border border-slate-700 px-3 py-2 text-sm text-slate-300 transition hover:border-teal-400 hover:text-teal-300" @click="clearSearch">Limpiar</button>
        </div>
        <p aria-live="polite" class="mt-1 h-4 text-xs text-slate-500">{{ statusMessage }}</p>
      </form>

      <p v-if="loading" class="mt-10 text-center text-slate-400">Cargando tu biblioteca…</p>
      <p v-else-if="error" role="alert" class="mt-10 rounded-lg border border-red-900 bg-red-950/60 px-4 py-3 text-center text-red-300">{{ error }}</p>

      <div v-else-if="total === 0 && !query" class="mt-14 text-center">
        <svg viewBox="0 0 24 24" class="mx-auto h-14 w-14 text-slate-700" fill="currentColor" aria-hidden="true"><path d="M12 3v10.55A4 4 0 1 0 14 17V7h4V3h-6z"/></svg>
        <h2 class="mt-4 text-xl font-semibold text-slate-200">Aún no has cargado nada</h2>
        <p class="mx-auto mt-2 max-w-sm text-slate-400">Tu primera carga es privada por defecto. Solo tú podrás verla y reproducirla.</p>
        <RouterLink :to="{ name: 'cargar' }" class="mt-6 inline-block rounded-lg bg-teal-500 px-5 py-2.5 font-medium text-slate-950 transition hover:bg-teal-400">Cargar tu primera canción</RouterLink>
      </div>

      <p v-else-if="total === 0" class="mt-10 text-center text-slate-400">Nada por “{{ query }}”. <button type="button" class="text-teal-300 underline underline-offset-2 hover:text-teal-200" @click="clearSearch">Limpiar búsqueda</button></p>

      <ul v-else class="mt-4 divide-y divide-slate-800 rounded-xl border border-slate-800">
        <li v-for="(item, index) in items" :key="item.location_id"
          class="flex items-center gap-3 px-4 py-3 transition hover:bg-slate-900/60">
          <button type="button" class="rounded-full bg-slate-800 p-2 text-teal-300 transition hover:bg-teal-500 hover:text-slate-950 disabled:cursor-not-allowed disabled:opacity-40"
            :disabled="!item.available" :aria-label="`Reproducir ${item.title}`" @click="playFromList(index)">
            <svg viewBox="0 0 24 24" class="h-4 w-4" fill="currentColor" aria-hidden="true"><path d="M8 5v14l11-7z"/></svg>
          </button>
          <RouterLink :to="{ name: 'detalle', params: { id: item.track_id } }" class="min-w-0 flex-1">
            <span class="block truncate font-medium text-slate-100">{{ item.title }}
              <span v-if="!item.available" class="ml-2 rounded-full border border-amber-800 bg-amber-950 px-2 py-0.5 text-[10px] font-medium uppercase text-amber-400">No disponible</span>
            </span>
            <span class="block truncate text-xs text-slate-400">{{ item.artists }}<template v-if="item.album"> · {{ item.album }}</template></span>
          </RouterLink>
          <span class="text-xs tabular-nums text-slate-500">{{ formatDuration(item.duration_seconds) }}</span>
        </li>
      </ul>

      <nav v-if="total > pageSize" aria-label="Paginación de la biblioteca" class="mt-4 flex items-center justify-between">
        <button type="button" class="rounded-lg border border-slate-700 px-3 py-1.5 text-sm text-slate-300 transition hover:border-teal-400 hover:text-teal-300 disabled:opacity-40" :disabled="page <= 1" @click="goToPage(page - 1)">Anterior</button>
        <span class="text-sm text-slate-400">Página {{ page }} de {{ totalPages }}</span>
        <button type="button" class="rounded-lg border border-slate-700 px-3 py-1.5 text-sm text-slate-300 transition hover:border-teal-400 hover:text-teal-300 disabled:opacity-40" :disabled="page >= totalPages" @click="goToPage(page + 1)">Siguiente</button>
      </nav>

      <section v-if="sharedItems.length" aria-labelledby="compartidas-heading" class="mt-10">
        <h2 id="compartidas-heading" class="text-lg font-semibold text-slate-200">Compartidas contigo</h2>
        <p class="mt-1 text-xs text-slate-500">Copias que otras cuentas compartieron contigo. Los permisos pueden haber sido revocados: cada reproducción se comprueba en el servidor.</p>
        <ul class="mt-3 divide-y divide-slate-800 rounded-xl border border-slate-800">
          <li v-for="(item, index) in sharedItems" :key="item.location_id" class="flex items-center gap-3 px-4 py-3">
            <button type="button" class="rounded-full bg-slate-800 p-2 text-teal-300 transition hover:bg-teal-500 hover:text-slate-950 disabled:cursor-not-allowed disabled:opacity-40"
              :disabled="!item.can_stream" :aria-label="`Reproducir ${item.title}`" @click="playShared(index)">
              <svg viewBox="0 0 24 24" class="h-4 w-4" fill="currentColor" aria-hidden="true"><path d="M8 5v14l11-7z"/></svg>
            </button>
            <div class="min-w-0 flex-1">
              <RouterLink :to="{ name: 'detalle', params: { id: item.track_id } }" class="block truncate text-sm font-medium text-slate-100 hover:text-teal-300">{{ item.title }}</RouterLink>
              <span class="block truncate text-xs text-slate-500">{{ item.artists }} · compartida por {{ item.owner_username }}</span>
            </div>
            <span v-if="item.can_download" class="text-xs text-slate-500">descarga permitida</span>
          </li>
        </ul>
      </section>
    </section>
  </main>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { usePlayerStore } from '../stores/player'
import { api } from '../services/api'
import { formatDuration } from '../services/format'

const auth = useAuthStore()
const player = usePlayerStore()
const router = useRouter()

const query = ref('')
const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 24
const loading = ref(false)
const error = ref('')
const sharedItems = ref([])

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))
const statusMessage = computed(() => (query.value && !loading.value ? `${total.value} ${total.value === 1 ? 'resultado' : 'resultados'}` : ''))

let searchTimer = null
watch(query, () => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    page.value = 1
    load()
  }, 300)
})

async function load() {
  loading.value = true
  error.value = ''
  try {
    const data = await api.library({ q: query.value.trim(), page: page.value, pageSize })
    items.value = data.items
    total.value = data.total
  } catch (err) {
    error.value = 'No se pudo cargar la biblioteca. Revisa tu conexión e inténtalo de nuevo.'
  } finally {
    loading.value = false
  }
}

function clearSearch() {
  query.value = ''
}

function playFromList(index) {
  player.setQueue(items.value, index)
}

function playShared(index) {
  const playable = sharedItems.value.filter((item) => item.can_stream)
  const target = sharedItems.value[index]
  const playableIndex = playable.indexOf(target)
  if (playableIndex === -1) return
  player.setQueue(playable.map((item) => ({ ...item, available: true })), playableIndex)
}

function goToPage(target) {
  page.value = target
  load()
}

async function onLogout() {
  await auth.logout()
  router.push('/acceso')
}

async function loadShared() {
  try {
    sharedItems.value = (await api.sharedWithMe()).items
  } catch {
    sharedItems.value = []
  }
}

onMounted(() => {
  load()
  loadShared()
})
</script>
