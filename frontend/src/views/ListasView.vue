<template>
  <main class="min-h-screen bg-slate-950 pb-24 text-slate-100">
    <header class="border-b border-slate-800">
      <div class="mx-auto flex max-w-5xl items-center justify-between gap-4 px-6 py-4">
        <span class="text-lg font-semibold tracking-wide text-teal-300">Mnemosine</span>
        <nav aria-label="Principal" class="flex items-center gap-3 text-sm">
          <RouterLink :to="{ name: 'biblioteca' }" class="rounded-lg px-3 py-1.5 text-slate-300 transition hover:text-teal-300">Mi biblioteca</RouterLink>
          <RouterLink :to="{ name: 'descubrir' }" class="rounded-lg px-3 py-1.5 text-slate-300 transition hover:text-teal-300">Descubrir</RouterLink>
          <RouterLink :to="{ name: 'cargar' }" class="rounded-lg bg-teal-500 px-3 py-1.5 font-medium text-slate-950 transition hover:bg-teal-400">Cargar</RouterLink>
        </nav>
      </div>
    </header>

    <section class="mx-auto max-w-5xl px-6 py-6">
      <div class="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p class="text-xs font-medium uppercase tracking-[0.3em] text-teal-300">Listas</p>
          <h1 class="mt-1 text-3xl font-semibold">Tus listas</h1>
        </div>
      </div>

      <form class="mt-5 flex flex-wrap items-center gap-2" @submit.prevent="createList">
        <label class="sr-only" for="new-list">Nombre de la nueva lista</label>
        <input id="new-list" v-model="newName" maxlength="255" required placeholder="Nombre de la nueva lista"
          class="w-64 rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 outline-none focus:border-teal-400" />
        <button type="submit" class="rounded-lg bg-teal-500 px-4 py-2 font-medium text-slate-950 transition hover:bg-teal-400 disabled:opacity-60" :disabled="creating">Crear lista</button>
      </form>

      <p v-if="loading" class="mt-10 text-center text-slate-400">Cargando…</p>
      <p v-else-if="error" role="alert" class="mt-10 rounded-lg border border-red-900 bg-red-950/60 px-4 py-3 text-center text-red-300">{{ error }}</p>
      <p v-else-if="playlists.length === 0" class="mt-10 text-center text-slate-400">Aún no tienes listas. Crea la primera arriba.</p>

      <ul v-else class="mt-5 grid gap-3 sm:grid-cols-2">
        <li v-for="playlist in playlists" :key="playlist.playlist_id">
          <RouterLink :to="{ name: 'lista', params: { id: playlist.playlist_id } }"
            class="block rounded-xl border border-slate-800 bg-slate-900/50 p-4 transition hover:border-teal-700 hover:bg-slate-900">
            <span class="block text-lg font-medium text-slate-100">{{ playlist.name }}</span>
            <span v-if="playlist.description" class="mt-1 block text-sm text-slate-400">{{ playlist.description }}</span>
            <span class="mt-2 block text-xs text-teal-300">{{ playlist.item_count }} {{ playlist.item_count === 1 ? 'canción' : 'canciones' }}</span>
          </RouterLink>
        </li>
      </ul>
    </section>
  </main>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../services/api'

const router = useRouter()
const playlists = ref([])
const newName = ref('')
const creating = ref(false)
const loading = ref(true)
const error = ref('')

async function load() {
  loading.value = true
  try {
    playlists.value = await api.playlists()
  } catch {
    error.value = 'No se pudieron cargar las listas.'
  } finally {
    loading.value = false
  }
}

async function createList() {
  creating.value = true
  try {
    const created = await api.createPlaylist({ name: newName.value.trim() })
    newName.value = ''
    router.push({ name: 'lista', params: { id: created.playlist_id } })
  } catch {
    error.value = 'No se pudo crear la lista.'
  } finally {
    creating.value = false
  }
}

onMounted(load)
</script>
