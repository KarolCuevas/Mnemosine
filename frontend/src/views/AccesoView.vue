<template>
  <main class="flex min-h-screen items-center justify-center bg-slate-950 px-4 py-10 text-slate-100">
    <div class="w-full max-w-md">
      <p class="text-center text-sm font-medium uppercase tracking-[0.3em] text-teal-300">Mnemosine</p>
      <h1 class="mt-3 text-center text-3xl font-semibold">Tu música, tuya</h1>
      <p class="mt-2 text-center text-sm text-slate-400">Biblioteca privada con cuentas e invitaciones.</p>

      <div class="mt-8 rounded-2xl border border-slate-800 bg-slate-900/60 p-6 shadow-xl">
        <div class="flex rounded-lg bg-slate-800 p-1 text-sm font-medium">
          <button
            type="button"
            class="flex-1 rounded-md px-3 py-2 transition"
            :class="mode === 'login' ? 'bg-teal-500 text-slate-950' : 'text-slate-300'"
            @click="mode = 'login'"
          >
            Iniciar sesión
          </button>
          <button
            type="button"
            class="flex-1 rounded-md px-3 py-2 transition"
            :class="mode === 'register' ? 'bg-teal-500 text-slate-950' : 'text-slate-300'"
            @click="mode = 'register'"
          >
            Crear cuenta
          </button>
        </div>

        <form class="mt-6 space-y-4" @submit.prevent="onSubmit">
          <template v-if="mode === 'register'">
            <div>
              <label for="username" class="mb-1 block text-xs font-medium text-slate-400">Usuario</label>
              <input id="username" v-model="form.username" required autocomplete="username" minlength="3" maxlength="64"
                class="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 outline-none focus:border-teal-400" />
            </div>
            <div>
              <label for="email" class="mb-1 block text-xs font-medium text-slate-400">Correo</label>
              <input id="email" v-model="form.email" required type="email" autocomplete="email" maxlength="255"
                class="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 outline-none focus:border-teal-400" />
            </div>
            <div>
              <label for="invitation" class="mb-1 block text-xs font-medium text-slate-400">Código de invitación</label>
              <input id="invitation" v-model="form.invitation_code" required minlength="8"
                class="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 outline-none focus:border-teal-400"
                placeholder="Te lo ha dado el administrador" />
            </div>
          </template>

          <template v-else>
            <div>
              <label for="identity" class="mb-1 block text-xs font-medium text-slate-400">Usuario o correo</label>
              <input id="identity" v-model="form.identity" required autocomplete="username" maxlength="255"
                class="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 outline-none focus:border-teal-400" />
            </div>
          </template>

          <div>
            <label for="password" class="mb-1 block text-xs font-medium text-slate-400">Contraseña</label>
            <input id="password" v-model="form.password" required type="password"
              :autocomplete="mode === 'login' ? 'current-password' : 'new-password'"
              :minlength="mode === 'register' ? 12 : 1"
              class="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 outline-none focus:border-teal-400" />
            <p v-if="mode === 'register'" class="mt-1 text-[11px] text-slate-500">Mínimo 12 caracteres.</p>
          </div>

          <p v-if="error" role="alert" class="rounded-lg border border-red-900 bg-red-950/60 px-3 py-2 text-sm text-red-300">{{ error }}</p>

          <button type="submit" :disabled="auth.loading"
            class="w-full rounded-lg bg-teal-500 px-4 py-2.5 font-semibold text-slate-950 transition hover:bg-teal-400 disabled:opacity-60">
            {{ auth.loading ? 'Un momento…' : (mode === 'login' ? 'Entrar' : 'Crear cuenta e iniciar sesión') }}
          </button>
        </form>
      </div>
    </div>
  </main>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { ApiError } from '../services/api'

const mode = ref('login')
const error = ref('')
const form = reactive({
  username: '',
  email: '',
  invitation_code: '',
  identity: '',
  password: '',
  display_name: ''
})
const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

async function onSubmit() {
  error.value = ''
  try {
    if (mode.value === 'login') {
      await auth.login(form.identity, form.password)
    } else {
      await auth.register({
        username: form.username,
        email: form.email,
        password: form.password,
        display_name: form.display_name || null,
        invitation_code: form.invitation_code
      })
    }
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/biblioteca'
    router.push(redirect)
  } catch (err) {
    if (err instanceof ApiError) {
      if (err.status === 429) error.value = 'Demasiados intentos. Espera unos minutos.'
      else error.value = err.message
    } else {
      error.value = 'No se pudo conectar con el servidor. ¿Está el backend en marcha?'
    }
  }
}
</script>
