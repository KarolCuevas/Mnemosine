<template>
  <main class="auth-layout">
    <section class="auth-story" aria-labelledby="welcome-title">
      <div class="brand"><span class="brand-mark"><AppIcon name="music" /></span><span>mnemosine<span class="brand-dot">.</span></span></div>
      <div>
        <h1 id="welcome-title">Tu música, tuya</h1>
        <p>Hay canciones que son parte de ti. Dales un lugar donde quedarse.</p>
        <div class="auth-record" aria-hidden="true"><div class="record-sleeve"><span>MNEMOSINE / VOL. 01</span><div class="sleeve-lines"></div><span>LA BANDA SONORA DE TU VIDA</span></div><div class="vinyl"><div class="vinyl-label"><AppIcon name="music" /></div></div></div>
      </div>
      <p class="auth-story-footer"><AppIcon name="headphones" /> Guarda. Organiza. Vuelve a escuchar.</p>
    </section>
    <section class="auth-form-area" aria-labelledby="access-title">
      <div class="auth-form-card">
        <h2 id="access-title">{{ mode === 'login' ? 'Qué bueno tenerte aquí.' : 'Tu colección empieza hoy.' }}</h2>
        <p>{{ mode === 'login' ? 'Entra y sigue donde dejaste tu música.' : 'Usa tu invitación para crear un espacio propio.' }}</p>
        <div class="auth-mode" role="group" aria-label="Acceso a tu cuenta">
          <button type="button" :aria-pressed="mode === 'login'" @click="mode = 'login'; error = ''">Iniciar sesión</button>
          <button type="button" :aria-pressed="mode === 'register'" @click="mode = 'register'; error = ''">Crear cuenta</button>
        </div>
        <form @submit.prevent="onSubmit">
          <template v-if="mode === 'register'">
            <div><label for="username" class="field-label">Usuario</label><input id="username" v-model="form.username" required autocomplete="username" minlength="3" maxlength="64" class="text-input" /></div>
            <div><label for="email" class="field-label">Correo</label><input id="email" v-model="form.email" required type="email" autocomplete="email" maxlength="255" class="text-input" /></div>
            <div><label for="invitation" class="field-label">Código de invitación</label><input id="invitation" v-model="form.invitation_code" required minlength="8" class="text-input" placeholder="El código que te compartieron" /></div>
          </template>
          <div v-else><label for="identity" class="field-label">Usuario o correo</label><input id="identity" v-model="form.identity" required autocomplete="username" maxlength="255" class="text-input" placeholder="Tu usuario o correo electrónico" /></div>
          <div><label for="password" class="field-label">Contraseña</label><input id="password" v-model="form.password" required type="password" :autocomplete="mode === 'login' ? 'current-password' : 'new-password'" :minlength="mode === 'register' ? 12 : 1" :aria-describedby="mode === 'register' ? 'password-help' : undefined" class="text-input" /><p v-if="mode === 'register'" id="password-help" class="mt-2 text-xs text-slate-400">Mínimo 12 caracteres.</p></div>
          <p v-if="error" role="alert" class="rounded-lg border border-red-900 bg-red-950/60 px-3 py-3 text-sm text-red-300">{{ error }}</p>
          <button type="submit" :disabled="auth.loading" class="button button-primary">{{ auth.loading ? 'Un momento…' : (mode === 'login' ? 'Entrar' : 'Crear cuenta e iniciar sesión') }}<AppIcon name="arrow" /></button>
        </form>
        <div class="auth-invite-note"><AppIcon name="lock" /> Un espacio privado. Acceso por invitación.</div>
      </div>
    </section>
  </main>
</template>

<script setup>
import AppIcon from '../components/AppIcon.vue'
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
      error.value = 'No pudimos conectar. Revisa tu conexión y vuelve a intentarlo.'
    }
  }
}
</script>
