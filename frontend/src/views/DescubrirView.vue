<template>
  <main class="min-h-screen bg-slate-950 pb-24 text-slate-100">
    <header class="border-b border-slate-800">
      <div class="mx-auto flex max-w-5xl items-center justify-between gap-4 px-6 py-4">
        <span class="text-lg font-semibold tracking-wide text-teal-300">Mnemosine</span>
        <nav aria-label="Principal" class="flex items-center gap-3 text-sm">
          <RouterLink :to="{ name: 'biblioteca' }" class="rounded-lg px-3 py-1.5 text-slate-300 transition hover:text-teal-300">Mi biblioteca</RouterLink>
          <RouterLink :to="{ name: 'listas' }" class="rounded-lg px-3 py-1.5 text-slate-300 transition hover:text-teal-300">Listas</RouterLink>
          <RouterLink :to="{ name: 'cargar' }" class="rounded-lg bg-teal-500 px-3 py-1.5 font-medium text-slate-950 transition hover:bg-teal-400">Cargar</RouterLink>
        </nav>
      </div>
    </header>

    <section class="mx-auto max-w-5xl px-6 py-6">
      <p class="text-xs font-medium uppercase tracking-[0.3em] text-teal-300">Descubrir</p>
      <h1 class="mt-1 text-3xl font-semibold">Bibliotecas públicas</h1>
      <p class="mt-2 max-w-xl text-slate-400">Cuentas con música publicada para las cuentas autenticadas del sistema. Nada de esto implica acceso público anónimo.</p>

      <p v-if="loading" class="mt-10 text-center text-slate-400">Cargando…</p>
      <p v-else-if="error" role="alert" class="mt-10 rounded-lg border border-red-900 bg-red-950/60 px-4 py-3 text-center text-red-300">{{ error }}</p>
      <p v-else-if="accounts.length === 0" class="mt-10 text-center text-slate-400">Nadie ha publicado música todavía.</p>

      <ul v-else class="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <li v-for="account in accounts" :key="account.username">
          <RouterLink :to="{ name: 'coleccion', params: { username: account.username } }"
            class="block rounded-xl border border-slate-800 bg-slate-900/50 p-4 transition hover:border-teal-700 hover:bg-slate-900">
            <span class="block text-lg font-medium text-slate-100">{{ account.display_name || account.username }}</span>
            <span class="mt-0.5 block text-xs text-slate-500">@{{ account.username }}</span>
            <span class="mt-2 block text-sm text-teal-300">{{ account.public_copies }} {{ account.public_copies === 1 ? 'canción pública' : 'canciones públicas' }}</span>
          </RouterLink>
        </li>
      </ul>
    </section>
  </main>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../services/api'

const accounts = ref([])
const loading = ref(true)
const error = ref('')

onMounted(async () => {
  try {
    accounts.value = (await api.discovery()).accounts
  } catch {
    error.value = 'No se pudo cargar Descubrir. Inténtalo de nuevo.'
  } finally {
    loading.value = false
  }
})
</script>
