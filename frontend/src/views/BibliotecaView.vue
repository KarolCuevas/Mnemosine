<template>
  <main class="min-h-screen bg-slate-950 text-slate-100">
    <header class="border-b border-slate-800">
      <div class="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
        <span class="text-lg font-semibold tracking-wide text-teal-300">Mnemosine</span>
        <div class="flex items-center gap-4 text-sm">
          <span class="text-slate-400">Hola, <span class="text-slate-100">{{ auth.user?.display_name || auth.user?.username }}</span></span>
          <button type="button" class="rounded-lg border border-slate-700 px-3 py-1.5 text-slate-300 transition hover:border-teal-400 hover:text-teal-300" @click="onLogout">
            Cerrar sesión
          </button>
        </div>
      </div>
    </header>

    <section class="mx-auto max-w-5xl px-6 py-16 text-center">
      <p class="text-xs font-medium uppercase tracking-[0.3em] text-teal-300">Mi biblioteca</p>
      <h1 class="mt-4 text-4xl font-semibold">Aún no hay canciones</h1>
      <p class="mx-auto mt-4 max-w-md text-slate-400">
        Tu biblioteca es privada por defecto. La carga de música, la búsqueda y el reproductor
        llegarán con la Fase 3 (primer recorrido funcional).
      </p>
      <button type="button" disabled class="mt-8 cursor-not-allowed rounded-lg bg-slate-800 px-5 py-2.5 font-medium text-slate-500">
        Cargar música — próximamente
      </button>
    </section>
  </main>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()

async function onLogout() {
  await auth.logout()
  router.push('/acceso')
}
</script>
